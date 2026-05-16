"""Knowledge Base (RAG) endpoints."""
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()

APP_DIR = Path(__file__).parent.parent
VECTOR_DB_PATH = APP_DIR / "data" / "vector_db"
SETTINGS_PATH = APP_DIR / "settings.json"


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        return {}


def _get_services():
    from services.llm_service import LLMService
    from services.rag_service import RagService
    settings = _load_settings()
    llm = LLMService(settings)
    rag = RagService(VECTOR_DB_PATH)
    return llm, rag, settings


# ── Collection endpoints ────────────────────────────────────────────────

@router.get("/knowledge-base/collections")
def list_collections():
    _, rag, _ = _get_services()
    return {"collections": rag.list_collections()}


@router.post("/knowledge-base/collections")
def create_collection(name: str = Form(...)):
    _, rag, _ = _get_services()
    rag.create_collection(name)
    return {"name": name}


@router.delete("/knowledge-base/collections/{name}")
def delete_collection(name: str):
    if name == "default":
        raise HTTPException(400, "Cannot delete the default collection")
    _, rag, _ = _get_services()
    rag.delete_collection(name)
    return {"deleted": name}


# ── Document endpoints ──────────────────────────────────────────────────

@router.get("/knowledge-base/{collection}/documents")
def list_documents(collection: str):
    _, rag, _ = _get_services()
    return {"documents": rag.list_documents(collection)}


@router.post("/knowledge-base/{collection}/upload")
async def upload_documents(
    collection: str,
    files: List[UploadFile] = File(...),
):
    llm, rag, settings = _get_services()
    chunk_size = settings.get("rag_chunk_size", 1000)
    overlap = settings.get("rag_chunk_overlap", 200)

    results = []
    for file in files:
        raw = await file.read()
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            results.append({"filename": file.filename, "chunks": 0, "error": "Could not decode file"})
            continue
        if not text.strip():
            results.append({"filename": file.filename, "chunks": 0, "error": "Empty file"})
            continue
        try:
            count = await rag.add_document(
                text=text,
                filename=file.filename,
                llm_service=llm,
                collection=collection,
                chunk_size=chunk_size,
                overlap=overlap,
            )
            results.append({"filename": file.filename, "chunks": count})
        except Exception as exc:
            results.append({"filename": file.filename, "chunks": 0, "error": str(exc)})

    return {"results": results}


@router.delete("/knowledge-base/{collection}/documents/{filename:path}")
def delete_document(collection: str, filename: str):
    _, rag, _ = _get_services()
    deleted = rag.delete_document(filename, collection)
    return {"deleted": filename, "chunks_removed": deleted}


# ── Search endpoint ─────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/knowledge-base/{collection}/search")
async def search(collection: str, body: SearchRequest):
    llm, rag, settings = _get_services()
    top_k = min(body.top_k, settings.get("rag_top_k", 5))
    hits = await rag.query(body.query, llm, collection, top_k)
    return {"hits": hits}
