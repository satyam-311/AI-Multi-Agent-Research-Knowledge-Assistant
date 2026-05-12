from __future__ import annotations

import asyncio
import json
import logging

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend import models
from backend.agents.arxiv_agent import ArxivAPIError, ArxivAgent
from backend.agents.ddg_agent import DDGAgent
from backend.agents.document_processing_agent import DocumentExtractionError
from backend.agents.embedding_agent import EmbeddingModelUnavailable
from backend.agents.rag_agent import RAGAgent, RAGResult
from backend.services.source_utils import normalize_source_items


logger = logging.getLogger(__name__)

UNCERTAIN_ANSWER_MARKERS = (
    "i could not find",
    "i don't know",
    "i do not know",
    "not enough context",
    "context is incomplete",
    "missing from the provided context",
)


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self._document_agent = None
        self._embedding_agent = None
        self._rag_agent = None
        self._answer_agent = None
        self._arxiv_agent = None
        self._ddg_agent = None

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
    def rag_agent(self):
        if self._rag_agent is None:
            self._rag_agent = RAGAgent()
        return self._rag_agent

    @property
    def answer_agent(self):
        if self._answer_agent is None:
            from backend.agents.answer_generation_agent import AnswerGenerationAgent

            self._answer_agent = AnswerGenerationAgent()
        return self._answer_agent

    @property
    def arxiv_agent(self):
        if self._arxiv_agent is None:
            self._arxiv_agent = ArxivAgent()
        return self._arxiv_agent

    @property
    def ddg_agent(self):
        if self._ddg_agent is None:
            self._ddg_agent = DDGAgent()
        return self._ddg_agent

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
            self.embedding_agent.index_document_chunks(
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
    ) -> tuple[str, dict[str, list[dict]]]:
        self.get_or_create_user(db, user_id)
        print("Query:", question)
        print("Is research query:", is_research_query(question))

        selected_document_id = self._resolve_document_id(db, user_id, document_id)
        if is_research_query(question):
            print("Calling ArXiv agent...")
            grouped_sources = {"rag": [], "arxiv": [], "ddg": []}
            arxiv_papers = asyncio.run(self._safe_arxiv_search(question))
            print("Number of papers:", len(arxiv_papers))

            if arxiv_papers:
                grouped_sources["arxiv"] = normalize_source_items(
                    self.arxiv_agent.build_payload(arxiv_papers[:5])["results"]
                )
                flat_sources = normalize_source_items(grouped_sources["arxiv"])
                answer = self.arxiv_agent.build_answer(arxiv_papers[:5])
            else:
                ddg_results = asyncio.run(self._safe_ddg_search(question))
                grouped_sources["ddg"] = normalize_source_items(
                    self.ddg_agent.build_payload(ddg_results[:5])["results"] if ddg_results else []
                )
                flat_sources = normalize_source_items(grouped_sources["ddg"])
                answer = self._build_ddg_fallback_answer(ddg_results[:5] if ddg_results else [])

            chat = models.ChatHistory(
                user_id=user_id,
                document_id=None,
                question=question,
                answer=answer,
                sources_json=json.dumps(flat_sources),
            )
            db.add(chat)
            db.commit()
            return answer, grouped_sources

        rag_result = self.rag_agent.collect_contexts(
            db=db,
            user_id=user_id,
            question=question,
            top_k=top_k,
            document_id=selected_document_id,
        )

        rag_answer = ""
        use_fallback = self._should_use_fallback(rag_result)
        if not use_fallback and rag_result.contexts:
            rag_answer = self.answer_agent.generate_answer(question=question, contexts=rag_result.contexts)
            if self._is_uncertain_answer(rag_answer):
                logger.info("RAG answer uncertain, forcing fallback")
                use_fallback = True

        merged_contexts = list(rag_result.contexts)
        grouped_sources: dict[str, list[dict]] = {
            "rag": normalize_source_items(rag_result.sources),
            "arxiv": [],
            "ddg": [],
        }

        if use_fallback:
            logger.info("Fallback to DDG for question=%s", question)
            ddg_contexts, ddg_sources = asyncio.run(self._run_ddg_fallback(question))
            merged_contexts.extend(ddg_contexts)
            grouped_sources["ddg"] = ddg_sources

        flat_sources = normalize_source_items(
            [*grouped_sources["rag"], *grouped_sources["arxiv"], *grouped_sources["ddg"]]
        )

        if merged_contexts:
            answer = (
                self.answer_agent.generate_answer(question=question, contexts=merged_contexts)
                if use_fallback or not rag_answer
                else rag_answer
            )
        else:
            answer = (
                "I could not find enough evidence in the uploaded PDFs, ArXiv, or web search "
                "to answer this question reliably."
            )

        logger.info(
            "Question answered question=%s rag_contexts=%s arxiv_sources=%s ddg_sources=%s fallback=%s",
            question,
            len(rag_result.contexts),
            len(grouped_sources["arxiv"]),
            len(grouped_sources["ddg"]),
            use_fallback,
        )

        chat = models.ChatHistory(
            user_id=user_id,
            document_id=selected_document_id,
            question=question,
            answer=answer,
            sources_json=json.dumps(flat_sources),
        )
        db.add(chat)
        db.commit()

        return answer, grouped_sources

    async def _run_ddg_fallback(self, question: str) -> tuple[list[dict], list[dict]]:
        ddg_results = await self._safe_ddg_search(question)
        if not ddg_results:
            return [], []

        contexts = self.ddg_agent.build_contexts(ddg_results)
        sources = normalize_source_items(self.ddg_agent.build_payload(ddg_results)["results"])
        return contexts, sources

    async def _safe_arxiv_search(self, question: str):
        try:
            return await self.arxiv_agent.search_papers_async(question, max_results=5)
        except ArxivAPIError as exc:
            logger.warning("ArXiv unavailable question=%s error=%s", question, exc)
            return []
        except Exception:
            logger.exception("Unexpected ArXiv failure question=%s", question)
            return []

    async def _safe_ddg_search(self, question: str):
        try:
            return await self.ddg_agent.search_async(question, max_results=5)
        except Exception:
            logger.exception("DDG unavailable question=%s", question)
            return []

    def _should_use_fallback(self, rag_result: RAGResult) -> bool:
        if rag_result.is_empty:
            logger.info("Fallback reason: RAG empty")
            return True
        if rag_result.is_low_confidence:
            logger.info(
                "Fallback reason: low similarity max=%.3f avg=%.3f",
                rag_result.max_similarity,
                rag_result.average_similarity,
            )
            return True
        return False

    def _is_uncertain_answer(self, answer: str) -> bool:
        normalized = " ".join(answer.lower().split())
        return any(marker in normalized for marker in UNCERTAIN_ANSWER_MARKERS)

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

    def _resolve_document_id(
        self, db: Session, user_id: int, document_id: int | None
    ) -> int | None:
        if document_id is None:
            return None

        selected_document = (
            db.query(models.Document)
            .filter(models.Document.id == document_id, models.Document.user_id == user_id)
            .first()
        )
        if selected_document is None:
            return None
        return document_id

    def _build_ddg_fallback_answer(self, results: list) -> str:
        if not results:
            return (
                "I could not find ArXiv papers or useful web results for this research query."
            )

        lines: list[str] = []
        for result in results[:5]:
            lines.append(f"Title: {result.title}")
            lines.append(f"Summary: {result.snippet}")
            lines.append(f"Link: {result.link}")
            lines.append("")
        return "\n".join(lines).strip()


def is_research_query(query: str) -> bool:
    keywords = [
        "research paper",
        "research on",
        "papers on",
        "arxiv",
        "latest research",
        "survey paper",
        "study on",
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in keywords)
