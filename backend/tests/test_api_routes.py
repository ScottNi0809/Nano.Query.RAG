"""Tests for API routes."""

import io

import pytest


class TestHealthRoute:
    async def test_health_returns_ok(self, async_client):
        response = await async_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "wtg-query-rag"
        assert data["chroma"]["status"] == "ok"


class TestChatRoute:
    async def test_chat_non_stream(self, async_client):
        response = await async_client.post(
            "/api/chat",
            json={"question": "What is RAG?", "stream": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data

    async def test_chat_empty_question_rejected(self, async_client):
        response = await async_client.post(
            "/api/chat",
            json={"question": "", "stream": False},
        )
        assert response.status_code == 422


class TestDocumentsRoute:
    async def test_list_documents(self, async_client):
        response = await async_client.get("/api/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)

    async def test_upload_txt_file(self, async_client, tmp_path):
        file_content = b"This is test content for upload."
        response = await async_client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["file_name"] == "test.txt"
        assert data["chunks_added"] == 1

    async def test_upload_unsupported_format_rejected(self, async_client):
        response = await async_client.post(
            "/api/documents/upload",
            files={"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        )
        assert response.status_code == 400

    async def test_delete_document(self, async_client):
        response = await async_client.delete("/api/documents/test-id")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
