from duckduckgo_search import DDGS


class WebSearchService:
    def search(self, query: str, max_results: int = 3) -> list[dict]:
        if not query.strip():
            return []

        results: list[dict] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max(1, min(max_results, 5))):
                results.append(
                    {
                        "title": str(item.get("title", "")).strip(),
                        "snippet": str(item.get("body", "")).strip(),
                        "link": str(item.get("href", "")).strip() or None,
                    }
                )
        return results[: max(1, min(max_results, 5))]
