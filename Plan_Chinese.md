# WTG.Query.RAG — 项目计划

> 基于 WiseTechGlobal 内部内容的检索增强生成（RAG）问答系统。

## 目录

- [概述](#概述)
- [架构](#架构)
- [技术栈](#技术栈)
- [本地环境准备与工具安装](#本地环境准备与工具安装)
- [阶段一：后端 API 基础](#阶段一后端-api-基础)
- [阶段二：数据源连接器](#阶段二数据源连接器)
- [阶段三：React 前端](#阶段三react-前端)
- [阶段四：容器化与部署](#阶段四容器化与部署)
- [阶段五：增强功能 — MemPalace 与高级检索](#阶段五增强功能--mempalace-与高级检索)
- [目标目录结构](#目标目录结构)
- [验证清单](#验证清单)
- [关键决策](#关键决策)
- [团队协作方案](#团队协作方案)
- [待解决问题](#待解决问题)

---

## 概述

构建一个全栈 RAG 问答系统，使 WiseTechGlobal 员工可以用自然语言对内部内容提问，并获得有据可查、附带引用的回答。

**数据源**（摄入到向量存储中）：

| 来源 | 示例 |
|---|---|
| 内部文档 | Markdown 文件、PDF 手册、文本文件 |
| Confluence / Wiki | 团队空间、知识库文章 |
| 源代码仓库 | CargoWise、Glow 及其他 WTG 仓库 |
| ediProd 工作项 | WI 描述、任务备注、事件报告 |

**关键特性**：

- 本地优先 — 所有数据和模型可在内网运行，除非明确配置否则不会向外传输数据
- LLM 不可知 — 通过单一环境变量即可在 OpenAI、Azure OpenAI、GitHub Models 或本地模型（Ollama 或 vLLM）之间切换
- 初始小规模 — 不超过 1,000 份文档，不超过 10 个并发用户
- 初始阶段不设身份认证（后续补充）

---

## 架构

```
                        ┌──────────────────────────────────────────────────────────┐
                        │                     本地服务器 / K8S 集群                  │
┌─────────────┐         │                                                          │
│             │  HTTP   │  ┌─────────────────────────────────────────────────────┐  │
│  React SPA  │────────▶│  │  FastAPI 后端 (Python)                              │  │
│  (聊天界面)  │◀────────│  │                                                     │  │
│             │  SSE    │  │  ┌──────────────┐   ┌──────────────┐                │  │
└─────────────┘         │  │  │  LangChain   │──▶│   ChromaDB   │                │  │
   Vite + TS            │  │  │  RAG Chain   │   │  向量存储     │                │  │
                        │  │  └──────┬───────┘   └──────────────┘                │  │
                        │  │         │                                            │  │
                        │  │  ┌──────▼───────┐   ┌──────────────────────────┐     │  │
                        │  │  │     LLM      │   │  摄入流水线               │     │  │
                        │  │  │  (可切换)     │   │  文件│Confluence│Git│edi │     │  │
                        │  │  └──────────────┘   └──────────────────────────┘     │  │
                        │  │                                                     │  │
                        │  │  ┌──────────────────────────────────────────────┐    │  │
                        │  │  │ [阶段5] MemPalace — 问答对话缓存             │    │  │
                        │  │  └──────────────────────────────────────────────┘    │  │
                        │  └─────────────────────────────────────────────────────┘  │
                        └──────────────────────────────────────────────────────────┘
```

**数据流**：

1. **摄入** — 连接器从数据源拉取内容 → 分块 → 嵌入 → 存入 ChromaDB。
2. **查询** — 用户在 React 聊天界面输入问题 → FastAPI 接收请求 → LangChain 从 ChromaDB 检索相关文档块 → LLM 基于这些文档块生成有据可查的回答 → 通过 SSE 流式传输回前端。
3. **记忆**（*阶段五*）— 每次问答完成后，将问答对存入 MemPalace。后续查询时先检查 MemPalace；如存在高置信度匹配，则直接返回缓存答案。

---

## 技术栈

| 层级 | 技术 | 版本 | 用途 |
|---|---|---|---|
| **前端** | React | 19.x | 聊天界面 SPA |
| | TypeScript | 5.x | 类型安全 |
| | Vite | 6.x | 构建工具与开发服务器 |
| | Ant Design *或* Shadcn/ui | latest | UI 组件库 |
| | Tailwind CSS | 4.x | 实用优先的样式框架 |
| **后端** | Python | 3.12 | 运行时（通过 conda `RAG` 环境） |
| | FastAPI | 0.115+ | REST API 框架 |
| | Uvicorn | 0.34+ | ASGI 服务器 |
| | Pydantic | 2.x | 配置与校验 |
| | Miniconda | latest | Python 环境与包管理 |
| **RAG** | LangChain | >=0.3 | 编排框架 |
| | LangChain Community | >=0.3 | 数据源加载器 |
| | LangChain OpenAI | >=0.3 | OpenAI/Azure/GitHub Models 集成 |
| **向量数据库** | ChromaDB | >=0.6 | 本地优先向量存储 |
| **嵌入模型** | text-embedding-3-large（*默认*） | — | OpenAI 嵌入模型 |
| | bge-m3 / multilingual-e5-large（*可选*） | — | 本地多语言替代方案 |
| **LLM** | GPT-4o（*默认*） | — | 云端 LLM |
| | Llama 3 / Qwen 2.5 / Mistral（*可选*） | — | 通过 Ollama（开发）或 vLLM（生产）运行的本地 LLM |
| **本地 LLM 服务器** | Ollama | latest | 简单易用的本地推理（CPU/GPU） |
| | vLLM | >=0.6 | 高吞吐量 GPU 推理服务器（生产环境） |
| **记忆** | MemPalace（*阶段五*） | >=3.3 | 对话记忆与缓存 |
| **基础设施** | Docker | 27.x | 容器化 |
| | Docker Compose | 2.x | 本地多容器编排 |
| | Kubernetes（*未来*） | 1.30+ | 生产环境编排 |

### 为什么选择 LangChain？

现有的 `rag.py` 已经基于 LangChain 构建 — 保留它可以避免重写。LangChain 还提供：

- 内置加载器支持 Confluence、Git 仓库、PDF、Markdown 等多种数据源
- LCEL（LangChain Expression Language）实现可组合、支持流式的链式调用
- RAG 框架中最大的生态系统和社区
- 如果团队后续觉得 LangChain 过于笨重，LlamaIndex 是具有类似概念的迁移目标

---

## 本地环境准备与工具安装

在开始开发前安装以下工具。所有命令均使用 WSL (Ubuntu/Debian)。**WSL、Git 和 Miniconda 已安装完成** — 跳过这些步骤。

### Conda 环境设置（RAG）

本项目所有 Python 依赖由名为 `RAG` 的单一 conda 环境统一管理。

```bash
# 1. 创建 RAG 环境（仅首次）
conda create -n RAG python=3.12 -y

# 2. 激活环境
conda activate RAG

# 3. 验证
python --version   # → Python 3.12.x
which python       # → ~/miniconda3/envs/RAG/bin/python
```

**日常工作流** — 每次打开新的 WSL 终端时：

```bash
# 从 Windows 终端进入 WSL（如果尚未在 WSL 中）
wsl

# 激活 conda 环境
conda activate RAG

# 进入项目目录
cd ~/git/WTG.Query.RAG
```

**在 RAG 环境中安装包**：

```bash
# 推荐：在 conda 环境内使用 pip（与 PyPI 专有包兼容性最佳）
pip install <package>

# 或使用 conda 安装 conda-forge 上可用的包
conda install -c conda-forge <package>

# 从 requirements.txt 安装所有项目依赖
pip install -r requirements.txt
```

> **注意**：大多数 LangChain / FastAPI / ChromaDB 包仅在 PyPI 上发布，因此在 conda 环境内使用 `pip install` 是标准做法。仅对那些受益于 conda 二进制构建的包使用 `conda install`（例如 `numpy`、`scipy`、`sentence-transformers`）。

### 1. Node.js 20+ 与 npm

React 前端构建工具链（Vite、TypeScript 等）所需。

```bash
# 通过 nvm 安装（推荐）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install --lts
nvm use --lts

# 或通过 NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**验证**：`node --version` → `v20.x.x`，`npm --version` → `10.x.x`

### 2. Docker

容器化（阶段四）及开发期间运行 ChromaDB 容器所需。

**方案 A — Docker Desktop（Windows 宿主，与 WSL 共享）**：

在 Windows 上安装 Docker Desktop，并在 Settings > Resources > WSL Integration 中启用 "Use the WSL 2 based engine" 和 "Enable integration with my default WSL distro"。

**方案 B — 在 WSL 内安装 Docker Engine**：

```bash
# 安装 Docker Engine
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 将当前用户添加到 docker 组（免 sudo）
sudo usermod -aG docker $USER
newgrp docker
```

**验证**：`docker --version` 和 `docker compose version`

### 3. 本地 LLM 服务器（可选 — Ollama 或 vLLM）

仅在需要完全本地运行 LLM 而不使用云端 API 时需要。根据硬件和使用场景**选择其一**。

#### Ollama vs vLLM 多维对比

| 维度 | Ollama | vLLM |
|---|---|---|
| **安装复杂度** | 一行命令，零配置 | 需要 CUDA + Python 环境 |
| **硬件要求** | CPU 或 GPU（Apple Silicon、NVIDIA） | **必须 NVIDIA GPU**（CUDA） |
| **吞吐量** | 单请求良好；并发时性能下降 | PagedAttention 优化；高并发表现优异 |
| **单请求延迟** | 低 | 低（冷启动略高） |
| **模型管理** | `ollama pull` 一键下载 | 需手动从 HuggingFace 下载权重 |
| **量化支持** | 内置 GGUF（Q4、Q5、Q8） | GPTQ / AWQ / FP16 — GPU 显存利用更高效 |
| **API 兼容性** | OpenAI 兼容（`/v1/chat/completions`） | OpenAI 兼容（`/v1/chat/completions`） |
| **嵌入模型支持** | 内置（`/api/embeddings`） | 通过 `--served-model-name` 参数 |
| **多 GPU 支持** | 有限 | 原生张量并行跨 GPU |
| **连续批处理** | 不支持 | 支持 — 生产吞吐的关键 |
| **适合场景** | 开发、个人使用、小规模、无 GPU | 生产部署、多用户并发访问 |

**使用建议**：
- **开发环境 / 无 GPU** → Ollama（零门槛上手）
- **生产部署 / 有 GPU 服务器** → vLLM（更高吞吐量，规模化后单请求成本更低）
- 两者都暴露 OpenAI 兼容 API，切换时仅需修改 `LLM_PROVIDER` 和 base URL。

#### 方案 A — Ollama

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动 Ollama 服务（如未自动启动）
ollama serve &

# 拉取模型
ollama pull llama3.1
ollama pull nomic-embed-text    # 本地嵌入模型
```

**验证**：`ollama --version` 和 `ollama list`

#### 方案 B — vLLM

> **前提条件**：NVIDIA GPU，CUDA 12.1+，7B 模型至少 16 GB 显存（14B+ 需要 24+ GB）。

```bash
# 将 vLLM 安装到 RAG conda 环境
conda activate RAG
pip install vllm

# 启动 vLLM（OpenAI 兼容 API）
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --host 0.0.0.0 \
  --port 8100 \
  --max-model-len 8192

# 使用量化模型（更少显存）：
python -m vllm.entrypoints.openai.api_server \
  --model TheBloke/Llama-3.1-8B-Instruct-GPTQ \
  --quantization gptq \
  --host 0.0.0.0 \
  --port 8100
```

**验证**：`curl http://localhost:8100/v1/models` — 应列出已加载的模型

> **注意**：vLLM 模型权重从 HuggingFace 下载。对于受限模型（如 Llama 3），可能需要 `huggingface-cli login`。设置 `HF_HOME` 可控制下载缓存目录。

### 4. kubectl 与 Helm（可选 — 用于 K8S，阶段四）

仅在部署到 Kubernetes 时需要。

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

**验证**：`kubectl version --client` 和 `helm version`

### 工具总结表

| 工具 | 状态 | 需要阶段 | 备注 |
|---|---|---|---|
| WSL | **已安装** | 全部 | — |
| Git | **已安装** | 全部 | — |
| Miniconda | **已安装** | 全部 | 管理 `RAG` conda 环境 |
| Python 3.12 | 通过 conda `RAG` 环境 | 阶段 1+ | `conda create -n RAG python=3.12` |
| Node.js 20+ | **待安装** | 阶段 3+ | `nvm install --lts` |
| Docker | **待安装** | 阶段 4+（更早亦可） | Docker Desktop WSL 集成或 WSL 内 `docker-ce` |
| Ollama | 可选 | 阶段 1+（如使用本地 LLM） | `curl -fsSL https://ollama.com/install.sh \| sh` — 简单开发环境 |
| vLLM | 可选 | 阶段 1+（如使用本地 LLM） | `pip install vllm` — 需要 NVIDIA GPU，高吞吐生产环境 |
| kubectl | 可选 | 阶段 4（仅 K8S） | `curl -LO ... && sudo install kubectl` |
| Helm | 可选 | 阶段 4（仅 K8S） | `curl ... \| bash` (get-helm-3) |

---

## 阶段一：后端 API 基础

**目标**：将当前基于 CLI 的 `rag.py` 重构为生产级 FastAPI 后端，提供 REST API 供 React 前端调用。

### 步骤 1.1 — 项目结构搭建

创建后端 Python 包及正确的项目配置。

**要做的事**：

- 在仓库根目录创建 `backend/` 目录
- 初始化 `backend/pyproject.toml`，包含所有 Python 依赖
- 在 `backend/app/` 下建立 Python 包及 `__init__.py` 文件
- 将当前 `rag.py` 中的可复用逻辑迁移到新包中

**核心依赖**（`pyproject.toml` 中）：

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
    "chromadb>=0.6.0",
    "pypdf>=4.0.0",
    "unstructured>=0.16.0",
    "python-dotenv>=1.0.0",
    "sse-starlette>=2.0.0",
    "python-multipart>=0.0.18",
]
```

**启动方式**：

```bash
# 确保在 conda RAG 环境中
conda activate RAG

cd ~/git/WTG.Query.RAG
mkdir -p backend/app/api/routes
mkdir -p backend/app/services
mkdir -p backend/app/connectors

# 将所有依赖安装到 RAG conda 环境
pip install fastapi "uvicorn[standard]" pydantic-settings \
  langchain langchain-community langchain-openai langchain-chroma \
  chromadb pypdf python-dotenv sse-starlette python-multipart

# 或从项目 requirements.txt 安装
pip install -r requirements.txt
```

### 步骤 1.2 — FastAPI 应用

构建带有 CORS、路由和流式支持的核心 API 应用。

**要做的事**：

- 创建 `backend/app/main.py` — FastAPI 应用入口，包含 CORS 中间件（允许 React 开发服务器调用 API）
- 在 `backend/app/api/routes/` 下创建路由模块：

| 文件 | 端点 | 描述 |
|---|---|---|
| `chat.py` | `POST /api/chat` | 接收问题，返回带引用的回答。支持 SSE 流式逐 token 输出。 |
| `documents.py` | `POST /api/documents/upload` | 上传 PDF/MD/TXT 文件用于摄入 |
| | `GET /api/documents` | 列出所有已索引文档及元数据 |
| | `DELETE /api/documents/{id}` | 从向量存储中删除文档 |
| `health.py` | `GET /api/health` | 健康检查 — 返回后端状态和 ChromaDB 连通性 |

**SSE 流式细节**：`/api/chat` 端点使用 `sse-starlette` 在 LLM 生成 token 时实时流式推送。响应格式：

```
event: token
data: {"content": "答"}

event: token
data: {"content": "案"}

event: sources
data: {"sources": [{"title": "doc.md", "page": 1, "score": 0.92}]}

event: done
data: {}
```

**开发运行方式**：

```bash
conda activate RAG
cd backend
uvicorn app.main:app --reload --port 8000
```

### 步骤 1.3 — RAG 服务层

从当前 `rag.py` 中提取并模块化 RAG 逻辑为清晰的服务类。

**要做的事**：

| 服务文件 | 职责 | 重构来源 |
|---|---|---|
| `services/rag_service.py` | 编排完整 RAG 流水线：接收问题 → 检索文档块 → 生成回答 → 返回结果与引用 | `rag.py` 中的 `get_qa_chain()` |
| `services/vectorstore_service.py` | ChromaDB 操作：初始化存储、添加文档、相似度搜索、按 ID 删除 | `rag.py` 中的 `build_vectorstore()` |
| `services/document_service.py` | 从磁盘或上传加载文件，使用 `RecursiveCharacterTextSplitter` 分块 | `rag.py` 中的 `load_documents()` |
| `services/llm_service.py` | 根据提供商配置创建合适的 LLM 和嵌入实例 | `rag.py` 中的 `get_llm_config()` |

**关键设计决策**：

- 使用 FastAPI 的 `Depends()` 实现**依赖注入**，使服务可测试、可替换
- `rag_service` 使用 LangChain 的 LCEL（`RunnableSequence`）替代旧版 `RetrievalQA` 链，实现原生流式传输
- ChromaDB `persist_directory` 默认为 `./chroma_db`（与当前相同），但可通过配置修改

### 步骤 1.4 — 多 LLM 提供商支持

使 LLM 后端可配置，让团队可以在云端和本地模型之间切换。

**要做的事**：

通过单一环境变量 `LLM_PROVIDER` 配置：

| `LLM_PROVIDER` | LLM 类 | 嵌入类 | 所需环境变量 | 备注 |
|---|---|---|---|---|
| `openai` | `ChatOpenAI` | `OpenAIEmbeddings` | `OPENAI_API_KEY` | 直接 OpenAI API |
| `azure` | `AzureChatOpenAI` | `AzureOpenAIEmbeddings` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | 企业 Azure 部署 |
| `github` | `ChatOpenAI`（自定义 base_url） | `OpenAIEmbeddings`（自定义 base_url） | `GITHUB_TOKEN` | GitHub Models 端点（当前默认） |
| `ollama` | `ChatOllama` | `OllamaEmbeddings` | `OLLAMA_BASE_URL`（默认 `http://localhost:11434`） | 完全本地，无需 API 密钥，简单易用 |
| `vllm` | `ChatOpenAI`（自定义 base_url） | `OpenAIEmbeddings`（自定义 base_url） | `VLLM_BASE_URL`（默认 `http://localhost:8100/v1`） | 完全本地，无需 API 密钥，高吞吐 GPU 推理 |

`llm_service.py` 的工厂方法根据此配置返回正确的 LangChain LLM 和嵌入实例。所有下游代码对提供商无感知。

> **注意**：`vllm` 提供商复用与 `github` 提供商相同的 `ChatOpenAI` / `OpenAIEmbeddings` 类，只是 `base_url` 指向本地 vLLM 服务器。这意味着零额外 LangChain 依赖。

### 步骤 1.5 — 配置管理

使用 Pydantic Settings 集中管理所有配置。

**要做的事**：

- 创建 `backend/app/config.py`，包含一个从环境变量和 `.env` 文件读取的 `Settings` 类
- 在仓库根目录创建 `.env.example`，文档化每个配置项

**`.env.example` 示例**：

```env
# LLM 提供商: openai | azure | github | ollama | vllm
LLM_PROVIDER=github

# GitHub Models（默认）
GITHUB_TOKEN=your_github_token_here

# OpenAI（如 LLM_PROVIDER=openai）
# OPENAI_API_KEY=sk-...

# Azure OpenAI（如 LLM_PROVIDER=azure）
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Ollama（如 LLM_PROVIDER=ollama）
# OLLAMA_BASE_URL=http://localhost:11434

# vLLM（如 LLM_PROVIDER=vllm）
# VLLM_BASE_URL=http://localhost:8100/v1
# VLLM_MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct

# 模型名称
MODEL_NAME=gpt-4o
EMBEDDING_MODEL=text-embedding-3-large

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db

# 摄入配置
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### 阶段一验证

```bash
# 启动后端
conda activate RAG
cd backend
uvicorn app.main:app --reload --port 8000

# 测试健康检查
curl http://localhost:8000/api/health

# 上传文档
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@../docs/sample.md"

# 提问
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is WTG.Query.RAG?"}'
```

预期结果：返回基于 `sample.md` 内容生成的 JSON 回答，附带源引用。

---

## 阶段二：数据源连接器

**目标**：为所有四个目标数据源构建摄入连接器，使 WTG 内部内容可以自动拉取、分块、嵌入并存入 ChromaDB。

### 步骤 2.1 — 文件连接器（Markdown / PDF / TXT）

**已部分实现** — 当前 `rag.py` 的 `load_documents()` 函数已处理此功能。将其重构为连接器模式。

**要做的事**：

- 创建 `backend/app/connectors/base_connector.py` — 定义连接器接口的抽象基类：
  ```python
  class BaseConnector(ABC):
      @abstractmethod
      async def fetch_documents(self) -> list[Document]: ...
      @abstractmethod
      async def get_metadata(self) -> dict: ...
  ```
- 创建 `backend/app/connectors/file_connector.py`：
  - 接受目录路径或上传文件
  - PDF 使用 `PyPDFLoader`，`.md` 使用 `UnstructuredMarkdownLoader`，`.txt` 使用 `TextLoader`
  - 附加元数据：`source_type=file`、`file_path`、`file_name`、`file_type`
- 通过 `POST /api/documents/upload`（单个或批量文件上传）和 `POST /api/ingest/files`（扫描目录）暴露

**核心依赖**：`pypdf`、`unstructured`（已在 requirements 中）

### 步骤 2.2 — Confluence / Wiki 连接器

从 Atlassian Confluence 空间拉取页面并建立索引。

**要做的事**：

- 创建 `backend/app/connectors/confluence_connector.py`
- 使用 LangChain 的 `ConfluenceLoader`（`langchain_community.document_loaders.ConfluenceLoader`）
- 配置（通过环境变量 / API 请求）：
  - `CONFLUENCE_URL` — Confluence 实例的基础 URL
  - `CONFLUENCE_USERNAME` — 服务账号用户名
  - `CONFLUENCE_API_TOKEN` — 用于认证的 API 令牌
  - `CONFLUENCE_SPACE_KEYS` — 要索引的空间键的逗号分隔列表（例如 `"ENG,OPS,ARCH"`）
- 功能：
  - **全量同步**：拉取已配置空间的所有页面
  - **增量同步**：跟踪每个页面的 `last_modified` 时间戳；后续同步时仅获取已更新的页面
  - **元数据**：`source_type=confluence`、`space_key`、`page_title`、`page_url`、`last_modified`
- 通过 `POST /api/ingest/confluence` 暴露

**核心依赖**：`atlassian-python-api`（添加到 `pyproject.toml`）

```bash
conda activate RAG
pip install atlassian-python-api
```

### 步骤 2.3 — 源代码仓库连接器

索引 WTG Git 仓库的源代码，实现代码感知搜索。

**要做的事**：

- 创建 `backend/app/connectors/code_connector.py`
- 两种方式（按仓库配置）：
  - **LangChain GitLoader**：`langchain_community.document_loaders.GitLoader` — 克隆并遍历
  - **自定义文件遍历**：将仓库克隆到临时目录，按扩展名过滤遍历文件
- 配置：
  - `repo_url` — Git 克隆 URL
  - `branch` — 要索引的分支（默认：`main`）
  - `include_extensions` — 要包含的文件类型（默认：`.cs, .py, .md, .xml, .json, .yaml, .sql`）
  - `exclude_paths` — 要跳过的目录（默认：`bin/, obj/, node_modules/, .git/`）
- **代码感知分块**：
  - `.cs`、`.py`、`.ts` 文件：使用 `langchain.text_splitter.Language` 感知分割器，尊重函数/类边界
  - `.md` 和文本文件：使用 `RecursiveCharacterTextSplitter`（与当前相同）
- **元数据**：`source_type=code`、`repo_name`、`file_path`、`language`、`branch`
- 通过 `POST /api/ingest/repository` 暴露，请求体为 `{"repo_url": "...", "branch": "main"}`

**核心依赖**：`gitpython`（添加到 `pyproject.toml`）

```bash
conda activate RAG
pip install gitpython
```

### 步骤 2.4 — ediProd 工作项连接器

索引 ediProd 中的工作项、任务备注和事件数据。

**要做的事**：

- 创建 `backend/app/connectors/ediprod_connector.py`
- 访问方式：**待定** — 选项包括：
  - 直接 REST API 调用 ediProd（如可用）
  - MCP 工具集成（`mcp_ediprod_*` 工具）
  - 数据库查询（如允许直接访问数据库）
- 每个工作项要提取的数据：
  - WI 编号、标题、描述（全文）
  - 任务备注（带时间戳的条目）
  - 状态、优先级、分配团队
  - 相关事件（如为 ISS 类型）
- **分块**：每个 WI 根据长度成为一个或多个文档块。任务备注单独分块，WI 编号作为元数据。
- **元数据**：`source_type=ediprod`、`wi_number`、`wi_type`、`status`、`team`
- **同步计划**：可配置的定期同步（例如每 4 小时）或手动触发
- 通过 `POST /api/ingest/ediprod` 暴露

> **注意**：此连接器的实现取决于 ediProd 访问方式的确认。开发时先用读取 JSON 文件的模拟连接器，然后替换为真实 API 集成。

### 步骤 2.5 — 摄入流水线编排器

统一协调所有连接器的服务。

**要做的事**：

- 创建 `backend/app/services/ingestion_service.py`，包含：
  - `ingest(source_type, config)` — 分发到对应连接器，分块、嵌入、存储
  - **去重**：计算每个文档块内容 + 源元数据的哈希值。插入 ChromaDB 前检查哈希是否已存在；如存在则跳过。
  - **后台执行**：小任务使用 FastAPI 的 `BackgroundTasks`。对于较长的摄入任务（大型仓库、完整 Confluence 同步），未来考虑使用任务队列（Celery + Redis）。
  - **状态追踪**：在内存字典（或 SQLite 持久化）中存储摄入任务状态（pending/running/completed/failed）
- 管理员 API 端点：

| 端点 | 方法 | 描述 |
|---|---|---|
| `/api/ingest/files` | POST | 触发文件目录扫描 |
| `/api/ingest/confluence` | POST | 触发 Confluence 空间同步 |
| `/api/ingest/repository` | POST | 触发 Git 仓库索引 |
| `/api/ingest/ediprod` | POST | 触发 ediProd WI 同步 |
| `/api/ingest/status` | GET | 列出所有摄入任务及状态 |
| `/api/ingest/status/{job_id}` | GET | 获取特定任务的状态 |

### 阶段二验证

对每个连接器：

1. 通过 API 端点触发摄入
2. 检查 `GET /api/ingest/status/{job_id}` 显示 `completed`
3. 检查 `GET /api/documents` 列出新摄入的文档及正确的元数据
4. 通过 `POST /api/chat` 提问一个只能从新摄入内容中回答的问题
5. 验证回答正确且引用了正确的来源

---

## 阶段三：React 前端

**目标**：构建一个 React 单页应用，包含对话式聊天界面和文档管理页面。

### 步骤 3.1 — React 项目搭建

使用现代工具链搭建前端项目。

**要做的事**：

```bash
cd ~/git/WTG.Query.RAG

# 使用 Vite 创建 React + TypeScript 项目
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install

# 安装 UI 库
npm install antd @ant-design/icons          # 或：npx shadcn@latest init
npm install tailwindcss @tailwindcss/vite    # Tailwind CSS
npm install react-markdown remark-gfm        # Markdown 渲染
npm install react-syntax-highlighter         # 代码块高亮
npm install zustand                          # 轻量状态管理
npm install axios                            # HTTP 客户端（可选，可用 fetch）
```

**项目结构**：

```
frontend/
├── src/
│   ├── api/              # 后端 API 客户端函数
│   │   ├── client.ts     # 基础 Axios/fetch 配置
│   │   ├── chat.ts       # 聊天 API（含 SSE 流式）
│   │   └── documents.ts  # 文档 CRUD API
│   ├── components/       # 可复用 UI 组件
│   │   ├── ChatMessage.tsx
│   │   ├── ChatInput.tsx
│   │   ├── SourceCitation.tsx
│   │   └── DocumentUpload.tsx
│   ├── pages/            # 顶层页面组件
│   │   ├── ChatPage.tsx
│   │   └── DocumentsPage.tsx
│   ├── stores/           # Zustand 状态存储
│   │   └── chatStore.ts
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

**Vite 开发服务器代理**（在 `vite.config.ts` 中）：

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

### 步骤 3.2 — 聊天界面

面向用户的主要页面：对话式问答界面。

**要做的事**：

- `ChatPage.tsx` — 全页聊天布局，消息列表在上，输入栏在底部
- `ChatMessage.tsx` — 渲染单条消息气泡：
  - **用户消息**：右对齐，纯文本
  - **助手消息**：左对齐，渲染为 Markdown（支持代码块、表格、列表）
  - **源引用**：助手消息下方可折叠区域，显示使用了哪些文档及相关性评分
- `ChatInput.tsx` — 文本输入框带发送按钮，支持 Enter 发送、Shift+Enter 换行
- **SSE 流式实现**：
  - 使用浏览器 `EventSource` API 或手动 `fetch()` 配合 `ReadableStream` 消费来自 `POST /api/chat` 的 SSE
  - 逐 token 显示（打字机效果）
  - 等待第一个 token 时显示"思考中..."指示器
- `SourceCitation.tsx` — 显示源文档名称、页面/章节和相关性评分。点击可展开相关文档块的预览。
- **聊天历史**：存储在 Zustand store 中；会话期间持久化。初始阶段不做服务端持久化。

### 步骤 3.3 — 文档管理页面

用于管理已索引文档语料库的管理页面。

**要做的事**：

- `DocumentsPage.tsx` — 表格列出所有已索引文档，包含列：
  - 文档名称、来源类型（file/confluence/code/ediprod）、索引日期、块数量
  - 每个文档的删除操作
- `DocumentUpload.tsx` — 拖拽上传区域（接受 PDF、MD、TXT）
- 摄入控制：
  - "同步 Confluence" 按钮 → 调用 `POST /api/ingest/confluence`
  - "同步仓库" 按钮 → 调用 `POST /api/ingest/repository`（带仓库 URL 输入）
  - "同步 ediProd" 按钮 → 调用 `POST /api/ingest/ediprod`
  - 每个同步任务的状态指示器（轮询 `GET /api/ingest/status`）

### 步骤 3.4 — API 客户端层

与后端通信的类型化 API 客户端函数。

**要做的事**：

- `api/client.ts` — 基础配置：
  - 基础 URL 来自环境变量（`VITE_API_BASE_URL`，默认 `/api`）
  - 错误处理包装器
- `api/chat.ts`：
  - `sendMessage(question: string): AsyncGenerator<ChatEvent>` — 打开 SSE 连接，逐个产出 token 事件
  - `ChatEvent`、`ChatResponse`、`SourceInfo` 的类型定义
- `api/documents.ts`：
  - `uploadDocument(file: File): Promise<UploadResult>`
  - `listDocuments(): Promise<DocumentInfo[]>`
  - `deleteDocument(id: string): Promise<void>`
  - `triggerIngestion(sourceType: string, config?: object): Promise<JobStatus>`
  - `getIngestionStatus(jobId?: string): Promise<JobStatus[]>`

### 阶段三验证

1. 同时启动后端（`uvicorn`）和前端（`npm run dev`）
2. 在浏览器打开 `http://localhost:5173`
3. 输入问题 → 看到流式回答逐 token 出现，下方附带源引用
4. 导航到文档页面 → 看到已索引文档列表
5. 上传新文件 → 看到它出现在列表中
6. 针对新上传的内容提问 → 获得正确答案

---

## 阶段四：容器化与部署

**目标**：将全栈打包为 Docker 容器，实现可复现的本地服务器部署，并可选支持 Kubernetes。

### 步骤 4.1 — Docker 配置

创建 Dockerfile 和 Compose 配置文件。

**要做的事**：

**`backend/Dockerfile`**：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`frontend/Dockerfile`**：

```dockerfile
# 构建阶段
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 部署阶段
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**`docker-compose.yml`**（仓库根目录）：

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - chroma_data:/app/chroma_db
      - ./docs:/app/docs
    depends_on:
      - chromadb

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  chroma_data:
```

**注意**：在生产 Docker 模式下，后端应通过 `chromadb:8000`（HTTP 客户端模式）连接 ChromaDB 容器，而非使用本地目录。需更新 `vectorstore_service.py` 以同时支持本地持久化和 HTTP 客户端模式。

### 步骤 4.2 — 本地部署

任何本地服务器的一键部署。

**要做的事**：

```bash
# 克隆并部署
git clone <repo_url>
cd WTG.Query.RAG
cp .env.example .env
# 编辑 .env 添加你的 API 密钥

# 构建并启动所有服务
docker compose up --build -d

# 验证
curl http://localhost:8000/api/health   # 后端
curl http://localhost:3000               # 前端
```

- 所有数据持久化在 `chroma_data` Docker 卷中
- 上传的文档从宿主机 `./docs` 挂载
- 日志：`docker compose logs -f backend`

### 步骤 4.3 — Kubernetes 清单（未来）

当部署需要扩展到单台服务器以上时。

**要做的事**：

- 创建 `k8s/` 目录，包含：

| 文件 | 资源 | 备注 |
|---|---|---|
| `namespace.yaml` | Namespace `wtg-rag` | 资源隔离 |
| `backend-deployment.yaml` | Deployment + Service | 1-2 副本，资源限制 |
| `frontend-deployment.yaml` | Deployment + Service | 1 副本，Nginx |
| `chromadb-statefulset.yaml` | StatefulSet + Service + PVC | 向量数据持久存储 |
| `configmap.yaml` | ConfigMap | 非敏感配置 |
| `secret.yaml` | Secret | API 密钥（生产环境使用外部密钥管理器） |
| `ingress.yaml` | Ingress | 前端和 API 的 HTTP 路由 |

- 可选：在 `helm/wtg-rag/` 下创建 **Helm chart**，用于跨环境的参数化部署

### 阶段四验证

1. 运行 `docker compose up --build` — 所有 3 个容器启动并通过健康检查
2. 打开 `http://localhost:3000` — React UI 加载
3. 上传文档 → 提问 → 收到正确回答
4. 运行 `docker compose down && docker compose up` — 数据持久化（ChromaDB 卷）
5. *（K8S）* `kubectl apply -k k8s/` → 所有 Pod 运行中，Ingress 可访问

---

## 阶段五：增强功能 — MemPalace 与高级检索

**目标**：通过 MemPalace 添加对话记忆，并通过混合搜索和重排序提升检索质量。

### 步骤 5.1 — MemPalace 集成

使用 [MemPalace](https://github.com/MemPalace/mempalace) 作为对话记忆层，缓存历史问答对并在未来相似问题中返回。

**MemPalace 是什么**：一个本地优先的 AI 记忆系统，使用语义搜索存储原始文本，组织为"记忆宫殿"结构（翼、房间、抽屉）。其默认后端是 ChromaDB。它擅长检索过去的对话和交互。

**在本项目中的定位**：

1. **每次问答后**：将问题、回答和检索到的源元数据作为"对话"存入专用的 MemPalace 翼（例如 `wtg-rag-qa`）
2. **RAG 检索前**：在 MemPalace 中搜索相似的历史问题
3. **如存在高置信度匹配**（相似度 > 阈值）：立即返回缓存答案，标记为 `"source": "memory"` — 这完全跳过 LLM 调用，几乎即时响应
4. **如无匹配**：正常执行完整 RAG 流水线

**要做的事**：

```bash
# 安装到 RAG conda 环境
conda activate RAG
pip install mempalace

# 初始化宫殿
mempalace init ./mempalace_data
```

- 创建 `backend/app/services/memory_service.py`：
  - `store_qa(question, answer, sources)` — 将问答对存入 MemPalace
  - `search_memory(question) -> Optional[CachedAnswer]` — 搜索相似的历史问答
  - 可配置的相似度阈值（默认：0.92）
- 修改 `rag_service.py`，在运行完整链之前先检查记忆
- 在聊天 API 响应中添加 `"from_memory": true/false` 标志，让 UI 可以标识缓存回答

**优势**：
- 消除重复/相似问题的冗余 LLM 调用
- 缓存查询几乎即时响应
- 记忆随系统使用自然增长

### 步骤 5.2 — 混合搜索（向量 + 关键词）

通过结合语义向量搜索和传统关键词搜索提升检索质量。

**要做的事**：

- 通过 `langchain_community.retrievers.BM25Retriever` 添加 BM25 关键词搜索
- 使用 `langchain.retrievers.EnsembleRetriever` 与 ChromaDB 向量搜索结合
- 可配置的权重比（默认：0.6 向量 + 0.4 关键词）
- 这有助于处理包含特定标识符、WI 编号、类名或精确术语的查询，纯向量搜索可能会遗漏这些内容

**核心依赖**：`rank-bm25`

```bash
conda activate RAG
pip install rank-bm25
```

### 步骤 5.3 — 交叉编码器重排序

在检索后添加重排序步骤以提升精确度。

**要做的事**：

- 检索 top-K 文档块（例如 K=20）后，通过交叉编码器模型重新评分相关性
- 将最相关的 top-N（例如 N=5）文档块返回给 LLM
- 模型：`cross-encoder/ms-marco-MiniLM-L-6-v2`（小巧、快速、有效）
- 可在 CPU 上本地运行 — 无需 GPU

**核心依赖**：`sentence-transformers`

```bash
# sentence-transformers 受益于 conda 的二进制构建
conda activate RAG
conda install -c conda-forge sentence-transformers
```

### 步骤 5.4 — UX 改进

优化前端用户体验。

**要做的事**：

- 在缓存回答上显示"来自记忆"标识（来自 MemPalace）
- 展开/折叠源文档预览
- 每个回答的点赞/点踩反馈按钮
  - 将反馈存储在本地 SQLite 数据库中
  - 使用反馈数据评估和改进检索质量
- 对话历史侧边栏（列出过去的对话）
- 深色模式支持

### 阶段五验证

1. 提问 → 获得完整 RAG 回答
2. 再次提同样的问题 → 从 MemPalace 获得回答（更快，带"来自记忆"标识）
3. 用特定 WI 编号提问 → 混合搜索返回正确的 ediProd WI
4. 对比有/无重排序时一组测试问题的检索质量
5. 点击差评 → 验证反馈已记录

---

## 目标目录结构

所有阶段完成后：

```
WTG.Query.RAG/
├── Plan.md                          # 本文件（英文版）
├── Plan_Chinese.md                  # 本文件（中文版）
├── README.md                        # 更新后的入门指南
├── docker-compose.yml               # 全栈 compose 文件
├── .env.example                     # 环境配置模板
├── .gitignore
│
├── backend/                         # Python FastAPI 后端
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # Pydantic Settings
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── chat.py          # POST /api/chat (SSE)
│   │   │       ├── documents.py     # 文档 CRUD
│   │   │       └── health.py        # 健康检查
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── rag_service.py       # RAG 编排
│   │   │   ├── vectorstore_service.py
│   │   │   ├── document_service.py
│   │   │   ├── llm_service.py       # 多提供商 LLM 工厂
│   │   │   ├── ingestion_service.py # 摄入编排器
│   │   │   └── memory_service.py    # MemPalace 集成（阶段五）
│   │   └── connectors/
│   │       ├── __init__.py
│   │       ├── base_connector.py    # 抽象基类
│   │       ├── file_connector.py    # PDF/MD/TXT
│   │       ├── confluence_connector.py
│   │       ├── code_connector.py    # Git 仓库
│   │       └── ediprod_connector.py # ediProd WIs
│   └── tests/
│       └── ...
│
├── frontend/                        # React SPA
│   ├── package.json
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── chat.ts
│   │   │   └── documents.ts
│   │   ├── components/
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── SourceCitation.tsx
│   │   │   └── DocumentUpload.tsx
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx
│   │   │   └── DocumentsPage.tsx
│   │   ├── stores/
│   │   │   └── chatStore.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── index.html
│
├── docs/                            # 文档语料库（挂载到后端）
│   └── sample.md
│
├── k8s/                             # Kubernetes 清单（阶段 4.3）
│   ├── namespace.yaml
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── chromadb-statefulset.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── ingress.yaml
│
└── rag.py                           # 旧版 CLI（保留，从 backend 导入）
```

---

## 验证清单

| 阶段 | 测试 | 通过标准 |
|---|---|---|
| 1 | `curl POST /api/chat` 针对 `sample.md` 提问 | 返回带正确源引用的回答 |
| 1 | `curl GET /api/health` | 返回 `{"status": "ok"}` |
| 2 | 通过 API 触发每个连接器 | `GET /api/ingest/status` 显示 `completed`；`GET /api/documents` 显示新条目 |
| 2 | 提问一个只能从 Confluence 内容回答的问题 | 正确回答并引用 Confluence 页面 |
| 3 | 打开 React UI，输入问题 | 流式回答逐 token 出现 |
| 3 | 通过 UI 上传文件，提问其内容 | 正确回答 |
| 4 | `docker compose up --build` | 所有容器健康；端到端问答在 `localhost:3000` 正常工作 |
| 4 | `docker compose down` 然后 `up` | 数据跨重启持久化 |
| 5 | 两次提同样的问题 | 第二次来自记忆（更快，有标识） |
| 5 | 用特定 WI 编号查询 | 混合搜索返回正确的 ediProd 内容 |

---

## 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| RAG 框架 | **LangChain**（保留现有） | 已在使用，最大生态系统，多源连接器，流式支持 |
| 向量数据库 | **ChromaDB** | 本地优先，轻量，已在使用，足以应对 <1K 文档 |
| 对话记忆 | **MemPalace**（阶段五） | 缓存历史问答对，非向量数据库替代品 |
| 后端框架 | **FastAPI** | 异步，原生 SSE 流式，自动 OpenAPI 文档，Pydantic 集成 |
| 前端框架 | **React + TypeScript + Vite** | 按需求指定；快速开发体验，大生态系统 |
| 身份认证 | **延后** | 初始阶段不设认证；需要时添加 SSO/LDAP |
| 部署 | **先 Docker Compose** | 小规模足够；需要时可用 K8S |
| LLM | **灵活（环境变量配置）** | 默认 GitHub Models/OpenAI；Ollama（开发）或 vLLM（生产）用于完全本地 |

---

## 团队协作方案

本项目设计为**两名开发者**并行工作。分工采用**垂直（功能型）**模式而非水平（前端 vs 后端），使**两位开发者都能获得端到端的 RAG 知识** — 从文档摄入、向量化、检索、LLM 生成、流式传输到前端渲染。

### 指导原则

- **交叉所有权** — 每人至少构建一个完整的连接器、一个 API 路由和一个前端页面
- **交叉审查** — 所有 PR 由对方审查
- **交换讲解** — 每个阶段结束时，每人向对方讲解自己的代码
- **阶段一完成后才开始阶段二/三** — 阶段一是基础；阶段二和阶段三之后可以并行推进

### 阶段一 — 后端 API 基础

| 模块 | 成员 A | 成员 B |
|---|---|---|
| **FastAPI 骨架** | | `main.py`、CORS、路由注册、`config.py`（Pydantic Settings） |
| **LLM 层** | `llm_service.py`（多提供商工厂）、`rag_service.py`（LCEL 链 + 流式） | |
| **数据层** | | `vectorstore_service.py`、`document_service.py`（分块） |
| **API 路由** | `chat.py`（POST /api/chat，SSE 流式） | `health.py`、`documents.py`（上传/列表/删除） |

**学习成果**：A 掌握 LLM 集成 + RAG 链构建 + SSE 流式；B 掌握向量存储操作 + 文档处理 + API 设计。

**检查点**：A 向 B 讲解 LCEL 链和流式内部原理；B 向 A 讲解 ChromaDB 操作和分块策略。

### 阶段二 — 数据源连接器

| 模块 | 成员 A | 成员 B |
|---|---|---|
| **连接器基类** | `base_connector.py`（两人共同设计接口） | |
| **文件连接器** | `file_connector.py`（从 `rag.py` 重构） | |
| **代码连接器** | `code_connector.py`（Language-aware 分割器） | |
| **Confluence 连接器** | | `confluence_connector.py`（LangChain ConfluenceLoader） |
| **ediProd 连接器** | | `ediprod_connector.py`（mock → 真实 API） |
| **摄入编排器** | | `ingestion_service.py`（调度 + 状态追踪） |
| **摄入 API 路由** | `/api/ingest/files`、`/api/ingest/repository` | `/api/ingest/confluence`、`/api/ingest/ediprod`、`/api/ingest/status` |

**学习成果**：两位开发者都编写连接器，覆盖完整的摄入流水线（获取 → 分块 → 嵌入 → 存储）。A 侧重代码感知分割；B 侧重外部系统集成。

### 阶段三 — React 前端

| 模块 | 成员 A | 成员 B |
|---|---|---|
| **项目搭建** | Vite + React + Tailwind + Zustand 初始化 | |
| **聊天页面** | `ChatPage.tsx`、`ChatMessage.tsx`、`ChatInput.tsx`、`SourceCitation.tsx` | |
| **SSE 客户端** | `api/chat.ts`（EventSource / ReadableStream） | |
| **文档管理页面** | | `DocumentsPage.tsx`、`DocumentUpload.tsx` |
| **摄入控制** | | 同步按钮 + 状态轮询 |
| **API 客户端基础** | | `api/client.ts`、`api/documents.ts` |

**学习成果**：A 掌握 SSE 流式消费 + Markdown 渲染；B 掌握文件上传 + 异步任务状态管理。两人都学习 React + TypeScript。

### 阶段四 — 容器化（结对编程）

此阶段建议通过**结对编程**共同完成：

- A 主导：`backend/Dockerfile` + `docker-compose.yml`
- B 主导：`frontend/Dockerfile` + `nginx.conf`
- 共同调试和集成测试

**理由**：Docker 和部署知识对两位开发者都很重要，且工作量不大，结对比分开更高效。

### 阶段五 — 增强功能

| 模块 | 成员 A | 成员 B |
|---|---|---|
| **混合搜索** | BM25 + EnsembleRetriever（向量 + 关键词） | |
| **交叉编码器重排序** | sentence-transformers reranker | |
| **MemPalace 集成** | | `memory_service.py`（存储/检索问答缓存） |
| **MemPalace → RAG 串联** | | 修改 `rag_service.py`：先查记忆 → 再走完整 RAG |
| **UX 增强** | | "来自记忆"标识、反馈按钮 |
| **质量评估** | 编写测试问题集；对比有/无重排序的效果 | 编写测试问题集；对比有/无记忆缓存的响应速度 |

### 知识覆盖矩阵

| RAG 概念 | 成员 A | 成员 B |
|---|---|---|
| LLM 集成（多提供商） | ✅ 阶段一主导 | 📖 阶段一审查 |
| RAG 链（LCEL） | ✅ 阶段一主导 | ✅ 阶段五修改 rag_service |
| 嵌入 + 向量存储 | 📖 阶段一审查 | ✅ 阶段一主导 |
| 文档分块 | ✅ 阶段二（代码感知） | ✅ 阶段一（通用） |
| 数据连接器开发 | ✅ 阶段二（文件 + 代码） | ✅ 阶段二（Confluence + ediProd） |
| SSE 流式（后端） | ✅ 阶段一聊天路由 | 📖 审查 |
| SSE 流式（前端） | ✅ 阶段三聊天 UI | 📖 审查 |
| React 前端 | ✅ 阶段三（聊天） | ✅ 阶段三（文档管理） |
| Docker 部署 | ✅ 阶段四结对 | ✅ 阶段四结对 |
| 检索增强（混合/重排序） | ✅ 阶段五主导 | 📖 审查 |
| 对话记忆（MemPalace） | 📖 审查 | ✅ 阶段五主导 |

✅ = 主导实现 &nbsp;&nbsp; 📖 = 通过代码审查 + 讲解学习

### 协作规则

1. **交换讲解** — 每个阶段结束时，每人向对方展示自己的代码。这是主要的知识传递机制。
2. **强制交叉审查** — A 的 PR 由 B 审查，反之亦然。禁止自行合并。
3. **顺序启动，并行推进** — 先共同完成阶段一。然后阶段二和阶段三可以并行推进。
4. **共享设计决策** — 两位开发者在独立实现前共同设计 `base_connector.py` 接口和 SSE 事件格式。

---

## 待解决问题

1. **ediProd API 访问方式** — ediProd 连接器访问工作项数据的首选方式是什么？选项：REST API、MCP 工具或直接数据库查询。
2. **Confluence 凭据** — 是否有可用于 Confluence API 访问的服务账号？应索引哪些空间？
3. **多语言支持** — 如果问答将同时使用中文和英文进行，嵌入模型应切换为 `multilingual-e5-large` 或 `bge-m3` 以获得更好的跨语言检索效果。是否需要？
4. **本地 LLM 偏好** — 如使用 Ollama 进行完全离线操作，首选哪个模型？推荐：`qwen2.5:14b`（多语言）、`llama3.1:8b`（英文为主）、`mistral:7b`（通用）。
5. **要索引的 Git 仓库** — 代码连接器应包含哪些 WTG 仓库？包含所有公开仓库还是精选列表？
