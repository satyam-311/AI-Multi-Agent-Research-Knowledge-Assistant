import json

from sqlalchemy.orm import Session

from backend import models, schemas
from backend.agents.answer_generation_agent import AnswerGenerationAgent
from backend.services.arxiv_service import ArxivService
from backend.services.document_rag_service import DocumentRAGService
from backend.services.web_search_service import WebSearchService


class MultiSourceAssistantService:
    def __init__(self) -> None:
        self.answer_agent = AnswerGenerationAgent()
        self.document_service = DocumentRAGService()
        self.arxiv_service = ArxivService()
        self.web_search_service = WebSearchService()

    def ask_question(
        self,
        db: Session,
        user_id: int,
        question: str,
        top_k: int,
        document_id: int | None,
    ) -> tuple[str, schemas.SourceGroups, list[str]]:
        use_research, use_web, use_documents = self._detect_sources(question, document_id)

        document_contexts: list[dict] = []
        research_items: list[dict] = []
        web_items: list[dict] = []

        if use_documents:
            document_contexts = self.document_service.search(
                db=db,
                user_id=user_id,
                question=question,
                top_k=top_k,
                document_id=document_id,
            )

        if use_research:
            try:
                research_items = self.arxiv_service.search(question, max_results=3)
            except Exception:
                research_items = []

        if use_web:
            try:
                web_items = self.web_search_service.search(question, max_results=3)
            except Exception:
                web_items = []

        contexts = (
            self._document_contexts(document_contexts)
            + self._research_contexts(research_items)
            + self._web_contexts(web_items)
        )
        answer = self.answer_agent.generate_answer(question=question, contexts=contexts)
        grouped_sources = schemas.SourceGroups(
            documents=self._document_sources(document_contexts),
            research=self._research_sources(research_items),
            web=self._web_sources(web_items),
        )
        flat_sources = self._flatten_sources(grouped_sources)

        chat = models.ChatHistory(
            user_id=user_id,
            document_id=document_id,
            question=question,
            answer=answer,
            sources_json=json.dumps(flat_sources),
        )
        db.add(chat)
        db.commit()

        return answer, grouped_sources, flat_sources

    def _detect_sources(
        self, question: str, document_id: int | None
    ) -> tuple[bool, bool, bool]:
        question_lower = question.lower()
        research_keywords = ("research", "papers", "paper", "study", "studies")
        web_keywords = ("latest", "news", "trend", "trends")
        doc_keywords = (
            "document",
            "pdf",
            "uploaded",
            "this paper",
            "this document",
            "my paper",
        )

        use_research = any(keyword in question_lower for keyword in research_keywords)
        use_web = any(keyword in question_lower for keyword in web_keywords)
        wants_document_context = document_id is not None or any(
            keyword in question_lower for keyword in doc_keywords
        )
        use_documents = wants_document_context or not (use_research or use_web)

        return use_research, use_web, use_documents

    def _document_contexts(self, items: list[dict]) -> list[dict]:
        return [
            {
                "source": item.get("source", "document"),
                "text": str(item.get("text", "")).strip(),
            }
            for item in items
            if str(item.get("text", "")).strip()
        ]

    def _research_contexts(self, items: list[dict]) -> list[dict]:
        contexts: list[dict] = []
        for item in items:
            title = item.get("title", "").strip()
            summary = item.get("summary", "").strip()
            link = item.get("link")
            lines = [f"Title: {title}", f"Summary: {summary}"]
            if link:
                lines.append(f"Link: {link}")
            contexts.append({"source": title or "arXiv", "text": "\n".join(lines)})
        return contexts

    def _web_contexts(self, items: list[dict]) -> list[dict]:
        contexts: list[dict] = []
        for item in items:
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()
            link = item.get("link")
            lines = [f"Title: {title}", f"Snippet: {snippet}"]
            if link:
                lines.append(f"Link: {link}")
            contexts.append({"source": title or "Web result", "text": "\n".join(lines)})
        return contexts

    def _document_sources(self, items: list[dict]) -> list[schemas.SourceItem]:
        return [
            schemas.SourceItem(
                title=str(item.get("source", "document")),
                snippet=str(item.get("text", ""))[:240],
                link=None,
            )
            for item in items
            if str(item.get("text", "")).strip()
        ]

    def _research_sources(self, items: list[dict]) -> list[schemas.SourceItem]:
        return [
            schemas.SourceItem(
                title=item.get("title", "").strip() or "arXiv result",
                snippet=item.get("summary", "").strip()[:240],
                link=item.get("link"),
            )
            for item in items
            if item.get("title") or item.get("summary")
        ]

    def _web_sources(self, items: list[dict]) -> list[schemas.SourceItem]:
        return [
            schemas.SourceItem(
                title=item.get("title", "").strip() or "Web result",
                snippet=item.get("snippet", "").strip()[:240],
                link=item.get("link"),
            )
            for item in items
            if item.get("title") or item.get("snippet")
        ]

    def _flatten_sources(self, sources: schemas.SourceGroups) -> list[str]:
        flat: list[str] = []
        for item in sources.documents:
            flat.append(item.title)
        for item in [*sources.research, *sources.web]:
            if item.link:
                flat.append(f"{item.title} | {item.link}")
            else:
                flat.append(item.title)
        return flat
