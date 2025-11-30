"""
CellByte Chat - FastAPI Backend
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_utils import ingest_csv, get_csv_metadata

load_dotenv()

app = FastAPI(
    title="CellByte Chat API",
    description="API for CSV chatbot with RAG capabilities",
    version="0.1.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestResponse(BaseModel):
    status: str
    name: str
    description: str
    rows_indexed: int


class MetadataResponse(BaseModel):
    files: list


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "CellByte Chat API is running"}


@app.post("/ingest/csv", response_model=IngestResponse)
async def ingest_csv_file(file: UploadFile = File(...)):
    """
    Upload and ingest a CSV file.
    
    - Generates an LLM description of the CSV
    - Stores content in FAISS vectorstore
    - Saves metadata to csv_metadata.json
    """
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )
    
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Ingest the CSV
        result = ingest_csv(tmp_path, filename=file.filename)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        return IngestResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ingesting CSV: {str(e)}"
        )


@app.get("/metadata", response_model=MetadataResponse)
async def get_metadata():
    """
    Get metadata for all ingested CSV files.
    """
    metadata = get_csv_metadata()
    return MetadataResponse(files=metadata.get("files", []))


@app.delete("/metadata/{filename}")
async def delete_csv_metadata(filename: str):
    """
    Delete metadata for a specific CSV file.
    
    Note: This only removes the metadata entry, not the vectors from FAISS.
    Full deletion would require rebuilding the vectorstore.
    """
    metadata = get_csv_metadata()
    
    # Find and remove the file
    original_count = len(metadata.get("files", []))
    metadata["files"] = [f for f in metadata.get("files", []) if f["name"] != filename]
    
    if len(metadata["files"]) == original_count:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found in metadata"
        )
    
    # Save updated metadata
    from llm_utils.csv_ingestion import _save_metadata
    _save_metadata(metadata)
    
    return {"status": "deleted", "name": filename}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

