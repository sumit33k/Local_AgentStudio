"""RAG service: ChromaDB vector store with chunking and semantic search."""
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


class RagService:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=str(self.db_path))
            except ImportError:
                raise HTTPException(500, "Install 'chromadb': pip install chromadb")
        return self._client

    def _collection(self, name: str = "default"):
        client = self._get_client()
        # Use cosine similarity; we supply our own embeddings so no embedding_function needed
        try:
            import chromadb.utils.embedding_functions as ef
        except ImportError:
            pass
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Collection management ───────────────────────────────────────────

    def list_collections(self) -> List[str]:
        try:
            client = self._get_client()
            return [c.name for c in client.list_collections()]
        except Exception:
            return []

    def create_collection(self, name: str) -> str:
        self._collection(name)
        return name

    def delete_collection(self, name: str) -> None:
        client = self._get_client()
        try:
            client.delete_collection(name)
        except Exception as exc:
            raise HTTPException(404, f"Collection not found: {exc}")

    # ── Document management ─────────────────────────────────────────────

    def list_documents(self, collection: str = "default") -> List[Dict]:
        col = self._collection(collection)
        try:
            result = col.get(include=["metadatas"])
            counts: Dict[str, int] = {}
            for meta in (result.get("metadatas") or []):
                fname = meta.get("filename", "unknown")
                counts[fname] = counts.get(fname, 0) + 1
            return [{"filename": k, "chunk_count": v} for k, v in sorted(counts.items())]
        except Exception:
            return []

    async def add_document(
        self,
        text: str,
        filename: str,
        llm_service,
        collection: str = "default",
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> int:
        chunks = _chunk_text(text, chunk_size, overlap)
        if not chunks:
            return 0

        col = self._collection(collection)

        ids, documents, metadatas, embeddings_list = [], [], [], []
        for idx, chunk in enumerate(chunks):
            embedding = await llm_service.embed(chunk)
            if not embedding:
                # Skip chunks we can't embed (embedding model may not be pulled)
                continue
            chunk_id = f"{filename}__chunk__{idx}__{uuid.uuid4().hex[:8]}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({"filename": filename, "chunk_idx": idx})
            embeddings_list.append(embedding)

        if ids:
            col.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings_list)

        return len(ids)

    def delete_document(self, filename: str, collection: str = "default") -> int:
        col = self._collection(collection)
        try:
            result = col.get(where={"filename": filename}, include=["metadatas"])
            ids = result.get("ids", [])
            if ids:
                col.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            raise HTTPException(500, f"Delete failed: {exc}")

    # ── Semantic search ─────────────────────────────────────────────────

    async def query(
        self,
        query_text: str,
        llm_service,
        collection: str = "default",
        top_k: int = 5,
    ) -> List[Dict]:
        embedding = await llm_service.embed(query_text)
        if not embedding:
            return []

        col = self._collection(collection)
        try:
            results = col.query(
                query_embeddings=[embedding],
                n_results=min(top_k, col.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        hits = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            hits.append({
                "text": doc,
                "filename": meta.get("filename", ""),
                "chunk_idx": meta.get("chunk_idx", 0),
                "score": round(1 - dist, 4),
            })
        return hits

    def build_context_from_hits(self, hits: List[Dict]) -> str:
        if not hits:
            return ""
        parts = ["--- Knowledge Base Context ---"]
        for h in hits:
            parts.append(f"[{h['filename']} | score:{h['score']}]\n{h['text']}")
        return "\n\n".join(parts)
