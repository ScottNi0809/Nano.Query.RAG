'''
作用
负责加载文件和分块，把上传的 PDF / Markdown / TXT 转成 LangChain Document。
'''

import glob
import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
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