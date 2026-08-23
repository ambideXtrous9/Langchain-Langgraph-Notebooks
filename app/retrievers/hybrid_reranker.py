"""Enhanced Retriever with Hybrid Search (BM25 + Semantic) and Source-Aware Reranking."""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
from pydantic import Field, PrivateAttr
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _ensure_nltk():
    """Ensure NLTK punkt tokenizer is available."""
    try:
        import nltk
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            try:
                nltk.download("punkt", quiet=True)
                nltk.download("punkt_tab", quiet=True)
            except Exception as e:
                logger.warning(f"Could not download NLTK punkt data: {e}")
    except ImportError:
        logger.warning("NLTK is not installed. Simple whitespace tokenization will be used as fallback.")


def _tokenize(text: str) -> List[str]:
    """Tokenize text using NLTK word_tokenize with fallback."""
    try:
        from nltk.tokenize import word_tokenize
        return word_tokenize(text.lower())
    except Exception:
        return text.lower().split()


class EnhancedGDNCRetriever(BaseRetriever):
    """Enhanced retriever with hybrid search (BM25 + semantic) and source-aware reranking.

    Combines the strengths of sparse (BM25) and dense (semantic) retrieval,
    with configurable weights, source-frequency awareness, and noise filtering.
    """

    # Required parameters
    base_retriever: Optional[BaseRetriever] = Field(
        default=None, description="Base dense retriever (e.g. FAISS, PGVector, In-Memory)"
    )

    # Optional parameters with defaults
    k: int = Field(default=5, description="Number of documents to return")
    rerank: bool = Field(default=True, description="Enable/disable reranking")
    model_name: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-12-v2",
        description="Cross-encoder model for reranking",
    )
    bm25_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for BM25 score in hybrid search (normalized with semantic_weight)",
    )
    min_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum score threshold for including results",
    )

    # Private attributes
    _reranker: Any = PrivateAttr(default=None)
    _bm25: Any = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        _ensure_nltk()
        self._init_reranker()

    def _init_reranker(self):
        """Initializes the CrossEncoder model if reranking is enabled."""
        if self.rerank and self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(self.model_name)
                logger.info(f"CrossEncoder '{self.model_name}' loaded successfully.")
            except Exception as e:
                logger.warning(
                    f"Could not load CrossEncoder model '{self.model_name}': {e}. "
                    "Operating with BM25 / dense scores only."
                )
                self._reranker = None

    def _should_skip_doc(self, doc: Document) -> bool:
        """Check if document should be skipped (index/reference/title/blank pages)."""
        if not doc.page_content.strip():
            return True

        source = str(doc.metadata.get("source", "")).lower()
        page_content = doc.page_content.lower()

        # Skip conditions for metadata
        skip_keywords = ["index", "reference", "contents", "title page", "table of contents"]
        if any(keyword in source for keyword in skip_keywords):
            return True

        # Check page content for common document noise indicators
        content_indicators = [
            "this page intentionally left blank",
            "table of contents",
            "index",
            "references",
            "title page",
        ]
        return any(indicator in page_content for indicator in content_indicators)

    def _compute_scores(self, query: str, docs: List[Document]) -> List[float]:
        """Compute combined BM25 and semantic scores for candidate documents."""
        if not docs:
            return []

        # 1. BM25 Sparse Scoring
        try:
            from rank_bm25 import BM25Okapi
            tokenized_corpus = [_tokenize(doc.page_content) for doc in docs]
            self._bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = _tokenize(query)
            bm25_scores = np.array(self._bm25.get_scores(tokenized_query), dtype=float)
        except Exception as e:
            logger.warning(f"BM25 scoring failed: {e}. Defaulting to equal sparse weights.")
            bm25_scores = np.ones(len(docs), dtype=float)

        # 2. Semantic CrossEncoder Reranking
        if self._reranker is not None:
            pairs = [(query, doc.page_content) for doc in docs]
            try:
                semantic_scores = np.array(self._reranker.predict(pairs), dtype=float)
            except Exception as e:
                logger.warning(f"CrossEncoder prediction failed: {e}")
                semantic_scores = np.ones(len(docs), dtype=float)
        else:
            semantic_scores = np.ones(len(docs), dtype=float)

        # 3. Normalize scores to [0, 1] range
        def normalize(scores: np.ndarray) -> np.ndarray:
            if not scores.size or np.max(scores) == np.min(scores):
                return np.ones_like(scores) * 0.5
            min_val, max_val = np.min(scores), np.max(scores)
            return (scores - min_val) / (max_val - min_val + 1e-9)

        bm25_norm = normalize(bm25_scores)
        semantic_norm = normalize(semantic_scores)

        # Combine scores using weighted sum
        combined = (self.bm25_weight * bm25_norm) + ((1.0 - self.bm25_weight) * semantic_norm)
        return combined.tolist()

    def get_relevant_documents(self, query: str) -> List[Document]:
        """Retrieve and rerank documents based on the query."""
        if self.base_retriever is None:
            return []

        # Get initial documents from base retriever
        docs = self.base_retriever.invoke(query)
        if not docs or not self.rerank:
            return docs[: self.k]

        # Filter out index/reference/title pages
        filtered_docs = [doc for doc in docs if not self._should_skip_doc(doc)]
        if not filtered_docs:
            return []

        # Compute hybrid scores for all filtered documents
        scores = self._compute_scores(query, filtered_docs)

        # Get source distribution for source-aware weighting
        sources = [str(doc.metadata.get("source", "general")).lower() for doc in filtered_docs]
        source_counts: Dict[str, int] = {}
        for src in sources:
            source_counts[src] = source_counts.get(src, 0) + 1
        max_source_count = max(source_counts.values()) if source_counts else 1

        # Score, apply source weighting, and sort documents
        scored_docs = []
        for doc, score, source in zip(filtered_docs, scores, sources):
            source_weight = 0.5 + (0.5 * (source_counts[source] / max_source_count))
            final_score = score * source_weight

            if final_score >= self.min_score:
                scored_docs.append((final_score, doc))

        # Sort by score descending and return top-k
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[: self.k]]

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        """Required synchronous method for BaseRetriever."""
        return self.get_relevant_documents(query)

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        """Required asynchronous method for BaseRetriever."""
        return self.get_relevant_documents(query)
