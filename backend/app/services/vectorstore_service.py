'''
作用
封装 ChromaDB 操作：初始化、添加文档、检索、列表、删除、健康检查。
'''

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