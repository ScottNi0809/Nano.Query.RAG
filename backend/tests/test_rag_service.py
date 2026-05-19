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
    ) as MockQR:
        qr_instance = MagicMock()
        qr_result = MagicMock()
        qr_result.queries = ["rewritten query"]
        qr_instance.rewrite = AsyncMock(return_value=qr_result)
        MockQR.return_value = qr_instance

        service = RAGService(
            llm_service=mock_llm_service,
            vectorstore_service=mock_vectorstore_service,
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
        mock_vectorstore_service.similarity_search_with_score.return_value = [(doc, 0.3)]

        with patch("app.services.rag_service.QueryRewriteService"):
            service = RAGService(
                llm_service=MagicMock(),
                vectorstore_service=mock_vectorstore_service,
            )

        results = service._retrieve_for_queries(["q1", "q2"], k=4)
        # Same doc returned for both queries -> only 1 after dedup
        assert len(results) == 1

    def test_results_sorted_by_score(self, mock_vectorstore_service):
        """Results should be sorted ascending by score (lower = better)."""
        doc_a = Document(page_content="A" * 201, metadata={"file_name": "a.txt"})
        doc_b = Document(page_content="B" * 201, metadata={"file_name": "b.txt"})

        mock_vectorstore_service.similarity_search_with_score.side_effect = [
            [(doc_a, 0.8)],
            [(doc_b, 0.2)],
        ]

        with patch("app.services.rag_service.QueryRewriteService"):
            service = RAGService(
                llm_service=MagicMock(),
                vectorstore_service=mock_vectorstore_service,
            )

        results = service._retrieve_for_queries(["q1", "q2"], k=4)
        scores = [score for _, score in results]
        assert scores == sorted(scores)


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
                    0.5,
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
                    0.5,
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
