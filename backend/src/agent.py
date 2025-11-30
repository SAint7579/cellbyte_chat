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
from langgraph.prebuilt import create_react_agent

from llm_utils.csv_ingestion import get_csv_metadata
from general_utils import get_logger

logger = get_logger("agent")


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
        logger.info("Initializing CellByteAgent...")
        
        # Load metadata if not provided
        if metadata is None:
            logger.debug("Loading metadata from csv_metadata.json")
            full_metadata = get_csv_metadata()
            metadata = [
                {
                    "name": f["name"], 
                    "description": f.get("description", ""),
                    "columns": f.get("columns", []),
                    "row_count": f.get("row_count", 0),
                    "head_5": f.get("head_5", []),
                }
                for f in full_metadata.get("files", [])
            ]
            logger.info(f"Loaded metadata for {len(metadata)} files")
        
        self.metadata = metadata
        self.system_prompt = self._build_system_prompt()
        logger.debug(f"System prompt built ({len(self.system_prompt)} chars)")
        
        # Create the LLM
        model_name = "gpt-5.1"
        logger.info(f"Creating LLM with model: {model_name}")
        try:
            self.llm = ChatOpenAI(model=model_name, temperature=0)
            logger.info("LLM created successfully")
        except Exception as e:
            logger.error(f"Failed to create LLM: {e}")
            raise
        
        # Tools available to the agent
        from llm_utils.tools import search_data, create_plot
        self.tools = [search_data, create_plot]
        logger.info(f"Loaded {len(self.tools)} tools: {[t.name for t in self.tools]}")
        
        # Create the ReAct agent
        try:
            self.agent = create_react_agent(
                self.llm,
                tools=self.tools,
                prompt=self.system_prompt,
            )
            logger.info("ReAct agent created successfully")
        except Exception as e:
            logger.error(f"Failed to create ReAct agent: {e}")
            raise
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with file metadata context."""
        
        if not self.metadata:
            files_context = "No files have been ingested yet."
        else:
            files_list = []
            for i, f in enumerate(self.metadata, 1):
                # Format head_5 as sample data
                head_5 = f.get("head_5", [])
                if head_5:
                    columns = list(head_5[0].keys()) if head_5 else []
                    sample_rows = []
                    for row in head_5[:3]:  # Show first 3 rows
                        row_str = " | ".join([str(row.get(c, ""))[:15] for c in columns[:5]])  # First 5 cols
                        sample_rows.append(f"      {row_str}")
                    sample_str = "\n".join(sample_rows)
                    sample_section = f"\n   Sample data:\n{sample_str}"
                else:
                    sample_section = ""
                
                # Show ALL columns
                all_columns = f.get('columns', [])
                columns_str = ', '.join(all_columns)
                
                files_list.append(
                    f"{i}. **{f['name']}** ({f.get('row_count', '?')} rows, {len(all_columns)} columns)\n"
                    f"   Columns: {columns_str}\n"
                    f"   {f['description'][:500]}{'...' if len(f['description']) > 500 else ''}"
                    f"{sample_section}"
                )
            files_context = "\n\n".join(files_list)
        
        return f"""You are CellByte, an intelligent data assistant that helps users explore and analyze CSV data.

## Available Data Files

{files_context}

## Your Capabilities

1. **Data Retrieval**: Use the `search_data` tool to find specific information from the CSV files.
2. **Visualization**: Use the `create_plot` tool to create charts and graphs. Always specify the filename.
3. **Data Analysis**: Help users understand patterns, trends, and insights in their data.

## Guidelines

- **ALWAYS use tools** when users ask about data or visualizations. DO NOT say data doesn't exist without checking first.
- **Fuzzy column matching**: Match user terms to actual column names flexibly. E.g., "additional benefit ratings" → `additional_benefit`, "brand" → `brand_name`.
- Use `search_data` when users ask about specific data points or information.
- Use `create_plot` when users ask for charts, graphs, visualizations, or plots. Pass the exact filename and describe the plot using actual column names.
- Be precise and cite which file the information comes from.
- Be conversational and helpful.
"""
    
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
        logger.info(f"Chat received message: {message[:100]}{'...' if len(message) > 100 else ''}")
        logger.debug(f"History length: {len(history) if history else 0}")
        
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
        logger.debug(f"Total messages to send: {len(messages)}")
        
        # Invoke the agent
        try:
            logger.info("Invoking agent...")
            result = self.agent.invoke({"messages": messages})
            logger.info(f"Agent returned {len(result['messages'])} messages")
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}", exc_info=True)
            raise
        
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
                    logger.info(f"Tool calls in response: {[tc['name'] for tc in msg.tool_calls]}")
                new_history.append(entry)
            elif isinstance(msg, ToolMessage):
                logger.debug(f"Tool result received (id: {msg.tool_call_id}): {msg.content[:200]}...")
                new_history.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content
                })
        
        # Extract final response
        final_message = result["messages"][-1]
        logger.info(f"Final response: {final_message.content[:100]}{'...' if len(final_message.content) > 100 else ''}")
        
        return final_message.content, new_history
    
    def refresh_metadata(self):
        """Reload metadata from csv_metadata.json and rebuild system prompt."""
        logger.info("Refreshing metadata...")
        full_metadata = get_csv_metadata()
        self.metadata = [
            {
                "name": f["name"], 
                "description": f.get("description", ""),
                "columns": f.get("columns", []),
                "row_count": f.get("row_count", 0),
                "head_5": f.get("head_5", []),
            }
            for f in full_metadata.get("files", [])
        ]
        self.system_prompt = self._build_system_prompt()
        
        # Recreate agent with new system prompt
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.system_prompt,
        )
        logger.info(f"Metadata refreshed. {len(self.metadata)} files loaded.")


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
