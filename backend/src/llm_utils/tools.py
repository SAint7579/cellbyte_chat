"""
Agent Tools

Collection of tools available to the CellByte agent.
"""

from langchain_core.tools import tool
from .csv_ingestion import get_vectorstore


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


# List of all available tools for easy import
ALL_TOOLS = [search_data]

