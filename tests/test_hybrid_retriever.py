"""Unit Tests for Hybrid Reranker and Source-Aware Filtering."""

import pytest
from langchain_core.documents import Document
from app.retrievers.hybrid_reranker import EnhancedGDNCRetriever
from app.retrievers.ensemble import create_in_memory_retriever, make_ensemble


def test_should_skip_doc_filters():
    """Tests document filtering for index, TOC, and blank pages."""
    retriever = EnhancedGDNCRetriever(base_retriever=None, rerank=False)

    blank_doc = Document(page_content="   ", metadata={"source": "doc1.pdf"})
    assert retriever._should_skip_doc(blank_doc) is True

    toc_doc = Document(page_content="1. Introduction\n2. Device Overview", metadata={"source": "table of contents"})
    assert retriever._should_skip_doc(toc_doc) is True

    valid_doc = Document(
        page_content="FDA 21 CFR Part 820 requires quality system controls.",
        metadata={"source": "cfr820.pdf"},
    )
    assert retriever._should_skip_doc(valid_doc) is False


def test_in_memory_retrieval():
    """Tests in-memory retriever search."""
    base_retriever = create_in_memory_retriever()
    docs = base_retriever.invoke("quality system regulation")
    assert len(docs) > 0
    assert any("820" in doc.page_content for doc in docs)


def test_ensemble_retriever_creation():
    """Tests dynamic ensemble retriever combining multiple sources."""
    retriever_map = {
        "cfr": create_in_memory_retriever(),
        "sng": create_in_memory_retriever(),
        "missing": None,
    }
    ensemble = make_ensemble(retriever_map, selected_keys=["cfr", "sng"])
    assert ensemble is not None
    assert len(ensemble.retrievers) == 2
