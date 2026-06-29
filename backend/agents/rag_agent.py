# rag_agent.py
# Retrieval-Augmented Generation context collector for the MARKA pipeline.
# Wraps ChromaDB vector retrieval behind a confidence-scoring interface that
# the orchestrator uses to decide whether web search fallback is needed.

from __future__ import annotations

# dataclass provides a typed, immutable result container for retrieval output
from dataclasses import dataclass
import logging

# SQLAlchemy session is used only for the PostgreSQL fallback path
from sqlalchemy.orm import Session

# ORM models for the PostgreSQL document fallback query
from backend import models
# RetrievalAgent handles the actual ChromaDB cosine similarity search
from backend.agents.retrieval_agent import RetrievalAgent


logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """
    Typed container for a single RAG retrieval pass.

    Packages both the raw contexts for LLM consumption and the derived confidence
    metrics that the orchestrator uses to make the web search fallback decision.
    Using a dataclass keeps the interface explicit and avoids passing raw dicts
    between agents.

    Attributes:
        contexts (list[dict]): Ordered list of retrieved text chunks, each containing
            source metadata, a similarity score, and the raw text passed to the LLM prompt.
        sources (list[dict]): Deduplicated source citation objects derived from contexts,
            formatted for the API response sources field.
        max_similarity (float): Highest cosine similarity score among all retrieved chunks.
            The orchestrator compares this against the 0.5 threshold to gate web fallback.
        average_similarity (float): Mean similarity across all contexts, used in logs to
            diagnose retrieval quality over time.
        used_database_fallback (bool): True when ChromaDB returned no results and the agent
            fell back to reading content_text directly from the PostgreSQL documents table.
    """

    contexts: list[dict]
    sources: list[dict]
    max_similarity: float
    average_similarity: float
    used_database_fallback: bool

    @property
    def is_empty(self) -> bool:
        """
        Check whether retrieval produced any context at all.

        Returns:
            bool: True if no contexts were retrieved from either ChromaDB or PostgreSQL.
        """
        return len(self.contexts) == 0

    @property
    def is_low_confidence(self) -> bool:
        """
        Determine whether the best retrieved chunk clears the minimum similarity threshold.

        The 0.5 threshold is the empirically chosen cutoff below which retrieved chunks
        are unlikely to be topically relevant to the query. Queries below this threshold
        trigger web search augmentation in the orchestrator.

        Returns:
            bool: True if max_similarity is below 0.5.
        """
        return self.max_similarity < 0.5


class RAGAgent:
    """
    Retrieval-Augmented Generation agent for the MARKA document knowledge base.

    Coordinates two retrieval strategies in priority order:
    1. Primary: ChromaDB vector cosine similarity search via RetrievalAgent.
    2. Fallback: Direct PostgreSQL content_text read when ChromaDB returns empty results.

    Returns a RAGResult that the orchestrator inspects for confidence scoring before
    deciding whether to call the web search agent.

    Attributes:
        retrieval_agent (RetrievalAgent): The ChromaDB vector query interface.
    """

    def __init__(self) -> None:
        self.retrieval_agent = RetrievalAgent()

    def collect_contexts(
        self, db: Session, user_id: int, question: str, top_k: int, document_id: int | None
    ) -> RAGResult:
        """
        Retrieve the most relevant text chunks for a user's question.

        Attempts ChromaDB vector similarity search first. If that returns no results
        (ChromaDB unavailable, no indexed documents, or embedding mismatch), falls back
        to fetching full document text from PostgreSQL so the LLM always has at least
        some grounding material to work with.

        Args:
            db (Session): SQLAlchemy session, used only for the PostgreSQL fallback query.
            user_id (int): Scopes ChromaDB search to this user's vector namespace.
            question (str): The user's question; it is embedded and compared against
                stored chunk vectors.
            top_k (int): Maximum number of chunks to retrieve from ChromaDB.
            document_id (int | None): If provided, restricts search to a single document's
                chunks; otherwise searches across all documents belonging to user_id.

        Returns:
            RAGResult: Contains ranked contexts, deduplicated sources, and confidence metrics.
        """
        logger.info("RAG triggered")
        contexts: list[dict] = []
        try:
            retrieved = self.retrieval_agent.retrieve_relevant_chunks(
                query=question,
                user_id=user_id,
                top_k=top_k,
                document_id=document_id,
            )
            contexts = [self._normalize_context(item) for item in retrieved]
        except Exception as exc:
            # Swallow ChromaDB errors entirely so a vector store outage does not crash
            # the request; the database fallback below will attempt recovery
            logger.warning("RAG retrieval failed for question=%s error=%s", question, exc)
            contexts = []

        used_database_fallback = False
        if not contexts:
            # ChromaDB returned nothing: read full document text from PostgreSQL to
            # ensure the LLM receives some context rather than generating a blind answer
            contexts = self._build_database_fallback_contexts(
                db=db,
                user_id=user_id,
                document_id=document_id,
                top_k=top_k,
            )
            used_database_fallback = len(contexts) > 0

        # Compute similarity statistics from retrieved chunks for confidence gating
        max_similarity = max((float(ctx.get("similarity", 0.0)) for ctx in contexts), default=0.0)
        average_similarity = (
            sum(float(ctx.get("similarity", 0.0)) for ctx in contexts) / len(contexts)
            if contexts
            else 0.0
        )
        logger.info(
            "RAG similarity max=%.3f avg=%.3f contexts=%s fallback=%s",
            max_similarity,
            average_similarity,
            len(contexts),
            used_database_fallback,
        )

        return RAGResult(
            contexts=contexts,
            sources=self.to_sources(contexts),
            max_similarity=max_similarity,
            average_similarity=average_similarity,
            used_database_fallback=used_database_fallback,
        )

    def to_sources(self, contexts: list[dict]) -> list[dict]:
        """
        Convert retrieved chunks into deduplicated source citation objects.

        Multiple chunks from the same document would otherwise produce duplicate
        entries in the API response's sources array. Deduplication is done by
        normalized document title so each source appears at most once.

        Args:
            contexts (list[dict]): Raw context dicts produced by collect_contexts.

        Returns:
            list[dict]: Deduplicated source dicts conforming to the standard source schema.
        """
        sources: list[dict] = []
        seen: set[str] = set()
        for ctx in contexts:
            title = str(ctx.get("title") or ctx.get("source") or "Document").strip()
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "type": "rag",
                    "title": title,
                    "summary": clean_summary(str(ctx.get("text") or "")),
                    "link": None,
                    "pdf_url": None,
                    "published_at": None,
                }
            )
        return sources

    def _normalize_context(self, payload: dict) -> dict:
        """
        Standardize a raw ChromaDB query result into the shared context schema.

        ChromaDB returns documents with varying metadata fields depending on how they
        were indexed. This method guarantees every context dict has the same set of
        keys before it is passed to the LLM prompt builder or source formatter.

        Args:
            payload (dict): Raw item from RetrievalAgent.retrieve_relevant_chunks,
                containing at minimum keys: text, similarity, distance, and source metadata.

        Returns:
            dict: Normalized context with guaranteed keys merged with all ChromaDB metadata.
        """
        return {
            "type": "rag",
            "source": payload.get("source", "unknown"),
            "title": payload.get("source", "unknown"),
            "summary": None,
            "link": None,
            "pdf_url": None,
            "published_at": None,
            "similarity": float(payload.get("similarity", 0.0)),
            "distance": float(payload.get("distance", 1.0)),
            # Spread remaining ChromaDB metadata fields (e.g. chunk_index, document_id, user_id)
            **payload,
        }

    def _build_database_fallback_contexts(
        self, db: Session, user_id: int, document_id: int | None, top_k: int
    ) -> list[dict]:
        """
        Build context dicts from document text stored directly in PostgreSQL.

        This fallback activates when ChromaDB is unavailable or returns no matches.
        It reads the content_text column written during document ingestion, which is
        the full extracted PDF text rather than an individual vector chunk.

        Similarity scores are set to 0.0 to signal zero vector confidence, which
        causes the orchestrator to layer web search results on top of these contexts.

        Args:
            db (Session): Active SQLAlchemy session for the documents table query.
            user_id (int): Filters to this user's document rows only.
            document_id (int | None): If provided, fetches only that document's text.
            top_k (int): Maximum number of document rows to fetch.

        Returns:
            list[dict]: Context dicts with similarity=0.0 indicating no vector match.
        """
        query = db.query(models.Document).filter(models.Document.user_id == user_id)
        if document_id is not None:
            query = query.filter(models.Document.id == document_id)

        documents = query.order_by(models.Document.created_at.desc()).limit(max(1, top_k)).all()
        contexts: list[dict] = []
        for document in documents:
            text = (document.content_text or document.content_preview or "").strip()
            if not text:
                continue
            contexts.append(
                {
                    "type": "rag",
                    "source": document.filename,
                    "title": document.filename,
                    "summary": clean_summary(text),
                    "link": None,
                    "pdf_url": None,
                    "published_at": None,
                    # Truncate to 4000 chars to stay within the LLM's context window
                    "text": text[:4000],
                    "document_id": document.id,
                    "user_id": document.user_id,
                    # Similarity is 0.0 because no vector comparison was performed;
                    # this ensures the orchestrator's confidence gate triggers web fallback
                    "similarity": 0.0,
                    "distance": 1.0,
                }
            )
        return contexts


def clean_summary(text: str, max_length: int = 280) -> str:
    """
    Normalize and truncate text for use as a source summary in the API response.

    Args:
        text (str): Raw text from a retrieved chunk or document content_text field.
        max_length (int): Maximum character length before truncation. Defaults to 280.

    Returns:
        str: Whitespace-collapsed text, truncated with an ellipsis if over max_length.
    """
    # Collapse all internal whitespace in a single pass before length-checking
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."
