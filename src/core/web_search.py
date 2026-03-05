"""Web search integration using DuckDuckGo (no API key needed)."""

from __future__ import annotations

from typing import Generator

from PyQt6.QtCore import QThread, pyqtSignal


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using DuckDuckGo. Returns list of {title, url, snippet}."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except ImportError:
        return [{"title": "검색 불가", "url": "", "snippet": "duckduckgo-search 패키지가 필요합니다. pip install duckduckgo-search"}]
    except Exception as e:
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


class WebSearchWorker(QThread):
    """Background web search worker."""

    search_finished = pyqtSignal(str)  # formatted results text
    search_error = pyqtSignal(str)

    def __init__(self, query: str, max_results: int = 5):
        super().__init__()
        self._query = query
        self._max_results = max_results

    def run(self):
        try:
            results = search_web(self._query, self._max_results)
            text = format_search_results(results)
            self.search_finished.emit(text)
        except Exception as e:
            self.search_error.emit(str(e))
