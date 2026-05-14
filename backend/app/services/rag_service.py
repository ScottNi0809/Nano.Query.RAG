'''
作用
负责完整 RAG 流程：

接收问题
查询重写（Query Rewrite）
从 ChromaDB 检索相关 chunk
组织 prompt
调用 LLM
返回答案和 source citations
支持 SSE 流式输出
'''

import json
from collections.abc import AsyncIterator

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.services.llm_service import LLMService
from app.services.query_rewrite_service import QueryRewriteService
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
        self.query_rewrite_service = QueryRewriteService(self.llm_service.get_chat_model())

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

    def _retrieve_for_queries(self, queries: list[str], k: int = 4) -> list:
        seen_content: set[str] = set()
        merged: list = []
        for query in queries:
            results = self.vectorstore_service.similarity_search_with_score(query, k=k)
            for doc, score in results:
                content_key = doc.page_content[:200]
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    merged.append((doc, score))
        merged.sort(key=lambda pair: pair[1])
        return merged

    # 非流式接口
    async def answer(self, question: str) -> dict:
        rewrite_result = await self.query_rewrite_service.rewrite(question)
        documents_with_scores = self._retrieve_for_queries(rewrite_result.queries)
        context = self._format_context(documents_with_scores)
        sources = self._format_sources(documents_with_scores)

        chain = RAG_PROMPT | self.llm_service.get_chat_model() | StrOutputParser()
        answer = await chain.ainvoke({"question": question, "context": context})

        return {
            "answer": answer,
            "sources": sources,
        }

    # 流式接口
    async def stream_answer(self, question: str) -> AsyncIterator[dict]:
        rewrite_result = await self.query_rewrite_service.rewrite(question)
        documents_with_scores = self._retrieve_for_queries(rewrite_result.queries)
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