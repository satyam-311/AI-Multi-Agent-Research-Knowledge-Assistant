# arxiv_agent.py
# ArXiv academic paper search agent for the MARKA research query path.
# Implements a production-grade client with in-process TTL caching,
# thread-safe rate limiting, and exponential-backoff retry logic to ensure
# the ArXiv API is never hammered during high-traffic periods.

from __future__ import annotations

# asyncio.to_thread offloads the blocking arxiv client call to a thread pool
import asyncio
# dataclass provides a typed, immutable container for paper metadata
from dataclasses import dataclass
from datetime import UTC
import logging
# threading.Lock makes the rate-limiter safe for concurrent FastAPI requests
import threading
import time

# Official ArXiv Python client library
import arxiv


logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    """
    Typed container for a single ArXiv paper's metadata.

    Normalizes the raw arxiv.Result object into a flat, serializable structure
    that the orchestrator and prompt builder can consume without touching the
    arxiv library's object model.

    Attributes:
        title (str): Cleaned paper title with collapsed whitespace.
        authors (list[str]): List of author name strings.
        summary (str): Truncated abstract (max 300 chars) for prompt inclusion.
        published_at (str): ISO 8601 date string (YYYY-MM-DD) in UTC.
        paper_id (str): ArXiv paper identifier (e.g. "1706.03762v5").
        pdf_url (str): Constructed direct PDF download URL.
    """

    title: str
    authors: list[str]
    summary: str
    published_at: str
    paper_id: str
    pdf_url: str

    def to_source(self) -> dict:
        """
        Serialize this paper to the standard source dict schema used by the API response.

        Returns:
            dict: Source dict with type="arxiv" and all citation fields populated.
        """
        return {
            "type": "arxiv",
            "title": self.title,
            "summary": self.summary,
            "pdf_url": self.pdf_url,
            "link": self.pdf_url,
            "published_at": self.published_at,
        }


class ArxivAPIError(Exception):
    """Raised when all retry attempts to the ArXiv API have been exhausted."""
    pass


class ArxivAgent:
    """
    Production-grade ArXiv academic paper search agent.

    Implements three reliability mechanisms on top of the base arxiv client:
    1. Thread-safe rate limiting: enforces a minimum interval between requests
       to avoid hitting ArXiv's undocumented rate limits.
    2. In-process TTL cache: caches search results for 15 minutes per (query, max_results)
       pair to eliminate redundant network calls for repeated queries.
    3. Exponential backoff retry: retries failed requests up to 3 times with
       linearly increasing sleep intervals (1s, 2s) between attempts.

    Attributes:
        _lock (threading.Lock): Mutex protecting the rate limiter's timestamp.
        _last_request_started_at (float): Monotonic timestamp of the most recent request.
        _min_interval_seconds (float): Minimum seconds between consecutive ArXiv requests.
        _cache (dict): TTL cache mapping (query, max_results) keys to (expiry, papers) tuples.
        _cache_ttl_seconds (int): Cache entry lifetime in seconds (default: 15 minutes).
        _max_retries (int): Maximum number of request attempts before raising ArxivAPIError.
        _client (arxiv.Client): Configured arxiv library client instance.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_started_at = 0.0
        # 3.5 seconds matches the arxiv library's own recommended delay_seconds
        self._min_interval_seconds = 3.5
        self._cache: dict[str, tuple[float, list[ArxivPaper]]] = {}
        # 15-minute TTL balances freshness with API load reduction
        self._cache_ttl_seconds = 15 * 60
        self._max_retries = 3
        self._client = arxiv.Client(
            page_size=10,
            delay_seconds=self._min_interval_seconds,
            num_retries=self._max_retries,
        )

    def is_research_query(self, query: str) -> bool:
        """
        Check whether a query string matches research-oriented keywords.

        This mirrors the orchestrator-level is_research_query function and is
        provided here for callers that hold a reference to the ArxivAgent directly.

        Args:
            query (str): Raw user query text.

        Returns:
            bool: True if the query should be routed to this agent.
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

    def search_papers(self, query: str, max_results: int = 5) -> list[ArxivPaper]:
        """
        Search ArXiv for papers matching the query, with caching and retry logic.

        Constructs a dual-field query (title OR abstract) to maximize result relevance,
        checks the in-process TTL cache before making a network call, and retries
        up to _max_retries times on failure.

        Args:
            query (str): Search terms; searched in both the ti (title) and abs (abstract) fields.
            max_results (int): Maximum number of papers to return. Defaults to 5.

        Returns:
            list[ArxivPaper]: Deduplicated list of ArxivPaper objects sorted by relevance.

        Raises:
            ArxivAPIError: If all retry attempts fail, wrapping the last encountered exception.
        """
        logger.info("ArXiv triggered")
        cache_key = self._cache_key(query, max_results)
        cached = self._get_cached_result(cache_key)
        if cached is not None:
            logger.info("ArXiv cache hit for query=%s count=%s", query, len(cached))
            return cached

        # Search both title and abstract fields to balance precision and recall
        formatted_query = f"ti:{query} OR abs:{query}"
        search = arxiv.Search(
            query=formatted_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            self._respect_rate_limit()
            try:
                logger.info("ArXiv request query=%s attempt=%s", query, attempt)
                papers = [self._convert_result(result) for result in self._client.results(search)]
                papers = self._dedupe_papers([paper for paper in papers if paper is not None])
                # Store result in cache before returning to serve future identical queries
                self._cache[cache_key] = (time.monotonic() + self._cache_ttl_seconds, papers)
                logger.info("ArXiv returned %s papers for query=%s", len(papers), query)
                return papers
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "ArXiv request failed for query=%s attempt=%s error=%s",
                    query,
                    attempt,
                    exc,
                )
                if attempt < self._max_retries:
                    # Linear backoff: sleep 1s on attempt 1, 2s on attempt 2
                    time.sleep(float(attempt))
                    continue
                break

        raise ArxivAPIError("ArXiv search failed.") from last_error

    async def search_papers_async(self, query: str, max_results: int = 5) -> list[ArxivPaper]:
        """
        Async wrapper for search_papers that runs the blocking call in a thread pool.

        The underlying arxiv client is synchronous (blocking HTTP). asyncio.to_thread
        offloads it to the default executor so the FastAPI event loop is not blocked.

        Args:
            query (str): Search terms forwarded to search_papers.
            max_results (int): Maximum number of papers to return. Defaults to 5.

        Returns:
            list[ArxivPaper]: Same result as search_papers, awaitable from async context.
        """
        return await asyncio.to_thread(self.search_papers, query, max_results)

    def build_contexts(self, papers: list[ArxivPaper]) -> list[dict]:
        """
        Convert a list of ArxivPaper objects into LLM-ready context dicts.

        The text field is formatted with labeled fields so the LLM can distinguish
        ArXiv sources from RAG or web sources within the combined prompt context.

        Args:
            papers (list[ArxivPaper]): Papers returned by search_papers.

        Returns:
            list[dict]: Context dicts conforming to the shared context schema,
            with type="arxiv" and text populated with a structured paper summary block.
        """
        contexts: list[dict] = []
        for paper in papers:
            contexts.append(
                {
                    "type": "arxiv",
                    "source": paper.title,
                    "title": paper.title,
                    "summary": paper.summary,
                    "published_at": paper.published_at,
                    "link": paper.pdf_url,
                    "pdf_url": paper.pdf_url,
                    "text": (
                        f"ArXiv Title: {paper.title}\n"
                        f"Published: {paper.published_at}\n"
                        f"Authors: {', '.join(paper.authors) or 'Unknown'}\n"
                        f"PDF URL: {paper.pdf_url}\n"
                        f"Summary: {paper.summary}"
                    ),
                }
            )
        return contexts

    def build_payload(self, papers: list[ArxivPaper]) -> dict:
        """
        Convert a list of ArxivPaper objects into the API response source payload format.

        This is the format that ends up in the "arxiv" key of the grouped_sources dict
        returned by the orchestrator and serialized in the AskResponse schema.

        Args:
            papers (list[ArxivPaper]): Papers returned by search_papers.

        Returns:
            dict: A dict with type="arxiv" and a "results" list of source dicts.
        """
        return {
            "type": "arxiv",
            "results": [
                {
                    "type": "arxiv",
                    "title": paper.title,
                    "pdf_url": paper.pdf_url,
                    "summary": paper.summary,
                    "link": paper.pdf_url,
                    "published_at": paper.published_at,
                }
                for paper in papers
            ],
        }

    def build_answer(self, papers: list[ArxivPaper]) -> str:
        """
        Build a plain-text answer from ArXiv paper summaries without calling the LLM.

        Used when the ArXiv agent handles the query entirely and no document context
        is available. Formatting the answer directly avoids a redundant LLM call and
        removes the risk of hallucinating paper details.

        Args:
            papers (list[ArxivPaper]): Papers to format into the answer string.

        Returns:
            str: Formatted multi-line answer listing paper titles, summaries, and PDF URLs,
            or a no-results message if the list is empty.
        """
        if not papers:
            return (
                "I could not find matching ArXiv papers for this research query. "
                "Falling back to web search sources may help."
            )

        lines: list[str] = []
        for paper in papers[:5]:
            lines.append(f"Title: {paper.title}")
            lines.append(f"Summary: {paper.summary}")
            lines.append(f"PDF: {paper.pdf_url}")
            lines.append("")
        return "\n".join(lines).strip()

    def _convert_result(self, result: arxiv.Result) -> ArxivPaper | None:
        """
        Convert a raw arxiv.Result object into a typed ArxivPaper dataclass.

        Validates that the result has a usable entry_id before constructing the
        paper object. Returns None for malformed results so the caller can filter them out.

        Args:
            result (arxiv.Result): Raw result object from the arxiv client.

        Returns:
            ArxivPaper | None: A populated ArxivPaper, or None if the result is invalid.
        """
        entry_id = (result.entry_id or "").strip()
        if not entry_id:
            return None

        # Extract the numeric paper ID from the ArXiv entry URL
        paper_id = entry_id.split("/")[-1]
        if not paper_id:
            return None

        # Construct the canonical PDF URL from the paper ID
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        logger.info("PDF URL generated: %s", pdf_url)

        published_at = ""
        if result.published is not None:
            # Normalize to UTC date to avoid timezone-dependent display differences
            published_at = result.published.astimezone(UTC).date().isoformat()

        authors = [author.name.strip() for author in result.authors if author.name.strip()]
        # Collapse internal whitespace before truncating to avoid mid-word cuts
        summary = self._truncate_summary(" ".join((result.summary or "").split()).strip())
        title = " ".join((result.title or "").split()).strip()
        if not title:
            return None

        return ArxivPaper(
            title=title,
            authors=authors,
            summary=summary or "No summary available from arXiv.",
            published_at=published_at,
            paper_id=paper_id,
            pdf_url=pdf_url,
        )

    def _dedupe_papers(self, papers: list[ArxivPaper]) -> list[ArxivPaper]:
        """
        Remove duplicate papers that share the same ArXiv paper_id.

        The arxiv client can occasionally return the same paper multiple times
        when the query matches both title and abstract fields.

        Args:
            papers (list[ArxivPaper]): Papers that may contain duplicates.

        Returns:
            list[ArxivPaper]: Papers with duplicates removed, preserving original order.
        """
        unique: dict[str, ArxivPaper] = {}
        for paper in papers:
            if paper.paper_id not in unique:
                unique[paper.paper_id] = paper
        return list(unique.values())

    def _cache_key(self, query: str, max_results: int) -> str:
        """
        Build a deterministic cache key from the query and result count.

        Normalizing the query (lowercase, collapsed whitespace) ensures that
        queries like "Attention Is All You Need" and "attention is all you need"
        map to the same cache entry.

        Args:
            query (str): The search query string.
            max_results (int): The requested result count.

        Returns:
            str: A normalized cache key string.
        """
        return f"{' '.join(query.lower().split())}::{max_results}"

    def _get_cached_result(self, cache_key: str) -> list[ArxivPaper] | None:
        """
        Retrieve a cached result if it has not yet expired.

        Expired entries are evicted on access rather than on a background timer
        to keep the implementation simple and avoid a separate cache-cleanup thread.

        Args:
            cache_key (str): The key produced by _cache_key.

        Returns:
            list[ArxivPaper] | None: The cached papers, or None if the entry is
            absent or expired.
        """
        cached = self._cache.get(cache_key)
        if cached is None:
            return None

        expires_at, papers = cached
        if expires_at < time.monotonic():
            # Evict the expired entry before returning None
            self._cache.pop(cache_key, None)
            return None
        return papers

    def _respect_rate_limit(self) -> None:
        """
        Enforce the minimum inter-request interval using a thread-safe lock.

        The lock ensures that two concurrent FastAPI requests cannot both read
        _last_request_started_at simultaneously and then both send requests at
        the same moment, which would violate ArXiv's rate limit policy.
        """
        with self._lock:
            now = time.monotonic()
            wait_seconds = self._min_interval_seconds - (now - self._last_request_started_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            # Record the timestamp after sleeping so the next caller waits from this point
            self._last_request_started_at = time.monotonic()

    def _truncate_summary(self, summary: str, max_length: int = 300) -> str:
        """
        Truncate an ArXiv abstract to a maximum length for prompt inclusion.

        ArXiv abstracts can be several hundred words. Truncating to 300 characters
        keeps the LLM prompt within a manageable size when multiple papers are included.

        Args:
            summary (str): The raw abstract text.
            max_length (int): Maximum character length. Defaults to 300.

        Returns:
            str: The original summary if short enough, or a truncated version with
            an ellipsis appended. Returns a placeholder if the input is empty.
        """
        if len(summary) <= max_length:
            return summary or "No summary available from arXiv."
        return f"{summary[:max_length].rstrip()}..."
