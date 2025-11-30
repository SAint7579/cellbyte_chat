"""
File Utilities

Shared functions for reading, loading, and analyzing tabular data files.
Used by plotting, analytics, and other tools.
"""

import csv
import pandas as pd
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("file_utils")

# =============================================================================
# Path Configuration
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATABASE_DIR = BASE_DIR / "database"
FAISS_DIR = DATABASE_DIR / "faiss_store"
FILES_DIR = DATABASE_DIR / "files"
METADATA_FILE = DATABASE_DIR / "csv_metadata.json"


def ensure_dirs():
    """Ensure database directories exist."""
    DATABASE_DIR.mkdir(exist_ok=True)
    FAISS_DIR.mkdir(exist_ok=True)
    FILES_DIR.mkdir(exist_ok=True)


# =============================================================================
# File Reading
# =============================================================================

def detect_delimiter(file_path: str) -> str:
    """
    Detect the delimiter used in a CSV/TSV file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Detected delimiter character (defaults to ',' if detection fails)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sample = f.read(8192)
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=',;\t|')
            logger.debug(f"Detected delimiter: '{dialect.delimiter}'")
            return dialect.delimiter
    except Exception as e:
        logger.warning(f"Delimiter detection failed: {e}, defaulting to ','")
        return ','


def read_tabular_file(file_path: str) -> tuple[pd.DataFrame, dict]:
    """
    Read a tabular file (CSV, TSV, Excel) and return DataFrame with file info.
    
    Supports:
    - CSV files (.csv) with auto-detected delimiters (, ; | \\t)
    - TSV files (.tsv, .txt with tabs)
    - Excel files (.xlsx, .xls)
    
    Args:
        file_path: Path to the tabular file
        
    Returns:
        Tuple of (DataFrame, file_info dict with 'type' and 'delimiter')
        
    Raises:
        ValueError: If file type is not supported
    """
    logger.info(f"Reading tabular file: {file_path}")
    path = Path(file_path)
    extension = path.suffix.lower()
    
    file_info = {
        "type": None,
        "delimiter": None,
        "extension": extension,
    }
    
    # Excel files
    if extension in ['.xlsx', '.xls']:
        try:
            df = pd.read_excel(file_path, engine='openpyxl' if extension == '.xlsx' else 'xlrd')
            file_info["type"] = "excel"
            logger.info(f"Read Excel file: {df.shape[0]} rows, {df.shape[1]} columns")
            return df, file_info
        except Exception as e:
            logger.error(f"Failed to read Excel file: {e}")
            raise ValueError(f"Failed to read Excel file: {str(e)}")
    
    # TSV files (explicit .tsv extension)
    if extension == '.tsv':
        df = pd.read_csv(file_path, delimiter='\t')
        file_info["type"] = "tsv"
        file_info["delimiter"] = '\t'
        logger.info(f"Read TSV file: {df.shape[0]} rows, {df.shape[1]} columns")
        return df, file_info
    
    # CSV and other text-based files - auto-detect delimiter
    if extension in ['.csv', '.txt', '']:
        delimiter = detect_delimiter(file_path)
        df = pd.read_csv(file_path, delimiter=delimiter)
        
        if delimiter == '\t':
            file_info["type"] = "tsv"
        else:
            file_info["type"] = "csv"
        file_info["delimiter"] = delimiter
        
        logger.info(f"Read CSV file: {df.shape[0]} rows, {df.shape[1]} columns, delimiter='{delimiter}'")
        return df, file_info
    
    # Unsupported extension - try as CSV anyway
    try:
        delimiter = detect_delimiter(file_path)
        df = pd.read_csv(file_path, delimiter=delimiter)
        file_info["type"] = "csv"
        file_info["delimiter"] = delimiter
        logger.info(f"Read file as CSV: {df.shape[0]} rows, {df.shape[1]} columns")
        return df, file_info
    except Exception as e:
        logger.error(f"Unsupported file type '{extension}': {e}")
        raise ValueError(f"Unsupported file type '{extension}': {str(e)}")


# =============================================================================
# Dataset Loading & Listing
# =============================================================================

def load_dataset(filename: str) -> Optional[pd.DataFrame]:
    """
    Load a dataset from the stored files directory.
    
    Args:
        filename: Name of the file to load
        
    Returns:
        DataFrame or None if file not found
    """
    logger.debug(f"Loading dataset: {filename}")
    file_path = FILES_DIR / filename
    
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return None
    
    try:
        df, _ = read_tabular_file(str(file_path))
        logger.debug(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        return None


def list_available_files() -> list[str]:
    """
    List all available dataset files.
    
    Returns:
        List of filenames
    """
    if not FILES_DIR.exists():
        return []
    files = [f.name for f in FILES_DIR.iterdir() if f.is_file()]
    logger.debug(f"Available files: {files}")
    return files


# =============================================================================
# Dataset Context (for LLM prompts)
# =============================================================================

def get_dataset_context(df: pd.DataFrame, filename: str = "dataset", file_metadata: dict | None = None) -> dict:
    """
    Get dataset context for LLM prompts (columns info, sample data, shape, file info).
    
    This standardized context is used by plotting, analytics, and other LLM tools.
    
    Args:
        df: The DataFrame to analyze
        filename: Name of the file (for logging)
        file_metadata: Optional metadata dict from get_file_metadata() containing
                      file_type, delimiter, description, etc.
        
    Returns:
        Dict with:
        - filename: Name of the file
        - file_type: Type of file (csv, tsv, excel)
        - delimiter: Delimiter used (for csv/tsv)
        - shape: {"rows": int, "columns": int}
        - columns: List of column info dicts
        - head_5: First 5 rows as list of dicts
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
    
    context = {
        "filename": filename,
        "file_type": file_metadata.get("file_type") if file_metadata else None,
        "delimiter": file_metadata.get("delimiter") if file_metadata else None,
        "shape": {"rows": df.shape[0], "columns": df.shape[1]},
        "columns": columns_info,
        "head_5": head_5
    }
    
    return context


def format_context_for_prompt(context: dict) -> str:
    """
    Format dataset context as a string for LLM prompts.
    
    Args:
        context: Dict from get_dataset_context()
        
    Returns:
        Formatted string ready to insert into prompts
    """
    # File info
    filename = context.get("filename", "unknown")
    file_type = context.get("file_type", "unknown")
    delimiter = context.get("delimiter")
    
    # Format file type with delimiter info
    if file_type == "csv" and delimiter:
        delimiter_display = repr(delimiter)  # Show '\t' as '\\t', ',' as ','
        file_info = f"CSV (delimiter: {delimiter_display})"
    elif file_type == "tsv":
        file_info = "TSV (tab-separated)"
    elif file_type == "excel":
        file_info = "Excel"
    else:
        file_info = file_type or "unknown"
    
    # Format columns info
    columns_str = "\n".join([
        f"  - {c['name']} ({c['dtype']}): {c['unique_count']} unique, samples: {c['samples']}"
        for c in context["columns"]
    ])
    
    # Format head_5 as a table
    head_5 = context.get("head_5", [])
    if head_5:
        headers = list(head_5[0].keys()) if head_5 else []
        head_str = "Sample data (first 5 rows):\n"
        head_str += " | ".join(headers) + "\n"
        head_str += "-" * 50 + "\n"
        for row in head_5:
            head_str += " | ".join([str(row.get(h, ""))[:20] for h in headers]) + "\n"
    else:
        head_str = "No sample data available"
    
    return f"""DATASET INFO:
- File: {filename}
- Format: {file_info}
- Shape: {context['shape']['rows']} rows × {context['shape']['columns']} columns
- Columns:
{columns_str}

{head_str}"""


def get_column_names(df: pd.DataFrame) -> list[str]:
    """Get list of column names from DataFrame."""
    return list(df.columns)


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Get list of numeric column names."""
    return df.select_dtypes(include=['number']).columns.tolist()


def get_categorical_columns(df: pd.DataFrame) -> list[str]:
    """Get list of categorical/object column names."""
    return df.select_dtypes(include=['object', 'category']).columns.tolist()


def get_datetime_columns(df: pd.DataFrame) -> list[str]:
    """Get list of datetime column names."""
    return df.select_dtypes(include=['datetime64']).columns.tolist()

