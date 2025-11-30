"""
Agent Tools

Collection of tools available to the CellByte agent.
"""

from langchain_core.tools import tool
from .csv_ingestion import get_vectorstore, list_available_files
from .plotting_utils import create_plot_from_request
from general_utils import get_logger

logger = get_logger("tools")


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
    logger.info(f"search_data called with query: {query}")
    
    try:
        vectorstore = get_vectorstore()
        
        if vectorstore is None:
            logger.warning("No vectorstore available")
            return "No data has been ingested yet. Please upload CSV files first."
        
        # Search for relevant documents
        logger.debug("Performing similarity search...")
        docs = vectorstore.similarity_search(query, k=5)
        logger.info(f"Found {len(docs)} matching documents")
        
        if not docs:
            logger.info("No relevant documents found")
            return "No relevant data found for your query."
        
        # Format results
        results = []
        for doc in docs:
            source = doc.metadata.get("source", "Unknown")
            results.append(f"[From {source}]: {doc.page_content}")
            logger.debug(f"Result from {source}: {doc.page_content[:100]}...")
        
        return "\n\n".join(results)
    
    except Exception as e:
        logger.error(f"search_data failed: {e}", exc_info=True)
        return f"Error searching data: {str(e)}"


@tool
def create_plot(plot_request: str, filename: str) -> str:
    """
    Create a Plotly visualization based on a natural language request.
    
    Use this tool when the user asks for charts, graphs, visualizations,
    or plots of their data. Returns an HTML string containing the interactive plot.
    
    Args:
        plot_request: Natural language description of the desired plot
                     (e.g., "pie chart of additional_benefit distribution")
        filename: Name of the CSV file to use for the plot
        
    Returns:
        HTML string containing the Plotly chart, or error message
    """
    logger.info(f"create_plot called - request: '{plot_request}', file: '{filename}'")
    
    try:
        html, code = create_plot_from_request(plot_request, filename)
        logger.info(f"Plot generated successfully ({len(html)} chars HTML)")
        logger.debug(f"Generated code:\n{code}")
        
        # Wrap in a container with styling
        html_wrapped = f'''<div class="plot-container" style="width:100%; min-height:400px; background:#1a1a2e; border-radius:8px; padding:10px;">
        {html}
        </div>'''
        
        return f"[PLOT_HTML]{html_wrapped}[/PLOT_HTML]"
    
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return str(e)
    except Exception as e:
        logger.error(f"create_plot failed: {e}", exc_info=True)
        return f"Error creating plot: {str(e)}"


# List of all available tools for easy import
ALL_TOOLS = [search_data, create_plot]
