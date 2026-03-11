import json

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend import models
from backend.agents.document_processing_agent import DocumentExtractionError
from backend.agents.embedding_agent import EmbeddingModelUnavailable


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self._document_agent = None
        self._embedding_agent = None
        self._retrieval_agent = None
        self._answer_agent = None

    @property
    def document_agent(self):
        if self._document_agent is None:
            from backend.agents.document_processing_agent import DocumentProcessingAgent

            self._document_agent = DocumentProcessingAgent()
        return self._document_agent

    @property
    def embedding_agent(self):
        if self._embedding_agent is None:
            from backend.agents.embedding_agent import EmbeddingAgent

            self._embedding_agent = EmbeddingAgent()
        return self._embedding_agent

    @property
    def retrieval_agent(self):
        if self._retrieval_agent is None:
            from backend.agents.retrieval_agent import RetrievalAgent

            self._retrieval_agent = RetrievalAgent()
        return self._retrieval_agent

    @property
    def answer_agent(self):
        if self._answer_agent is None:
            from backend.agents.answer_generation_agent import AnswerGenerationAgent

            self._answer_agent = AnswerGenerationAgent()
        return self._answer_agent

    def get_or_create_user(self, db: Session, user_id: int) -> models.User:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user is not None:
            return user

        user = models.User(
            id=user_id,
            name=f"User {user_id}",
            email=f"user{user_id}@local.dev",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    async def upload_document(
        self, db: Session, user_id: int, file: UploadFile
    ) -> tuple[models.Document, int]:
        self.get_or_create_user(db, user_id)
        try:
            raw_text = await self.document_agent.extract_text(file)
        except DocumentExtractionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid or unreadable PDF.") from exc

        if not raw_text:
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in PDF. The file may be image-only or scanned.",
            )

        chunks = self.document_agent.chunk_text(raw_text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks generated from document.")

        document = models.Document(
            user_id=user_id,
            filename=file.filename or "uploaded.pdf",
            content_preview=raw_text[:500],
            content_text=raw_text,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        try:
            agent = self.embedding_agent
            agent.index_document_chunks(
                user_id=user_id,
                document_id=document.id,
                filename=document.filename,
                chunks=chunks,
            )
        except EmbeddingModelUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail="Failed to generate embeddings for this document."
            ) from exc
        return document, len(chunks)

    def ask_question(
        self, db: Session, user_id: int, question: str, top_k: int, document_id: int | None
    ) -> tuple[str, list[str]]:
        self.get_or_create_user(db, user_id)
        selected_document_id = document_id
        selected_document = None

        if document_id is not None:
            selected_document = (
                db.query(models.Document)
                .filter(models.Document.id == document_id, models.Document.user_id == user_id)
                .first()
            )
            if selected_document is None:
                selected_document_id = None

        try:
            contexts = self.retrieval_agent.retrieve_relevant_chunks(
                query=question,
                user_id=user_id,
                top_k=top_k,
                document_id=selected_document_id,
            )
        except Exception:
            contexts = []

        if not contexts:
            contexts = self._build_database_fallback_contexts(
                db=db,
                user_id=user_id,
                document_id=selected_document_id,
                top_k=top_k,
            )

        answer = self.answer_agent.generate_answer(question=question, contexts=contexts)
        sources = [ctx.get("source", "unknown") for ctx in contexts]

        chat = models.ChatHistory(
            user_id=user_id,
            document_id=selected_document_id,
            question=question,
            answer=answer,
            sources_json=json.dumps(sources),
        )
        db.add(chat)
        db.commit()

        return answer, sources

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
                    "text": text[:4000],
                    "source": document.filename,
                    "document_id": document.id,
                    "user_id": document.user_id,
                }
            )
        return contexts

    def delete_document(self, db: Session, user_id: int, document_id: int) -> None:
        document = (
            db.query(models.Document)
            .filter(models.Document.id == document_id, models.Document.user_id == user_id)
            .first()
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found for this user.")

        (
            db.query(models.ChatHistory)
            .filter(
                models.ChatHistory.document_id == document_id,
                models.ChatHistory.user_id == user_id,
            )
            .delete(synchronize_session=False)
        )
        db.delete(document)
        db.commit()

        try:
            self.embedding_agent.delete_document_chunks(user_id=user_id, document_id=document_id)
        except Exception:
            pass
