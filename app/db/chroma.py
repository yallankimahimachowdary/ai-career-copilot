"""Persistent ChromaDB vector client and collection manager."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.core.logging import logger

CHROMA_DIR = Path("data/chromadb")
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

_client: Optional[chromadb.ClientAPI] = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client instance."""
    global _client
    if _client is None:
        logger.info(f"Initializing persistent ChromaDB client at {CHROMA_DIR.resolve()}")
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR.resolve()),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_job_postings_collection() -> chromadb.Collection:
    """Retrieve or create the job_postings_embeddings Chroma collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="job_postings_embeddings",
        metadata={"hnsw:space": "cosine"},
    )


def get_interview_material_collection() -> chromadb.Collection:
    """Retrieve or create the interview_material_embeddings Chroma collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="interview_material_embeddings",
        metadata={"hnsw:space": "cosine"},
    )


class ChromaService:
    """High-level abstraction for indexing and querying vectors in ChromaDB."""

    def __init__(self):
        self.jobs_col = get_job_postings_collection()
        self.interview_col = get_interview_material_collection()

    def upsert_job_postings(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Upsert job postings by unique ID (external_id or uuid) to prevent duplicates."""
        if not ids:
            return
        self.jobs_col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query_jobs(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform nearest-neighbor search for job postings."""
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return self.jobs_col.query(**kwargs)

    def get_job_count(self) -> int:
        """Return total items in the job_postings_embeddings collection."""
        return self.jobs_col.count()

    def upsert_interview_material(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Upsert interview materials."""
        if not ids:
            return
        self.interview_col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )


chroma_service = ChromaService()
