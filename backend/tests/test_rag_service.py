"""Tests for app.services.rag_service module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.services.rag_service import RAGService


@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    model = MagicMock()
    model.ainvoke = AsyncMock(return_value=MagicMock(content="LLM answer"))
    service.get_chat_model.return_value = model
    service.get_embeddings.return_value = MagicMock()
    return service


@pytest.fixture
def mock_vectorstore_service():
    service = MagicMock()
    service.similarity_search_with_score.return_value = [
        (
            Document(
                page_content="Relevant chunk content here",
                metadata={
                    "document_id": "doc1",
                    "chunk_id": "doc1:0",
                    "file_name": "test.txt",
                    "source_type": "file",
                    "file_path": "/docs/test.txt",
                },
            ),
            0.5,
        ),
    ]
    return service


@pytest.fixture
def rag_service(mock_llm_service, mock_vectorstore_service):
    with patch(
        "app.services.rag_service.QueryRewriteService"
    ) as MockQR, patch(
        "app.services.rag_service.get_hybrid_retriever_service"
    ) as mock_hybrid_fn:
        qr_instance = MagicMock()
        qr_result = MagicMock()
        qr_result.queries = ["rewritten query"]
        qr_instance.rewrite = AsyncMock(return_value=qr_result)
        MockQR.return_value = qr_instance

        mock_hybrid = MagicMock()
        mock_hybrid.hybrid_search.return_value = [
            (
                Document(
                    page_content="Relevant chunk content here",
                    metadata={
                        "document_id": "doc1",
                        "chunk_id": "doc1:0",
                        "file_name": "test.txt",
                        "source_type": "file",
                        "file_path": "/docs/test.txt",
                    },
                ),
                {"rrf": 0.5, "bm25": 0.3, "vector": 0.7},
            ),
        ]
        mock_hybrid_fn.return_value = mock_hybrid

        service = RAGService(
            llm_service=mock_llm_service,
            vectorstore_service=mock_vectorstore_service,
            hybrid_retriever_service=mock_hybrid,
        )
        service.query_rewrite_service = qr_instance
        return service


class TestRAGServiceRetrieve:
    def test_deduplication(self, mock_vectorstore_service):
        """Identical content from different queries should be deduped."""
        doc = Document(
            page_content="Same content here repeated across queries to verify dedup logic works",
            metadata={"file_name": "a.txt"},
        )

        mock_hybrid = MagicMock()
        mock_hybrid.hybrid_search.return_value = [(doc, {"rrf": 0.3, "bm25": 0.2, "vector": 0.4})]

        with patch("app.services.rag_service.QueryRewriteService"), \
             patch("app.services.rag_service.get_hybrid_retriever_service", return_value=mock_hybrid):
            service = RAGService(
                llm_service=MagicMock(),
                vectorstore_service=mock_vectorstore_service,
                hybrid_retriever_service=mock_hybrid,
            )

        results = service._retrieve_for_queries(["q1", "q2"], k=4)
        # Same doc returned for both queries -> only 1 after dedup
        assert len(results) == 1

    def test_results_sorted_by_score_descending(self, mock_vectorstore_service):
        """Results should be sorted descending by RRF score (higher = better)."""
        doc_a = Document(page_content="A" * 201, metadata={"file_name": "a.txt"})
        doc_b = Document(page_content="B" * 201, metadata={"file_name": "b.txt"})

        mock_hybrid = MagicMock()
        mock_hybrid.hybrid_search.side_effect = [
            [(doc_a, {"rrf": 0.2, "bm25": 0.1, "vector": 0.3})],
            [(doc_b, {"rrf": 0.8, "bm25": 0.6, "vector": 0.9})],
        ]

        with patch("app.services.rag_service.QueryRewriteService"), \
             patch("app.services.rag_service.get_hybrid_retriever_service", return_value=mock_hybrid):
            service = RAGService(
                llm_service=MagicMock(),
                vectorstore_service=mock_vectorstore_service,
                hybrid_retriever_service=mock_hybrid,
            )

        results = service._retrieve_for_queries(["q1", "q2"], k=4)
        scores = [s["rrf"] for _, s in results]
        assert scores == sorted(scores, reverse=True)


class TestRAGServiceAnswer:
    async def test_answer_returns_answer_and_sources(self, rag_service):
        with patch.object(rag_service, "_retrieve_for_queries") as mock_retrieve:
            mock_retrieve.return_value = [
                (
                    Document(
                        page_content="Context chunk",
                        metadata={
                            "document_id": "d1",
                            "chunk_id": "d1:0",
                            "file_name": "test.txt",
                            "source_type": "file",
                            "file_path": "/test.txt",
                        },
                    ),
                    {"rrf": 0.5, "bm25": 0.3, "vector": 0.7},
                )
            ]

            # Mock the LLM chain
            with patch("app.services.rag_service.RAG_PROMPT") as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value="The answer is 42")
                mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))

                result = await rag_service.answer("what is the meaning?")

        assert "answer" in result
        assert "sources" in result
        assert isinstance(result["sources"], list)


class TestRAGServiceStream:
    async def test_stream_yields_tokens_sources_done(self, rag_service):
        with patch.object(rag_service, "_retrieve_for_queries") as mock_retrieve:
            mock_retrieve.return_value = [
                (
                    Document(
                        page_content="Context",
                        metadata={
                            "document_id": "d1",
                            "chunk_id": "d1:0",
                            "file_name": "test.txt",
                            "source_type": "file",
                            "file_path": "/test.txt",
                        },
                    ),
                    {"rrf": 0.5, "bm25": 0.3, "vector": 0.7},
                )
            ]

            # Mock the chain's astream
            async def fake_astream(*args, **kwargs):
                for tok in ["Hello", " ", "world"]:
                    yield tok

            with patch("app.services.rag_service.RAG_PROMPT") as mock_prompt:
                mock_chain = MagicMock()
                mock_chain.astream = fake_astream
                mock_prompt.__or__ = MagicMock(return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)))

                events = []
                async for event in rag_service.stream_answer("test question"):
                    events.append(event)

        event_types = [e["event"] for e in events]
        assert "token" in event_types
        assert event_types[-2] == "sources"
        assert event_types[-1] == "done"
