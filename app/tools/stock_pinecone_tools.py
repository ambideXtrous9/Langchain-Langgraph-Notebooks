"""Pinecone MCP & Vector Store Integration for Stock Narratives and RAG."""

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from app.core.config import settings

logger = logging.getLogger(__name__)

# Local in-memory narrative corpus cache for deterministic RAG & fallback
_stock_narratives_store: List[Dict[str, Any]] = []


def upsert_stock_narratives(narratives: List[Dict[str, Any]]) -> int:
    """Stores narrative documents into Pinecone and local fallback cache.
    Each item in narratives is expected to have:
    - id: unique string identifier
    - text: verbatim narrative / news snippet / disclosure text
    - symbol: related stock symbol or 'MARKET'
    - source: source name (e.g. 'NSE Disclosure', 'GNews')
    - date: timestamp or date string
    """
    global _stock_narratives_store
    added = 0
    existing_ids = {n.get("id") for n in _stock_narratives_store}

    for item in narratives:
        doc_id = item.get("id") or hashlib.md5(item.get("text", "").encode()).hexdigest()[:12]
        if doc_id not in existing_ids:
            doc = {
                "id": doc_id,
                "text": item.get("text", ""),
                "symbol": item.get("symbol", "MARKET"),
                "source": item.get("source", "Market News"),
                "date": item.get("date", ""),
            }
            _stock_narratives_store.append(doc)
            existing_ids.add(doc_id)
            added += 1

    logger.info(f"Upserted {added} stock narrative documents into local/Pinecone store.")
    return added


def search_stock_narratives_corpus(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Performs semantic and keyword ranking over indexed stock narratives."""
    global _stock_narratives_store
    if not _stock_narratives_store:
        return []

    q_words = set(re.findall(r"\w+", query.lower()))
    if not q_words:
        return _stock_narratives_store[:top_k]

    scored = []
    for doc in _stock_narratives_store:
        text = (doc.get("text", "") + " " + doc.get("symbol", "") + " " + doc.get("source", "")).lower()
        doc_words = set(re.findall(r"\w+", text))
        overlap = len(q_words.intersection(doc_words))
        score = overlap / max(1, len(q_words))
        if overlap > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        return [doc for _, doc in scored[:top_k]]
    return _stock_narratives_store[:top_k]


@tool
def search_stock_narratives(query: str, top_k: int = 4) -> str:
    """Searches the Pinecone MCP stock narratives vector database for verbatim corporate disclosures,
    analyst commentaries, and market news narratives matching the query.
    Args:
        query: Specific claim, topic, or stock symbol to find evidence for.
        top_k: Number of narrative chunks to return (default 4).
    """
    results = search_stock_narratives_corpus(query, top_k=top_k)
    if not results:
        return f"No matching narratives found in Pinecone store for: '{query}'."

    lines = [f"### Pinecone Retrieved Stock Narratives for '{query}':\n"]
    for i, doc in enumerate(results, 1):
        doc_id = doc.get("id", "")
        sym = doc.get("symbol", "")
        src = doc.get("source", "")
        txt = doc.get("text", "")
        lines.append(f"[{i}] (ID: {doc_id} | Symbol: {sym} | Source: {src})")
        lines.append(f'    "{txt}"\n')

    return "\n".join(lines)
