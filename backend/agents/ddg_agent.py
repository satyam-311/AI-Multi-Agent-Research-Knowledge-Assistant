# ddg_agent.py
# Tavily web search agent for the MARKA fallback retrieval path.
# Called when ChromaDB vector similarity is below the confidence threshold
# or when ArXiv returns no results for a research query. Implements
# thread-safe rate limiting and retry logic for reliable API access.

from __future__ import annotations

# asyncio.to_thread offloads the blocking httpx call to a thread pool
import asyncio
# dataclass provides a typed, immutable container for individual search results
from dataclasses import dataclass
import logging
# threading.Lock makes the rate limiter safe under concurrent FastAPI requests
import threading
import time

# httpx is used for synchronous HTTP calls to the Tavily REST API
import httpx

# Runtime configuration providing the Tavily API key
from backend.config import get_settings


logger = logging.getLogger(__name__)

# Tavily's REST endpoint for executing web searches
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass
class DDGResult:
    """
    Typed container for a single Tavily web search result.

    Normalizes the raw Tavily API response dict into a flat, serializable
    structure for use by the orchestrator and prompt builder.

    Attributes:
        title (str): Page or article title from the Tavily result.
        link (str): Canonical URL of the source page.
        snippet (str): Short content excerpt from the page body.
    """

    title: str
    link: str
    snippet: str

    def to_source(self) -> dict:
        """
        Serialize this result to the standard source dict schema used by the API response.

        Returns:
            dict: Source dict with type="ddg" and all citation fields populated.
        """
        return {
            "type": "ddg",
            "title": self.title,
            "summary": self.snippet,
            "link": self.link,
            "pdf_url": None,
            "published_at": None,
        }


class DDGAgent:
    """
    Tavily web search agent that provides live web context for the MARKA fallback path.

    Triggered by the orchestrator when:
    - ChromaDB vector similarity is below the 0.5 confidence threshold (RAG fallback).
    - ArXiv returns no papers for a research query (ArXiv fallback).

    Implements thread-safe rate limiting (1 request per second minimum) and linear
    backoff retry logic (up to 2 retries) to handle transient Tavily API errors.

    Attributes:
        _lock (threading.Lock): Mutex protecting the rate limiter's timestamp.
        _last_request_started_at (float): Monotonic timestamp of the last API call.
        _min_interval_seconds (float): Minimum seconds between Tavily API requests.
        _max_retries (int): Maximum number of request attempts before returning empty.
        _timeout_seconds (float): HTTP request timeout in seconds.
        settings: Parsed application settings containing the Tavily API key.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_started_at = 0.0
        # 1-second minimum interval to avoid Tavily rate limiting on free-tier keys
        self._min_interval_seconds = 1.0
        self._max_retries = 2
        self._timeout_seconds = 20.0
        self.settings = get_settings()

    def search(self, query: str, max_results: int = 5) -> list[DDGResult]:
        """
        Execute a synchronous Tavily web search with retry and rate limiting.

        Returns an empty list (rather than raising) on all failure modes so the
        orchestrator can degrade gracefully when the web search path is unavailable.

        Args:
            query (str): Search query forwarded directly to the Tavily API.
            max_results (int): Maximum number of results to request. Defaults to 5.

        Returns:
            list[DDGResult]: Deduplicated list of web results, or an empty list if
            the API key is missing, the request times out, or all retries fail.
        """
        logger.info("tavily triggered")
        # Guard early if the API key was not configured; avoids a guaranteed 401 error
        if not self.settings.tavily_api_key:
            logger.warning("tavily api key missing")
            return []

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            self._respect_rate_limit()
            try:
                logger.info("tavily request", extra={"query": query, "attempt": attempt})
                response = httpx.post(
                    TAVILY_SEARCH_URL,
                    json={
                        "api_key": self.settings.tavily_api_key,
                        "query": query,
                        # "advanced" search depth yields more relevant snippets than "basic"
                        "search_depth": "advanced",
                        "max_results": max_results,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                raw_results = payload.get("results", [])
                results = self._dedupe_results(raw_results)
                logger.info("tavily success", extra={"query": query, "count": len(results)})
                return results
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "tavily error",
                    extra={"query": query, "attempt": attempt, "error": str(exc)},
                )
                if attempt < self._max_retries:
                    # Linear backoff: sleep 1s on first failure, 2s on second
                    time.sleep(float(attempt))
                    continue
                break

        if last_error is not None:
            logger.exception("tavily search failed after retries", exc_info=last_error)
        # Return empty list instead of raising so the orchestrator can handle the failure
        return []

    async def search_async(self, query: str, max_results: int = 5) -> list[DDGResult]:
        """
        Async wrapper that runs the blocking search call in a thread pool.

        The Tavily HTTP call is synchronous. asyncio.to_thread offloads it to
        the default executor so the FastAPI event loop is not blocked during the
        request, which is critical when the orchestrator awaits both ArXiv and
        Tavily concurrently.

        Args:
            query (str): Search query forwarded to search.
            max_results (int): Maximum number of results to return. Defaults to 5.

        Returns:
            list[DDGResult]: Same result as search, awaitable from an async context.
        """
        return await asyncio.to_thread(self.search, query, max_results)

    def build_contexts(self, results: list[DDGResult]) -> list[dict]:
        """
        Convert Tavily results into LLM-ready context dicts.

        Formats each result as a labeled text block that the AnswerGenerationAgent
        includes in the prompt alongside RAG chunks and ArXiv summaries.

        Args:
            results (list[DDGResult]): Results from search or search_async.

        Returns:
            list[dict]: Context dicts with type="ddg" conforming to the shared
            context schema used across all agents.
        """
        contexts: list[dict] = []
        for result in results:
            contexts.append(
                {
                    "type": "ddg",
                    "source": result.title,
                    "text": (
                        f"Web result title: {result.title}\n"
                        f"Link: {result.link}\n"
                        f"Snippet: {result.snippet}"
                    ),
                    "title": result.title,
                    "summary": result.snippet,
                    "link": result.link,
                    "pdf_url": None,
                    "published_at": None,
                }
            )
        return contexts

    def build_payload(self, results: list[DDGResult]) -> dict:
        """
        Convert Tavily results into the API response source payload format.

        The returned dict is merged into the "ddg" key of the grouped_sources dict
        that the orchestrator passes back through the AskResponse schema.

        Args:
            results (list[DDGResult]): Results from search or search_async.

        Returns:
            dict: A dict with type="ddg" and a "results" list of source citation dicts.
        """
        return {
            "type": "ddg",
            "results": [
                {
                    "type": "ddg",
                    "title": result.title,
                    "snippet": result.snippet,
                    "summary": result.snippet,
                    "link": result.link,
                }
                for result in results
            ],
        }

    def _dedupe_results(self, raw_results: list[dict]) -> list[DDGResult]:
        """
        Parse Tavily API response items and remove duplicate URLs.

        Tavily occasionally returns the same URL with different title or snippet
        text. Deduplication is keyed on the canonical URL to ensure the LLM
        does not see the same source twice in the prompt context.

        Args:
            raw_results (list[dict]): Raw result dicts from the Tavily API response.

        Returns:
            list[DDGResult]: Deduplicated DDGResult instances in their original order.
        """
        unique: dict[str, DDGResult] = {}
        for item in raw_results:
            # Tavily uses "url" in its v2 API; "href" is retained for compatibility
            link = str(item.get("url") or item.get("href") or "").strip()
            if not link or link in unique:
                continue

            title = str(item.get("title") or "").strip() or link
            # "content" is the primary snippet field in Tavily v2; fall back to older field names
            snippet = str(item.get("content") or item.get("snippet") or item.get("body") or "").strip()
            unique[link] = DDGResult(title=title, link=link, snippet=snippet)
        return list(unique.values())

    def _respect_rate_limit(self) -> None:
        """
        Enforce the minimum inter-request interval using a thread-safe lock.

        The lock ensures concurrent FastAPI requests do not both read
        _last_request_started_at simultaneously and fire two Tavily requests
        back-to-back, which would violate the rate limit on free-tier API keys.
        """
        with self._lock:
            now = time.monotonic()
            wait_seconds = self._min_interval_seconds - (now - self._last_request_started_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            # Update timestamp after sleeping so the next caller waits from this point
            self._last_request_started_at = time.monotonic()
