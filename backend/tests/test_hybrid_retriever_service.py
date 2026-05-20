"""Tests for app.services.hybrid_retriever_service module."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.hybrid_retriever_service import HybridRetrieverService


@pytest.fixture
def mock_vectorstore_service():
    service = MagicMock()
    # Mock ChromaDB collection.get() for BM25 index building
    service.vectorstore._collection.get.return_value = {
        "ids": ["doc1:0", "doc1:1", "doc2:0"],
        "documents": [
            "FastAPI is a modern web framework for building APIs with Python",
            "LangChain provides tools for building LLM applications easily",
            "BM25 is a ranking function used in information retrieval",
        ],
        "metadatas": [
            {"document_id": "doc1", "chunk_id": "doc1:0", "file_name": "fastapi.txt"},
            {"document_id": "doc1", "chunk_id": "doc1:1", "file_name": "langchain.txt"},
            {"document_id": "doc2", "chunk_id": "doc2:0", "file_name": "bm25.txt"},
        ],
    }
    # Mock vector search results
    service.similarity_search_with_score.return_value = [
        (
            Document(
                page_content="FastAPI is a modern web framework for building APIs with Python",
                metadata={"document_id": "doc1", "chunk_id": "doc1:0", "file_name": "fastapi.txt"},
            ),
            0.3,
        ),
        (
            Document(
                page_content="LangChain provides tools for building LLM applications easily",
                metadata={"document_id": "doc1", "chunk_id": "doc1:1", "file_name": "langchain.txt"},
            ),
            0.5,
        ),
    ]
    return service


@pytest.fixture
def mock_settings():
    from app.config import Settings
    return Settings(
        llm_provider="ollama",
        bm25_weight=0.5,
        chroma_persist_dir="./test_chroma_db",
        _env_file=None,
    )


@pytest.fixture
def hybrid_service(mock_vectorstore_service, mock_settings):
    return HybridRetrieverService(
        vectorstore_service=mock_vectorstore_service,
        settings=mock_settings,
    )


class TestHybridRetrieverTokenize:
    def test_basic_tokenization(self):
        tokens = HybridRetrieverService._tokenize("Hello World! This is a TEST.")
        assert tokens == ["hello", "world", "this", "is", "a", "test"]

    def test_empty_string(self):
        tokens = HybridRetrieverService._tokenize("")
        assert tokens == []

    def test_special_characters(self):
        tokens = HybridRetrieverService._tokenize("BM25-based retrieval (v2.0)")
        assert "bm25" in tokens
        assert "retrieval" in tokens
        assert "v2" in tokens


class TestHybridRetrieverBM25:
    def test_build_index(self, hybrid_service):
        hybrid_service._build_bm25_index()
        assert hybrid_service._bm25 is not None
        assert len(hybrid_service._bm25_docs) == 3

    def test_bm25_search_returns_results(self, hybrid_service):
        results = hybrid_service.bm25_search("BM25 ranking information retrieval", k=2)
        assert len(results) <= 2
        assert all(isinstance(doc, Document) for doc, _ in results)
        # BM25 doc should rank highest for this query
        assert "BM25" in results[0][0].page_content or "ranking" in results[0][0].page_content

    def test_bm25_search_empty_corpus(self, mock_settings):
        vs = MagicMock()
        vs.vectorstore._collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        service = HybridRetrieverService(vectorstore_service=vs, settings=mock_settings)
        results = service.bm25_search("anything", k=4)
        assert results == []

    def test_refresh_rebuilds_index(self, hybrid_service):
        hybrid_service.refresh_index()
        assert hybrid_service._bm25 is not None
        assert len(hybrid_service._bm25_docs) == 3


class TestHybridRetrieverHybridSearch:
    def test_hybrid_returns_merged_results(self, hybrid_service):
        results = hybrid_service.hybrid_search("FastAPI web framework", k=4)
        assert len(results) > 0
        # Each result is (Document, rrf_score)
        for doc, score in results:
            assert isinstance(doc, Document)
            assert isinstance(score, float)
            assert score > 0

    def test_hybrid_respects_k(self, hybrid_service):
        results = hybrid_service.hybrid_search("Python", k=2)
        assert len(results) <= 2

    def test_hybrid_deduplicates(self, hybrid_service):
        """Same document from both BM25 and vector should appear once with combined score."""
        results = hybrid_service.hybrid_search("FastAPI modern web framework", k=4)
        content_keys = [doc.page_content[:200] for doc, _ in results]
        assert len(content_keys) == len(set(content_keys))

    def test_hybrid_with_zero_bm25_weight(self, mock_vectorstore_service):
        """When bm25_weight=0, should behave like pure vector search."""
        from app.config import Settings
        settings = Settings(llm_provider="ollama", bm25_weight=0.0, _env_file=None)
        service = HybridRetrieverService(
            vectorstore_service=mock_vectorstore_service,
            settings=settings,
        )
        results = service.hybrid_search("test", k=4)
        # Should still return results (from vector path)
        assert len(results) > 0

    def test_hybrid_with_full_bm25_weight(self, mock_vectorstore_service):
        """When bm25_weight=1.0, only BM25 contributes to ranking."""
        from app.config import Settings
        settings = Settings(llm_provider="ollama", bm25_weight=1.0, _env_file=None)
        service = HybridRetrieverService(
            vectorstore_service=mock_vectorstore_service,
            settings=settings,
        )
        results = service.hybrid_search("BM25 information retrieval", k=4)
        assert len(results) > 0
