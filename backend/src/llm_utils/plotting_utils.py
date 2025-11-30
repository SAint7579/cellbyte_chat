"""
Plotting Utilities

LLM-powered chart generation using Plotly.
"""

import pandas as pd
from langchain_openai import ChatOpenAI

from general_utils import (
    get_logger,
    load_dataset,
    list_available_files,
    get_dataset_context,
    format_context_for_prompt,
)

logger = get_logger("plotting")


def generate_plot_code(plot_request: str, context: dict) -> str:
    """
    Use LLM to generate Plotly code for the requested visualization.
    
    Args:
        plot_request: Natural language description of the plot
        context: Dict from get_dataset_context()
        
    Returns:
        Generated Python code string
    """
    logger.info(f"Generating plot code for: {plot_request}")
    
    # Format context for prompt
    context_str = format_context_for_prompt(context)
    
    model_name = "gpt-5.1"
    logger.info(f"Using LLM model: {model_name}")
    
    try:
        llm = ChatOpenAI(model=model_name, temperature=0)
    except Exception as e:
        logger.error(f"Failed to create LLM: {e}")
        raise
    
    prompt = f"""You are a Python data visualization expert. Generate Plotly code to create the requested visualization.

    {context_str}

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
    
    # Get context using shared utility
    context = get_dataset_context(df, filename)
    
    # Generate code
    code = generate_plot_code(plot_request, context)
    
    # Execute and get HTML
    html = execute_plot_code(code, df)
    
    logger.info("=== Plot creation completed ===")
    
    return html, code
