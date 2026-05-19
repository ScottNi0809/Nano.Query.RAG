"""Shared fixtures for all tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from app.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Settings with safe defaults that don't require external services."""
    return Settings(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        model_name="test-model",
        embedding_model="test-embed",
        chroma_persist_dir="./test_chroma_db",
        docs_dir="./test_docs",
        chunk_size=200,
        chunk_overlap=50,
        _env_file=None,
    )


@pytest.fixture
def mock_chat_model():
    """A fake chat model that returns a canned response."""
    model = MagicMock()
    model.ainvoke = AsyncMock(return_value=AIMessage(content="Test answer"))
    model.astream = AsyncMock()

    async def fake_stream(*args, **kwargs):
        for token in ["Test", " ", "answer"]:
            yield token

    model.astream.side_effect = fake_stream
    return model


@pytest.fixture
def mock_embeddings():
    """A fake embedding model returning fixed-dimension vectors."""
    embeddings = MagicMock()
    embeddings.embed_documents.return_value = [[0.1] * 384]
    embeddings.embed_query.return_value = [0.1] * 384
    return embeddings


@pytest.fixture
def sample_documents() -> list[Document]:
    """Sample documents for testing."""
    return [
        Document(
            page_content="FastAPI is a modern web framework for Python.",
            metadata={"source": "test.txt", "file_name": "test.txt", "source_type": "file"},
        ),
        Document(
            page_content="LangChain provides tools for building LLM applications.",
            metadata={"source": "langchain.txt", "file_name": "langchain.txt", "source_type": "file"},
        ),
    ]


@pytest.fixture
async def async_client():
    """AsyncClient for testing FastAPI endpoints with mocked dependencies."""
    with (
        patch("app.api.routes.health.get_vectorstore_service") as mock_vs,
        patch("app.api.routes.chat.get_rag_service") as mock_rag,
        patch("app.api.routes.documents.get_vectorstore_service") as mock_vs_docs,
        patch("app.api.routes.documents.get_document_service") as mock_doc,
        patch("app.api.routes.documents.get_settings") as mock_settings_fn,
    ):
        # Health endpoint mock
        vs_instance = MagicMock()
        vs_instance.health_check.return_value = {"status": "ok", "document_chunks": 5}
        vs_instance.list_documents.return_value = []
        vs_instance.delete_document.return_value = {"document_id": "test-id", "deleted": True}
        mock_vs.return_value = vs_instance
        mock_vs_docs.return_value = vs_instance

        # RAG service mock
        rag_instance = MagicMock()
        rag_instance.answer = AsyncMock(return_value={
            "answer": "Test answer",
            "sources": [{"title": "test.txt", "score": 0.9}],
        })
        mock_rag.return_value = rag_instance

        # Document service mock
        doc_instance = MagicMock()
        doc_instance.load_file.return_value = [
            Document(page_content="test content", metadata={"file_name": "test.txt"})
        ]
        doc_instance.split_documents.return_value = [
            Document(page_content="test content", metadata={"file_name": "test.txt"})
        ]
        mock_doc.return_value = doc_instance

        # Settings mock
        settings_instance = Settings(
            llm_provider="ollama",
            chroma_persist_dir="./test_chroma_db",
            docs_dir="./test_docs",
            _env_file=None,
        )
        mock_settings_fn.return_value = settings_instance

        vs_instance.add_documents.return_value = {"document_id": "test-id", "chunks_added": 1}

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
