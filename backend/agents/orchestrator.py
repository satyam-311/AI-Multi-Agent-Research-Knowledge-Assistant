# orchestrator.py
# Central coordination layer for the MARKA multi-agent system.
# Owns the adaptive routing logic that decides which combination of agents
# (RAG, ArXiv, web search) handles each user query, and drives every
# document ingestion and deletion workflow.

from __future__ import annotations

# Standard library: async execution bridge, JSON serialization, structured logging
import asyncio
import json
import logging

# FastAPI types for HTTP error propagation and multipart file upload handling
from fastapi import HTTPException, UploadFile
# SQLAlchemy session for all PostgreSQL read/write operations in this module
from sqlalchemy.orm import Session

# ORM models representing the PostgreSQL schema (users, documents, chat_history)
from backend import models
# Domain-specific agent imports for each retrieval and generation path
from backend.agents.arxiv_agent import ArxivAPIError, ArxivAgent
from backend.agents.ddg_agent import DDGAgent
from backend.agents.document_processing_agent import DocumentExtractionError
from backend.agents.embedding_agent import EmbeddingModelUnavailable
from backend.agents.rag_agent import RAGAgent, RAGResult
# Utility that normalizes heterogeneous source dicts into a consistent API schema
from backend.services.source_utils import normalize_source_items


logger = logging.getLogger(__name__)

# Phrases that signal the LLM could not produce a supported answer from the
# retrieved context. When detected, the orchestrator triggers a web search fallback
# before returning the response to the user.
UNCERTAIN_ANSWER_MARKERS = (
    "i could not find",
    "i don't know",
    "i do not know",
    "not enough context",
    "context is incomplete",
    "missing from the provided context",
)


class MultiAgentOrchestrator:
    """
    Central coordinator for the MARKA multi-agent RAG pipeline.

    Orchestrates six specialized agents: DocumentProcessingAgent, EmbeddingAgent,
    RAGAgent, AnswerGenerationAgent, ArxivAgent, and DDGAgent. Implements adaptive
    routing that selects the appropriate retrieval path based on query intent and
    confidence scoring, following a LangGraph-style conditional workflow.

    All agents are instantiated lazily on first property access to avoid loading
    heavyweight models (sentence-transformers, LLM clients) at application startup.

    Attributes:
        _document_agent: Handles PDF text extraction and chunking.
        _embedding_agent: Encodes text chunks into vectors and indexes them in ChromaDB.
        _rag_agent: Performs ChromaDB vector search and returns confidence-scored results.
        _answer_agent: Calls the configured LLM (Groq or Ollama) to synthesize answers.
        _arxiv_agent: Queries the ArXiv API for academic papers with caching and rate limiting.
        _ddg_agent: Queries the Tavily API for live web results with retry logic.
    """

    def __init__(self) -> None:
        # Initialize all agent slots to None; each is created only when first accessed
        self._document_agent = None
        self._embedding_agent = None
        self._rag_agent = None
        self._answer_agent = None
        self._arxiv_agent = None
        self._ddg_agent = None

    @property
    def document_agent(self):
        """
        Lazy-load the DocumentProcessingAgent on first access.

        Returns:
            DocumentProcessingAgent: Singleton instance for this orchestrator lifecycle.
        """
        if self._document_agent is None:
            from backend.agents.document_processing_agent import DocumentProcessingAgent

            self._document_agent = DocumentProcessingAgent()
        return self._document_agent

    @property
    def embedding_agent(self):
        """
        Lazy-load the EmbeddingAgent on first access.

        The sentence-transformer model download and ChromaDB client initialization
        happen here, not at startup, so the server is available immediately.

        Returns:
            EmbeddingAgent: Singleton instance for this orchestrator lifecycle.
        """
        if self._embedding_agent is None:
            from backend.agents.embedding_agent import EmbeddingAgent

            self._embedding_agent = EmbeddingAgent()
        return self._embedding_agent

    @property
    def rag_agent(self):
        """
        Lazy-load the RAGAgent on first access.

        Returns:
            RAGAgent: Singleton wrapping the RetrievalAgent and confidence scoring logic.
        """
        if self._rag_agent is None:
            self._rag_agent = RAGAgent()
        return self._rag_agent

    @property
    def answer_agent(self):
        """
        Lazy-load the AnswerGenerationAgent on first access.

        Returns:
            AnswerGenerationAgent: Singleton that holds the Groq or Ollama LLM client.
        """
        if self._answer_agent is None:
            from backend.agents.answer_generation_agent import AnswerGenerationAgent

            self._answer_agent = AnswerGenerationAgent()
        return self._answer_agent

    @property
    def arxiv_agent(self):
        """
        Lazy-load the ArxivAgent on first access.

        Returns:
            ArxivAgent: Singleton with its own thread-safe rate limiter and TTL cache.
        """
        if self._arxiv_agent is None:
            self._arxiv_agent = ArxivAgent()
        return self._arxiv_agent

    @property
    def ddg_agent(self):
        """
        Lazy-load the DDGAgent (Tavily web search) on first access.

        Returns:
            DDGAgent: Singleton with its own thread-safe rate limiter.
        """
        if self._ddg_agent is None:
            self._ddg_agent = DDGAgent()
        return self._ddg_agent

    def get_or_create_user(self, db: Session, user_id: int) -> models.User:
        """
        Fetch a user from PostgreSQL, or create a placeholder row if none exists.

        This guard satisfies the foreign key constraint on the documents and
        chat_history tables. In the normal auth flow the user is always pre-created
        by AuthService; this handles edge cases where a numeric user_id arrives
        without a prior registration step (e.g. development testing).

        Args:
            db (Session): Active SQLAlchemy session bound to the PostgreSQL connection.
            user_id (int): The user identifier extracted from the verified JWT payload.

        Returns:
            models.User: The existing or newly created User ORM instance.
        """
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user is not None:
            return user

        # Create a minimal placeholder to satisfy FK constraints on downstream tables
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
        """
        Ingest a PDF document into the MARKA knowledge base for a specific user.

        Executes a sequential four-stage pipeline:
        1. Text extraction (pypdf with OCR fallback via Tesseract).
        2. Chunking with RecursiveCharacterTextSplitter (chunk_size=900, overlap=150).
        3. PostgreSQL record creation to obtain a valid document_id.
        4. Sentence-transformer embedding and ChromaDB indexing namespaced by
           (user_id, document_id).

        Each stage raises a distinct HTTP error so the frontend can surface a
        meaningful failure message to the user.

        Args:
            db (Session): Active SQLAlchemy session for PostgreSQL write operations.
            user_id (int): Owner of the document; used to namespace ChromaDB vectors.
            file (UploadFile): Multipart PDF upload received from the FastAPI route handler.

        Returns:
            tuple[models.Document, int]: The persisted Document ORM record and the
            number of vector chunks successfully indexed in ChromaDB.

        Raises:
            HTTPException 400: PDF cannot be parsed, is empty, or yields no extractable text.
            HTTPException 503: Sentence-transformer embedding model is unavailable.
            HTTPException 500: Vector indexing fails for any other reason.
        """
        self.get_or_create_user(db, user_id)
        try:
            raw_text = await self.document_agent.extract_text(file)
        except DocumentExtractionError as exc:
            # Surface structured extraction errors (encrypted PDF, wrong file type) directly
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

        # Persist the document to PostgreSQL first to get a valid document.id;
        # this ID becomes the ChromaDB collection namespace key in the next step
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
        """
        Route a user query through the adaptive multi-agent pipeline and return
        a source-grounded answer with citations.

        Routing decision tree (evaluated in priority order):

        Branch A - Research query (ArXiv path):
            Triggered when the query explicitly mentions papers, ArXiv, research, or surveys.
            1. Query the ArXiv agent for academic papers.
            2. If ArXiv returns results, build answer from paper summaries.
            3. If ArXiv is empty, fall back to Tavily web search.

        Branch B - Document query (RAG path):
            Triggered for all other queries.
            1. Run ChromaDB vector search via RAGAgent.
            2. If RAG confidence is sufficient (max similarity >= 0.5), generate answer.
            3. If the LLM answer contains uncertainty markers, force web search fallback.
            4. Merge RAG and web contexts and re-generate if fallback was triggered.

        In both branches the final Q&A pair and all cited sources are persisted to
        the PostgreSQL chat_history table.

        Args:
            db (Session): Active SQLAlchemy session for document reads and history writes.
            user_id (int): Identifies the user's ChromaDB namespace to search.
            question (str): Raw question text submitted by the user.
            top_k (int): Maximum number of vector chunks to retrieve from ChromaDB.
            document_id (int | None): Restricts RAG search to one document if provided;
                searches across all user documents if None.

        Returns:
            tuple[str, dict[str, list[dict]]]: The generated answer string and a dict
            grouping normalized sources by type: {"rag": [...], "arxiv": [...], "ddg": [...]}.
        """
        self.get_or_create_user(db, user_id)
        print("Query:", question)
        print("Is research query:", is_research_query(question))

        selected_document_id = self._resolve_document_id(db, user_id, document_id)

        # --- Branch A: Research / academic query path ---
        # Queries that explicitly reference papers or ArXiv bypass document retrieval
        # entirely and are routed directly to the ArXiv academic search agent.
        if is_research_query(question):
            print("Calling ArXiv agent...")
            grouped_sources = {"rag": [], "arxiv": [], "ddg": []}
            arxiv_papers = asyncio.run(self._safe_arxiv_search(question))
            print("Number of papers:", len(arxiv_papers))

            if arxiv_papers:
                # ArXiv returned papers: build the answer directly from paper summaries
                # without calling the LLM to reduce latency on literature queries
                grouped_sources["arxiv"] = normalize_source_items(
                    self.arxiv_agent.build_payload(arxiv_papers[:5])["results"]
                )
                flat_sources = normalize_source_items(grouped_sources["arxiv"])
                answer = self.arxiv_agent.build_answer(arxiv_papers[:5])
            else:
                # ArXiv unavailable or returned no matches: fall back to Tavily web search
                # so the user receives a useful response rather than an empty dead end
                ddg_results = asyncio.run(self._safe_ddg_search(question))
                grouped_sources["ddg"] = normalize_source_items(
                    self.ddg_agent.build_payload(ddg_results[:5])["results"] if ddg_results else []
                )
                flat_sources = normalize_source_items(grouped_sources["ddg"])
                answer = self._build_ddg_fallback_answer(ddg_results[:5] if ddg_results else [])

            # Research queries are not scoped to any uploaded document,
            # so document_id is stored as None in the chat history record
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

        # --- Branch B: Document RAG path ---
        # All non-research queries go through ChromaDB vector retrieval first.
        rag_result = self.rag_agent.collect_contexts(
            db=db,
            user_id=user_id,
            question=question,
            top_k=top_k,
            document_id=selected_document_id,
        )

        rag_answer = ""
        # Primary confidence gate: check whether vector retrieval produced results
        # strong enough to answer without supplementing from the web
        use_fallback = self._should_use_fallback(rag_result)
        if not use_fallback and rag_result.contexts:
            rag_answer = self.answer_agent.generate_answer(question=question, contexts=rag_result.contexts)
            # Secondary confidence gate: if the LLM itself signals it lacks information,
            # override the vector confidence score and trigger web search anyway
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
            # Merge web contexts with any existing RAG chunks so the LLM can
            # synthesize a richer answer that draws from both document and web sources
            ddg_contexts, ddg_sources = asyncio.run(self._run_ddg_fallback(question))
            merged_contexts.extend(ddg_contexts)
            grouped_sources["ddg"] = ddg_sources

        flat_sources = normalize_source_items(
            [*grouped_sources["rag"], *grouped_sources["arxiv"], *grouped_sources["ddg"]]
        )

        if merged_contexts:
            # Re-generate over merged contexts only when fallback added new material;
            # reuse the already-generated rag_answer otherwise to save an LLM call
            answer = (
                self.answer_agent.generate_answer(question=question, contexts=merged_contexts)
                if use_fallback or not rag_answer
                else rag_answer
            )
        else:
            # No context from any agent: return a transparent refusal so the user
            # knows why they received no answer rather than a hallucinated one
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

        # Persist Q&A pair and all cited sources to PostgreSQL for chat history replay
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
        """
        Execute a Tavily web search and format the results for pipeline consumption.

        Args:
            question (str): The user question forwarded directly to the Tavily API.

        Returns:
            tuple[list[dict], list[dict]]: LLM-ready context dicts and normalized
            source dicts for the API response sources field.
        """
        ddg_results = await self._safe_ddg_search(question)
        if not ddg_results:
            return [], []

        contexts = self.ddg_agent.build_contexts(ddg_results)
        sources = normalize_source_items(self.ddg_agent.build_payload(ddg_results)["results"])
        return contexts, sources

    async def _safe_arxiv_search(self, question: str):
        """
        Run an ArXiv search with full exception isolation.

        A network failure, rate-limit response, or API error must not propagate
        to the user-facing route, so all exceptions are caught here and logged.

        Args:
            question (str): Query string forwarded to the ArXiv search API.

        Returns:
            list[ArxivPaper]: Papers returned by ArXiv, or an empty list on any error.
        """
        try:
            return await self.arxiv_agent.search_papers_async(question, max_results=5)
        except ArxivAPIError as exc:
            # ArXiv rate-limit or service outage: degrade gracefully to DDG fallback
            logger.warning("ArXiv unavailable question=%s error=%s", question, exc)
            return []
        except Exception:
            logger.exception("Unexpected ArXiv failure question=%s", question)
            return []

    async def _safe_ddg_search(self, question: str):
        """
        Run a Tavily web search with full exception isolation.

        Args:
            question (str): Query string forwarded to the Tavily API.

        Returns:
            list[DDGResult]: Web results, or an empty list on any error.
        """
        try:
            return await self.ddg_agent.search_async(question, max_results=5)
        except Exception:
            logger.exception("DDG unavailable question=%s", question)
            return []

    def _should_use_fallback(self, rag_result: RAGResult) -> bool:
        """
        Decide whether the RAG result requires web search augmentation.

        Two conditions independently trigger fallback:
        - No chunks were retrieved from ChromaDB or PostgreSQL (is_empty).
        - Chunks were retrieved but max cosine similarity is below 0.5, indicating
          the document content is likely not topically relevant to this question.

        Args:
            rag_result (RAGResult): Output from RAGAgent.collect_contexts.

        Returns:
            bool: True when the orchestrator should call the web search agent.
        """
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
        """
        Detect whether the LLM's answer contains explicit uncertainty language.

        This is a secondary hallucination guard applied after the vector confidence
        check. Even when retrieved chunks score above the 0.5 threshold, the LLM
        may indicate it cannot find a conclusive answer. Detecting these phrases
        allows the orchestrator to trigger web search as a recovery step.

        Args:
            answer (str): The raw answer text returned by AnswerGenerationAgent.

        Returns:
            bool: True if any UNCERTAIN_ANSWER_MARKERS phrase appears in the answer.
        """
        # Collapse whitespace before substring matching to handle line breaks in the answer
        normalized = " ".join(answer.lower().split())
        return any(marker in normalized for marker in UNCERTAIN_ANSWER_MARKERS)

    def delete_document(self, db: Session, user_id: int, document_id: int) -> None:
        """
        Remove a document and all associated data from PostgreSQL and ChromaDB.

        Deletion is ordered to respect FK constraints and data consistency:
        1. Ownership check (404 if the document does not belong to user_id).
        2. Delete all ChatHistory rows that reference this document.
        3. Delete the Document row from PostgreSQL.
        4. Delete the corresponding vector embeddings from ChromaDB.

        ChromaDB deletion is attempted last and silently suppressed on failure
        because the PostgreSQL record is the authoritative source of document
        existence from the user's perspective. Orphaned vectors are invisible
        after the document row is removed.

        Args:
            db (Session): Active SQLAlchemy session.
            user_id (int): Must match the document owner to prevent privilege escalation.
            document_id (int): Primary key of the document to delete.

        Raises:
            HTTPException 404: No document with this ID exists for the given user.
        """
        document = (
            db.query(models.Document)
            .filter(models.Document.id == document_id, models.Document.user_id == user_id)
            .first()
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found for this user.")

        # Delete chat history first to avoid FK constraint violations when the document row is removed
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
            # Silently suppress ChromaDB failures: the document is already gone from
            # PostgreSQL and orphaned vectors will never be returned to this user
            pass

    def _resolve_document_id(
        self, db: Session, user_id: int, document_id: int | None
    ) -> int | None:
        """
        Validate that the requested document_id belongs to the authenticated user.

        This prevents a user from accessing another user's vector embeddings by
        supplying an arbitrary document_id they do not own. If ownership cannot be
        confirmed, the query silently broadens to all of the user's documents.

        Args:
            db (Session): Active SQLAlchemy session.
            user_id (int): The authenticated user's ID from the verified JWT.
            document_id (int | None): The document_id from the API request payload.

        Returns:
            int | None: The validated document_id, or None if it was absent or invalid.
        """
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
        """
        Format Tavily web results into a plain-text answer without calling the LLM.

        Used when ArXiv returns no papers for a research query. Formatting without
        an LLM call keeps latency low and avoids hallucination risk on sparse context.

        Args:
            results (list): List of DDGResult dataclass instances from the DDGAgent.

        Returns:
            str: Formatted multi-line answer, or a no-results message if the list is empty.
        """
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
    """
    Determine whether a query should be routed to the ArXiv academic search agent.

    The routing decision is keyword-based rather than LLM-based to keep it
    deterministic, fast, and transparent. Any query that explicitly references
    papers, ArXiv, or research is treated as a literature search rather than a
    document comprehension task.

    Args:
        query (str): Raw question text from the user.

    Returns:
        bool: True if the query should be handled by the ArXiv agent path.
    """
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
