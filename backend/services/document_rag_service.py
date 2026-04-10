from sqlalchemy.orm import Session

import models
from agents.retrieval_agent import RetrievalAgent


class DocumentRAGService:
    def __init__(self) -> None:
        self.retrieval_agent = RetrievalAgent()

    def search(
        self,
        db: Session,
        user_id: int,
        question: str,
        top_k: int,
        document_id: int | None,
    ) -> list[dict]:
        try:
            contexts = self.retrieval_agent.retrieve_relevant_chunks(
                query=question,
                user_id=user_id,
                top_k=top_k,
                document_id=document_id,
            )
        except Exception:
            contexts = []

        if contexts:
            return contexts
        return self._build_database_fallback_contexts(
            db=db,
            user_id=user_id,
            document_id=document_id,
            top_k=top_k,
        )

    def _build_database_fallback_contexts(
        self,
        db: Session,
        user_id: int,
        document_id: int | None,
        top_k: int,
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
                    "text": text[:4000],
                    "source": document.filename,
                    "document_id": document.id,
                    "user_id": document.user_id,
                }
            )
        return contexts
