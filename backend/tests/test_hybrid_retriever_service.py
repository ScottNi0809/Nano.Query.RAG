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
        """测试基础英文分词"""
        tokens = HybridRetrieverService._tokenize("Hello World! This is a TEST.")
        assert "hello" in tokens
        assert "world" in tokens
        assert "this" in tokens

    def test_empty_string(self):
        """测试空字符串"""
        tokens = HybridRetrieverService._tokenize("")
        assert tokens == []

    def test_composite_words(self):
        """测试复合词：Qwen2.5、Python3.11 等"""
        tokens = HybridRetrieverService._tokenize("Qwen2.5 and Python3.11")
        assert "qwen2.5" in tokens or "qwen" in tokens  # jieba/复合词处理
        assert "python3.11" in tokens or "python" in tokens
        assert "and" in tokens

    def test_chinese_tokenization(self):
        """测试中文分词"""
        tokens = HybridRetrieverService._tokenize("千问是开源大模型")
        assert len(tokens) > 0
        # jieba 应该分出 "千问"、"大模型" 等词
        content = "".join(tokens)
        assert "千问" in content or "千" in tokens
        assert "大模型" in content or "大" in tokens

    def test_mixed_chinese_english(self):
        """测试中英混合"""
        tokens = HybridRetrieverService._tokenize("千问 Qwen2.5 是 LLM 大模型")
        # 应该同时包含中文词和英文词
        assert len(tokens) > 3
        text = "".join(tokens)
        assert "qwen" in text or "qwen2.5" in text
        assert "llm" in text


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
        # Each result is (Document, scores_dict)
        for doc, scores in results:
            assert isinstance(doc, Document)
            assert isinstance(scores, dict)
            assert "rrf" in scores
            assert "bm25" in scores
            assert "vector" in scores
            assert scores["rrf"] > 0

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
