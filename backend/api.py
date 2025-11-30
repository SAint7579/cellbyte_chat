"""
CellByte Chat - FastAPI Backend
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Fix OpenMP conflict with FAISS on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Load .env from project root BEFORE other imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_utils import ingest_csv, get_csv_metadata, delete_file
from agent import CellByteAgent


# =============================================================================
# API Configuration
# =============================================================================

tags_metadata = [
    {
        "name": "Health",
        "description": "API health and status checks",
    },
    {
        "name": "Chat",
        "description": "Conversational AI endpoints for querying data",
    },
    {
        "name": "Files",
        "description": "File ingestion and management",
    },
    {
        "name": "History",
        "description": "Chat history management",
    },
]

app = FastAPI(
    title="CellByte Chat API",
    description="""
## CSV Chatbot with RAG

CellByte Chat is an AI-powered chatbot that allows you to have natural language 
conversations with your CSV data.

### Features
- **File Ingestion**: Upload CSV files to be indexed and made queryable
- **RAG-powered Chat**: Ask questions about your data in natural language
- **Tool Calling**: Agent can search data and perform actions autonomously

### Workflow
1. Upload CSV files via `/files/ingest`
2. Refresh agent context via `/chat/refresh`
3. Start chatting via `/chat`
    """,
    version="0.1.0",
    openapi_tags=tags_metadata,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Pydantic Models
# =============================================================================

# --- File Models ---

class IngestResponse(BaseModel):
    """Response after successfully ingesting a file."""
    status: str = Field(..., example="success")
    name: str = Field(..., example="sales_data.csv")
    description: str = Field(..., description="LLM-generated description of the file")
    rows_indexed: int = Field(..., example=1500)


class FileMetadata(BaseModel):
    """Metadata for an ingested file."""
    name: str
    date_ingested: str
    description: str
    row_count: int
    columns: list[str]
    file_type: Optional[str] = None
    delimiter: Optional[str] = None


class FilesListResponse(BaseModel):
    """List of all ingested files."""
    files: list[dict]


class DeleteResponse(BaseModel):
    """Response after deleting a file."""
    status: str = Field(..., example="deleted")
    name: str
    remaining_files: int


# --- Chat Models ---

class ChatMessage(BaseModel):
    """A single message in the chat history."""
    role: str = Field(..., description="Role: 'user', 'assistant', or 'tool'")
    content: str = Field(..., description="Message content")
    tool_calls: Optional[list] = Field(None, description="Tool calls made by assistant")
    tool_call_id: Optional[str] = Field(None, description="ID for tool response messages")


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str = Field(..., description="The user's message", example="What products have the highest sales?")
    history: Optional[list[ChatMessage]] = Field(None, description="Previous conversation history")


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    response: str = Field(..., description="The agent's response")
    history: list = Field(..., description="Updated conversation history including tool calls")


# =============================================================================
# Agent Initialization
# =============================================================================

agent = CellByteAgent()


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/healthz", tags=["Health"])
async def healthz():
    """
    Health check endpoint.
    
    Returns the API status. Use this to verify the service is running.
    """
    return {"status": "ok", "message": "CellByte Chat API is running"}


# =============================================================================
# Chat Endpoints
# =============================================================================

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Chat with the AI agent.
    
    Send a message and receive an AI-generated response. The agent can:
    - Search through your ingested CSV data
    - Answer questions about your data
    - Maintain conversation context via history
    
    **History Format:**
    The history includes all messages including tool calls, allowing full 
    transparency into what the agent did to generate its response.
    """
    try:
        history = None
        if request.history:
            history = [msg.model_dump(exclude_none=True) for msg in request.history]
        
        response, updated_history = agent.chat(request.message, history=history)
        
        return ChatResponse(response=response, history=updated_history)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in chat: {str(e)}")


@app.post("/chat/refresh", tags=["Chat"])
async def refresh_agent():
    """
    Refresh the agent's file metadata.
    
    Call this after ingesting new files to update the agent's knowledge 
    of available data. The agent's system prompt will be rebuilt with 
    the latest file descriptions.
    """
    try:
        agent.refresh_metadata()
        return {
            "status": "ok", 
            "message": "Agent metadata refreshed",
            "files_loaded": len(agent.metadata)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing agent: {str(e)}")


# =============================================================================
# File Management Endpoints
# =============================================================================

@app.post("/files/ingest", response_model=IngestResponse, tags=["Files"])
async def ingest_csv_file(file: UploadFile = File(..., description="CSV file to ingest")):
    """
    Upload and ingest a CSV file.
    
    This endpoint:
    1. Generates an LLM-powered description of the CSV
    2. Creates embeddings for semantic search
    3. Stores vectors in FAISS vectorstore
    4. Saves metadata to csv_metadata.json
    
    **Note:** After ingesting, call `/chat/refresh` to update the agent.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        result = ingest_csv(tmp_path, filename=file.filename)
        return IngestResponse(**result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting CSV: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/files", response_model=FilesListResponse, tags=["Files"])
async def list_files():
    """
    List all ingested files.
    
    Returns metadata for all files that have been ingested, including:
    - File name and ingestion date
    - LLM-generated description
    - Row count and column names
    - Statistical summary
    """
    metadata = get_csv_metadata()
    return FilesListResponse(files=metadata.get("files", []))


@app.delete("/files/{filename}", response_model=DeleteResponse, tags=["Files"])
async def delete_csv_file(filename: str):
    """
    Delete an ingested file.
    
    This will:
    1. Remove the file's metadata from csv_metadata.json
    2. Rebuild the FAISS vectorstore without this file's vectors
    
    **Note:** After deleting, call `/chat/refresh` to update the agent.
    """
    try:
        result = delete_file(filename)
        return DeleteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


# =============================================================================
# History Endpoints
# =============================================================================

HISTORY_DIR = PROJECT_ROOT / "history"
HISTORY_DIR.mkdir(exist_ok=True)


class ChatHistoryModel(BaseModel):
    """A saved chat history."""
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list


@app.get("/history", tags=["History"])
async def list_histories():
    """
    List all saved chat histories.
    """
    import json
    histories = []
    
    for file in HISTORY_DIR.glob("*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                histories.append({
                    "id": data.get("id"),
                    "title": data.get("title", "Untitled"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                })
        except Exception:
            continue
    
    histories.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return histories


@app.get("/history/{history_id}", tags=["History"])
async def get_history(history_id: str):
    """
    Get a specific chat history by ID.
    """
    import json
    file_path = HISTORY_DIR / f"{history_id}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="History not found")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.put("/history/{history_id}", tags=["History"])
async def save_history(history_id: str, history: ChatHistoryModel):
    """
    Save or update a chat history.
    """
    import json
    file_path = HISTORY_DIR / f"{history_id}.json"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history.model_dump(), f, indent=2, ensure_ascii=False)
    
    return {"status": "saved", "id": history_id}


@app.delete("/history/{history_id}", tags=["History"])
async def delete_history(history_id: str):
    """
    Delete a chat history.
    """
    file_path = HISTORY_DIR / f"{history_id}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="History not found")
    
    file_path.unlink()
    return {"status": "deleted", "id": history_id}


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
