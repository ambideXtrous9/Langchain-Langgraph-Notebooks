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
    pc = get_pinecone_client()
    if not pc:
        return "Pinecone API key is not configured or client failed to initialize."

    try:
        # Check if index exists
        active_indexes = [idx.name for idx in pc.list_indexes()]
        if index_name not in active_indexes:
            if active_indexes:
                index_name = active_indexes[0]
            else:
                return f"No Pinecone indexes found. Active indexes: {active_indexes}"

        index = pc.Index(index_name)
        
        # Prepare embedding model
        openai_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        embeddings = None
        if openai_key:
            try:
                from langchain_openai import OpenAIEmbeddings
                embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    openai_api_key=openai_key,
                )
            except Exception:
                try:
                    from langchain_openai import OpenAIEmbeddings
                    embeddings = OpenAIEmbeddings(
                        model="text-embedding-ada-002",
                        openai_api_key=openai_key,
                    )
                except Exception as emb_err:
                    logger.warning(f"Could not initialize OpenAIEmbeddings: {emb_err}")

        results_by_hop = []
        seen_texts = set()

        for hop_idx, q in enumerate(queries, 1):
            hop_output = [f"### 🔗 HOP {hop_idx}: \"{q}\""]
            
            matches = []
            if embeddings:
                try:
                    query_vector = embeddings.embed_query(q)
                    query_res = index.query(
                        vector=query_vector,
                        top_k=top_k_per_hop,
                        include_metadata=True,
                        namespace=namespace if namespace else None,
                    )
                    matches = query_res.get("matches", [])
                except Exception as q_err:
                    logger.warning(f"Direct vector query failed for hop {hop_idx}: {q_err}")

            if not matches:
                # Attempt index search if integrated inference index
                try:
                    search_res = index.search(
                        query={"top_k": top_k_per_hop, "inputs": {"text": q}},
                        namespace=namespace if namespace else None,
                    )
                    matches = search_res.get("result", {}).get("hits", [])
                except Exception:
                    pass

            if matches:
                for rank, m in enumerate(matches, 1):
                    metadata = m.get("metadata", {}) or m.get("fields", {})
                    score = m.get("score", 0.0) or m.get("_score", 0.0)
                    text = (
                        metadata.get("text")
                        or metadata.get("page_content")
                        or metadata.get("chunk_text")
                        or metadata.get("content")
                        or str(metadata)
                    )
                    source = metadata.get("book") or metadata.get("title") or metadata.get("source") or "Harry Potter Canon"
                    chapter = metadata.get("chapter") or metadata.get("chapter_title") or ""

                    # Deduplicate identical paragraphs across hops
                    text_hash = text[:80]
                    is_dup = text_hash in seen_texts
                    seen_texts.add(text_hash)

                    dup_badge = " *(Already seen in earlier hop)*" if is_dup else ""
                    chapter_str = f", Chapter: {chapter}" if chapter else ""
                    hop_output.append(
                        f"- **[Result {rank}]** (Score: {score:.4f}{dup_badge})\n"
                        f"  *Source: {source}{chapter_str}*\n"
                        f"  > \"{text.strip()}\""
                    )
            else:
                hop_output.append("- *No vector matches returned for this hop.*")

            results_by_hop.append("\n".join(hop_output))

        return "\n\n".join(results_by_hop)

    except Exception as exc:
        logger.error(f"Error in pinecone_multihop_search: {exc}", exc_info=True)
        return f"Error executing Multi-Hop Pinecone search: {exc}"


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
