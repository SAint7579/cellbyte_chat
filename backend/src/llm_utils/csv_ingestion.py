import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

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
        Generated description string
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Build a summary of the data for the LLM
    csv_summary = f"""
    Filename: {filename}
    Shape: {df.shape[0]} rows × {df.shape[1]} columns

    Columns and Types:
    {df.dtypes.to_string()}

    Sample Data (first 5 rows):
    {df.head().to_string()}

    Basic Statistics:
    {df.describe(include='all').to_string()}
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


def ingest_csv(file_path: str, filename: Optional[str] = None) -> dict:
    """
    Ingest a CSV file: generate description, store in FAISS, save metadata.
    
    Args:
        file_path: Path to the CSV file
        filename: Optional custom name (defaults to file basename)
        
    Returns:
        Dict with ingestion results including name, description, and status
    """
    _ensure_dirs()
    
    # Read the CSV
    df = pd.read_csv(file_path)
    
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
    
    file_metadata = {
        "name": filename,
        "date_ingested": datetime.now().isoformat(),
        "description": description,
        "row_count": len(df),
        "columns": list(df.columns),
        "describe": df.describe(include='all').to_dict(),
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
    }


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

