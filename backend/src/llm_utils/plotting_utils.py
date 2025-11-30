"""
Plotting Utilities

LLM-powered chart generation using Plotly.
"""

from langchain_openai import ChatOpenAI
import pandas as pd
from .csv_ingestion import load_dataset, list_available_files, get_csv_metadata
from general_utils import get_logger

logger = get_logger("plotting")


def get_dataset_context(filename: str, df: pd.DataFrame) -> dict:
    """
    Get dataset context including head(5) for LLM prompts.
    
    Args:
        filename: Name of the file
        df: The DataFrame
        
    Returns:
        Dict with columns info and head_5
    """
    logger.debug(f"Getting dataset context for {filename}")
    
    # Get column info
    columns_info = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        unique_count = df[col].nunique()
        sample_values = df[col].dropna().head(3).tolist()
        columns_info.append({
            "name": col,
            "dtype": dtype,
            "unique_count": unique_count,
            "samples": sample_values
        })
    
    # Get head(5)
    try:
        head_5 = df.head(5).to_dict(orient='records')
    except Exception:
        head_5 = []
    
    logger.debug(f"Context: {df.shape[0]} rows, {df.shape[1]} columns")
    
    return {
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
        "columns": columns_info,
        "head_5": head_5
    }


def generate_plot_code(plot_request: str, dataset_context: dict) -> str:
    """
    Use LLM to generate Plotly code for the requested visualization.
    
    Args:
        plot_request: Natural language description of the plot
        dataset_context: Dict containing columns info and head_5
        
    Returns:
        Generated Python code string
    """
    logger.info(f"Generating plot code for: {plot_request}")
    
    # Format columns info
    columns_str = "\n".join([
        f"  - {c['name']} ({c['dtype']}): {c['unique_count']} unique, samples: {c['samples']}"
        for c in dataset_context["columns"]
    ])
    
    # Format head_5 as a table
    head_5 = dataset_context.get("head_5", [])
    if head_5:
        head_str = "Sample data (first 5 rows):\n"
        # Get column headers
        headers = list(head_5[0].keys()) if head_5 else []
        head_str += " | ".join(headers) + "\n"
        head_str += "-" * 50 + "\n"
        for row in head_5:
            head_str += " | ".join([str(row.get(h, ""))[:20] for h in headers]) + "\n"
    else:
        head_str = "No sample data available"
    
    model_name = "gpt-5.1"
    logger.info(f"Using LLM model: {model_name}")
    
    try:
        llm = ChatOpenAI(model=model_name, temperature=0)
    except Exception as e:
        logger.error(f"Failed to create LLM: {e}")
        raise
    
    prompt = f"""You are a Python data visualization expert. Generate Plotly code to create the requested visualization.

    DATASET INFO:
    - Shape: {dataset_context['shape']['rows']} rows × {dataset_context['shape']['columns']} columns
    - Columns:
    {columns_str}

    {head_str}

    USER REQUEST: {plot_request}

    REQUIREMENTS:
    1. Write Python code that uses Plotly Express or Plotly Graph Objects
    2. The DataFrame is already loaded as `df`
    3. Create the figure and store it in a variable called `fig`
    4. Do NOT call fig.show() - just create the figure
    5. Use a dark theme: template="plotly_dark"
    6. Make the chart visually appealing with good colors
    7. Add appropriate title and labels
    8. Handle any potential NaN or missing values appropriately

    Respond with ONLY the Python code, no explanations or markdown:"""

    logger.debug(f"Prompt length: {len(prompt)} chars")
    
    try:
        response = llm.invoke(prompt)
        code = response.content.strip()
        logger.debug(f"Raw LLM response: {code[:500]}...")
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}", exc_info=True)
        raise
    
    # Clean up code (remove markdown if present)
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    
    cleaned_code = code.strip()
    logger.info(f"Generated code ({len(cleaned_code)} chars)")
    logger.debug(f"Cleaned code:\n{cleaned_code}")
    
    return cleaned_code


def execute_plot_code(code: str, df: pd.DataFrame) -> str:
    """
    Execute the generated Plotly code and return HTML.
    
    Args:
        code: Python code that creates a Plotly figure
        df: DataFrame to use
        
    Returns:
        HTML string containing the Plotly chart
        
    Raises:
        Exception: If code execution fails
    """
    logger.info("Executing generated plot code...")
    logger.debug(f"Code to execute:\n{code}")
    
    import plotly.express as px
    import plotly.graph_objects as go
    import numpy as np
    
    # Create execution namespace
    exec_globals = {
        "df": df,
        "px": px,
        "go": go,
        "pd": pd,
        "np": np,
    }
    exec_locals = {}
    
    # Execute the generated code
    try:
        exec(code, exec_globals, exec_locals)
        logger.debug("Code executed successfully")
    except Exception as e:
        logger.error(f"Code execution failed: {e}", exc_info=True)
        logger.error(f"Failed code:\n{code}")
        raise
    
    # Get the figure
    fig = exec_locals.get("fig") or exec_globals.get("fig")
    
    if fig is None:
        logger.error("No 'fig' variable found after code execution")
        raise ValueError("Code executed but no 'fig' variable was created")
    
    # Convert to HTML
    try:
        html = fig.to_html(include_plotlyjs="cdn", full_html=False)
        logger.info(f"Generated HTML ({len(html)} chars)")
    except Exception as e:
        logger.error(f"Failed to convert figure to HTML: {e}")
        raise
    
    return html


def create_plot_from_request(plot_request: str, filename: str) -> tuple[str, str]:
    """
    Full pipeline: load data, generate code, execute, return HTML.
    
    Args:
        plot_request: Natural language description of the plot
        filename: Name of the CSV file
        
    Returns:
        Tuple of (html_string, generated_code) or raises exception
    """
    logger.info(f"=== Starting plot creation ===")
    logger.info(f"Request: {plot_request}")
    logger.info(f"File: {filename}")
    
    # Load dataset
    logger.info(f"Loading dataset: {filename}")
    df = load_dataset(filename)
    
    if df is None:
        available = list_available_files()
        logger.error(f"File '{filename}' not found. Available: {available}")
        raise FileNotFoundError(
            f"File '{filename}' not found. Available files: {', '.join(available) if available else 'None'}"
        )
    
    logger.info(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
    
    # Get context
    context = get_dataset_context(filename, df)
    
    # Generate code
    code = generate_plot_code(plot_request, context)
    
    # Execute and get HTML
    html = execute_plot_code(code, df)
    
    logger.info("=== Plot creation completed ===")
    
    return html, code
