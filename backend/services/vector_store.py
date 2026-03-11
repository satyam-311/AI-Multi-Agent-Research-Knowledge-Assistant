import logging
import math
from functools import lru_cache
from pathlib import Path

from chromadb import PersistentClient

from backend.config import get_settings

logger = logging.getLogger(__name__)


class InMemoryCollection:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        for item_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self._items[item_id] = {
                "id": item_id,
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def query(self, query_embeddings: list[list[float]], n_results: int, where: dict) -> dict:
        query_embedding = query_embeddings[0]
        matches = [
            item for item in self._items.values() if _matches_where(item["metadata"], where)
        ]
        ranked = sorted(
            matches,
            key=lambda item: _cosine_distance(query_embedding, item["embedding"]),
        )[: max(1, n_results)]
        return {
            "ids": [[item["id"] for item in ranked]],
            "documents": [[item["document"] for item in ranked]],
            "metadatas": [[item["metadata"] for item in ranked]],
            "distances": [[_cosine_distance(query_embedding, item["embedding"]) for item in ranked]],
        }

    def delete(self, where: dict) -> None:
        ids_to_delete = [
            item_id
            for item_id, item in self._items.items()
            if _matches_where(item["metadata"], where)
        ]
        for item_id in ids_to_delete:
            self._items.pop(item_id, None)


def _cosine_distance(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    return 1.0 - (numerator / (left_norm * right_norm))


def _matches_where(metadata: dict, where: dict) -> bool:
    if "$and" in where:
        return all(_matches_where(metadata, clause) for clause in where["$and"])

    for key, condition in where.items():
        if "$eq" in condition and metadata.get(key) != condition["$eq"]:
            return False
    return True


@lru_cache(maxsize=1)
def get_vector_client():
    settings = get_settings()
    try:
        Path(settings.chroma_persist_directory).mkdir(parents=True, exist_ok=True)
        return PersistentClient(path=settings.chroma_persist_directory)
    except Exception as exc:
        logger.warning(
            "Persistent Chroma store unavailable at '%s'; using in-memory vector store for this session. Root error: %s: %s",
            settings.chroma_persist_directory,
            exc.__class__.__name__,
            exc,
        )
        return None


@lru_cache(maxsize=1)
def get_document_collection():
    client = get_vector_client()
    if client is None:
        return InMemoryCollection()
    return client.get_or_create_collection(name="documents")


def build_metadata_filter(user_id: int, document_id: int | None = None) -> dict:
    clauses = [{"user_id": {"$eq": user_id}}]
    if document_id is not None:
        clauses.append({"document_id": {"$eq": document_id}})
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
