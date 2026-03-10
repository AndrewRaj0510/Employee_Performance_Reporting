"""
FastAPI Backend for the HR RAG System.
Run with: uvicorn main:app --reload --port 8000
"""
import sys
import os

# Add the parent directory (POC root) to the path so we can import SQL, Vector_DB, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any, Dict

from orchestrator import process_query

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="HR RAG API",
    description="FastAPI backend that routes queries to SQL (Postgres) or Vector (ChromaDB) tools.",
    version="1.0.0"
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic Models ────────────────────────────────────────────────────────────
class HistoryTurn(BaseModel):
    role: str                        # "user" or "assistant"
    content: str
    sql_query: Optional[str] = None  # populated for assistant turns that ran SQL

class ChatRequest(BaseModel):
    query: str
    history: List[HistoryTurn] = []

class EvidenceModel(BaseModel):
    sql_query: Optional[str] = None
    sql_columns: Optional[List[str]] = None
    sql_table: Optional[List[List[Any]]] = None
    vector_context: Optional[str] = None
    vector_sources: Optional[List[str]] = None
    latency: float

class ChatResponse(BaseModel):
    response_text: str
    intent: str  # "SQL" | "VECTOR" | "BOTH" | "FOLLOWUP"
    evidence: EvidenceModel

# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "HR RAG API is running."}

@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Accepts a natural-language query and returns
    a structured response including the answer, intent, and evidence.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        history = [{"role": t.role, "content": t.content} for t in request.history]
        result = process_query(request.query.strip(), history=history)
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
