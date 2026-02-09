"""
Song Factory - Web Search Module

Provides DuckDuckGo web search and HTML content fetching for the
Lore Discovery tab.  No API keys required.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional

import requests

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WebSearchError(Exception):
    """Raised when a web search or page fetch fails."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result from DuckDuckGo."""
    title: str
    url: str
    snippet: str
    body: str = ""


# ---------------------------------------------------------------------------
# HTML stripping (stdlib only)
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Simple HTML-to-text extractor that skips script/style/nav tags."""

    _SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._pieces.append(text)

    def get_text(self) -> str:
        return "\n".join(self._pieces)


def _strip_html(html: str) -> str:
    """Strip HTML tags and return plain text."""
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    return extractor.get_text()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Run a DuckDuckGo web search and return results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.

    Returns:
        List of SearchResult objects.

    Raises:
        WebSearchError: If the search fails.
    """
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        raise WebSearchError(f"DuckDuckGo search failed: {exc}") from exc

    results = []
    for item in raw:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("href", ""),
            snippet=item.get("body", ""),
        ))
    return results


def fetch_content(url: str, timeout: int = 15, max_chars: int = 15000) -> str:
    """Fetch a web page and return its text content.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        max_chars: Maximum characters to return.

    Returns:
        Plain text extracted from the page HTML.

    Raises:
        WebSearchError: If the fetch fails.
    """
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SongFactory/1.0)"},
        )
        resp.raise_for_status()
    except Exception as exc:
        raise WebSearchError(f"Failed to fetch {url}: {exc}") from exc

    text = _strip_html(resp.text)
    if len(text) > max_chars:
        text = text[:max_chars]
    return text
