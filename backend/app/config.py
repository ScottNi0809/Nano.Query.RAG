'''
作用
集中读取 .env 和环境变量，供所有 service 和 route 使用。

需要实现的能力
LLM_PROVIDER: openai | azure | github | ollama | vllm
各 provider 的 API key / base URL
模型名称
ChromaDB 本地目录
chunk 大小和 overlap
docs 上传目录
'''

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor all relative paths to the backend/ directory (where pyproject.toml lives)
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["openai", "azure", "github", "ollama", "vllm"] = "github"

    github_token: str | None = None

    openai_api_key: str | None = None

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None

    ollama_base_url: str = "http://localhost:11434"

    vllm_base_url: str = "http://localhost:8100/v1"
    vllm_model_name: str | None = None

    model_name: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-large"

    chroma_persist_dir: str = "./chroma_db"
    docs_dir: str = "../docs"

    chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=200, ge=0)

    bm25_weight: float = Field(default=0.5, ge=0.0, le=1.0)

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """Resolve relative paths against _BACKEND_ROOT so that the same
        ChromaDB and docs directory are used regardless of the working
        directory from which the process is launched."""
        chroma = Path(self.chroma_persist_dir)
        if not chroma.is_absolute():
            self.chroma_persist_dir = str((_BACKEND_ROOT / chroma).resolve())

        docs = Path(self.docs_dir)
        if not docs.is_absolute():
            self.docs_dir = str((_BACKEND_ROOT / docs).resolve())

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()