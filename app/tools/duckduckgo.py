"""DuckDuckGo Search Tool using ddgs for live web intelligence."""

import logging
from typing import Any, Dict, List, Optional
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS  # type: ignore

logger = logging.getLogger(__name__)


def duckduckgo_search(
    query: str,
    max_results: int = 3,
    region: str = "us-en",
    timelimit: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Executes a DuckDuckGo search and returns formatted structured search results."""
    try:
        with DDGS() as ddgs:
            results = list(
                ddgs.text(
                    query,
                    region=region,
                    safesearch="moderate",
                    timelimit=timelimit,
                    max_results=max_results,
                )
            )
            logger.info(f"DuckDuckGo search for '{query}' returned {len(results)} results.")
            return results
    except Exception as e:
        logger.error(f"DuckDuckGo search error for query '{query}': {e}")
        return []


def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
    """Formats DuckDuckGo search results into a clean markdown document for research analysis."""
    if not results:
        return f"### Search Query: {query}\n*No search results retrieved.*"

    chunks = [f"### Research Query: {query}"]
    for idx, r in enumerate(results, 1):
        title = r.get("title", "No Title")
        snippet = r.get("body", "No Snippet")
        href = r.get("href", "")
        chunks.append(f"**[{idx}] {title}**\n- **Snippet**: {snippet}\n- **Source**: {href}")

    return "\n\n".join(chunks)
