from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC
import logging
import threading
import time

import arxiv


logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    title: str
    authors: list[str]
    summary: str
    published_at: str
    paper_id: str
    pdf_url: str

    def to_source(self) -> dict:
        return {
            "type": "arxiv",
            "title": self.title,
            "summary": self.summary,
            "pdf_url": self.pdf_url,
            "link": self.pdf_url,
            "published_at": self.published_at,
        }


class ArxivAPIError(Exception):
    pass


class ArxivAgent:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_started_at = 0.0
        self._min_interval_seconds = 3.5
        self._cache: dict[str, tuple[float, list[ArxivPaper]]] = {}
        self._cache_ttl_seconds = 15 * 60
        self._max_retries = 3
        self._client = arxiv.Client(
            page_size=10,
            delay_seconds=self._min_interval_seconds,
            num_retries=self._max_retries,
        )

    def is_research_query(self, query: str) -> bool:
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
        logger.info("ArXiv triggered")
        cache_key = self._cache_key(query, max_results)
        cached = self._get_cached_result(cache_key)
        if cached is not None:
            logger.info("ArXiv cache hit for query=%s count=%s", query, len(cached))
            return cached

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
                    time.sleep(float(attempt))
                    continue
                break

        raise ArxivAPIError("ArXiv search failed.") from last_error

    async def search_papers_async(self, query: str, max_results: int = 5) -> list[ArxivPaper]:
        return await asyncio.to_thread(self.search_papers, query, max_results)

    def build_contexts(self, papers: list[ArxivPaper]) -> list[dict]:
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
        entry_id = (result.entry_id or "").strip()
        if not entry_id:
            return None

        paper_id = entry_id.split("/")[-1]
        if not paper_id:
            return None

        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        logger.info("PDF URL generated: %s", pdf_url)

        published_at = ""
        if result.published is not None:
            published_at = result.published.astimezone(UTC).date().isoformat()

        authors = [author.name.strip() for author in result.authors if author.name.strip()]
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
        unique: dict[str, ArxivPaper] = {}
        for paper in papers:
            if paper.paper_id not in unique:
                unique[paper.paper_id] = paper
        return list(unique.values())

    def _cache_key(self, query: str, max_results: int) -> str:
        return f"{' '.join(query.lower().split())}::{max_results}"

    def _get_cached_result(self, cache_key: str) -> list[ArxivPaper] | None:
        cached = self._cache.get(cache_key)
        if cached is None:
            return None

        expires_at, papers = cached
        if expires_at < time.monotonic():
            self._cache.pop(cache_key, None)
            return None
        return papers

    def _respect_rate_limit(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait_seconds = self._min_interval_seconds - (now - self._last_request_started_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_started_at = time.monotonic()

    def _truncate_summary(self, summary: str, max_length: int = 300) -> str:
        if len(summary) <= max_length:
            return summary or "No summary available from arXiv."
        return f"{summary[:max_length].rstrip()}..."
