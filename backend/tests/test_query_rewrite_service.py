"""Tests for app.services.query_rewrite_service module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.query_rewrite_service import QueryRewriteService


class TestQueryRewriteService:
    @pytest.fixture
    def mock_chain_model(self):
        """Create a mock chat model whose chain returns controlled output."""
        model = MagicMock()
        return model

    def _make_service_with_response(self, response_text: str) -> QueryRewriteService:
        """Create a QueryRewriteService with a mocked chain returning given text."""
        model = MagicMock()
        service = QueryRewriteService(chat_model=model)
        service._chain = MagicMock()
        service._chain.ainvoke = AsyncMock(return_value=response_text)
        return service

    async def test_valid_single_query(self):
        service = self._make_service_with_response('{"queries": ["what is RAG?"]}')
        result = await service.rewrite("what is RAG")
        assert result.queries == ["what is RAG?"]
        assert result.original == "what is RAG"

    async def test_valid_multiple_queries(self):
        service = self._make_service_with_response(
            '{"queries": ["query one", "query two", "query three"]}'
        )
        result = await service.rewrite("complex question")
        assert len(result.queries) == 3
        assert result.queries == ["query one", "query two", "query three"]

    async def test_max_three_queries_enforced(self):
        service = self._make_service_with_response(
            '{"queries": ["q1", "q2", "q3", "q4", "q5"]}'
        )
        result = await service.rewrite("many queries")
        assert len(result.queries) == 3

    async def test_fallback_on_invalid_json(self):
        service = self._make_service_with_response("This is not JSON at all")
        result = await service.rewrite("original question")
        assert result.queries == ["original question"]

    async def test_fallback_on_empty_queries_list(self):
        service = self._make_service_with_response('{"queries": []}')
        result = await service.rewrite("my question")
        assert result.queries == ["my question"]

    async def test_fallback_on_queries_with_empty_strings(self):
        service = self._make_service_with_response('{"queries": ["", "  "]}')
        result = await service.rewrite("fallback test")
        assert result.queries == ["fallback test"]

    async def test_fallback_on_non_string_queries(self):
        service = self._make_service_with_response('{"queries": [123, null]}')
        result = await service.rewrite("type check")
        assert result.queries == ["type check"]

    async def test_strips_whitespace_from_queries(self):
        service = self._make_service_with_response('{"queries": ["  hello world  "]}')
        result = await service.rewrite("whitespace test")
        assert result.queries == ["hello world"]

    async def test_original_preserved(self):
        service = self._make_service_with_response('{"queries": ["rewritten"]}')
        result = await service.rewrite("my original")
        assert result.original == "my original"
