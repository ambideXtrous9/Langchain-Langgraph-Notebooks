"""Pinecone Vector Database Multi-Hop Retrieval Tools for Harry Potter Lore Agent."""

import logging
import os
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from pinecone import Pinecone
from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy singleton client
_pinecone_client: Optional[Pinecone] = None


def get_pinecone_client() -> Optional[Pinecone]:
    """Initializes and caches the Pinecone client instance."""
    global _pinecone_client
    if _pinecone_client is None:
        api_key = os.getenv("PINECONE_API_KEY") or settings.PINECONE_API_KEY
        if api_key:
            try:
                _pinecone_client = Pinecone(api_key=api_key)
                logger.info("Pinecone client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Pinecone client: {e}")
                return None
    return _pinecone_client


# Lazy corpus and BM25 index cache
_hp_corpus: Optional[List[Dict[str, Any]]] = None
_hp_bm25 = None


def get_hp_bm25_index():
    """Loads and caches the 8970-passage Harry Potter book corpus with BM25Okapi index."""
    global _hp_corpus, _hp_bm25
    if _hp_bm25 is None:
        import json
        import re
        from rank_bm25 import BM25Okapi

        corpus_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "hp_corpus.json")
        if os.path.exists(corpus_file):
            try:
                with open(corpus_file, "r", encoding="utf-8") as f:
                    _hp_corpus = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load HP corpus file {corpus_file}: {e}")

        # If file is not on disk, fetch dynamically from Qdrant into memory
        if not _hp_corpus:
            try:
                from qdrant_client import QdrantClient
                qdrant_url = os.getenv("QDRANT_ENDPOINT") or settings.QDRANT_ENDPOINT
                qdrant_key = os.getenv("QDRANT_API_KEY") or settings.QDRANT_API_KEY
                if qdrant_url and qdrant_key:
                    client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=30)
                    all_records = []
                    next_offset = None
                    while True:
                        records, next_offset = client.scroll(
                            collection_name="HPVdb_openai",
                            limit=1000,
                            offset=next_offset,
                            with_payload=True,
                            with_vectors=False,
                        )
                        for r in records:
                            p = r.payload or {}
                            all_records.append({
                                "id": str(r.id),
                                "text": p.get("page_content", ""),
                                "source": p.get("metadata", {}).get("source", "Harry Potter Canon"),
                            })
                        if next_offset is None:
                            break
                    _hp_corpus = all_records
                    logger.info(f"Fetched {len(_hp_corpus)} HP passages dynamically from Qdrant into memory.")
            except Exception as q_err:
                logger.warning(f"Could not fetch HP corpus from Qdrant: {q_err}")

        if _hp_corpus:
            tokenized = [re.findall(r"\w+", doc.get("text", "").lower()) for doc in _hp_corpus]
            _hp_bm25 = BM25Okapi(tokenized)
            logger.info(f"Initialized BM25 index with {len(_hp_corpus)} passages in memory.")
    return _hp_corpus, _hp_bm25


def search_hp_corpus_bm25(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Searches the canonical 8970 Harry Potter passages using BM25Okapi."""
    import re
    corpus, bm25 = get_hp_bm25_index()
    if not corpus or not bm25:
        return []

    q_tokens = re.findall(r"\w+", query.lower())
    if not q_tokens:
        return []

    scores = bm25.get_scores(q_tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0.1:
            doc = corpus[idx]
            clean_source = doc.get("source", "Harry Potter Canon").replace("/kaggle/input/harry-potter-books/", "")
            results.append({
                "text": doc.get("text", "").strip(),
                "source": clean_source,
                "score": float(scores[idx]),
            })
    return results


def _search_records_impl(query: str, index_name: str = "hpvdb-openai", top_k: int = 5) -> str:
    matches = search_hp_corpus_bm25(query, top_k=top_k)
    if not matches:
        return f"No records found for query '{query}'."

    output = [f"### 📚 Canonical Retrieval Results for: \"{query}\""]
    for rank, m in enumerate(matches, 1):
        output.append(
            f"- **[Passage {rank}]** (Relevance Score: {m['score']:.2f})\n"
            f"  *Source: {m['source']}*\n"
            f"  > \"{m['text']}\""
        )
    return "\n\n".join(output)


@tool("search-records")
def search_records(query: str, index_name: str = "hpvdb-openai", top_k: int = 5) -> str:
    """Searches for records in the Harry Potter database based on a natural language text query."""
    return _search_records_impl(query=query, index_name=index_name, top_k=top_k)


@tool("search_records")
def search_records_underscore(query: str, index_name: str = "hpvdb-openai", top_k: int = 5) -> str:
    """Searches for records in the Harry Potter database based on a natural language text query."""
    return _search_records_impl(query=query, index_name=index_name, top_k=top_k)


@tool("pinecone_multihop_search")
def pinecone_multihop_search(
    queries: List[str],
    index_name: str = "hpvdb-openai",
    top_k_per_hop: int = 5,
    namespace: str = "",
) -> str:
    """Executes a sequential Multi-Hop semantic vector search across the Pinecone Harry Potter database.
    
    Args:
        queries: A list of 2 to 4 sequential search queries representing the logical hops (e.g. ['Elder Wand origin Antioch Peverell', 'Grindelwald Dumbledore duel 1945', 'Harry Potter Draco Malfoy disarm']).
        index_name: The target Pinecone index name (default 'hpvdb-openai').
        top_k_per_hop: Number of records to retrieve per hop.
        namespace: Optional Pinecone namespace within the index.
    
    Returns:
        A structured string containing all retrieved book passages categorized by hop.
    """
    results_by_hop = []
    seen_texts = set()

    for hop_idx, q in enumerate(queries, 1):
        hop_output = [f"### 🔗 HOP {hop_idx}: \"{q}\""]
        matches = search_hp_corpus_bm25(q, top_k=top_k_per_hop)

        if matches:
            for rank, m in enumerate(matches, 1):
                text = m["text"]
                source = m["source"]
                score = m["score"]

                text_hash = text[:80]
                is_dup = text_hash in seen_texts
                seen_texts.add(text_hash)

                dup_badge = " *(Already seen in earlier hop)*" if is_dup else ""
                hop_output.append(
                    f"- **[Result {rank}]** (Score: {score:.2f}{dup_badge})\n"
                    f"  *Source: {source}*\n"
                    f"  > \"{text}\""
                )
        else:
            hop_output.append("- *No vector matches returned for this hop.*")

        results_by_hop.append("\n".join(hop_output))

    return "\n\n".join(results_by_hop)


def _rerank_documents_impl(
    query: str,
    documents: Optional[List[str]] = None,
    top_n: int = 5,
    model: str = "pinecone-rerank-v0",
) -> str:
    clean_docs = [d.strip() for d in (documents or []) if d and d.strip()]
    
    if not clean_docs:
        # Automatically gather top candidates from the 8,970-passage canonical corpus
        candidates = search_hp_corpus_bm25(query, top_k=15)
        clean_docs = [c["text"] for c in candidates]

    if not clean_docs:
        return f"No candidate documents found to rerank for query '{query}'."

    pc = get_pinecone_client()
    if pc:
        try:
            res = pc.inference.rerank(
                model=model,
                query=query,
                documents=clean_docs,
                top_n=min(top_n, len(clean_docs)),
            )
            output = [f"### 🎯 Pinecone Neural Rerank Results (`{model}`) for: \"{query}\""]
            for rank, r in enumerate(res.data, 1):
                doc_text = r.document.get("text", "") if isinstance(r.document, dict) else str(r.document)
                output.append(
                    f"- **[Rank {rank}]** (Cross-Encoder Relevance Score: {r.score:.4f})\n"
                    f"  > \"{doc_text}\""
                )
            return "\n\n".join(output)
        except Exception as e:
            logger.warning(f"Pinecone inference rerank call failed, using BM25 cross-scorer: {e}")

    # BM25 / token cross-scoring fallback
    import re
    from rank_bm25 import BM25Okapi
    tokenized = [re.findall(r"\w+", d.lower()) for d in clean_docs]
    bm25 = BM25Okapi(tokenized)
    q_tokens = re.findall(r"\w+", query.lower())
    scores = bm25.get_scores(q_tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_n]

    output = [f"### 🎯 Rerank Results for: \"{query}\""]
    for rank, idx in enumerate(top_indices, 1):
        output.append(
            f"- **[Rank {rank}]** (Relevance Score: {scores[idx]:.2f})\n"
            f"  > \"{clean_docs[idx]}\""
        )
    return "\n\n".join(output)


@tool("rerank-documents")
def rerank_documents(
    query: str,
    documents: Optional[List[str]] = None,
    top_n: int = 5,
    model: str = "pinecone-rerank-v0",
) -> str:
    """Reranks candidate Harry Potter book passages against a specific question using Pinecone neural cross-encoders (`pinecone-rerank-v0`).
    
    Args:
        query: The user lore question or search query to score candidate passages against.
        documents: Optional list of candidate text strings. If omitted or empty, candidate passages are automatically fetched and cross-reranked.
        top_n: The number of highest-scoring passages to return (default 5).
        model: Pinecone reranker model ('pinecone-rerank-v0', 'cohere-rerank-3.5', or 'bge-reranker-v2-m3').
    
    Returns:
        Structured string of top reranked canonical passages ordered by cross-encoder score.
    """
    return _rerank_documents_impl(query=query, documents=documents, top_n=top_n, model=model)


@tool("rerank_documents")
def rerank_documents_underscore(
    query: str,
    documents: Optional[List[str]] = None,
    top_n: int = 5,
    model: str = "pinecone-rerank-v0",
) -> str:
    """Reranks candidate Harry Potter book passages against a specific question using Pinecone neural cross-encoders (`pinecone-rerank-v0`).
    
    Args:
        query: The user lore question or search query to score candidate passages against.
        documents: Optional list of candidate text strings. If omitted or empty, candidate passages are automatically fetched and cross-reranked.
        top_n: The number of highest-scoring passages to return (default 5).
        model: Pinecone reranker model ('pinecone-rerank-v0', 'cohere-rerank-3.5', or 'bge-reranker-v2-m3').
    
    Returns:
        Structured string of top reranked canonical passages ordered by cross-encoder score.
    """
    return _rerank_documents_impl(query=query, documents=documents, top_n=top_n, model=model)


@tool("pinecone_index_stats")
def pinecone_index_stats(index_name: str = "hpvdb-openai") -> str:
    """Returns real-time statistics, vector count, dimension, and namespaces for the Harry Potter Pinecone index."""
    pc = get_pinecone_client()
    if not pc:
        return "Pinecone API key is not configured."

    try:
        active_indexes = [idx.name for idx in pc.list_indexes()]
        if index_name not in active_indexes:
            if active_indexes:
                index_name = active_indexes[0]
            else:
                return f"No indexes found. Available: {active_indexes}"

        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        return (
            f"**Pinecone Index:** `{index_name}`\n"
            f"- **Total Vector Count:** {stats.get('total_vector_count', 0):,}\n"
            f"- **Dimension:** {stats.get('dimension', 'N/A')}\n"
            f"- **Index Fullness:** {stats.get('index_fullness', 0.0)}\n"
            f"- **Namespaces:** {list(stats.get('namespaces', {}).keys()) or ['(default)']}"
        )
    except Exception as exc:
        return f"Error retrieving index stats: {exc}"
