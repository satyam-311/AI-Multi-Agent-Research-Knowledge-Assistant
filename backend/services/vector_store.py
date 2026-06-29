# vector_store.py
# ChromaDB client and collection management for the MARKA vector retrieval layer.
# Provides a singleton persistent ChromaDB client with an in-process fallback
# that keeps the application functional even when the on-disk store is unavailable.

import logging
import math
# lru_cache ensures the ChromaDB client and collection are created only once
# per process, avoiding repeated disk I/O and connection overhead
from functools import lru_cache
from pathlib import Path

# ChromaDB PersistentClient stores vector embeddings on disk across restarts
from chromadb import PersistentClient

# Application settings for the ChromaDB persistence directory path
from backend.config import get_settings

logger = logging.getLogger(__name__)


class InMemoryCollection:
    """
    In-process vector store that mirrors the ChromaDB collection interface.

    Used as a fallback when the persistent ChromaDB directory cannot be created
    or accessed (e.g. read-only filesystem, missing directory permissions). Data
    is lost when the process restarts, so this is suitable only for development
    or degraded-mode operation.

    Implements the same add, query, and delete method signatures as a ChromaDB
    Collection so callers (EmbeddingAgent, RetrievalAgent) need no conditional logic.

    Attributes:
        _items (dict): In-memory store mapping chunk ID strings to their document,
            embedding, and metadata payloads.
    """

    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """
        Insert or replace vector chunks in the in-memory store.

        Args:
            ids (list[str]): Unique string IDs for each chunk (e.g. "42_0", "42_1").
            documents (list[str]): Raw text of each chunk.
            embeddings (list[list[float]]): Dense vectors corresponding to each chunk.
            metadatas (list[dict]): Metadata dicts (user_id, document_id, source, chunk_index).

        Returns:
            None
        """
        for item_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
            self._items[item_id] = {
                "id": item_id,
                "document": document,
                "embedding": embedding,
                "metadata": metadata,
            }

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict,
        include: list[str] | None = None,
    ) -> dict:
        """
        Find the n_results most similar chunks to the query embedding.

        Filters candidates by the metadata where clause, computes cosine distance
        for each match, and returns results sorted by ascending distance (best first).

        Args:
            query_embeddings (list[list[float]]): List containing a single query vector.
            n_results (int): Number of top results to return.
            where (dict): Metadata filter in ChromaDB's $eq/$and clause format.
            include (list[str] | None): Ignored; included for interface compatibility.

        Returns:
            dict: ChromaDB-compatible response with keys: ids, documents, metadatas, distances.
            Each value is a nested list (one sublist per query embedding).
        """
        query_embedding = query_embeddings[0]
        # Filter the item store to only candidates that match the user/document scope
        matches = [
            item for item in self._items.values() if _matches_where(item["metadata"], where)
        ]
        # Sort by cosine distance ascending so the most similar chunks come first
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
        """
        Remove all chunks whose metadata matches the given filter.

        Args:
            where (dict): Metadata filter in ChromaDB's $eq/$and clause format.

        Returns:
            None
        """
        ids_to_delete = [
            item_id
            for item_id, item in self._items.items()
            if _matches_where(item["metadata"], where)
        ]
        for item_id in ids_to_delete:
            self._items.pop(item_id, None)


def _cosine_distance(left: list[float], right: list[float]) -> float:
    """
    Compute the cosine distance between two vectors.

    Cosine distance = 1 - cosine_similarity. A value of 0 means the vectors
    are identical; a value of 1 means they are orthogonal (unrelated).

    Args:
        left (list[float]): First dense vector.
        right (list[float]): Second dense vector of the same dimensionality.

    Returns:
        float: Cosine distance in the range [0.0, 1.0]. Returns 1.0 if either
        vector has zero magnitude (undefined similarity).
    """
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        # A zero-magnitude vector has undefined cosine similarity; treat as orthogonal
        return 1.0
    return 1.0 - (numerator / (left_norm * right_norm))


def _matches_where(metadata: dict, where: dict) -> bool:
    """
    Evaluate a ChromaDB-style metadata filter clause against a metadata dict.

    Supports the $and compound operator and the $eq equality operator used by
    build_metadata_filter, which is sufficient for the user_id + document_id scope
    pattern used throughout MARKA.

    Args:
        metadata (dict): The metadata stored alongside a ChromaDB chunk.
        where (dict): Filter clause in ChromaDB format (e.g. {"user_id": {"$eq": 1}}).

    Returns:
        bool: True if the metadata satisfies all conditions in the where clause.
    """
    if "$and" in where:
        # Recursively evaluate each sub-clause; all must match
        return all(_matches_where(metadata, clause) for clause in where["$and"])

    for key, condition in where.items():
        if "$eq" in condition and metadata.get(key) != condition["$eq"]:
            return False
    return True


@lru_cache(maxsize=1)
def get_vector_client():
    """
    Return the singleton ChromaDB PersistentClient, or None if initialization fails.

    The lru_cache ensures the client is constructed at most once per process,
    avoiding repeated disk access on every request. Returns None (rather than
    raising) so that get_document_collection can substitute an InMemoryCollection.

    Returns:
        PersistentClient | None: A connected ChromaDB client, or None if the
        persistence directory cannot be created or the client cannot connect.
    """
    settings = get_settings()
    try:
        # Ensure the persistence directory exists before passing it to PersistentClient
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
    """
    Return the singleton ChromaDB collection used to store all document chunks.

    If the PersistentClient is unavailable, returns an InMemoryCollection that
    satisfies the same interface so agents can run without code changes.

    The single "documents" collection stores chunks from all users; user-level
    isolation is enforced through the user_id metadata filter on every query.

    Returns:
        chromadb.Collection | InMemoryCollection: The live ChromaDB collection,
        or the in-memory fallback if the persistent client could not be initialized.
    """
    client = get_vector_client()
    if client is None:
        return InMemoryCollection()
    # get_or_create_collection is idempotent: safe to call on every startup
    return client.get_or_create_collection(name="documents")


def build_metadata_filter(user_id: int, document_id: int | None = None) -> dict:
    """
    Construct a ChromaDB metadata filter that scopes queries to a user's documents.

    When document_id is provided, the filter restricts results to chunks from
    that specific document. When it is None, all of the user's documents are
    searched. The $and operator is used for compound filters because ChromaDB
    requires it when more than one field condition is needed.

    Args:
        user_id (int): The authenticated user's ID. Always included in the filter.
        document_id (int | None): Optional document scope. Defaults to None.

    Returns:
        dict: A ChromaDB where-clause dict. A single-condition filter omits $and
        for ChromaDB compatibility (some versions require exactly the right structure).
    """
    clauses = [{"user_id": {"$eq": user_id}}]
    if document_id is not None:
        clauses.append({"document_id": {"$eq": document_id}})
    # ChromaDB requires $and only when there are two or more conditions
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
