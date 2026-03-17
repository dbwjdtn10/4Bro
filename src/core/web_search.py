"""Web search integration using DuckDuckGo (no API key needed).

Provides a simple search_web() function with an in-memory TTL cache
protected by a threading lock for safe use from worker threads.
"""

from __future__ import annotations

import threading
import time

from .logger import log

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Thread-safe TTL cache
# ---------------------------------------------------------------------------
_search_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 3600  # 1 hour
_cache_lock = threading.Lock()


def _get_cached(query: str) -> list[dict] | None:
    """Return cached results if still valid, else None."""
    with _cache_lock:
        if query in _search_cache:
            timestamp, results = _search_cache[query]
            if time.time() - timestamp < _CACHE_TTL:
                log.debug(f"Search cache hit: {query}")
                return results
            del _search_cache[query]
    return None


def _set_cache(query: str, results: list[dict]):
    """Store search results in cache with current timestamp."""
    with _cache_lock:
        _search_cache[query] = (time.time(), results)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using DuckDuckGo. Returns list of {title, url, snippet}."""
    # Check cache first
    cached = _get_cached(query)
    if cached is not None:
        return cached

    if DDGS is None:
        log.error("duckduckgo-search 패키지 미설치")
        return [{"title": "검색 불가", "url": "", "snippet": "duckduckgo-search 패키지가 필요합니다. pip install duckduckgo-search"}]

    log.info(f"Web search start: {query} (max_results={max_results})")
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        _set_cache(query, results)
        log.info(f"Web search complete: {query} ({len(results)} results)")
        return results
    except Exception as e:
        log.error(f"Web search failed: {query} - {e}")
        return [{"title": "검색 오류", "url": "", "snippet": str(e)}]


def format_search_results(results: list[dict]) -> str:
    """Format search results into text for AI context."""
    if not results:
        return "(검색 결과 없음)"
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"{i}. {r['title']}")
        if r["url"]:
            parts.append(f"   URL: {r['url']}")
        if r["snippet"]:
            parts.append(f"   {r['snippet']}")
        parts.append("")
    return "\n".join(parts)
