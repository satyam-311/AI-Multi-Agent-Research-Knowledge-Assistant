import httpx
import feedparser


class ArxivService:
    API_URL = "https://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        if not query.strip():
            return []

        response = httpx.get(
            self.API_URL,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max(1, min(max_results, 5)),
            },
            timeout=12.0,
        )
        response.raise_for_status()

        feed = feedparser.parse(response.text)
        results: list[dict] = []
        for entry in feed.entries[: max(1, min(max_results, 5))]:
            results.append(
                {
                    "title": str(getattr(entry, "title", "")).strip(),
                    "summary": str(getattr(entry, "summary", "")).strip().replace("\n", " "),
                    "link": str(getattr(entry, "link", "")).strip() or None,
                }
            )
        return results
