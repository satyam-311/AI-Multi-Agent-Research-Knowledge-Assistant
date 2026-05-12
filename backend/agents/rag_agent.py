from __future__ import annotations

from dataclasses import dataclass
import logging

from sqlalchemy.orm import Session

from backend import models
from backend.agents.retrieval_agent import RetrievalAgent


logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    contexts: list[dict]
    sources: list[dict]
    max_similarity: float
    average_similarity: float
    used_database_fallback: bool

    @property
    def is_empty(self) -> bool:
        return len(self.contexts) == 0

    @property
    def is_low_confidence(self) -> bool:
        return self.max_similarity < 0.5


class RAGAgent:
    def __init__(self) -> None:
        self.retrieval_agent = RetrievalAgent()

    def collect_contexts(
        self, db: Session, user_id: int, question: str, top_k: int, document_id: int | None
    ) -> RAGResult:
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
            logger.warning("RAG retrieval failed for question=%s error=%s", question, exc)
            contexts = []

        used_database_fallback = False
        if not contexts:
            contexts = self._build_database_fallback_contexts(
                db=db,
                user_id=user_id,
                document_id=document_id,
                top_k=top_k,
            )
            used_database_fallback = len(contexts) > 0

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
            **payload,
        }

    def _build_database_fallback_contexts(
        self, db: Session, user_id: int, document_id: int | None, top_k: int
    ) -> list[dict]:
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
                    "text": text[:4000],
                    "document_id": document.id,
                    "user_id": document.user_id,
                    "similarity": 0.0,
                    "distance": 1.0,
                }
            )
        return contexts


def clean_summary(text: str, max_length: int = 280) -> str:
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."
