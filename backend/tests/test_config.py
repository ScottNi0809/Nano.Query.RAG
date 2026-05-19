"""Tests for app.config module."""

import pytest

from app.config import Settings


class TestSettings:
    def test_default_provider_is_github(self):
        settings = Settings(llm_provider="github", _env_file=None)
        assert settings.llm_provider == "github"

    def test_default_chunk_size(self):
        settings = Settings(_env_file=None)
        assert settings.chunk_size == 1000
        assert settings.chunk_overlap == 200

    def test_chunk_size_minimum(self):
        with pytest.raises(Exception):
            Settings(chunk_size=50, _env_file=None)

    def test_chunk_overlap_minimum(self):
        with pytest.raises(Exception):
            Settings(chunk_overlap=-1, _env_file=None)

    def test_custom_values(self):
        settings = Settings(
            llm_provider="ollama",
            model_name="llama3",
            chroma_persist_dir="/tmp/test",
            chunk_size=500,
            chunk_overlap=100,
            _env_file=None,
        )
        assert settings.llm_provider == "ollama"
        assert settings.model_name == "llama3"
        assert settings.chroma_persist_dir == "/tmp/test"
        assert settings.chunk_size == 500
        assert settings.chunk_overlap == 100

    def test_invalid_provider_rejected(self):
        with pytest.raises(Exception):
            Settings(llm_provider="invalid_provider", _env_file=None)

    def test_cors_origins_default(self):
        settings = Settings(_env_file=None)
        assert "http://localhost:5173" in settings.cors_origins
