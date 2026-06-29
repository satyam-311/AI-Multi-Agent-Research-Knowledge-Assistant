# source_utils.py
# Source normalization utilities for the MARKA API response layer.
# Converts heterogeneous source representations (dicts, strings, URLs) produced
# by three different agents (RAG, ArXiv, DDG) into a consistent schema that
# the AskResponse Pydantic model can serialize without type errors.

from __future__ import annotations

from typing import Any


def normalize_source_items(raw_sources: object) -> list[dict[str, Any]]:
    """
    Normalize a collection of raw source objects into a deduplicated list of
    standard source dicts.

    Sources from the three agents arrive in different shapes: ArXiv returns
    dicts with pdf_url, DDG returns dicts with link and snippet, and the RAG
    path can return either dicts or plain strings. This function maps all forms
    to the same six-key schema: type, title, summary, link, pdf_url, published_at.

    Deduplication is keyed on (type, title, link, pdf_url) to prevent the same
    paper or web page from appearing twice when both the ArXiv and web agents
    return overlapping results.

    Args:
        raw_sources (object): Any value that might contain source items. Non-list
            values are treated as empty to handle None or unexpected types gracefully.

    Returns:
        list[dict[str, Any]]: Deduplicated list of normalized source dicts. Each dict
        is guaranteed to have all six schema keys, with None for absent fields.
    """
    if not isinstance(raw_sources, list):
        return []

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_sources:
        source = _normalize_single_source(item)
        if source is None:
            continue
        # Build a deduplication key from the four identifying fields
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
    """
    Normalize a single raw source value into the standard source dict schema.

    Handles two raw forms:
    - str: A plain text title or a URL. URLs are inferred to be ArXiv if the
      domain contains "arxiv.org", otherwise typed as "rag".
    - dict: A source dict from any agent. Fields are extracted by name with
      fallbacks for legacy naming conventions (e.g. "filename" for "title",
      "snippet" for "summary").

    Args:
        item (object): A single raw source value from any agent's output.

    Returns:
        dict[str, Any] | None: A normalized source dict with all six schema keys,
        or None if the item contains no usable citation information.
    """
    if isinstance(item, str):
        value = item.strip()
        if not value:
            return None
        is_url = value.startswith("http://") or value.startswith("https://")
        return {
            # Classify ArXiv URLs by domain; all other sources default to "rag"
            "type": "arxiv" if "arxiv.org/" in value else "rag",
            "title": value if not is_url else None,
            "summary": None,
            "link": value if is_url else None,
            "pdf_url": value if value.endswith(".pdf") else None,
            "published_at": None,
        }

    if not isinstance(item, dict):
        # Silently skip unexpected types (e.g. None, int) rather than raising
        return None

    source_type = str(item.get("type") or "rag").strip().lower()
    # "filename" and "source" are legacy keys from earlier agent versions
    title = _clean_text(item.get("title") or item.get("filename") or item.get("source"))
    summary = _clean_text(item.get("summary"))
    link = _clean_text(item.get("link"))
    pdf_url = _clean_text(item.get("pdf_url"))
    published_at = _clean_text(item.get("published_at"))

    # Cross-populate link and pdf_url so both fields are set when only one is present
    if not link and pdf_url:
        link = pdf_url
    if not pdf_url and link and link.endswith(".pdf"):
        pdf_url = link

    # Discard sources that have no identifying information at all
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
    """
    Strip a string value and return None if the result is empty.

    Args:
        value (object): A value that may or may not be a non-empty string.

    Returns:
        str | None: The stripped string, or None if the value is not a string
        or is empty after stripping.
    """
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
