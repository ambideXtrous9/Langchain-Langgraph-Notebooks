"""Google News (GNews) Integration Tool for Indian Stock Market Intelligence."""

import logging
from typing import Any, Dict, List, Optional
from gnews import GNews
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Module-level cache to prevent redundant HTTP queries during multi-agent runs
_news_cache: Dict[str, List[Dict[str, Any]]] = {}


def get_gnews_client(period: str = "7d", max_results: int = 6) -> GNews:
    """Creates a configured GNews client for Indian financial news."""
    return GNews(language="en", country="IN", period=period, max_results=max_results)


def fetch_news_articles(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Fetches news articles for a query from Google News India with in-memory caching."""
    cache_key = f"{query.lower().strip()}::{max_results}"
    if cache_key in _news_cache:
        return _news_cache[cache_key]

    try:
        client = get_gnews_client(max_results=max_results)
        results = client.get_news(f"{query} NSE stock OR share price OR earnings")
        if not results:
            results = client.get_news(query)

        cleaned = []
        for item in results[:max_results]:
            cleaned.append({
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "published_date": item.get("published date", ""),
                "url": item.get("url", ""),
                "publisher": item.get("publisher", {}).get("title", "News") if isinstance(item.get("publisher"), dict) else str(item.get("publisher", "")),
            })
        _news_cache[cache_key] = cleaned
        return cleaned
    except Exception as exc:
        logger.warning(f"GNews retrieval error for '{query}': {exc}")
        return []


@tool
def search_stock_news(query: str, max_results: int = 5) -> str:
    """Fetches recent news articles and market sentiment from Google News India for an Indian stock, sector, or market catalyst.
    Args:
        query: Stock symbol, company name, or sector topic (e.g. 'TATA MOTORS', 'NIFTY IT', 'Banking sector credit growth').
        max_results: Maximum number of articles to return (default 5).
    """
    articles = fetch_news_articles(query=query, max_results=max_results)
    if not articles:
        return f"No recent news found for query: '{query}'."

    output_lines = [f"### Latest Market News for '{query}':\n"]
    for i, art in enumerate(articles, 1):
        title = art.get("title", "Untitled")
        pub = art.get("publisher", "Source")
        dt = art.get("published_date", "")
        desc = art.get("description", "")
        output_lines.append(f"{i}. **{title}** ({pub} - {dt})")
        if desc:
            output_lines.append(f"   > {desc}")
        output_lines.append("")

    return "\n".join(output_lines)
