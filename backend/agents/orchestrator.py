import asyncio
import json
import re
from io import BytesIO
from urllib.parse import quote_plus

import httpx
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from sqlalchemy.orm import Session

import models
from config import get_settings
from agents.document_processing_agent import DocumentExtractionError
from agents.embedding_agent import EmbeddingModelUnavailable
from mcp_client import get_tools


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._document_agent = None
        self._embedding_agent = None
        self._retrieval_agent = None
        self._answer_agent = None
        self._recent_external_contexts: dict[int, list[dict]] = {}

    @property
    def document_agent(self):
        if self._document_agent is None:
            from agents.document_processing_agent import DocumentProcessingAgent

            self._document_agent = DocumentProcessingAgent()
        return self._document_agent

    @property
    def embedding_agent(self):
        if self._embedding_agent is None:
            from agents.embedding_agent import EmbeddingAgent

            self._embedding_agent = EmbeddingAgent()
        return self._embedding_agent

    @property
    def retrieval_agent(self):
        if self._retrieval_agent is None:
            from agents.retrieval_agent import RetrievalAgent

            self._retrieval_agent = RetrievalAgent()
        return self._retrieval_agent

    @property
    def answer_agent(self):
        if self._answer_agent is None:
            from agents.answer_generation_agent import AnswerGenerationAgent

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

    def create_processing_document(
        self, db: Session, user_id: int, filename: str
    ) -> models.Document:
        self.get_or_create_user(db, user_id)
        document = models.Document(
            user_id=user_id,
            filename=filename or "uploaded.pdf",
            content_preview="Processing document...",
            content_text="",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    async def process_uploaded_document_bytes(
        self,
        db: Session,
        user_id: int,
        document_id: int,
        filename: str,
        content_type: str | None,
        file_bytes: bytes,
    ) -> int:
        document = (
            db.query(models.Document)
            .filter(models.Document.id == document_id, models.Document.user_id == user_id)
            .first()
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found for processing.")

        upload = UploadFile(
            file=BytesIO(file_bytes),
            filename=filename,
            headers=Headers({"content-type": content_type or "application/pdf"}),
        )
        raw_text = await self.document_agent.extract_text(upload)
        if not raw_text:
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in PDF. The file may be image-only or scanned.",
            )

        chunks = self.document_agent.chunk_text(raw_text)
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks generated from document.")

        document.filename = filename or document.filename
        document.content_preview = raw_text[:500]
        document.content_text = raw_text
        db.add(document)
        db.commit()
        db.refresh(document)

        agent = self.embedding_agent
        agent.index_document_chunks(
            user_id=user_id,
            document_id=document.id,
            filename=document.filename,
            chunks=chunks,
        )
        return len(chunks)

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

        pdf_contexts = self._load_pdf_contexts(
            db=db,
            user_id=user_id,
            question=question,
            top_k=top_k,
            document_id=selected_document_id,
        )
        if self._should_prefer_external_research(question):
            pdf_contexts = []
        arxiv_contexts = (
            self._load_arxiv_contexts(question=question, top_k=top_k, pdf_contexts=pdf_contexts)
            if self._should_use_arxiv(question)
            else []
        )
        web_contexts = (
            self._load_web_contexts(question=question, top_k=top_k)
            if self._should_fetch_web_resources(question)
            else []
        )
        recent_contexts = (
            self._recent_external_contexts.get(user_id, [])
            if self._should_reuse_external_contexts(question)
            else []
        )
        history_link_contexts = (
            self._load_recent_link_contexts_from_history(db=db, user_id=user_id)
            if self._is_link_request(question)
            else []
        )
        if self._should_reuse_external_contexts(question):
            recent_contexts = self._prioritize_link_contexts(recent_contexts)
            contexts = recent_contexts + history_link_contexts + pdf_contexts + arxiv_contexts + web_contexts
        else:
            contexts = pdf_contexts + arxiv_contexts + web_contexts + recent_contexts + history_link_contexts
        contexts = self._deduplicate_contexts(contexts)
        contexts = self._rank_contexts(question, contexts)
        contexts = self._trim_contexts(contexts)

        if arxiv_contexts or web_contexts:
            self._recent_external_contexts[user_id] = self._deduplicate_contexts(
                arxiv_contexts + web_contexts
            )

        direct_link_answer = self._build_direct_link_answer(
            question,
            recent_contexts + history_link_contexts,
            contexts,
        )
        if direct_link_answer is not None:
            answer = direct_link_answer
        else:
            answer = self.answer_agent.generate_answer(question=question, contexts=contexts)
        sources = self._build_sources(contexts)

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

    def _should_use_arxiv(self, question: str) -> bool:
        if not self.settings.enable_mcp:
            return False
        question_lower = question.lower()
        return any(
            token in question_lower
            for token in ("paper", "papers", "research", "arxiv", "latest", "study", "studies")
        )

    def _should_fetch_web_resources(self, question: str) -> bool:
        question_lower = question.lower()
        trigger_phrases = (
            "recommend",
            "relevant topic",
            "relevant topics",
            "detailed explanation",
            "detail explanation",
            "content about",
            "learn more",
            "resource",
            "resources",
            "tutorial",
            "tutorials",
            "video",
            "videos",
            "youtube",
            "explaination",
            "explanation",
            "where can i study",
            "suggest content",
            "suggest resources",
            "suggest tutorials",
            "suggest videos",
        )
        return any(phrase in question_lower for phrase in trigger_phrases)

    def _should_prefer_external_research(self, question: str) -> bool:
        question_lower = question.lower()
        if self._is_document_grounded_query(question):
            return False
        return any(
            phrase in question_lower
            for phrase in (
                "research in",
                "research about",
                "research on",
                "papers on",
                "papers about",
                "papers in",
                "studies in",
                "latest research in",
                "latest papers on",
                "domain",
            )
        )

    def _is_document_grounded_query(self, question: str) -> bool:
        question_lower = question.lower()
        return any(
            phrase in question_lower
            for phrase in (
                "this paper",
                "this pdf",
                "this document",
                "uploaded document",
                "uploaded pdf",
                "above paper",
                "above research",
                "above topic",
                "above topics",
                "my paper",
                "my pdf",
                "in this",
            )
        )

    def _should_reuse_external_contexts(self, question: str) -> bool:
        question_lower = question.lower()
        follow_up_phrases = (
            "provide me the link",
            "give me the link",
            "send the link",
            "share the link",
            "url",
            "links",
            "paper link",
            "research link",
            "those papers",
            "above research",
            "above paper",
        )
        return any(phrase in question_lower for phrase in follow_up_phrases)

    def _is_link_request(self, question: str) -> bool:
        question_lower = question.lower()
        return any(
            phrase in question_lower
            for phrase in (
                "provide me the link",
                "give me the link",
                "send the link",
                "share the link",
                "paper link",
                "research link",
                "links of above research",
                "links of above paper",
                "url",
                "urls",
            )
        )

    def _load_pdf_contexts(
        self, db: Session, user_id: int, question: str, top_k: int, document_id: int | None
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

    def _load_arxiv_contexts(self, question: str, top_k: int, pdf_contexts: list[dict]) -> list[dict]:
        try:
            from anyio import from_thread

            return from_thread.run(self._fetch_arxiv_contexts, question, top_k, pdf_contexts)
        except RuntimeError:
            return asyncio.run(self._fetch_arxiv_contexts(question, top_k, pdf_contexts))
        except Exception:
            return []

    def _load_web_contexts(self, question: str, top_k: int) -> list[dict]:
        try:
            from anyio import from_thread

            contexts = from_thread.run(self._fetch_web_contexts, question, top_k)
        except RuntimeError:
            contexts = asyncio.run(self._fetch_web_contexts(question, top_k))
        except Exception:
            contexts = []
        if contexts:
            return contexts
        return [{"text": self._build_resource_suggestions(question), "source": "Suggested Resources"}]

    async def _fetch_arxiv_contexts(
        self, question: str, top_k: int, pdf_contexts: list[dict]
    ) -> list[dict]:
        try:
            tools = await get_tools()
            search_tool = next(
                (tool for tool in tools if getattr(tool, "name", "") == "search_papers"),
                None,
            )
            if search_tool is None:
                return []

            result = await search_tool.ainvoke(
                {
                    "query": self._build_arxiv_query(question, pdf_contexts),
                    "max_results": max(1, min(top_k, 3)),
                }
            )
            return self._rank_contexts(
                question,
                self._normalize_arxiv_contexts(result),
            )[:3]
        except Exception:
            return []

    async def _fetch_web_contexts(self, question: str, top_k: int) -> list[dict]:
        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                follow_redirects=True,
                trust_env=False,
            ) as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": question,
                        "format": "json",
                        "no_html": "1",
                        "no_redirect": "1",
                        "skip_disambig": "1",
                    },
                )
                response.raise_for_status()
                payload = response.json()
            return self._normalize_web_contexts(question=question, payload=payload, top_k=top_k)
        except Exception:
            return []

    def _normalize_arxiv_contexts(self, result) -> list[dict]:
        if not result:
            return []

        if isinstance(result, str):
            text = result.strip()
            return [{"text": text, "source": "arXiv MCP"}] if text else []

        if isinstance(result, dict):
            if "text" in result and isinstance(result["text"], str):
                parsed = self._parse_arxiv_payload(result["text"])
                if parsed is not None:
                    return self._normalize_arxiv_contexts(parsed)
            for key in ("papers", "results", "items", "data"):
                value = result.get(key)
                if isinstance(value, list):
                    return self._normalize_arxiv_contexts(value)
            return [{"text": json.dumps(result, ensure_ascii=True), "source": "arXiv MCP"}]

        if isinstance(result, list):
            contexts: list[dict] = []
            for item in result:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        contexts.append({"text": text, "source": "arXiv MCP"})
                    continue

                if isinstance(item, dict) and "text" in item and isinstance(item["text"], str):
                    parsed = self._parse_arxiv_payload(item["text"])
                    if parsed is not None:
                        contexts.extend(self._normalize_arxiv_contexts(parsed))
                        continue

                if not isinstance(item, dict):
                    contexts.append(
                        {"text": json.dumps(item, ensure_ascii=True), "source": "arXiv MCP"}
                    )
                    continue

                title = str(item.get("title", "")).strip()
                summary = str(item.get("summary") or item.get("abstract") or "").strip()
                authors = item.get("authors")
                published = str(item.get("published", "")).strip()
                url = str(item.get("url") or item.get("pdf_url") or item.get("entry_id") or "").strip()

                lines = []
                if title:
                    lines.append(f"Title: {title}")
                if authors:
                    if isinstance(authors, list):
                        lines.append("Authors: " + ", ".join(str(author) for author in authors))
                    else:
                        lines.append(f"Authors: {authors}")
                if published:
                    lines.append(f"Published: {published}")
                if summary:
                    lines.append(f"Summary: {summary}")
                if url:
                    lines.append(f"URL: {url}")

                text = "\n".join(lines).strip() or json.dumps(item, ensure_ascii=True)
                contexts.append({"text": text, "source": title or "arXiv MCP", "url": url})
            return contexts

        return [{"text": json.dumps(result, ensure_ascii=True), "source": "arXiv MCP"}]

    def _parse_arxiv_payload(self, value: str):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None

    def _build_arxiv_query(self, question: str, pdf_contexts: list[dict]) -> str:
        cleaned_question = re.sub(
            r"\b(suggest|recommend|provide|give|me|some|other|research|papers|paper|related|latest|study|studies|link|links|about|this|that|it|can|you|please)\b",
            " ",
            question.lower(),
        )
        cleaned_question = re.sub(r"\s+", " ", cleaned_question).strip()

        topic_hints = self._extract_topic_hints(pdf_contexts) if self._is_document_grounded_query(question) else ""
        query_parts = [part for part in [cleaned_question, topic_hints] if part]
        if not query_parts:
            return question
        return " ".join(query_parts[:2]).strip()

    def _extract_topic_hints(self, pdf_contexts: list[dict]) -> str:
        if not pdf_contexts:
            return ""

        combined_text = " ".join(str(item.get("text", "")) for item in pdf_contexts[:2])
        combined_text_lower = combined_text.lower()
        hints: list[str] = []
        known_phrases = (
            "retrieval augmented generation",
            "rag",
            "multi-agent",
            "research assistant",
            "hallucination",
            "contextual fragmentation",
            "knowledge graph",
            "multimodal",
            "marka",
            "transformer",
        )
        for phrase in known_phrases:
            if phrase in combined_text_lower:
                hints.append(phrase)

        acronyms = re.findall(r"\b[A-Z][A-Z0-9-]{2,}\b", combined_text)
        for acronym in acronyms:
            lowered = acronym.lower()
            if lowered not in hints:
                hints.append(lowered)

        return " ".join(hints[:4])

    def _normalize_web_contexts(self, question: str, payload: dict, top_k: int) -> list[dict]:
        contexts: list[dict] = []

        abstract = str(payload.get("AbstractText", "")).strip()
        abstract_url = str(payload.get("AbstractURL", "")).strip()
        heading = str(payload.get("Heading", "")).strip()
        if abstract:
            lines = []
            if heading:
                lines.append(f"Topic: {heading}")
            lines.append(f"Summary: {abstract}")
            if abstract_url:
                lines.append(f"Reference: {abstract_url}")
            contexts.append({"text": "\n".join(lines), "source": "DuckDuckGo Summary"})

        related_items = self._extract_related_topics(payload.get("RelatedTopics", []))
        for item in related_items[: max(1, top_k)]:
            text = str(item.get("Text", "")).strip()
            url = str(item.get("FirstURL", "")).strip()
            if not text:
                continue
            lines = [f"Related topic: {text}"]
            if url:
                lines.append(f"Link: {url}")
            contexts.append({"text": "\n".join(lines), "source": "DuckDuckGo Related"})
            if url:
                contexts[-1]["url"] = url

        contexts.append(
            {
                "text": self._build_resource_suggestions(question),
                "source": "Suggested Resources",
            }
        )
        return self._rank_contexts(question, contexts)[: max(1, min(top_k + 1, 4))]

    def _extract_related_topics(self, items) -> list[dict]:
        results: list[dict] = []
        if not isinstance(items, list):
            return results

        for item in items:
            if not isinstance(item, dict):
                continue
            if "Topics" in item:
                results.extend(self._extract_related_topics(item.get("Topics", [])))
                continue
            results.append(item)
        return results

    def _build_resource_suggestions(self, question: str) -> str:
        encoded = quote_plus(question)
        return "\n".join(
            [
                "Suggested external resources for deeper explanation:",
                f"YouTube search: https://www.youtube.com/results?search_query={encoded}",
                f"DuckDuckGo search: https://duckduckgo.com/?q={encoded}",
                f"Google Scholar search: https://scholar.google.com/scholar?q={encoded}",
                f"GitHub search: https://github.com/search?q={encoded}&type=repositories",
                f"arXiv search: https://arxiv.org/search/?query={encoded}&searchtype=all",
            ]
        )

    def _rank_contexts(self, question: str, contexts: list[dict]) -> list[dict]:
        if not contexts:
            return []

        query_tokens = self._tokenize(self._build_relevance_query(question, contexts))
        if not query_tokens:
            return contexts

        ranked = sorted(
            contexts,
            key=lambda context: self._context_score(context, query_tokens),
            reverse=True,
        )
        return ranked

    def _build_relevance_query(self, question: str, contexts: list[dict]) -> str:
        topic_hints = self._extract_topic_hints(contexts)
        parts = [question.lower().strip(), topic_hints.strip()]
        return " ".join(part for part in parts if part)

    def _context_score(self, context: dict, query_tokens: set[str]) -> tuple[int, int]:
        haystack = " ".join(
            [
                str(context.get("source", "")),
                str(context.get("text", "")),
                str(context.get("url", "")),
            ]
        ).lower()
        haystack_tokens = self._tokenize(haystack)
        overlap = len(query_tokens & haystack_tokens)
        has_url = 1 if str(context.get("url", "")).startswith(("http://", "https://")) else 0
        return (overlap + has_url, len(str(context.get("text", ""))))

    def _tokenize(self, value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9][a-z0-9-]{1,}", value.lower())
            if token not in {
                "this",
                "that",
                "with",
                "from",
                "have",
                "your",
                "about",
                "give",
                "some",
                "more",
                "into",
                "paper",
                "papers",
                "research",
            }
        }

    def _trim_contexts(self, contexts: list[dict]) -> list[dict]:
        trimmed: list[dict] = []
        total_chars = 0
        max_contexts = 6
        max_total_chars = 9000

        for context in contexts:
            if len(trimmed) >= max_contexts:
                break

            trimmed_context = dict(context)
            text = str(trimmed_context.get("text", "")).strip()
            if not text:
                continue

            max_text_chars = 1800 if str(trimmed_context.get("source", "")).endswith(".pdf") else 900
            trimmed_context["text"] = text[:max_text_chars]
            context_chars = len(trimmed_context["text"])
            if total_chars + context_chars > max_total_chars and trimmed:
                break

            total_chars += context_chars
            trimmed.append(trimmed_context)

        return trimmed or contexts[:2]

    def _deduplicate_contexts(self, contexts: list[dict]) -> list[dict]:
        deduplicated: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for context in contexts:
            text = str(context.get("text", "")).strip()
            source = str(context.get("source", "")).strip()
            key = (source, text)
            if not text or key in seen:
                continue
            seen.add(key)
            deduplicated.append(context)
        return deduplicated

    def _prioritize_link_contexts(self, contexts: list[dict]) -> list[dict]:
        linked_contexts = [
            context
            for context in contexts
            if any(
                marker in str(context.get("text", ""))
                for marker in ("URL:", "Link:", "YouTube search:", "DuckDuckGo search:")
            )
        ]
        if linked_contexts:
            return self._rank_contexts("links urls papers research", linked_contexts)
        return contexts

    def _build_direct_link_answer(
        self, question: str, recent_contexts: list[dict], contexts: list[dict]
    ) -> str | None:
        if not self._is_link_request(question):
            return None

        link_items = self._collect_link_items(recent_contexts or contexts)
        if not link_items:
            return None

        top_items = link_items[:5]
        lines = ["Relevant links:"]
        for item in top_items:
            label = item["label"]
            url = item["url"]
            lines.append(f"- {label}: {url}")
        return "\n".join(lines)

    def _collect_link_items(self, contexts: list[dict]) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()

        for context in contexts:
            source = str(context.get("source", "")).strip() or "Reference"
            url = str(context.get("url", "")).strip()
            if url.startswith(("http://", "https://")) and url not in seen:
                seen.add(url)
                items.append({"label": source, "url": url})

            if source == "Suggested Resources":
                for link_source in self._extract_link_sources_from_text(str(context.get("text", ""))):
                    entry = self._parse_source_entry(link_source)
                    if entry is None:
                        continue
                    if entry["url"] in seen:
                        continue
                    seen.add(entry["url"])
                    items.append(entry)
        return items

    def _load_recent_link_contexts_from_history(self, db: Session, user_id: int) -> list[dict]:
        history_rows = (
            db.query(models.ChatHistory)
            .filter(models.ChatHistory.user_id == user_id)
            .order_by(models.ChatHistory.created_at.desc())
            .limit(5)
            .all()
        )

        contexts: list[dict] = []
        for row in history_rows:
            try:
                sources = json.loads(row.sources_json or "[]")
            except json.JSONDecodeError:
                continue

            if not isinstance(sources, list):
                continue

            for source in sources:
                if not isinstance(source, str):
                    continue
                entry = self._parse_source_entry(source)
                if entry is None:
                    continue
                contexts.append(
                    {
                        "text": f"Link: {entry['url']}",
                        "source": entry["label"],
                        "url": entry["url"],
                    }
                )

        return self._deduplicate_contexts(contexts)

    def _build_sources(self, contexts: list[dict]) -> list[str]:
        sources: list[str] = []
        for context in contexts:
            source = str(context.get("source", "unknown")).strip() or "unknown"
            url = str(context.get("url", "")).strip()
            if url.startswith("http://") or url.startswith("https://"):
                sources.append(f"{source} | {url}")
                continue

            if source == "Suggested Resources":
                sources.extend(self._extract_link_sources_from_text(str(context.get("text", ""))))
                continue

            sources.append(source)
        return sources

    def _extract_link_sources_from_text(self, text: str) -> list[str]:
        sources: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if ": " not in line:
                continue
            label, value = line.split(": ", 1)
            value = value.strip()
            if value.startswith("http://") or value.startswith("https://"):
                sources.append(f"{label} | {value}")
        return sources

    def _parse_source_entry(self, value: str) -> dict | None:
        if " | " not in value:
            return None
        label, url = value.split(" | ", 1)
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return None
        return {"label": label.strip() or url, "url": url}

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
