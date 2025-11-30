import os
import json
import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root (override=True to override system env vars)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def _detect_delimiter(file_path: str) -> str:
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
            return dialect.delimiter
    except Exception:
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
            # Try reading first sheet by default
            df = pd.read_excel(file_path, engine='openpyxl' if extension == '.xlsx' else 'xlrd')
            file_info["type"] = "excel"
            return df, file_info
        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {str(e)}")
    
    # TSV files (explicit .tsv extension)
    if extension == '.tsv':
        df = pd.read_csv(file_path, delimiter='\t')
        file_info["type"] = "tsv"
        file_info["delimiter"] = '\t'
        return df, file_info
    
    # CSV and other text-based files - auto-detect delimiter
    if extension in ['.csv', '.txt', '']:
        delimiter = _detect_delimiter(file_path)
        df = pd.read_csv(file_path, delimiter=delimiter)
        
        # Determine type based on delimiter
        if delimiter == '\t':
            file_info["type"] = "tsv"
        else:
            file_info["type"] = "csv"
        file_info["delimiter"] = delimiter
        
        return df, file_info
    
    # Unsupported extension - try as CSV anyway
    try:
        delimiter = _detect_delimiter(file_path)
        df = pd.read_csv(file_path, delimiter=delimiter)
        file_info["type"] = "csv"
        file_info["delimiter"] = delimiter
        return df, file_info
    except Exception as e:
        raise ValueError(f"Unsupported file type '{extension}': {str(e)}")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATABASE_DIR = BASE_DIR / "database"
FAISS_DIR = DATABASE_DIR / "faiss_store"
METADATA_FILE = DATABASE_DIR / "csv_metadata.json"


def _ensure_dirs():
    """Ensure database directories exist."""
    DATABASE_DIR.mkdir(exist_ok=True)
    FAISS_DIR.mkdir(exist_ok=True)


def _load_metadata() -> dict:
    """Load existing metadata from JSON file."""
    if METADATA_FILE.exists():
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": []}


def _save_metadata(metadata: dict):
    """Save metadata to JSON file."""
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def _generate_csv_description(df: pd.DataFrame, filename: str) -> str:
    """
    Use ChatOpenAI to generate a description of the CSV file.
    
    Args:
        df: Pandas DataFrame of the CSV
        filename: Name of the CSV file
        
    Returns:
        Generated description string, or error message if generation fails
    """
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Build a summary of the data for the LLM
        # Safely get statistics
        try:
            stats_str = df.describe(include='all').to_string()
        except Exception:
            stats_str = "Could not generate statistics"
        
        csv_summary = f"""
Filename: {filename}
Shape: {df.shape[0]} rows × {df.shape[1]} columns

Columns and Types:
{df.dtypes.to_string()}

Sample Data (first 5 rows):
{df.head().to_string()}

Basic Statistics:
{stats_str}
"""
        
        prompt = f"""You are a data analyst. Analyze this CSV file and provide a concise but comprehensive description.

Include:
1. What this dataset appears to contain (domain/subject)
2. Key columns and what they represent
3. Data quality observations (missing values, data types)
4. Potential use cases for this data

CSV Summary:
{csv_summary}

Provide a clear, structured description in 2-3 paragraphs."""

        response = llm.invoke(prompt)
        return response.content
    
    except Exception as e:
        return f"[Auto-generated description failed: {str(e)}] File contains {len(df)} rows and {len(df.columns)} columns: {', '.join(df.columns.tolist())}"


def _csv_to_documents(df: pd.DataFrame, filename: str) -> list[Document]:
    """
    Convert CSV rows to LangChain Documents for vectorstore.
    
    Args:
        df: Pandas DataFrame
        filename: Source filename for metadata
        
    Returns:
        List of Document objects
    """
    documents = []
    
    # Convert each row to a document
    for idx, row in df.iterrows():
        # Create a text representation of the row
        row_text = " | ".join([f"{col}: {val}" for col, val in row.items()])
        
        doc = Document(
            page_content=row_text,
            metadata={
                "source": filename,
                "row_index": idx,
            }
        )
        documents.append(doc)
    
    return documents


def ingest_file(file_path: str, filename: Optional[str] = None) -> dict:
    """
    Ingest a tabular file (CSV, TSV, Excel): generate description, store in FAISS, save metadata.
    
    Args:
        file_path: Path to the file (CSV, TSV, XLSX, XLS)
        filename: Optional custom name (defaults to file basename)
        
    Returns:
        Dict with ingestion results including name, description, and status
    """
    _ensure_dirs()
    
    # Read the file with auto-detection
    df, file_info = read_tabular_file(file_path)
    
    # Determine filename
    if filename is None:
        filename = Path(file_path).name
    
    # Generate description using LLM
    description = _generate_csv_description(df, filename)
    
    # Convert to documents
    documents = _csv_to_documents(df, filename)
    
    # Create embeddings and store in FAISS
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    
    # Check if FAISS store already exists
    faiss_index_path = FAISS_DIR / "index.faiss"
    
    if faiss_index_path.exists():
        # Load existing and add new documents
        vectorstore = FAISS.load_local(
            str(FAISS_DIR), 
            embeddings,
            allow_dangerous_deserialization=True
        )
        vectorstore.add_documents(documents)
    else:
        # Create new vectorstore
        vectorstore = FAISS.from_documents(documents, embeddings)
    
    # Save vectorstore
    vectorstore.save_local(str(FAISS_DIR))
    
    # Update metadata
    metadata = _load_metadata()
    
    # Check if file already exists in metadata (update it)
    existing_idx = next(
        (i for i, f in enumerate(metadata["files"]) if f["name"] == filename),
        None
    )
    
    # Safely get describe stats
    try:
        describe_stats = df.describe(include='all').to_dict()
    except Exception:
        describe_stats = {"error": "Could not generate statistics"}
    
    file_metadata = {
        "name": filename,
        "date_ingested": datetime.now().isoformat(),
        "description": description,
        "row_count": len(df),
        "columns": list(df.columns),
        "file_type": file_info.get("type"),
        "delimiter": file_info.get("delimiter"),
        "describe": describe_stats,
    }
    
    if existing_idx is not None:
        metadata["files"][existing_idx] = file_metadata
    else:
        metadata["files"].append(file_metadata)
    
    _save_metadata(metadata)
    
    return {
        "status": "success",
        "name": filename,
        "description": description,
        "rows_indexed": len(documents),
        "file_type": file_info.get("type"),
    }


# Backward-compatible alias
ingest_csv = ingest_file


def get_csv_metadata() -> dict:
    """
    Get all CSV metadata.
    
    Returns:
        Dict containing all file metadata
    """
    return _load_metadata()


def get_vectorstore() -> Optional[FAISS]:
    """
    Load and return the FAISS vectorstore.
    
    Returns:
        FAISS vectorstore or None if not exists
    """
    faiss_index_path = FAISS_DIR / "index.faiss"
    
    if not faiss_index_path.exists():
        return None
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    return FAISS.load_local(
        str(FAISS_DIR),
        embeddings,
        allow_dangerous_deserialization=True
    )


def delete_file(filename: str) -> dict:
    """
    Delete a file's metadata and remove its vectors from FAISS.
    
    Args:
        filename: Name of the file to delete
        
    Returns:
        Dict with deletion status
        
    Raises:
        ValueError: If file not found in metadata
    """
    metadata = _load_metadata()
    
    # Find the file in metadata
    file_exists = any(f["name"] == filename for f in metadata.get("files", []))
    
    if not file_exists:
        raise ValueError(f"File '{filename}' not found in metadata")
    
    # Remove from metadata
    metadata["files"] = [f for f in metadata["files"] if f["name"] != filename]
    _save_metadata(metadata)
    
    # Rebuild FAISS index without the deleted file's vectors
    faiss_index_path = FAISS_DIR / "index.faiss"
    
    if faiss_index_path.exists():
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = FAISS.load_local(
            str(FAISS_DIR),
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Get all documents and filter out the deleted file's documents
        # Note: FAISS doesn't support direct deletion, so we rebuild
        docstore = vectorstore.docstore
        index_to_id = vectorstore.index_to_docstore_id
        
        remaining_docs = []
        for idx, doc_id in index_to_id.items():
            doc = docstore.search(doc_id)
            if doc and doc.metadata.get("source") != filename:
                remaining_docs.append(doc)
        
        # Delete old index
        if faiss_index_path.exists():
            os.unlink(faiss_index_path)
        pkl_path = FAISS_DIR / "index.pkl"
        if pkl_path.exists():
            os.unlink(pkl_path)
        
        # Rebuild with remaining documents (if any)
        if remaining_docs:
            new_vectorstore = FAISS.from_documents(remaining_docs, embeddings)
            new_vectorstore.save_local(str(FAISS_DIR))
    
    return {
        "status": "deleted",
        "name": filename,
        "remaining_files": len(metadata["files"]),
    }

