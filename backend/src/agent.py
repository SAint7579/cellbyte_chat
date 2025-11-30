import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Fix OpenMP conflict with FAISS on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent ## Makes this a bit hardcoded on how the agent flow works. Could be replaced with a custom graph and tool call handler in the future if needed. The flow is better than create_tool_calling_agent though.

from llm_utils.csv_ingestion import get_vectorstore, get_csv_metadata


class CellByteAgent:
    """
    An agentic chatbot that can query CSV data using RAG.
    
    Attributes:
        metadata: List of file metadata (name, description)
        agent: LangGraph ReAct agent
    """
    
    def __init__(self, metadata: Optional[list[dict]] = None):
        """
        Initialize the agent with file metadata.
        
        Args:
            metadata: List of dicts with 'name' and 'description' keys.
                     If None, loads from csv_metadata.json
        """
        # Load metadata if not provided
        if metadata is None:
            full_metadata = get_csv_metadata()
            metadata = [
                {"name": f["name"], "description": f.get("description", "")}
                for f in full_metadata.get("files", [])
            ]
        
        self.metadata = metadata
        self.system_prompt = self._build_system_prompt()
        
        # Create the RAG tool
        rag_tool = self._create_rag_tool()
        
        # Create the LLM
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Create the ReAct agent
        self.agent = create_react_agent(
            self.llm,
            tools=[rag_tool],
            prompt=self.system_prompt,
        )
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with file metadata context."""
        
        if not self.metadata:
            files_context = "No files have been ingested yet."
        else:
            files_list = []
            for i, f in enumerate(self.metadata, 1):
                files_list.append(f"{i}. **{f['name']}**\n   {f['description']}")
            files_context = "\n\n".join(files_list)
        
        return f"""You are CellByte's AI agent, an intelligent data assistant that helps users explore and analyze CSV data.

                ## Available Data Files

                {files_context}

                ## Your Capabilities

                1. **Data Retrieval**: Use the `search_data` tool to find specific information from the CSV files.
                2. **Data Analysis**: Help users understand patterns, trends, and insights in their data.
                3. **Explanations**: Provide clear explanations of data findings.

                ## Guidelines

                - Always use the `search_data` tool when users ask about specific data points or information.
                - Be precise and cite which file the information comes from.
                - If data is not found, let the user know clearly.
                - For calculations or analytics, describe what analysis would be needed (analytics tools coming soon).
                - Be conversational and helpful.
                """
    
    def _create_rag_tool(self):
        """Create the RAG search tool. This is added as a function in case the user adds files in the middle of the chat."""
        
        @tool
        def search_data(query: str) -> str:
            """
            Search the CSV data for relevant information.
            
            Use this tool to find specific data points, rows, or information
            from the ingested CSV files.
            
            Args:
                query: The search query describing what data to find
                
            Returns:
                Relevant data from the CSV files
            """
            vectorstore = get_vectorstore()
            
            if vectorstore is None:
                return "No data has been ingested yet. Please upload CSV files first."
            
            # Search for relevant documents
            docs = vectorstore.similarity_search(query, k=5)
            
            if not docs:
                return "No relevant data found for your query."
            
            # Format results
            results = []
            for doc in docs:
                source = doc.metadata.get("source", "Unknown")
                results.append(f"[From {source}]: {doc.page_content}")
            
            return "\n\n".join(results)
        
        return search_data
    
    def chat(self, message: str, history: Optional[list[dict]] = None) -> tuple[str, list[dict]]:
        """
        Send a message to the agent and get a response.
        
        Args:
            message: The user's message
            history: Optional list of previous messages in format:
                    [
                        {"role": "user", "content": "..."},
                        {"role": "assistant", "content": "...", "tool_calls": [...]},
                        {"role": "tool", "tool_call_id": "...", "content": "..."},
                        ...
                    ]
                    
        Returns:
            Tuple of (response_string, updated_history)
        """
        # Build messages list from history
        messages = []
        
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    # Reconstruct AIMessage with tool_calls if present
                    if msg.get("tool_calls"):
                        messages.append(AIMessage(
                            content=msg.get("content", ""),
                            tool_calls=msg["tool_calls"]
                        ))
                    else:
                        messages.append(AIMessage(content=msg["content"]))
                elif msg["role"] == "tool":
                    messages.append(ToolMessage(
                        content=msg["content"],
                        tool_call_id=msg["tool_call_id"]
                    ))
        
        # Add current message
        messages.append(HumanMessage(content=message))
        
        # Invoke the agent
        result = self.agent.invoke({"messages": messages})
        
        # Build updated history from all new messages (skip messages already in history)
        new_history = history.copy() if history else []
        start_idx = len(messages) - 1  # Start from the new user message
        
        for msg in result["messages"][start_idx:]:
            if isinstance(msg, HumanMessage):
                new_history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry = {"role": "assistant", "content": msg.content}
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    entry["tool_calls"] = msg.tool_calls
                new_history.append(entry)
            elif isinstance(msg, ToolMessage):
                new_history.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content
                })
        
        # Extract final response
        final_message = result["messages"][-1]
        return final_message.content, new_history
    
    def refresh_metadata(self):
        """Reload metadata from csv_metadata.json and rebuild system prompt."""
        full_metadata = get_csv_metadata()
        self.metadata = [
            {"name": f["name"], "description": f.get("description", "")}
            for f in full_metadata.get("files", [])
        ]
        self.system_prompt = self._build_system_prompt()
        # Might need a way of storing different system messagess for debugging, since this cannot go in the chat history now.
        # Recreate agent with new system prompt
        rag_tool = self._create_rag_tool()
        self.agent = create_react_agent(
            self.llm,
            tools=[rag_tool],
            prompt=self.system_prompt,
        )


if __name__ == "__main__":
    agent = CellByteAgent()
    history = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            
            response, history = agent.chat(user_input, history=history)
            print(f"Agent: {response}\n")
            
        except KeyboardInterrupt:
            break
