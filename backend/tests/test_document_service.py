"""Tests for app.services.document_service module."""

import tempfile
from pathlib import Path

import pytest

from app.config import Settings
from app.services.document_service import DocumentService


@pytest.fixture
def doc_service() -> DocumentService:
    settings = Settings(
        chunk_size=200,
        chunk_overlap=50,
        docs_dir="./test_docs",
        _env_file=None,
    )
    return DocumentService(settings=settings)


class TestDocumentServiceLoadFile:
    def test_load_txt_file(self, doc_service: DocumentService, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world. This is test content.", encoding="utf-8")

        docs = doc_service.load_file(str(txt_file))
        assert len(docs) >= 1
        assert "Hello world" in docs[0].page_content
        assert docs[0].metadata["file_name"] == "test.txt"
        assert docs[0].metadata["file_type"] == "txt"
        assert docs[0].metadata["source_type"] == "file"

    def test_load_unsupported_format_raises(self, doc_service: DocumentService, tmp_path: Path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("col1,col2\na,b", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file type"):
            doc_service.load_file(str(csv_file))

    def test_load_md_file(self, doc_service: DocumentService, tmp_path: Path):
        md_file = tmp_path / "readme.md"
        md_file.write_text("# Title\n\nSome markdown content.", encoding="utf-8")

        docs = doc_service.load_file(str(md_file))
        assert len(docs) >= 1
        assert docs[0].metadata["file_type"] == "md"


class TestDocumentServiceSplit:
    def test_split_long_document(self, doc_service: DocumentService):
        from langchain_core.documents import Document

        long_text = "word " * 500  # ~2500 chars, larger than chunk_size=200
        docs = [Document(page_content=long_text, metadata={"source": "test"})]

        chunks = doc_service.split_documents(docs)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.page_content) <= doc_service.settings.chunk_size + 50  # small tolerance

    def test_split_short_document_stays_single(self, doc_service: DocumentService):
        from langchain_core.documents import Document

        short_text = "Short content."
        docs = [Document(page_content=short_text, metadata={"source": "test"})]

        chunks = doc_service.split_documents(docs)
        assert len(chunks) == 1
        assert chunks[0].page_content == short_text


class TestDocumentServiceLoadDirectory:
    def test_load_directory_finds_txt_files(self, doc_service: DocumentService, tmp_path: Path):
        (tmp_path / "a.txt").write_text("File A content", encoding="utf-8")
        (tmp_path / "b.txt").write_text("File B content", encoding="utf-8")
        (tmp_path / "skip.csv").write_text("ignored", encoding="utf-8")

        docs = doc_service.load_directory(str(tmp_path))
        assert len(docs) == 2

    def test_load_empty_directory(self, doc_service: DocumentService, tmp_path: Path):
        docs = doc_service.load_directory(str(tmp_path))
        assert docs == []
