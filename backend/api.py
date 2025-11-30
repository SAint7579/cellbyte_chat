"""
CellByte Chat - FastAPI Backend
"""

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root BEFORE other imports (override=True to override system env vars)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_utils import ingest_csv, get_csv_metadata

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


@app.get("/healthz")
async def healthz():
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
    
    tmp_path = None
    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Ingest the CSV
        result = ingest_csv(tmp_path, filename=file.filename)
        
        return IngestResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ingesting CSV: {str(e)}"
        )
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

