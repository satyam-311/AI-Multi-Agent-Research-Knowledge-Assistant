from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import threading
import time

import httpx

from backend.config import get_settings


logger = logging.getLogger(__name__)
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass
class DDGResult:
    title: str
    link: str
    snippet: str

    def to_source(self) -> dict:
        return {
            "type": "ddg",
            "title": self.title,
            "summary": self.snippet,
            "link": self.link,
            "pdf_url": None,
            "published_at": None,
        }


class DDGAgent:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_started_at = 0.0
        self._min_interval_seconds = 1.0
        self._max_retries = 2
        self._timeout_seconds = 20.0
        self.settings = get_settings()

    def search(self, query: str, max_results: int = 5) -> list[DDGResult]:
        logger.info("tavily triggered")
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
                    time.sleep(float(attempt))
                    continue
                break

        if last_error is not None:
            logger.exception("tavily search failed after retries", exc_info=last_error)
        return []

    async def search_async(self, query: str, max_results: int = 5) -> list[DDGResult]:
        return await asyncio.to_thread(self.search, query, max_results)

    def build_contexts(self, results: list[DDGResult]) -> list[dict]:
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
        unique: dict[str, DDGResult] = {}
        for item in raw_results:
            link = str(item.get("url") or item.get("href") or "").strip()
            if not link or link in unique:
                continue

            title = str(item.get("title") or "").strip() or link
            snippet = str(item.get("content") or item.get("snippet") or item.get("body") or "").strip()
            unique[link] = DDGResult(title=title, link=link, snippet=snippet)
        return list(unique.values())

    def _respect_rate_limit(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait_seconds = self._min_interval_seconds - (now - self._last_request_started_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_started_at = time.monotonic()
