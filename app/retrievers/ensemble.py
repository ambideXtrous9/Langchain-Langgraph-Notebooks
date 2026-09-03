import logging
from typing import Dict, List, Optional
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

try:
    from langchain_classic.retrievers import EnsembleRetriever
except ImportError:
    try:
        from langchain.retrievers import EnsembleRetriever
    except ImportError:
        try:
            from langchain.retrievers.ensemble import EnsembleRetriever
        except ImportError:
            EnsembleRetriever = None

logger = logging.getLogger(__name__)


class InMemoryDocRetriever(BaseRetriever):
    """Simple in-memory keyword / substring retriever for testing and fallback."""

    docs: List[Document] = []
    k: int = 5

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        query_lower = query.lower()
        scored_docs = []
        for doc in self.docs:
            score = sum(1 for word in query_lower.split() if word in doc.page_content.lower())
            scored_docs.append((score, doc))
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[: self.k]]

    async def _aget_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        return self._get_relevant_documents(query, run_manager=run_manager)


def create_in_memory_retriever(
    documents: Optional[List[Document]] = None,
    domain: str = "general",
    k: int = 5,
) -> BaseRetriever:
    """Helper to create an in-memory document retriever."""
    if documents is None:
        documents = [
            Document(
                page_content="ISO/IEC 27001 Information Security Management Systems requires organizations to establish security controls.",
                metadata={"source": "iso", "section": "27001"},
            ),
            Document(
                page_content="NIST SP 800-53 Security and Privacy Controls for Information Systems and Organizations.",
                metadata={"source": "nist", "standard": "800-53"},
            ),
            Document(
                page_content="Enterprise Architecture Guidance: Cloud System Verification and Security Baseline Auditing.",
                metadata={"source": "guidance", "type": "architecture"},
            ),
        ]
    return InMemoryDocRetriever(docs=documents, k=k)


def make_ensemble(
    retriever_map: Dict[str, Optional[BaseRetriever]],
    selected_keys: List[str],
    weights: Optional[List[float]] = None,
) -> Optional[BaseRetriever]:
    """Creates an EnsembleRetriever dynamically combining multiple domain vector stores.

    Args:
        retriever_map: Dictionary mapping domain names (e.g. 'cfr', 'sng', 'gdnc') to retrievers.
        selected_keys: List of domain keys to include in the ensemble.
        weights: Optional relative weighting list matching selected_keys length.

    Returns:
        EnsembleRetriever or None if no valid retrievers found.
    """
    valid_retrievers = [retriever_map[k] for k in selected_keys if retriever_map.get(k) is not None]
    if not valid_retrievers:
        logger.warning("No valid retrievers selected or loaded for ensemble.")
        return None

    # If weights not provided, default to equal weighting
    if weights is None:
        weights = [1.0 / len(valid_retrievers)] * len(valid_retrievers)

    return EnsembleRetriever(retrievers=valid_retrievers, weights=weights)
