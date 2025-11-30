"""
CSV Ingestion

Functions for ingesting CSV files into the FAISS vectorstore and managing metadata.
"""

import os
import json
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
from langchain_core.documents import Document

from general_utils import (
    get_logger,
    # File utilities
    read_tabular_file,
    load_dataset,
    list_available_files,
    # Paths
    DATABASE_DIR,
    FAISS_DIR,
    FILES_DIR,
    METADATA_FILE,
    ensure_dirs,
)

logger = get_logger("csv_ingestion")


# =============================================================================
# Metadata Management
# =============================================================================

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


def get_csv_metadata() -> dict:
    """
    Get all CSV metadata.
    
    Returns:
        Dict containing all file metadata
    """
    return _load_metadata()


# =============================================================================
# LLM-based Description Generation
# =============================================================================

def _generate_csv_description(df: pd.DataFrame, filename: str) -> str:
    """
    Use ChatOpenAI to generate a description of the CSV file.
    
    Args:
        df: Pandas DataFrame of the CSV
        filename: Name of the CSV file
        
    Returns:
        Generated description string, or error message if generation fails
    """
    logger.info(f"Generating description for {filename}...")
    
    try:
        model_name = "gpt-5.1"
        logger.debug(f"Using LLM: {model_name}")
        llm = ChatOpenAI(model=model_name, temperature=0)
        
        # Build a summary of the data for the LLM
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

        logger.debug(f"Prompt length: {len(prompt)} chars")
        response = llm.invoke(prompt)
        logger.info(f"Description generated ({len(response.content)} chars)")
        return response.content
    
    except Exception as e:
        logger.error(f"Description generation failed: {e}", exc_info=True)
        return f"[Auto-generated description failed: {str(e)}] File contains {len(df)} rows and {len(df.columns)} columns: {', '.join(df.columns.tolist())}"


# =============================================================================
# Document Conversion for Vectorstore
# =============================================================================

def _csv_to_documents(df: pd.DataFrame, filename: str) -> list[Document]:
    """
    Convert CSV rows to LangChain Documents for vectorstore.
    
    Args:
        df: Pandas DataFrame
        filename: Source filename for metadata
        
    Returns:
        List of Document objects
    """
    logger.debug(f"Converting {len(df)} rows to documents")
    documents = []
    
    for idx, row in df.iterrows():
        row_text = " | ".join([f"{col}: {val}" for col, val in row.items()])
        
        doc = Document(
            page_content=row_text,
            metadata={
                "source": filename,
                "row_index": idx,
            }
        )
        documents.append(doc)
    
    logger.debug(f"Created {len(documents)} documents")
    return documents


# =============================================================================
# File Ingestion
# =============================================================================

def ingest_file(file_path: str, filename: Optional[str] = None) -> dict:
    """
    Ingest a tabular file (CSV, TSV, Excel): generate description, store in FAISS, save metadata.
    
    Args:
        file_path: Path to the file (CSV, TSV, XLSX, XLS)
        filename: Optional custom name (defaults to file basename)
        
    Returns:
        Dict with ingestion results including name, description, and status
    """
    logger.info(f"=== Starting file ingestion ===")
    logger.info(f"File: {file_path}")
    
    ensure_dirs()
    
    # Read the file with auto-detection
    df, file_info = read_tabular_file(file_path)
    
    # Determine filename
    if filename is None:
        filename = Path(file_path).name
    logger.info(f"Filename: {filename}")
    
    # Save original file to database
    import shutil
    dest_path = FILES_DIR / filename
    shutil.copy2(file_path, dest_path)
    logger.info(f"Saved original file to: {dest_path}")
    
    # Generate description using LLM
    description = _generate_csv_description(df, filename)
    
    # Convert to documents
    documents = _csv_to_documents(df, filename)
    
    # Create embeddings and store in FAISS
    logger.info("Creating embeddings...")
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    except Exception as e:
        logger.error(f"Failed to create embeddings: {e}")
        raise
    
    # Check if FAISS store already exists
    faiss_index_path = FAISS_DIR / "index.faiss"
    
    if faiss_index_path.exists():
        logger.info("Loading existing FAISS index...")
        vectorstore = FAISS.load_local(
            str(FAISS_DIR), 
            embeddings,
            allow_dangerous_deserialization=True
        )
        logger.info(f"Adding {len(documents)} documents to existing index...")
        vectorstore.add_documents(documents)
    else:
        logger.info(f"Creating new FAISS index with {len(documents)} documents...")
        vectorstore = FAISS.from_documents(documents, embeddings)
    
    # Save vectorstore
    vectorstore.save_local(str(FAISS_DIR))
    logger.info("FAISS index saved")
    
    # Update metadata
    metadata = _load_metadata()
    
    existing_idx = next(
        (i for i, f in enumerate(metadata["files"]) if f["name"] == filename),
        None
    )
    
    # Safely get describe stats
    try:
        describe_df = df.describe(include='all').fillna("")
        describe_df = describe_df.replace([float('inf'), float('-inf')], "")
        describe_stats = describe_df.to_dict()
    except Exception:
        describe_stats = {"error": "Could not generate statistics"}
    
    # Get head(5) as sample data
    try:
        head_df = df.head(5).fillna("")
        head_5 = head_df.to_dict(orient='records')
    except Exception:
        head_5 = []
    
    file_metadata = {
        "name": filename,
        "date_ingested": datetime.now().isoformat(),
        "description": description,
        "row_count": len(df),
        "columns": list(df.columns),
        "file_type": file_info.get("type"),
        "delimiter": file_info.get("delimiter"),
        "describe": describe_stats,
        "head_5": head_5,
    }
    
    if existing_idx is not None:
        metadata["files"][existing_idx] = file_metadata
        logger.info(f"Updated existing metadata for {filename}")
    else:
        metadata["files"].append(file_metadata)
        logger.info(f"Added new metadata for {filename}")
    
    _save_metadata(metadata)
    
    logger.info(f"=== Ingestion complete: {len(documents)} rows indexed ===")
    
    return {
        "status": "success",
        "name": filename,
        "description": description,
        "rows_indexed": len(documents),
        "file_type": file_info.get("type"),
    }


# Backward-compatible alias
ingest_csv = ingest_file


# =============================================================================
# Vectorstore Access
# =============================================================================

def get_vectorstore() -> Optional[FAISS]:
    """
    Load and return the FAISS vectorstore.
    
    Returns:
        FAISS vectorstore or None if not exists
    """
    faiss_index_path = FAISS_DIR / "index.faiss"
    
    if not faiss_index_path.exists():
        logger.warning("FAISS index does not exist")
        return None
    
    logger.debug("Loading FAISS vectorstore...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vectorstore = FAISS.load_local(
        str(FAISS_DIR),
        embeddings,
        allow_dangerous_deserialization=True
    )
    logger.debug("FAISS vectorstore loaded")
    return vectorstore


# =============================================================================
# File Deletion
# =============================================================================

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
    logger.info(f"Deleting file: {filename}")
    metadata = _load_metadata()
    
    file_exists = any(f["name"] == filename for f in metadata.get("files", []))
    
    if not file_exists:
        logger.error(f"File '{filename}' not found in metadata")
        raise ValueError(f"File '{filename}' not found in metadata")
    
    # Remove from metadata
    metadata["files"] = [f for f in metadata["files"] if f["name"] != filename]
    _save_metadata(metadata)
    logger.info("Removed from metadata")
    
    # Rebuild FAISS index without the deleted file's vectors
    faiss_index_path = FAISS_DIR / "index.faiss"
    
    if faiss_index_path.exists():
        logger.info("Rebuilding FAISS index...")
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = FAISS.load_local(
            str(FAISS_DIR),
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        docstore = vectorstore.docstore
        index_to_id = vectorstore.index_to_docstore_id
        
        remaining_docs = []
        for idx, doc_id in index_to_id.items():
            doc = docstore.search(doc_id)
            if doc and doc.metadata.get("source") != filename:
                remaining_docs.append(doc)
        
        logger.info(f"Keeping {len(remaining_docs)} documents from other files")
        
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
            logger.info("FAISS index rebuilt")
        else:
            logger.info("No remaining documents, index cleared")
    
    logger.info(f"File '{filename}' deleted successfully")
    
    return {
        "status": "deleted",
        "name": filename,
        "remaining_files": len(metadata["files"]),
    }
