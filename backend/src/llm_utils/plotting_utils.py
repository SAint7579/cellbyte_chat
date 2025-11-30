"""
Plotting Utilities

LLM-powered chart generation using Plotly.
Includes retry logic via conversation history.
"""

import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from general_utils import (
    get_logger,
    load_dataset,
    list_available_files,
    get_dataset_context,
    format_context_for_prompt,
)

logger = get_logger("plotting")

MAX_RETRIES = 3


def _clean_code(code: str) -> str:
    """Remove markdown formatting from code."""
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


def _execute_plot_code(code: str, df: pd.DataFrame) -> str:
    """Execute Plotly code and return HTML."""
    import plotly.express as px
    import plotly.graph_objects as go
    import numpy as np
    
    exec_globals = {"df": df, "px": px, "go": go, "pd": pd, "np": np}
    exec_locals = {}
    
    exec(code, exec_globals, exec_locals)
    
    fig = exec_locals.get("fig") or exec_globals.get("fig")
    if fig is None:
        raise ValueError("No 'fig' variable created")
    
    return fig.to_html(include_plotlyjs="cdn", full_html=False)


def create_plot_from_request(plot_request: str, filename: str) -> tuple[str, str]:
    """
    Generate and execute Plotly code with retry logic using conversation history.
    
    On failure, appends the error to the conversation and asks LLM to fix it.
    """
    logger.info(f"=== Plot creation: {plot_request} | File: {filename} ===")
    
    # Load dataset
    df = load_dataset(filename)
    if df is None:
        available = list_available_files()
        raise FileNotFoundError(
            f"File '{filename}' not found. Available: {', '.join(available) if available else 'None'}"
        )
    
    logger.info(f"Dataset: {df.shape[0]} rows, {df.shape[1]} columns")
    
    # Build context and initial prompt
    context_str = format_context_for_prompt(get_dataset_context(df, filename))
    
    system_prompt = f"""You are a Python data visualization expert. Generate Plotly code.

{context_str}

REQUIREMENTS:
1. Use Plotly Express or Graph Objects
2. DataFrame is loaded as `df`
3. Store figure in variable `fig`
4. Do NOT call fig.show()
5. Use template="plotly_dark"
6. Only use columns that exist in the dataset above
7. Return ONLY Python code, no markdown or explanations"""

    # Initialize conversation
    messages = [HumanMessage(content=f"{system_prompt}\n\nUSER REQUEST: {plot_request}")]
    
    llm = ChatOpenAI(model="gpt-5.1", temperature=0)
    code = None
    
    for attempt in range(MAX_RETRIES):
        logger.info(f"Attempt {attempt + 1}/{MAX_RETRIES}")
        
        # Get code from LLM
        response = llm.invoke(messages)
        code = _clean_code(response.content)
        messages.append(AIMessage(content=response.content))
        
        logger.debug(f"Generated code:\n{code}")
        
        # Try to execute
        try:
            html = _execute_plot_code(code, df)
            logger.info("=== Plot created successfully ===")
            return html, code
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
            
            if attempt < MAX_RETRIES - 1:
                # Append error and ask for fix
                messages.append(HumanMessage(
                    content=f"ERROR: {error_msg}\n\nFix the code. Only use columns that exist. Return ONLY the corrected Python code:"
                ))
            else:
                logger.error(f"All {MAX_RETRIES} attempts failed")
                raise
    
    raise RuntimeError("Plot creation failed")
