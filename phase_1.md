# Phase 1 实现指南 — Backend API Foundation

> 本文只覆盖 `Plan.md` 中的 **Phase 1: Backend API Foundation**。目标是把当前 CLI 版 `rag.py` 重构为可被 React 前端调用的 FastAPI 后端，并跑通最小端到端 RAG 流程。

---

## 1. 当前状态核对

根据当前本地文件和 git changes，Phase 1 已经完成了一小部分骨架，但核心功能还没有实现。

### 已经存在

| 文件 / 目录 | 当前状态 | 说明 |
|---|---|---|
| `backend/pyproject.toml` | 已存在 | 基础依赖已写入，但建议补充 `langchain-ollama` |
| `backend/app/main.py` | 已存在 | FastAPI 应用和 CORS 已有，但只注册了 health 路由 |
| `backend/app/api/routes/health.py` | 已存在 | 返回简单健康状态，但还没有检查 ChromaDB |
| `backend/app/api/routes/__init__.py` | 已存在 | 只导出了 `health_router` |
| `.env.example` | 已更新 | 已包含 openai / azure / github / ollama / vllm 配置项 |
| `backend/app/config.py` | 空文件 | 需要实现 Pydantic Settings |
| `backend/app/api/routes/chat.py` | 空文件 | 需要实现 `/api/chat` |
| `backend/app/api/routes/documents.py` | 空文件 | 需要实现文档上传、列表、删除 |
| `services/*.py` | 空文件，且位置不符合 Plan | 应迁移到 `backend/app/services/` 下 |

### 主要缺口

1. `backend/app/config.py` 尚未实现集中配置。
2. `backend/app/services/` 目录为空，需要实现四个服务：
   - `llm_service.py`
   - `document_service.py`
   - `vectorstore_service.py`
   - `rag_service.py`
3. `chat.py` 和 `documents.py` 是空文件。
4. `main.py` 只注册了 health 路由，没有注册 chat/documents。
5. `health.py` 没有检查 ChromaDB 连通性。
6. 根目录下新增的 `services/` 目录不符合目标结构，建议移除或迁移。
7. `rag.py` 仍保留旧 CLI 逻辑，并且存在重复 `else` 的语法错误，应在 Phase 1 末尾修正为兼容入口，或暂时不再作为主入口使用。

---

## 2. Phase 1 的完成标准

Phase 1 完成后，应至少满足以下条件：

| 能力 | 目标 |
|---|---|
| FastAPI 启动 | `uvicorn app.main:app --reload --port 8000` 可以正常启动 |
| 健康检查 | `GET /api/health` 返回 `status=ok`，并包含 ChromaDB 状态 |
| 文档上传 | `POST /api/documents/upload` 可上传 `.md` / `.txt` / `.pdf` |
| 文档索引 | 上传后文件被加载、分块、写入 ChromaDB |
| 文档列表 | `GET /api/documents` 可列出已索引文档 |
| 文档删除 | `DELETE /api/documents/{document_id}` 可删除某个文档的向量块 |
| RAG 问答 | `POST /api/chat` 可根据已上传文档回答问题 |
| 来源引用 | chat 响应包含 `sources` |
| 多 Provider 配置 | `LLM_PROVIDER` 至少支持 `github` 和 `openai`，建议同时留好 `ollama` / `vllm` 分支 |

---

## 3. 推荐最终目录结构（Phase 1）

当前根目录下的 `services/` 不符合 Plan。建议把服务层放到 `backend/app/services/`。

```text
WTG.Query.RAG/
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── health.py
│       │       ├── chat.py
│       │       └── documents.py
│       └── services/
│           ├── __init__.py
│           ├── llm_service.py
│           ├── document_service.py
│           ├── vectorstore_service.py
│           └── rag_service.py
├── docs/
├── .env.example
└── rag.py
```

建议处理方式：

```bash
# 在 WSL / bash 中执行
mkdir -p backend/app/services
rm -rf services
```

如果不想立刻删除根目录 `services/`，至少不要继续往里面写代码，避免后续 import 路径混乱。

---

## 4. 需要补充的依赖

`backend/pyproject.toml` 已经有大部分依赖。为了支持 Ollama provider，建议增加：

```toml
"langchain-ollama>=0.2.0",
```

更新后的核心依赖建议如下：

```toml
[project]
name = "wtg-query-rag"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic-settings>=2.0.0",
    "langchain>=0.3.0",
    "langchain-community>=0.3.0",
    "langchain-openai>=0.3.0",
    "langchain-chroma>=0.2.0",
    "langchain-ollama>=0.2.0",
    "chromadb>=0.6.0",
    "pypdf>=4.0.0",
    "unstructured>=0.16.0",
    "python-dotenv>=1.0.0",
    "sse-starlette>=2.0.0",
    "python-multipart>=0.0.18",
]
```

安装命令：

```bash
conda activate RAG
cd /mnt/c/git/GitHub/wisetechglobal/wtg.query.rag
pip install -r requirements.txt
pip install -e ./backend
```

如果暂时不做 editable install，也可以直接在 `backend/` 目录下启动：

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

---

## 5. 文件实现细节

下面是 Phase 1 每个目标文件建议填入的代码。第一版目标是**能跑通最小端到端流程**，不追求过度抽象。

---

## 5.1 `backend/app/config.py`

### 作用

集中读取 `.env` 和环境变量，供所有 service 和 route 使用。

### 需要实现的能力

- `LLM_PROVIDER`: `openai | azure | github | ollama | vllm`
- 各 provider 的 API key / base URL
- 模型名称
- ChromaDB 本地目录
- chunk 大小和 overlap
- docs 上传目录

### 建议代码

```python
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 注意点

- `env_file=(".env", "../.env")` 是为了兼容从 repo root 或 `backend/` 目录启动。
- `docs_dir="../docs"` 是因为开发时通常从 `backend/` 目录启动 uvicorn。
- 如果之后改为 Docker，路径可通过环境变量覆盖。

---

## 5.2 `backend/app/services/llm_service.py`

### 作用

根据 `LLM_PROVIDER` 创建对应的 LLM 和 embedding 实例。

### Provider 策略

| Provider | Chat Model | Embedding Model | 说明 |
|---|---|---|---|
| `github` | `ChatOpenAI` + GitHub Models base URL | `OpenAIEmbeddings` + GitHub Models base URL | 当前默认 |
| `openai` | `ChatOpenAI` | `OpenAIEmbeddings` | 直接 OpenAI |
| `azure` | `AzureChatOpenAI` | `AzureOpenAIEmbeddings` | 企业 Azure OpenAI |
| `ollama` | `ChatOllama` | `OllamaEmbeddings` | 本地开发最方便 |
| `vllm` | `ChatOpenAI` + vLLM base URL | `OpenAIEmbeddings` + vLLM base URL | 需要 vLLM 提供 embedding endpoint，否则后续应拆分 embedding provider |

### 建议代码

```python
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import (
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    ChatOpenAI,
    OpenAIEmbeddings,
)

from app.config import Settings, get_settings


GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


class LLMService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_chat_model(self) -> BaseChatModel:
        provider = self.settings.llm_provider

        if provider == "github":
            if not self.settings.github_token:
                raise ValueError("GITHUB_TOKEN is required when LLM_PROVIDER=github")
            return ChatOpenAI(
                model=self.settings.model_name,
                temperature=0,
                api_key=self.settings.github_token,
                base_url=GITHUB_MODELS_BASE_URL,
            )

        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            return ChatOpenAI(
                model=self.settings.model_name,
                temperature=0,
                api_key=self.settings.openai_api_key,
            )

        if provider == "azure":
            if not self.settings.azure_openai_endpoint or not self.settings.azure_openai_api_key:
                raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required when LLM_PROVIDER=azure")
            return AzureChatOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                azure_deployment=self.settings.azure_openai_deployment or self.settings.model_name,
                api_version="2024-02-15-preview",
                temperature=0,
            )

        if provider == "ollama":
            return ChatOllama(
                model=self.settings.model_name,
                base_url=self.settings.ollama_base_url,
                temperature=0,
            )

        if provider == "vllm":
            return ChatOpenAI(
                model=self.settings.vllm_model_name or self.settings.model_name,
                temperature=0,
                api_key="not-needed",
                base_url=self.settings.vllm_base_url,
            )

        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    def get_embeddings(self) -> Embeddings:
        provider = self.settings.llm_provider

        if provider == "github":
            if not self.settings.github_token:
                raise ValueError("GITHUB_TOKEN is required when LLM_PROVIDER=github")
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.github_token,
                base_url=GITHUB_MODELS_BASE_URL,
            )

        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.openai_api_key,
            )

        if provider == "azure":
            if not self.settings.azure_openai_endpoint or not self.settings.azure_openai_api_key:
                raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required when LLM_PROVIDER=azure")
            return AzureOpenAIEmbeddings(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                azure_deployment=self.settings.azure_openai_embedding_deployment or self.settings.embedding_model,
                api_version="2024-02-15-preview",
            )

        if provider == "ollama":
            return OllamaEmbeddings(
                model=self.settings.embedding_model,
                base_url=self.settings.ollama_base_url,
            )

        if provider == "vllm":
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key="not-needed",
                base_url=self.settings.vllm_base_url,
            )

        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def get_llm_service() -> LLMService:
    return LLMService()
```

### Ollama 本地模型建议

如果用 Ollama，本地 `.env` 可先这样配置：

```env
LLM_PROVIDER=ollama
MODEL_NAME=qwen2.5:14b
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

需要先执行：

```bash
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

### vLLM 注意点

vLLM 更适合作为 chat model server。Embedding 是否可用取决于你是否另起一个 embedding model endpoint。第一版如果要简单稳定，建议：

- 本地开发：`ollama` 同时负责 chat + embedding
- 云端开发：`github` / `openai` 同时负责 chat + embedding
- vLLM：先只用于生产 chat，embedding provider 后续单独拆分

---

## 5.3 `backend/app/services/document_service.py`

### 作用

负责加载文件和分块，把上传的 PDF / Markdown / TXT 转成 LangChain `Document`。

### 建议代码

```python
import glob
import os
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)

from app.config import Settings, get_settings


class DocumentService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def load_file(self, file_path: str) -> list[Document]:
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == ".pdf":
            loader = PyPDFLoader(str(path))
        elif extension == ".md":
            loader = UnstructuredMarkdownLoader(str(path))
        elif extension in (".txt", ".text"):
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        documents = loader.load()
        for document in documents:
            document.metadata.update(
                {
                    "source_type": "file",
                    "file_path": str(path),
                    "file_name": path.name,
                    "file_type": extension.lstrip("."),
                }
            )
        return documents

    def load_directory(self, directory: str | None = None) -> list[Document]:
        docs_dir = directory or self.settings.docs_dir
        documents: list[Document] = []

        for file_path in glob.glob(os.path.join(docs_dir, "**", "*"), recursive=True):
            if not os.path.isfile(file_path):
                continue
            if Path(file_path).suffix.lower() not in (".pdf", ".md", ".txt", ".text"):
                continue
            documents.extend(self.load_file(file_path))

        return documents

    def split_documents(self, documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        return splitter.split_documents(documents)


def get_document_service() -> DocumentService:
    return DocumentService()
```

### 第一版不需要做的事

- 不需要实现 Confluence / Git / ediProd，这些属于 Phase 2。
- 不需要复杂的去重逻辑，这在 Phase 2 ingestion orchestrator 中处理更合适。

---

## 5.4 `backend/app/services/vectorstore_service.py`

### 作用

封装 ChromaDB 操作：初始化、添加文档、检索、列表、删除、健康检查。

### 建议代码

```python
from collections import defaultdict
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import Settings, get_settings
from app.services.llm_service import LLMService


class VectorStoreService:
    def __init__(self, settings: Settings | None = None, llm_service: LLMService | None = None):
        self.settings = settings or get_settings()
        self.llm_service = llm_service or LLMService(self.settings)
        self._vectorstore: Chroma | None = None

    @property
    def vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                persist_directory=self.settings.chroma_persist_dir,
                embedding_function=self.llm_service.get_embeddings(),
            )
        return self._vectorstore

    def health_check(self) -> dict:
        try:
            count = self.vectorstore._collection.count()
            return {"status": "ok", "document_chunks": count}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def add_documents(self, documents: list[Document], document_id: str | None = None) -> dict:
        if not documents:
            return {"document_id": document_id, "chunks_added": 0}

        resolved_document_id = document_id or str(uuid4())
        ids = []

        for index, document in enumerate(documents):
            chunk_id = f"{resolved_document_id}:{index}"
            document.metadata["document_id"] = resolved_document_id
            document.metadata["chunk_id"] = chunk_id
            ids.append(chunk_id)

        self.vectorstore.add_documents(documents, ids=ids)
        return {"document_id": resolved_document_id, "chunks_added": len(documents)}

    def similarity_search_with_score(self, query: str, k: int = 4) -> list[tuple[Document, float]]:
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def list_documents(self) -> list[dict]:
        raw = self.vectorstore._collection.get(include=["metadatas"])
        grouped: dict[str, dict] = {}
        chunk_counts: defaultdict[str, int] = defaultdict(int)

        for metadata in raw.get("metadatas", []):
            if not metadata:
                continue
            document_id = metadata.get("document_id") or metadata.get("file_path") or "unknown"
            chunk_counts[document_id] += 1
            grouped.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "file_name": metadata.get("file_name", "unknown"),
                    "file_path": metadata.get("file_path"),
                    "source_type": metadata.get("source_type", "unknown"),
                    "file_type": metadata.get("file_type"),
                },
            )

        return [
            {**document, "chunk_count": chunk_counts[document_id]}
            for document_id, document in grouped.items()
        ]

    def delete_document(self, document_id: str) -> dict:
        self.vectorstore._collection.delete(where={"document_id": document_id})
        return {"document_id": document_id, "deleted": True}


_vectorstore_service: VectorStoreService | None = None


def get_vectorstore_service() -> VectorStoreService:
    global _vectorstore_service
    if _vectorstore_service is None:
        _vectorstore_service = VectorStoreService()
    return _vectorstore_service
```

### 注意点

- 这里使用了 `Chroma._collection`，这是为了 Phase 1 快速实现 list/delete/health。后续可以封装得更干净。
- 每个上传文件生成一个 `document_id`，每个 chunk 生成一个 `chunk_id`。
- `list_documents()` 是按 `document_id` 聚合 chunk。

---

## 5.5 `backend/app/services/rag_service.py`

### 作用

负责完整 RAG 流程：

1. 接收问题
2. 从 ChromaDB 检索相关 chunk
3. 组织 prompt
4. 调用 LLM
5. 返回答案和 source citations
6. 支持 SSE 流式输出

### 建议代码

```python
import json
from collections.abc import AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.services.llm_service import LLMService
from app.services.vectorstore_service import VectorStoreService, get_vectorstore_service


RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant for WiseTechGlobal internal knowledge. "
            "Answer using only the provided context. If the context does not contain "
            "the answer, say you do not know. Always keep the answer grounded and concise.",
        ),
        (
            "human",
            "Question:\n{question}\n\nContext:\n{context}",
        ),
    ]
)


class RAGService:
    def __init__(
        self,
        llm_service: LLMService | None = None,
        vectorstore_service: VectorStoreService | None = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.vectorstore_service = vectorstore_service or get_vectorstore_service()

    def _format_context(self, documents_with_scores) -> str:
        parts = []
        for index, (document, score) in enumerate(documents_with_scores, start=1):
            source = document.metadata.get("file_name") or document.metadata.get("source") or "unknown"
            parts.append(
                f"[Source {index}: {source}; score={score}]\n{document.page_content}"
            )
        return "\n\n---\n\n".join(parts)

    def _format_sources(self, documents_with_scores) -> list[dict]:
        sources = []
        for document, score in documents_with_scores:
            sources.append(
                {
                    "document_id": document.metadata.get("document_id"),
                    "chunk_id": document.metadata.get("chunk_id"),
                    "title": document.metadata.get("file_name") or document.metadata.get("source", "unknown"),
                    "source_type": document.metadata.get("source_type", "unknown"),
                    "file_path": document.metadata.get("file_path"),
                    "score": float(score),
                    "preview": document.page_content[:500],
                }
            )
        return sources

    async def answer(self, question: str) -> dict:
        documents_with_scores = self.vectorstore_service.similarity_search_with_score(question, k=4)
        context = self._format_context(documents_with_scores)
        sources = self._format_sources(documents_with_scores)

        chain = RAG_PROMPT | self.llm_service.get_chat_model() | StrOutputParser()
        answer = await chain.ainvoke({"question": question, "context": context})

        return {
            "answer": answer,
            "sources": sources,
        }

    async def stream_answer(self, question: str) -> AsyncIterator[dict]:
        documents_with_scores = self.vectorstore_service.similarity_search_with_score(question, k=4)
        context = self._format_context(documents_with_scores)
        sources = self._format_sources(documents_with_scores)

        chain = RAG_PROMPT | self.llm_service.get_chat_model() | StrOutputParser()

        async for token in chain.astream({"question": question, "context": context}):
            yield {
                "event": "token",
                "data": json.dumps({"content": token}, ensure_ascii=False),
            }

        yield {
            "event": "sources",
            "data": json.dumps({"sources": sources}, ensure_ascii=False),
        }
        yield {
            "event": "done",
            "data": json.dumps({}, ensure_ascii=False),
        }


def get_rag_service() -> RAGService:
    return RAGService()
```

### 说明

- 这里没有使用旧的 `RetrievalQA`，而是使用 LCEL：`prompt | llm | StrOutputParser()`。
- 非流式接口用 `answer()`。
- SSE 流式接口用 `stream_answer()`。
- 第一版 source citation 只包含 metadata 和 preview，前端后续可以直接展示。

---

## 5.6 `backend/app/api/routes/health.py`

### 当前问题

当前只返回：

```json
{
  "status": "healthy",
  "service": "wtg-query-rag"
}
```

Plan 中希望 health 能体现 ChromaDB 连通性，并且验证口径是 `status=ok`。

### 建议代码

```python
from fastapi import APIRouter

from app.services.vectorstore_service import get_vectorstore_service

router = APIRouter()


@router.get("/health")
async def health_check():
    vectorstore_status = get_vectorstore_service().health_check()
    overall_status = "ok" if vectorstore_status.get("status") == "ok" else "degraded"

    return {
        "status": overall_status,
        "service": "wtg-query-rag",
        "chroma": vectorstore_status,
    }
```

---

## 5.7 `backend/app/api/routes/chat.py`

### 作用

实现：

- `POST /api/chat`
- 支持 JSON 响应
- 支持 SSE 流式响应

### 请求示例

```json
{
  "question": "What is WTG.Query.RAG?",
  "stream": true
}
```

### 建议代码

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.services.rag_service import get_rag_service

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    stream: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


@router.post("/chat")
async def chat(request: ChatRequest):
    rag_service = get_rag_service()

    try:
        if request.stream:
            return EventSourceResponse(rag_service.stream_answer(request.question))

        result = await rag_service.answer(request.question)
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

### 验证命令

非流式：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is WTG.Query.RAG?", "stream": false}'
```

流式：

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is WTG.Query.RAG?", "stream": true}'
```

---

## 5.8 `backend/app/api/routes/documents.py`

### 作用

实现：

- `POST /api/documents/upload`
- `GET /api/documents`
- `DELETE /api/documents/{document_id}`

### 建议代码

```python
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.services.document_service import get_document_service
from app.services.vectorstore_service import get_vectorstore_service

router = APIRouter()


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    settings = get_settings()
    docs_dir = Path(settings.docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(file.filename or "uploaded-file").name
    extension = Path(original_name).suffix.lower()
    if extension not in (".pdf", ".md", ".txt", ".text"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

    document_id = str(uuid4())
    target_path = docs_dir / f"{document_id}_{original_name}"

    content = await file.read()
    target_path.write_bytes(content)

    document_service = get_document_service()
    vectorstore_service = get_vectorstore_service()

    loaded_documents = document_service.load_file(str(target_path))
    chunks = document_service.split_documents(loaded_documents)
    result = vectorstore_service.add_documents(chunks, document_id=document_id)

    return {
        "document_id": document_id,
        "file_name": original_name,
        "saved_path": str(target_path),
        "chunks_added": result["chunks_added"],
    }


@router.get("/documents")
async def list_documents():
    return {
        "documents": get_vectorstore_service().list_documents(),
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    result = get_vectorstore_service().delete_document(document_id)
    return result
```

### 注意点

- 上传文件会保存到 `docs_dir`。
- 文件名加上 `document_id` 前缀，避免同名覆盖。
- Phase 1 暂时只处理单文件上传；批量上传可后续扩展。

---

## 5.9 `backend/app/api/routes/__init__.py`

### 当前状态

当前只导出 health：

```python
from .health import router as health_router
```

### 建议代码

```python
from .chat import router as chat_router
from .documents import router as documents_router
from .health import router as health_router

__all__ = [
    "chat_router",
    "documents_router",
    "health_router",
]
```

---

## 5.10 `backend/app/main.py`

### 当前问题

- 只注册了 `health_router`
- CORS 默认端口包含 `5174`，但 Vite 默认是 `5173`
- 没有注册 chat/documents

### 建议代码

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat_router, documents_router, health_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


settings = get_settings()

app = FastAPI(
    title="WTG Query RAG",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(documents_router, prefix="/api", tags=["documents"])
```

---

## 5.11 `rag.py`

### 当前问题

`rag.py` 仍然是旧 CLI 版，并且存在重复 `else` 导致语法错误。

当前问题位置类似：

```python
else:
    return None, None, None, None
else:
    return None, None
```

### Phase 1 推荐处理方式

第一阶段建议先把 FastAPI 后端跑通。`rag.py` 可以先简化为兼容入口，避免语法错误阻塞工具或测试。

### 简化后的建议代码

```python
"""
Legacy CLI entry point for WTG.Query.RAG.

The production API lives under backend/app.
Run the backend with:

    cd backend
    uvicorn app.main:app --reload --port 8000
"""

import subprocess
import sys


def main():
    print("Starting WTG.Query.RAG FastAPI backend...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--port",
            "8000",
        ],
        cwd="backend",
        check=False,
    )


if __name__ == "__main__":
    main()
```

也可以暂时只修复重复 `else`，保留 CLI 版。不过从 Plan 来看，Phase 1 的目标是 FastAPI 后端，因此更推荐让 `rag.py` 成为旧入口或说明性入口。

---

## 6. 实现顺序建议

建议按以下顺序做，避免一边写一边 import 失败：

1. 删除或忽略根目录 `services/`，创建 `backend/app/services/`。
2. 实现 `backend/app/config.py`。
3. 实现 `backend/app/services/llm_service.py`。
4. 实现 `backend/app/services/document_service.py`。
5. 实现 `backend/app/services/vectorstore_service.py`。
6. 更新 `backend/app/api/routes/health.py`。
7. 实现 `backend/app/api/routes/documents.py`。
8. 实现 `backend/app/services/rag_service.py`。
9. 实现 `backend/app/api/routes/chat.py`。
10. 更新 `backend/app/api/routes/__init__.py`。
11. 更新 `backend/app/main.py`。
12. 修复或简化 `rag.py`。
13. 本地启动并执行 curl 验证。

---

## 7. 本地验证步骤

### 7.1 启动 Ollama（如果使用本地模型）

```bash
ollama serve > /tmp/ollama.log 2>&1 &
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

`.env` 示例：

```env
LLM_PROVIDER=ollama
MODEL_NAME=qwen2.5:14b
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
CHROMA_PERSIST_DIR=./chroma_db
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### 7.2 启动后端

```bash
conda activate RAG
cd /mnt/c/git/GitHub/wisetechglobal/wtg.query.rag/backend
uvicorn app.main:app --reload --port 8000
```

### 7.3 验证健康检查

```bash
curl http://localhost:8000/api/health
```

期望返回类似：

```json
{
  "status": "ok",
  "service": "wtg-query-rag",
  "chroma": {
    "status": "ok",
    "document_chunks": 0
  }
}
```

### 7.4 上传 sample.md

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@../docs/sample.md"
```

期望返回：

```json
{
  "document_id": "...",
  "file_name": "sample.md",
  "saved_path": "...",
  "chunks_added": 1
}
```

### 7.5 查看文档列表

```bash
curl http://localhost:8000/api/documents
```

期望能看到刚才上传的文档。

### 7.6 提问

非流式：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is WTG.Query.RAG?", "stream": false}'
```

流式：

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is WTG.Query.RAG?", "stream": true}'
```

---

## 8. Phase 1 Definition of Done

Phase 1 可以认为完成，当且仅当：

- [ ] `backend/app/config.py` 有可用的 `Settings`
- [ ] `backend/app/services/llm_service.py` 能创建 chat model 和 embedding model
- [ ] `backend/app/services/document_service.py` 能加载和分块 PDF / MD / TXT
- [ ] `backend/app/services/vectorstore_service.py` 能 add / search / list / delete / health check
- [ ] `backend/app/services/rag_service.py` 能返回 answer + sources
- [ ] `POST /api/documents/upload` 可上传并索引文档
- [ ] `GET /api/documents` 可列出文档
- [ ] `DELETE /api/documents/{document_id}` 可删除文档
- [ ] `POST /api/chat` 可非流式返回回答
- [ ] `POST /api/chat` 可 SSE 流式返回 token、sources、done
- [ ] `GET /api/health` 返回 `status=ok` 并包含 Chroma 状态
- [ ] `main.py` 注册 health/chat/documents 三组路由
- [ ] `rag.py` 不再有语法错误
- [ ] 根目录 `services/` 不再作为实现目录使用

---

## 9. Phase 1 暂不处理的内容

以下内容不要塞进 Phase 1，否则范围会变大：

| 内容 | 所属阶段 |
|---|---|
| Confluence connector | Phase 2 |
| Git repository connector | Phase 2 |
| ediProd connector | Phase 2 |
| ingestion job status | Phase 2 |
| React frontend | Phase 3 |
| Docker Compose | Phase 4 |
| MemPalace | Phase 5 |
| Hybrid search / BM25 | Phase 5 |
| Cross-encoder reranking | Phase 5 |

---

## 10. 建议下一步

如果只想最快跑通 Phase 1，建议先实现最小闭环：

1. `config.py`
2. `llm_service.py`
3. `document_service.py`
4. `vectorstore_service.py`
5. `documents.py`
6. `rag_service.py`
7. `chat.py`
8. `main.py`

完成后先用 `docs/sample.md` 做端到端验证，再考虑补充错误处理、测试和更漂亮的响应模型。
