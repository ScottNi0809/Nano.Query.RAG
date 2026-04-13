"""
Minimal RAG Demo using LangChain
Supports: PDF files, Markdown files, plain text files
"""

import os
import sys
import glob
from dotenv import load_dotenv

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA

load_dotenv()

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# GitHub Models endpoint (works with GitHub Copilot subscription)
GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


# Default models — override with MODEL_NAME / EMBEDDING_MODEL in .env
DEFAULT_CHAT_MODEL = "gpt-4o"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"


def get_llm_config():
    """Return (api_key, base_url, chat_model, embed_model) based on available env vars."""
    github_token = os.environ.get("GITHUB_TOKEN")
    openai_key = os.environ.get("OPENAI_API_KEY")
    chat_model = os.environ.get("MODEL_NAME", DEFAULT_CHAT_MODEL)
    embed_model = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    if github_token:
        print(f"Using GitHub Models endpoint | chat={chat_model} | embed={embed_model}")
        return github_token, GITHUB_MODELS_BASE_URL, chat_model, embed_model
    elif openai_key:
        print(f"Using OpenAI API | chat={chat_model} | embed={embed_model}")
        return openai_key, None, chat_model, embed_model
    else:
        return None, None, None, None
    else:
        return None, None


def load_documents(docs_dir: str):
    """Load PDF, Markdown, and text files from the docs directory."""
    documents = []

    for filepath in glob.glob(os.path.join(docs_dir, "**", "*"), recursive=True):
        if not os.path.isfile(filepath):
            continue
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext == ".pdf":
                loader = PyPDFLoader(filepath)
            elif ext == ".md":
                loader = UnstructuredMarkdownLoader(filepath)
            elif ext in (".txt", ".text"):
                loader = TextLoader(filepath, encoding="utf-8")
            else:
                continue
            documents.extend(loader.load())
            print(f"  Loaded: {filepath}")
        except Exception as e:
            print(f"  Error loading {filepath}: {e}")

    return documents


def build_vectorstore(documents, persist_dir: str, api_key: str, base_url: str | None, embed_model: str):
    """Split documents and build a Chroma vector store."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(documents)
    print(f"  Split into {len(chunks)} chunks")

    embed_kwargs = {"model": embed_model, "api_key": api_key}
    if base_url:
        embed_kwargs["base_url"] = base_url
    embeddings = OpenAIEmbeddings(**embed_kwargs)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    return vectorstore


def get_qa_chain(vectorstore, api_key: str, base_url: str | None, chat_model: str):
    """Create a RetrievalQA chain."""
    llm_kwargs = {"model": chat_model, "temperature": 0, "api_key": api_key}
    if base_url:
        llm_kwargs["base_url"] = base_url
    llm = ChatOpenAI(**llm_kwargs)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
    )


def main():
    api_key, base_url, chat_model, embed_model = get_llm_config()
    if not api_key:
        print("Error: Set GITHUB_TOKEN or OPENAI_API_KEY in your .env file (see .env.example)")
        sys.exit(1)

    if not os.path.isdir(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"Created '{DOCS_DIR}/' — add your PDF/MD/TXT files there and re-run.")
        sys.exit(0)

    # Load and index
    print("Loading documents...")
    documents = load_documents(DOCS_DIR)
    if not documents:
        print(f"No documents found in '{DOCS_DIR}/'. Add PDF, MD, or TXT files.")
        sys.exit(0)

    print("Building vector store...")
    vectorstore = build_vectorstore(documents, CHROMA_DIR, api_key, base_url, embed_model)

    # QA loop
    qa_chain = get_qa_chain(vectorstore, api_key, base_url, chat_model)
    print("\nRAG system ready! Type your questions (type 'quit' to exit).\n")

    while True:
        query = input("Q: ").strip()
        if not query or query.lower() in ("quit", "exit", "q"):
            break

        result = qa_chain.invoke({"query": query})
        print(f"\nA: {result['result']}\n")

        sources = {doc.metadata.get("source", "unknown") for doc in result["source_documents"]}
        print(f"Sources: {', '.join(sources)}\n")


if __name__ == "__main__":
    main()
