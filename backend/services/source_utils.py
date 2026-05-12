from __future__ import annotations

from typing import Any


def normalize_source_items(raw_sources: object) -> list[dict[str, Any]]:
    if not isinstance(raw_sources, list):
        return []

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_sources:
        source = _normalize_single_source(item)
        if source is None:
            continue
        key = "|".join(
            [
                str(source.get("type") or ""),
                str(source.get("title") or ""),
                str(source.get("link") or ""),
                str(source.get("pdf_url") or ""),
            ]
        ).lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(source)
    return normalized


def _normalize_single_source(item: object) -> dict[str, Any] | None:
    if isinstance(item, str):
        value = item.strip()
        if not value:
            return None
        is_url = value.startswith("http://") or value.startswith("https://")
        return {
            "type": "arxiv" if "arxiv.org/" in value else "rag",
            "title": value if not is_url else None,
            "summary": None,
            "link": value if is_url else None,
            "pdf_url": value if value.endswith(".pdf") else None,
            "published_at": None,
        }

    if not isinstance(item, dict):
        return None

    source_type = str(item.get("type") or "rag").strip().lower()
    title = _clean_text(item.get("title") or item.get("filename") or item.get("source"))
    summary = _clean_text(item.get("summary"))
    link = _clean_text(item.get("link"))
    pdf_url = _clean_text(item.get("pdf_url"))
    published_at = _clean_text(item.get("published_at"))

    if not link and pdf_url:
        link = pdf_url
    if not pdf_url and link and link.endswith(".pdf"):
        pdf_url = link

    if not any([title, summary, link, pdf_url]):
        return None

    return {
        "type": source_type or "rag",
        "title": title,
        "summary": summary,
        "link": link,
        "pdf_url": pdf_url,
        "published_at": published_at,
    }


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
