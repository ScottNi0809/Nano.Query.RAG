# WTG.Query.RAG — Project Plan

> A Retrieval-Augmented Generation (RAG) Q&A system for WiseTechGlobal internal content.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Local Prerequisites & Tool Installation](#local-prerequisites--tool-installation)
- [Phase 1: Backend API Foundation](#phase-1-backend-api-foundation)
- [Phase 2: Data Source Connectors](#phase-2-data-source-connectors)
- [Phase 3: React Frontend](#phase-3-react-frontend)
- [Phase 4: Containerization & Deployment](#phase-4-containerization--deployment)
- [Phase 5: Enhancements — MemPalace & Advanced Retrieval](#phase-5-enhancements--mempalace--advanced-retrieval)
- [Target Directory Structure](#target-directory-structure)
- [Verification Checklist](#verification-checklist)
- [Key Decisions](#key-decisions)
- [Open Questions](#open-questions)

---

## Overview

Build a full-stack RAG Q&A system that allows WiseTechGlobal employees to ask natural-language questions against internal content and receive grounded, citation-backed answers.

**Data sources** (ingested into the vector store):

| Source | Examples |
|---|---|
| Internal documentation | Markdown files, PDF manuals, text files |
| Confluence / Wiki | Team spaces, knowledge-base articles |
| Source code repositories | CargoWise, Glow, and other WTG repos |
| ediProd work items | WI descriptions, task notes, incident reports |

**Key properties**:

- Local-first — all data and models can run on-premises, nothing leaves the network unless explicitly configured
- LLM-agnostic — swap between OpenAI, Azure OpenAI, GitHub Models, or a fully local Ollama model via a single env variable
- Small scale initially — fewer than 1,000 documents, fewer than 10 concurrent users
- No authentication in initial phases (deferred)

---

## Architecture

```
                        ┌──────────────────────────────────────────────────────────┐
                        │                     Local Server / K8S Cluster           │
┌─────────────┐         │                                                          │
│             │  HTTP   │  ┌─────────────────────────────────────────────────────┐  │
│  React SPA  │────────▶│  │  FastAPI Backend (Python)                           │  │
│  (Chat UI)  │◀────────│  │                                                     │  │
│             │  SSE    │  │  ┌──────────────┐   ┌──────────────┐                │  │
└─────────────┘         │  │  │  LangChain   │──▶│   ChromaDB   │                │  │
   Vite + TS            │  │  │  RAG Chain   │   │  VectorStore │                │  │
                        │  │  └──────┬───────┘   └──────────────┘                │  │
                        │  │         │                                            │  │
                        │  │  ┌──────▼───────┐   ┌──────────────────────────┐     │  │
                        │  │  │     LLM      │   │  Ingestion Pipeline      │     │  │
                        │  │  │  (flexible)  │   │  File│Confluence│Git│edi │     │  │
                        │  │  └──────────────┘   └──────────────────────────┘     │  │
                        │  │                                                     │  │
                        │  │  ┌──────────────────────────────────────────────┐    │  │
                        │  │  │ [Phase 5] MemPalace — Q&A Conversation Cache│    │  │
                        │  │  └──────────────────────────────────────────────┘    │  │
                        │  └─────────────────────────────────────────────────────┘  │
                        └──────────────────────────────────────────────────────────┘
```

**Data flow**:

1. **Ingestion** — Connectors pull content from data sources → chunk → embed → store in ChromaDB.
2. **Query** — User types a question in the React chat UI → FastAPI receives the request → LangChain retrieves relevant chunks from ChromaDB → LLM generates an answer grounded in those chunks → streamed back to the UI via SSE.
3. **Memory** *(Phase 5)* — After each Q&A, the pair is stored in MemPalace. On subsequent queries, MemPalace is checked first; if a high-confidence match exists, the cached answer is returned directly.

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend** | React | 19.x | Chat UI SPA |
| | TypeScript | 5.x | Type safety |
| | Vite | 6.x | Build tool & dev server |
| | Ant Design *or* Shadcn/ui | latest | UI component library |
| | Tailwind CSS | 4.x | Utility-first styling |
| **Backend** | Python | 3.11+ | Runtime |
| | FastAPI | 0.115+ | REST API framework |
| | Uvicorn | 0.34+ | ASGI server |
| | Pydantic | 2.x | Config & validation |
| **RAG** | LangChain | >=0.3 | Orchestration framework |
| | LangChain Community | >=0.3 | Data source loaders |
| | LangChain OpenAI | >=0.3 | OpenAI/Azure/GitHub Models integration |
| **Vector DB** | ChromaDB | >=0.6 | Local-first vector store |
| **Embedding** | text-embedding-3-large *(default)* | — | OpenAI embedding model |
| | bge-m3 / multilingual-e5-large *(optional)* | — | Local multilingual alternative |
| **LLM** | GPT-4o *(default)* | — | Cloud LLM |
| | Llama 3 / Qwen 2.5 / Mistral *(optional)* | — | Local LLM via Ollama |
| **Memory** | MemPalace *(Phase 5)* | >=3.3 | Conversation memory & caching |
| **Infra** | Docker | 27.x | Containerization |
| | Docker Compose | 2.x | Local multi-container orchestration |
| | Kubernetes *(future)* | 1.30+ | Production orchestration |

### Why LangChain?

The existing `rag.py` is already LangChain-based — keeping it avoids a rewrite. LangChain also provides:

- Built-in loaders for Confluence, Git repos, PDF, Markdown, and many more
- LCEL (LangChain Expression Language) for composable, streaming-capable chains
- The largest ecosystem and community of any RAG framework
- If the team later finds LangChain too heavy, LlamaIndex is a migration target with similar concepts

---

## Local Prerequisites & Tool Installation

Install the following tools **before starting development**. All commands below use WSL (Ubuntu/Debian). If you haven't enabled WSL yet, run `wsl --install` from a Windows terminal first.

### 1. Python 3.11+

The backend runtime. Required for FastAPI, LangChain, and all Python dependencies.

```bash
# Check existing version
python3 --version

# Install on Ubuntu/Debian (WSL)
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# Or install a specific version via deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

**Verify**: `python3 --version` → `Python 3.12.x`

### 2. Node.js 20+ & npm

Required for the React frontend build toolchain (Vite, TypeScript, etc.).

```bash
# Install via nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install --lts
nvm use --lts

# Or via NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**Verify**: `node --version` → `v20.x.x` and `npm --version` → `10.x.x`

### 3. Git

Version control. Almost certainly already installed in WSL.

```bash
git --version

# If not installed:
sudo apt install -y git
```

### 4. Docker

Required for containerization (Phase 4) and running ChromaDB as a container during development.

**Option A — Docker Desktop (Windows host, shared with WSL)**:

Install Docker Desktop on Windows and enable "Use the WSL 2 based engine" + "Enable integration with my default WSL distro" in Settings > Resources > WSL Integration.

**Option B — Docker Engine inside WSL**:

```bash
# Install Docker Engine
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add current user to docker group (avoids sudo)
sudo usermod -aG docker $USER
newgrp docker
```

**Verify**: `docker --version` and `docker compose version`

### 5. uv (Recommended Python Package Manager)

A fast Python package manager that replaces pip + venv. Optional but strongly recommended.

```bash
# Install via standalone installer (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Or via pip
pip install uv
```

**Verify**: `uv --version`

### 6. Ollama (Optional — for Local LLM)

Only needed if you want to run LLMs locally without cloud API calls.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service (if not auto-started)
ollama serve &

# Pull models
ollama pull llama3.1
ollama pull nomic-embed-text    # local embedding model
```

**Verify**: `ollama --version` and `ollama list`

### 7. kubectl & Helm (Optional — for K8S, Phase 4)

Only needed when deploying to Kubernetes.

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

**Verify**: `kubectl version --client` and `helm version`

### Tool Summary Table

| Tool | Required? | Phase Needed | Install Command (WSL / bash) |
|---|---|---|---|
| Python 3.11+ | **Yes** | Phase 1+ | `sudo apt install -y python3 python3-pip python3-venv` |
| Node.js 20+ | **Yes** | Phase 3+ | `nvm install --lts` (via nvm) |
| Git | **Yes** | All | `sudo apt install -y git` |
| Docker | **Yes** | Phase 4+ (optional earlier) | Docker Desktop WSL integration or `docker-ce` in WSL |
| uv | Recommended | Phase 1+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Ollama | Optional | Phase 1+ (if local LLM) | `curl -fsSL https://ollama.com/install.sh \| sh` |
| kubectl | Optional | Phase 4 (K8S only) | `curl -LO ... && sudo install kubectl` |
| Helm | Optional | Phase 4 (K8S only) | `curl ... \| bash` (get-helm-3) |

---

## Phase 1: Backend API Foundation

**Goal**: Refactor the current CLI-based `rag.py` into a production-ready FastAPI backend with a REST API that the React frontend can consume.

### Step 1.1 — Project Structure Setup

Create the backend Python package with proper project configuration.

**What to do**:

- Create a `backend/` directory at the repo root
- Initialize `backend/pyproject.toml` with all Python dependencies
- Set up a Python package under `backend/app/` with `__init__.py` files
- Move reusable logic from the current `rag.py` into the new package

**Key dependencies** (in `pyproject.toml`):

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

**How to bootstrap**:

```bash
cd ~/git/WTG.Query.RAG
mkdir -p backend/app/api/routes
mkdir -p backend/app/services
mkdir -p backend/app/connectors

# Initialize with uv (recommended)
cd backend
uv init --name wtg-query-rag
uv add fastapi uvicorn langchain langchain-community langchain-openai \
  langchain-chroma chromadb pypdf python-dotenv sse-starlette \
  python-multipart pydantic-settings
```

### Step 1.2 — FastAPI Application

Build the core API application with CORS, routing, and streaming support.

**What to do**:

- Create `backend/app/main.py` — FastAPI application entry point with CORS middleware (allows the React dev server to call the API)
- Create route modules under `backend/app/api/routes/`:

| File | Endpoints | Description |
|---|---|---|
| `chat.py` | `POST /api/chat` | Accepts a question, returns an answer with source citations. Supports SSE streaming for token-by-token output. |
| `documents.py` | `POST /api/documents/upload` | Upload PDF/MD/TXT files for ingestion |
| | `GET /api/documents` | List all indexed documents with metadata |
| | `DELETE /api/documents/{id}` | Remove a document from the vector store |
| `health.py` | `GET /api/health` | Health check — returns backend status and ChromaDB connectivity |

**SSE streaming detail**: The `/api/chat` endpoint uses `sse-starlette` to stream LLM tokens as they are generated. The response format:

```
event: token
data: {"content": "The"}

event: token
data: {"content": " answer"}

event: sources
data: {"sources": [{"title": "doc.md", "page": 1, "score": 0.92}]}

event: done
data: {}
```

**How to run** (development):

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### Step 1.3 — RAG Service Layer

Extract and modularize the RAG logic from the current `rag.py` into clean service classes.

**What to do**:

| Service File | Responsibility | Refactored From |
|---|---|---|
| `services/rag_service.py` | Orchestrates the full RAG pipeline: receive question → retrieve chunks → generate answer → return with sources | `get_qa_chain()` in `rag.py` |
| `services/vectorstore_service.py` | ChromaDB operations: initialize store, add documents, similarity search, delete by ID | `build_vectorstore()` in `rag.py` |
| `services/document_service.py` | Load files from disk or uploads, split into chunks with `RecursiveCharacterTextSplitter` | `load_documents()` in `rag.py` |
| `services/llm_service.py` | Create the appropriate LLM and embedding instances based on provider config | `get_llm_config()` in `rag.py` |

**Key design decisions**:

- Use **dependency injection** via FastAPI's `Depends()` so services are testable and swappable
- The `rag_service` uses LangChain's LCEL (`RunnableSequence`) instead of the legacy `RetrievalQA` chain, enabling native streaming
- ChromaDB `persist_directory` defaults to `./chroma_db` (same as current) but is configurable

### Step 1.4 — Multi-LLM Provider Support

Make the LLM backend configurable so the team can switch between cloud and local models.

**What to do**:

Configure via a single environment variable `LLM_PROVIDER`:

| `LLM_PROVIDER` | LLM Class | Embedding Class | Required Env Vars | Notes |
|---|---|---|---|---|
| `openai` | `ChatOpenAI` | `OpenAIEmbeddings` | `OPENAI_API_KEY` | Direct OpenAI API |
| `azure` | `AzureChatOpenAI` | `AzureOpenAIEmbeddings` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | Enterprise Azure deployment |
| `github` | `ChatOpenAI` (custom base_url) | `OpenAIEmbeddings` (custom base_url) | `GITHUB_TOKEN` | GitHub Models endpoint (current default) |
| `ollama` | `ChatOllama` | `OllamaEmbeddings` | `OLLAMA_BASE_URL` (default `http://localhost:11434`) | Fully local, no API key needed |

The `llm_service.py` factory method returns the correct LangChain LLM and embedding instances based on this config. All downstream code is provider-agnostic.

### Step 1.5 — Configuration Management

Centralize all configuration using Pydantic Settings.

**What to do**:

- Create `backend/app/config.py` with a `Settings` class that reads from environment variables and `.env` files
- Create `.env.example` at the repo root documenting every configuration key

**Example `.env.example`**:

```env
# LLM Provider: openai | azure | github | ollama
LLM_PROVIDER=github

# GitHub Models (default)
GITHUB_TOKEN=your_github_token_here

# OpenAI (if LLM_PROVIDER=openai)
# OPENAI_API_KEY=sk-...

# Azure OpenAI (if LLM_PROVIDER=azure)
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Ollama (if LLM_PROVIDER=ollama)
# OLLAMA_BASE_URL=http://localhost:11434

# Model names
MODEL_NAME=gpt-4o
EMBEDDING_MODEL=text-embedding-3-large

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db

# Ingestion
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Phase 1 Verification

```bash
# Start the backend
cd backend
uvicorn app.main:app --reload --port 8000

# Test health check
curl http://localhost:8000/api/health

# Upload a document
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@../docs/sample.md"

# Ask a question
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is WTG.Query.RAG?"}'
```

Expected: Returns a JSON response with an answer grounded in `sample.md` content and source citations.

---

## Phase 2: Data Source Connectors

**Goal**: Build ingestion connectors for all four target data sources so that WTG internal content can be automatically pulled, chunked, embedded, and stored in ChromaDB.

### Step 2.1 — File Connector (Markdown / PDF / TXT)

**Already partially implemented** — the current `rag.py` `load_documents()` function handles this. Refactor it into the connector pattern.

**What to do**:

- Create `backend/app/connectors/base_connector.py` — abstract base class defining the connector interface:
  ```python
  class BaseConnector(ABC):
      @abstractmethod
      async def fetch_documents(self) -> list[Document]: ...
      @abstractmethod
      async def get_metadata(self) -> dict: ...
  ```
- Create `backend/app/connectors/file_connector.py`:
  - Accept a directory path or uploaded files
  - Use `PyPDFLoader` for PDFs, `UnstructuredMarkdownLoader` for `.md`, `TextLoader` for `.txt`
  - Attach metadata: `source_type=file`, `file_path`, `file_name`, `file_type`
- Expose via `POST /api/documents/upload` (single or batch file upload) and `POST /api/ingest/files` (scan a directory)

**Key dependency**: `pypdf`, `unstructured` (already in requirements)

### Step 2.2 — Confluence / Wiki Connector

Pull pages from Atlassian Confluence spaces and index them.

**What to do**:

- Create `backend/app/connectors/confluence_connector.py`
- Use LangChain's `ConfluenceLoader` (`langchain_community.document_loaders.ConfluenceLoader`)
- Configuration (via env / API request):
  - `CONFLUENCE_URL` — Base URL of the Confluence instance
  - `CONFLUENCE_USERNAME` — Service account username
  - `CONFLUENCE_API_TOKEN` — API token for authentication
  - `CONFLUENCE_SPACE_KEYS` — Comma-separated list of space keys to index (e.g., `"ENG,OPS,ARCH"`)
- Features:
  - **Full sync**: Pull all pages from configured spaces
  - **Incremental sync**: Track the `last_modified` timestamp per page; on subsequent syncs, only fetch updated pages
  - **Metadata**: `source_type=confluence`, `space_key`, `page_title`, `page_url`, `last_modified`
- Expose via `POST /api/ingest/confluence`

**Key dependency**: `atlassian-python-api` (add to `pyproject.toml`)

```bash
uv add atlassian-python-api
```

### Step 2.3 — Source Code Repository Connector

Index source code from WTG Git repositories for code-aware search.

**What to do**:

- Create `backend/app/connectors/code_connector.py`
- Two approaches (configure per repo):
  - **LangChain GitLoader**: `langchain_community.document_loaders.GitLoader` — clone and walk
  - **Custom file walk**: Clone repo to a temp directory, walk files with extension filter
- Configuration:
  - `repo_url` — Git clone URL
  - `branch` — Branch to index (default: `main`)
  - `include_extensions` — File types to include (default: `.cs, .py, .md, .xml, .json, .yaml, .sql`)
  - `exclude_paths` — Directories to skip (default: `bin/, obj/, node_modules/, .git/`)
- **Code-aware chunking**:
  - For `.cs`, `.py`, `.ts` files: use `langchain.text_splitter.Language`-aware splitters that respect function/class boundaries
  - For `.md` and text: use `RecursiveCharacterTextSplitter` (same as current)
- **Metadata**: `source_type=code`, `repo_name`, `file_path`, `language`, `branch`
- Expose via `POST /api/ingest/repository` with body `{"repo_url": "...", "branch": "main"}`

**Key dependency**: `gitpython` (add to `pyproject.toml`)

```bash
uv add gitpython
```

### Step 2.4 — ediProd Work Items Connector

Index work items, task notes, and incident data from ediProd.

**What to do**:

- Create `backend/app/connectors/ediprod_connector.py`
- Access method: **TBD** — options include:
  - Direct REST API calls to ediProd (if available)
  - MCP tool integration (`mcp_ediprod_*` tools)
  - Database query (if direct DB access is permitted)
- Data to extract per work item:
  - WI number, title, description (full text)
  - Task notes (timestamped entries)
  - Status, priority, assigned team
  - Related incidents (if ISS type)
- **Chunking**: Each WI becomes one or more chunks depending on length. Task notes are chunked separately with WI number as metadata.
- **Metadata**: `source_type=ediprod`, `wi_number`, `wi_type`, `status`, `team`
- **Sync schedule**: Configurable periodic sync (e.g., every 4 hours) or manual trigger
- Expose via `POST /api/ingest/ediprod`

> **Note**: This connector's implementation depends on the ediProd access method being confirmed. Start with a mock connector that reads from a JSON file for development, then replace with the real API integration.

### Step 2.5 — Ingestion Pipeline Orchestrator

Unified service that coordinates all connectors.

**What to do**:

- Create `backend/app/services/ingestion_service.py` with:
  - `ingest(source_type, config)` — Dispatch to the appropriate connector, chunk, embed, store
  - **Deduplication**: Compute a hash of each chunk's content + source metadata. Before inserting into ChromaDB, check if the hash exists; skip if it does.
  - **Background execution**: Use FastAPI's `BackgroundTasks` for small jobs. For longer ingestion runs (large repos, full Confluence sync), consider a task queue (Celery + Redis) in the future.
  - **Status tracking**: Store ingestion job status (pending/running/completed/failed) in an in-memory dict (or SQLite for persistence)
- Admin API endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/api/ingest/files` | POST | Trigger file directory scan |
| `/api/ingest/confluence` | POST | Trigger Confluence space sync |
| `/api/ingest/repository` | POST | Trigger Git repo indexing |
| `/api/ingest/ediprod` | POST | Trigger ediProd WI sync |
| `/api/ingest/status` | GET | List all ingestion jobs with status |
| `/api/ingest/status/{job_id}` | GET | Get status of a specific job |

### Phase 2 Verification

For each connector:

1. Trigger an ingestion via the API endpoint
2. Check `GET /api/ingest/status/{job_id}` shows `completed`
3. Check `GET /api/documents` lists the newly ingested documents with correct metadata
4. Ask a question via `POST /api/chat` that can only be answered from the newly ingested content
5. Verify the answer is correct and cites the right source

---

## Phase 3: React Frontend

**Goal**: Build a React single-page application with a conversational chat interface and a document management page.

### Step 3.1 — React Project Setup

Scaffold the frontend project with modern tooling.

**What to do**:

```bash
cd ~/git/WTG.Query.RAG

# Create React + TypeScript project with Vite
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install

# Install UI libraries
npm install antd @ant-design/icons          # OR: npx shadcn@latest init
npm install tailwindcss @tailwindcss/vite    # Tailwind CSS
npm install react-markdown remark-gfm        # Markdown rendering
npm install react-syntax-highlighter         # Code block highlighting
npm install zustand                          # Lightweight state management
npm install axios                            # HTTP client (optional, can use fetch)
```

**Project structure**:

```
frontend/
├── src/
│   ├── api/              # Backend API client functions
│   │   ├── client.ts     # Base Axios/fetch config
│   │   ├── chat.ts       # Chat API with SSE streaming
│   │   └── documents.ts  # Document CRUD API
│   ├── components/       # Reusable UI components
│   │   ├── ChatMessage.tsx
│   │   ├── ChatInput.tsx
│   │   ├── SourceCitation.tsx
│   │   └── DocumentUpload.tsx
│   ├── pages/            # Top-level page components
│   │   ├── ChatPage.tsx
│   │   └── DocumentsPage.tsx
│   ├── stores/           # Zustand state stores
│   │   └── chatStore.ts
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

**Vite dev server proxy** (in `vite.config.ts`):

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

### Step 3.2 — Chat Interface

The primary user-facing page: a conversational Q&A interface.

**What to do**:

- `ChatPage.tsx` — Full-page chat layout with message list and input bar at the bottom
- `ChatMessage.tsx` — Renders a single message bubble:
  - **User messages**: Right-aligned, simple text
  - **Assistant messages**: Left-aligned, rendered as Markdown (supports code blocks, tables, lists)
  - **Source citations**: Collapsible section below assistant messages showing which documents were used, with relevance scores
- `ChatInput.tsx` — Text input with send button, supports Enter to send, Shift+Enter for newline
- **SSE streaming implementation**:
  - Use the browser `EventSource` API or a manual `fetch()` with `ReadableStream` to consume SSE from `POST /api/chat`
  - Display tokens as they arrive (typewriter effect)
  - Show a "thinking..." indicator while waiting for the first token
- `SourceCitation.tsx` — Shows source document name, page/section, and relevance score. Clicking expands a preview of the relevant chunk text.
- **Chat history**: Stored in Zustand store; persists for the session. No server-side persistence initially.

### Step 3.3 — Document Management Page

An admin-style page for managing the indexed document corpus.

**What to do**:

- `DocumentsPage.tsx` — Table listing all indexed documents with columns:
  - Document name, source type (file/confluence/code/ediprod), indexed date, chunk count
  - Delete action per document
- `DocumentUpload.tsx` — Drag-and-drop file upload zone (accepts PDF, MD, TXT)
- Ingestion controls:
  - "Sync Confluence" button → calls `POST /api/ingest/confluence`
  - "Sync Repository" button → calls `POST /api/ingest/repository` (with repo URL input)
  - "Sync ediProd" button → calls `POST /api/ingest/ediprod`
  - Status indicator per sync job (polling `GET /api/ingest/status`)

### Step 3.4 — API Client Layer

Typed API client functions for communicating with the backend.

**What to do**:

- `api/client.ts` — Base configuration:
  - Base URL from env (`VITE_API_BASE_URL`, defaults to `/api`)
  - Error handling wrapper
- `api/chat.ts`:
  - `sendMessage(question: string): AsyncGenerator<ChatEvent>` — Opens SSE connection, yields token events
  - Type definitions for `ChatEvent`, `ChatResponse`, `SourceInfo`
- `api/documents.ts`:
  - `uploadDocument(file: File): Promise<UploadResult>`
  - `listDocuments(): Promise<DocumentInfo[]>`
  - `deleteDocument(id: string): Promise<void>`
  - `triggerIngestion(sourceType: string, config?: object): Promise<JobStatus>`
  - `getIngestionStatus(jobId?: string): Promise<JobStatus[]>`

### Phase 3 Verification

1. Start backend (`uvicorn`) and frontend (`npm run dev`) concurrently
2. Open `http://localhost:5173` in a browser
3. Type a question → see streaming answer appear token by token with source citations below
4. Navigate to Documents page → see indexed documents listed
5. Upload a new file → see it appear in the list
6. Ask a question about the newly uploaded content → get a correct answer

---

## Phase 4: Containerization & Deployment

**Goal**: Package the full stack into Docker containers for reproducible local server deployment, with optional Kubernetes support.

### Step 4.1 — Docker Setup

Create Dockerfiles and a Compose configuration for the full stack.

**What to do**:

**`backend/Dockerfile`**:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install uv && uv sync --no-dev
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`frontend/Dockerfile`**:

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**`docker-compose.yml`** (at repo root):

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

**Note**: In production Docker mode, the backend should connect to the ChromaDB container via `chromadb:8000` (HTTP client mode) instead of using a local directory. Update `vectorstore_service.py` to support both local persistence and HTTP client modes.

### Step 4.2 — Local Deployment

Single-command deployment for any local server.

**What to do**:

```bash
# Clone and deploy
git clone <repo_url>
cd WTG.Query.RAG
cp .env.example .env
# Edit .env with your API keys

# Build and start all services
docker compose up --build -d

# Verify
curl http://localhost:8000/api/health   # Backend
curl http://localhost:3000               # Frontend
```

- All data persists in the `chroma_data` Docker volume
- Uploaded documents are mounted from `./docs` on the host
- Logs: `docker compose logs -f backend`

### Step 4.3 — Kubernetes Manifests (Future)

When the deployment needs to scale beyond a single server.

**What to do**:

- Create `k8s/` directory with:

| File | Resource | Notes |
|---|---|---|
| `namespace.yaml` | Namespace `wtg-rag` | Isolate resources |
| `backend-deployment.yaml` | Deployment + Service | 1-2 replicas, resource limits |
| `frontend-deployment.yaml` | Deployment + Service | 1 replica, Nginx |
| `chromadb-statefulset.yaml` | StatefulSet + Service + PVC | Persistent storage for vector data |
| `configmap.yaml` | ConfigMap | Non-secret configuration |
| `secret.yaml` | Secret | API keys (use external secret manager in production) |
| `ingress.yaml` | Ingress | HTTP routing for frontend and API |

- Optional: Create a **Helm chart** under `helm/wtg-rag/` for parameterized deployment across environments

### Phase 4 Verification

1. Run `docker compose up --build` — all 3 containers start and pass health checks
2. Open `http://localhost:3000` — React UI loads
3. Upload a document → ask a question → receive a correct answer
4. Run `docker compose down && docker compose up` — data persists (ChromaDB volume)
5. *(K8S)* `kubectl apply -k k8s/` → all pods running, Ingress accessible

---

## Phase 5: Enhancements — MemPalace & Advanced Retrieval

**Goal**: Add conversation memory via MemPalace and improve retrieval quality with hybrid search and reranking.

### Step 5.1 — MemPalace Integration

Use [MemPalace](https://github.com/MemPalace/mempalace) as a conversation memory layer that caches past Q&A pairs and returns them for similar future questions.

**What MemPalace is**: A local-first AI memory system that stores verbatim text with semantic search, organized into a "palace" structure (wings, rooms, drawers). Its default backend is ChromaDB. It excels at retrieving past conversations and interactions.

**How it fits in this project**:

1. **After each Q&A**: Store the question, answer, and retrieved source metadata as a "conversation" in a dedicated MemPalace wing (e.g., `wtg-rag-qa`)
2. **Before RAG retrieval**: Search MemPalace for similar past questions
3. **If high-confidence match** (similarity > threshold): Return the cached answer immediately, tagged with `"source": "memory"` — this skips the LLM call entirely and is near-instant
4. **If no match**: Proceed with full RAG pipeline as normal

**What to do**:

```bash
# Install
uv add mempalace

# Initialize palace
mempalace init ./mempalace_data
```

- Create `backend/app/services/memory_service.py`:
  - `store_qa(question, answer, sources)` — Mine the Q&A pair into MemPalace
  - `search_memory(question) -> Optional[CachedAnswer]` — Search for similar past Q&A
  - Configurable similarity threshold (default: 0.92)
- Modify `rag_service.py` to check memory before running the full chain
- Add `"from_memory": true/false` flag to the chat API response so the UI can indicate cached answers

**Benefits**:
- Eliminates redundant LLM calls for repeated/similar questions
- Near-instant responses for cached queries
- Memory grows organically as the system is used

### Step 5.2 — Hybrid Search (Vector + Keyword)

Improve retrieval quality by combining semantic vector search with traditional keyword search.

**What to do**:

- Add BM25 keyword search via `langchain_community.retrievers.BM25Retriever`
- Combine with ChromaDB vector search using `langchain.retrievers.EnsembleRetriever`
- Configurable weight ratio (default: 0.6 vector + 0.4 keyword)
- This helps with queries containing specific identifiers, WI numbers, class names, or exact terms that pure vector search may miss

**Key dependency**: `rank-bm25`

```bash
uv add rank-bm25
```

### Step 5.3 — Cross-Encoder Reranking

Add a reranking step after retrieval to improve precision.

**What to do**:

- After retrieving top-K chunks (e.g., K=20), pass them through a cross-encoder model to re-score relevance
- Return the top-N (e.g., N=5) most relevant chunks to the LLM
- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (small, fast, effective)
- Can run locally on CPU — no GPU required

**Key dependency**: `sentence-transformers`

```bash
uv add sentence-transformers
```

### Step 5.4 — UX Improvements

Polish the frontend experience.

**What to do**:

- Show a "From memory" badge on cached answers (from MemPalace)
- Expand/collapse source document previews
- Thumbs up/down feedback buttons on each answer
  - Store feedback in a local SQLite database
  - Use feedback data to evaluate and improve retrieval quality over time
- Conversation history sidebar (list past conversations)
- Dark mode support

### Phase 5 Verification

1. Ask a question → get a full RAG answer
2. Ask the same question again → get the answer from MemPalace (faster, with "from memory" indicator)
3. Ask a question with a specific WI number → hybrid search returns the correct ediProd WI
4. Compare retrieval quality with and without reranking on a set of test questions
5. Click thumbs down on a bad answer → verify feedback is recorded

---

## Target Directory Structure

After all phases are complete:

```
WTG.Query.RAG/
├── Plan.md                          # This file
├── README.md                        # Updated getting-started guide
├── docker-compose.yml               # Full-stack compose file
├── .env.example                     # Environment config template
├── .gitignore
│
├── backend/                         # Python FastAPI backend
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── config.py                # Pydantic Settings
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── chat.py          # POST /api/chat (SSE)
│   │   │       ├── documents.py     # Document CRUD
│   │   │       └── health.py        # Health check
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── rag_service.py       # RAG orchestration
│   │   │   ├── vectorstore_service.py
│   │   │   ├── document_service.py
│   │   │   ├── llm_service.py       # Multi-provider LLM factory
│   │   │   ├── ingestion_service.py # Ingestion orchestrator
│   │   │   └── memory_service.py    # MemPalace integration (Phase 5)
│   │   └── connectors/
│   │       ├── __init__.py
│   │       ├── base_connector.py    # Abstract base
│   │       ├── file_connector.py    # PDF/MD/TXT
│   │       ├── confluence_connector.py
│   │       ├── code_connector.py    # Git repos
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
├── docs/                            # Document corpus (mounted into backend)
│   └── sample.md
│
├── k8s/                             # Kubernetes manifests (Phase 4.3)
│   ├── namespace.yaml
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── chromadb-statefulset.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── ingress.yaml
│
└── rag.py                           # Legacy CLI (preserved, imports from backend)
```

---

## Verification Checklist

| Phase | Test | Pass Criteria |
|---|---|---|
| 1 | `curl POST /api/chat` with question about `sample.md` | Returns answer with correct source citation |
| 1 | `curl GET /api/health` | Returns `{"status": "ok"}` |
| 2 | Trigger each connector via API | `GET /api/ingest/status` shows `completed`; `GET /api/documents` shows new entries |
| 2 | Ask a question answerable only from Confluence content | Correct answer citing Confluence page |
| 3 | Open React UI, type a question | Streaming answer appears token by token |
| 3 | Upload a file via UI, ask about its content | Correct answer |
| 4 | `docker compose up --build` | All containers healthy; E2E Q&A works on `localhost:3000` |
| 4 | `docker compose down` then `up` | Data persists across restarts |
| 5 | Ask the same question twice | Second response is from memory (faster, flagged) |
| 5 | Query with specific WI number | Hybrid search returns correct ediProd content |

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| RAG Framework | **LangChain** (keep current) | Already in use, largest ecosystem, multi-source connectors, streaming support |
| Vector Database | **ChromaDB** | Local-first, lightweight, already in use, sufficient for <1K docs |
| Conversation Memory | **MemPalace** (Phase 5) | Caches past Q&A pairs, not a vector DB replacement |
| Backend Framework | **FastAPI** | Async, SSE streaming native, automatic OpenAPI docs, Pydantic integration |
| Frontend Framework | **React + TypeScript + Vite** | As requested; fast dev experience, large ecosystem |
| Authentication | **Deferred** | No auth in initial phases; add SSO/LDAP when needed |
| Deployment | **Docker Compose first** | Sufficient for small scale; K8S available when needed |
| LLM | **Flexible (env-configurable)** | Start with GitHub Models/OpenAI; Ollama for fully local option |

---

## Open Questions

1. **ediProd API access** — What is the preferred method for the ediProd connector to access work item data? Options: REST API, MCP tools, or direct database query.
2. **Confluence credentials** — Is there a service account available for Confluence API access? Which spaces should be indexed?
3. **Multilingual support** — If Q&A will be conducted in both Chinese and English, the embedding model should be switched to `multilingual-e5-large` or `bge-m3` for better cross-lingual retrieval. Is this needed?
4. **Local LLM preference** — If using Ollama for fully offline operation, which model is preferred? Recommendations: `qwen2.5:14b` (multilingual), `llama3.1:8b` (English-focused), `mistral:7b` (general).
5. **Git repositories to index** — Which WTG repositories should be included in the code connector? Should it include all public repos or a curated list?
