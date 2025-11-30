"""
Analytics Utilities

LLM-powered data analytics using Python/SciPy.
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
    get_numeric_columns,
)
from .csv_ingestion import get_file_metadata

logger = get_logger("analytics")

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


def _execute_analytics_code(code: str, df: pd.DataFrame) -> dict:
    """Execute analytics code and return result dict."""
    import re
    import numpy as np
    from scipy import stats
    import sklearn
    from sklearn import preprocessing, metrics, cluster
    
    exec_globals = {
        "df": df,
        "pd": pd,
        "np": np,
        "re": re,           # Regular expressions
        "stats": stats,
        "sklearn": sklearn,
        "preprocessing": preprocessing,
        "metrics": metrics,
        "cluster": cluster,
    }
    exec_locals = {}
    
    exec(code, exec_globals, exec_locals)
    
    result = exec_locals.get("result") or exec_globals.get("result")
    if result is None:
        raise ValueError("No 'result' variable created")
    
    # Normalize result format
    if not isinstance(result, dict):
        result = {"summary": str(result), "data": result}
    if "summary" not in result:
        result["summary"] = "Analysis completed."
    
    return result


def run_analytics(analytics_request: str, filename: str) -> dict:
    """
    Generate and execute analytics code with retry logic using conversation history.
    
    On failure, appends the error to the conversation and asks LLM to fix it.
    """
    logger.info(f"=== Analytics: {analytics_request} | File: {filename} ===")
    
    # Load dataset
    df = load_dataset(filename)
    if df is None:
        available = list_available_files()
        raise FileNotFoundError(
            f"File '{filename}' not found. Available: {', '.join(available) if available else 'None'}"
        )
    
    logger.info(f"Dataset: {df.shape[0]} rows, {df.shape[1]} columns")
    
    # Get file metadata (includes delimiter, file_type)
    file_metadata = get_file_metadata(filename)
    
    # Build context and initial prompt
    context_str = format_context_for_prompt(get_dataset_context(df, filename, file_metadata))
    
    system_prompt = f"""You are a Python data analytics expert. Generate analysis code.

{context_str}

REQUIREMENTS:
1. Use pandas, numpy, scipy.stats as needed
2. DataFrame is loaded as `df`
3. Store result in variable `result` as dict with:
   - "summary": human-readable findings string
   - "data": numerical/tabular results
4. Handle NaN values appropriately
5. Round numbers to 4 decimal places
6. Only use columns that exist in the dataset above
7. Return ONLY Python code, no markdown or explanations"""

    # Initialize conversation
    messages = [HumanMessage(content=f"{system_prompt}\n\nUSER REQUEST: {analytics_request}")]
    
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
            result = _execute_analytics_code(code, df)
            result["code"] = code
            logger.info("=== Analytics completed successfully ===")
            return result
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
    
    raise RuntimeError("Analytics failed")


# =============================================================================
# Quick analysis functions (no LLM needed)
# =============================================================================

def quick_describe(filename: str) -> dict:
    """Get quick descriptive statistics for a file."""
    df = load_dataset(filename)
    if df is None:
        raise FileNotFoundError(f"File '{filename}' not found")
    
    return {
        "summary": f"Descriptive statistics for {filename}",
        "data": df.describe(include='all').to_dict()
    }


def quick_correlation(filename: str, method: str = "pearson") -> dict:
    """Get correlation matrix for numeric columns."""
    df = load_dataset(filename)
    if df is None:
        raise FileNotFoundError(f"File '{filename}' not found")
    
    numeric_cols = get_numeric_columns(df)
    if len(numeric_cols) < 2:
        return {"summary": "Not enough numeric columns for correlation", "data": {}}
    
    corr = df[numeric_cols].corr(method=method)
    return {
        "summary": f"{method.capitalize()} correlation matrix for {len(numeric_cols)} numeric columns",
        "data": corr.to_dict()
    }


def quick_value_counts(filename: str, column: str) -> dict:
    """Get value counts for a categorical column."""
    df = load_dataset(filename)
    if df is None:
        raise FileNotFoundError(f"File '{filename}' not found")
    
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in {filename}")
    
    counts = df[column].value_counts().to_dict()
    return {
        "summary": f"Value counts for '{column}' ({len(counts)} unique values)",
        "data": counts
    }
