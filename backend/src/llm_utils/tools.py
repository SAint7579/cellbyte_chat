"""
Agent Tools

Collection of tools available to the CellByte agent.
"""

from langchain_core.tools import tool
from .csv_ingestion import get_vectorstore
from .plotting_utils import create_plot_from_request
from .analytics_utils import run_analytics
from general_utils import get_logger

logger = get_logger("tools")


@tool
def search_data(query: str) -> str:
    """
    Search the CSV data for relevant information using semantic search.
    
    Use this tool to find specific rows, records, or text information
    from the ingested CSV files. This is best for finding examples,
    looking up specific entries, or exploring the data.
    
    NOTE: This tool returns sample rows, NOT calculations. For statistics
    like mean, median, sum, count, correlations, etc., use analyze_data instead.
    
    Args:
        query: The search query describing what data to find
        
    Returns:
        Relevant rows/records from the CSV files
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
def analyze_data(analysis_request: str, filename: str) -> str:
    """
    Perform statistical analysis or calculations on a CSV file.
    
    Use this tool when the user asks for:
    - Statistics: mean, median, mode, min, max, sum, count, std, variance
    - Aggregations: group by, value counts, distributions
    - Correlations: correlation matrix, relationships between columns
    - Comparisons: compare groups, t-tests, chi-square tests
    - Data summaries: describe, info, missing values analysis
    
    This tool generates and executes Python/pandas code to compute the answer.
    
    Args:
        analysis_request: Natural language description of the analysis
                         (e.g., "calculate the median yearly_price_avg_today_apu")
        filename: Name of the CSV file to analyze
        
    Returns:
        Analysis results with summary and data
    """
    logger.info(f"analyze_data called - request: '{analysis_request}', file: '{filename}'")
    
    try:
        result = run_analytics(analysis_request, filename)
        
        # Format the response
        summary = result.get("summary", "Analysis completed.")
        data = result.get("data", {})
        
        # Format data nicely
        if isinstance(data, dict):
            if len(data) <= 10:
                data_str = "\n".join([f"  {k}: {v}" for k, v in data.items()])
            else:
                # Truncate if too many items
                items = list(data.items())[:10]
                data_str = "\n".join([f"  {k}: {v}" for k, v in items])
                data_str += f"\n  ... and {len(data) - 10} more items"
        else:
            data_str = str(data)
        
        logger.info(f"Analysis completed: {summary[:100]}...")
        
        return f"**Analysis Result:**\n{summary}\n\n**Data:**\n{data_str}"
    
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return str(e)
    except Exception as e:
        logger.error(f"analyze_data failed: {e}", exc_info=True)
        return f"Error analyzing data: {str(e)}"


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
ALL_TOOLS = [search_data, analyze_data, create_plot]
