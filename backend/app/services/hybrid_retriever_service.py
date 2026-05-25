'''
作用
混合检索服务：BM25（关键词）+ 向量检索（语义）结合。
使用 RRF（Reciprocal Rank Fusion）融合两路检索结果。
'''

import logging

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.config import Settings, get_settings
from app.services.vectorstore_service import VectorStoreService, get_vectorstore_service

logger = logging.getLogger(__name__)


class HybridRetrieverService:
    def __init__(
        self,
        vectorstore_service: VectorStoreService | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.vectorstore_service = vectorstore_service or get_vectorstore_service()
        self._bm25: BM25Okapi | None = None
        self._bm25_docs: list[Document] = []

    def _build_bm25_index(self) -> None:
        """从 ChromaDB 中获取所有文档并构建 BM25 索引。"""
        raw = self.vectorstore_service.vectorstore._collection.get(
            include=["documents", "metadatas"]
        )

        documents_text = raw.get("documents", [])
        metadatas = raw.get("metadatas", [])
        ids = raw.get("ids", [])

        if not documents_text:
            self._bm25 = None
            self._bm25_docs = []
            return

        self._bm25_docs = []
        tokenized_corpus = []

        for i, text in enumerate(documents_text):
            if not text:
                continue
            metadata = metadatas[i] if i < len(metadatas) else {}
            doc = Document(page_content=text, metadata=metadata or {})
            self._bm25_docs.append(doc)
            tokenized_corpus.append(self._tokenize(text))

        if tokenized_corpus:
            self._bm25 = BM25Okapi(tokenized_corpus)
            logger.info("BM25 index built with %d documents", len(tokenized_corpus))
        else:
            self._bm25 = None

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        混合分词：支持中文（jieba）+ 英文复合词（正则）。
        
        例如：
        - "Qwen2.5" -> ["qwen2.5"]
        - "Python3.11" -> ["python3.11"]  
        - "千问是开源大模型" -> ["千问", "是", "开源", "大模型"]
        - "Qwen2.5 is 大模型" -> ["qwen2.5", "is", "大模型"]
        """
        import re
        import jieba
        
        text = text.lower()
        
        # 检测是否包含中文字符
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        
        if has_chinese:
            # 对中文使用 jieba 分词
            tokens = list(jieba.cut(text))
            # 过滤出有意义的词（去掉纯空格、标点等）
            tokens = [t.strip() for t in tokens if t.strip() and re.search(r'[\w\u4e00-\u9fff]', t)]
            return tokens
        else:
            # 对纯英文使用改进正则：支持复合词如 "qwen2.5"、"python3.11"
            # 匹配模式：字母数字.字母数字 或 单词
            tokens = re.findall(r'[a-z]+[\d.]*[a-z]*\d*|[a-z]+|\d+', text)
            return tokens

    def refresh_index(self) -> None:
        """重新构建 BM25 索引。文档变更后应调用。"""
        self._build_bm25_index()

    @staticmethod
    def _normalize_vector(distance: float) -> float:
        """Convert vector distance to similarity percentage (0-100, higher=better).

        ChromaDB returns distances where lower = more similar.
        Uses 1/(1+d)*100 to map [0,∞) → (0,100].
        """
        if distance < 0:
            distance = 0.0
        return round(1.0 / (1.0 + distance) * 100, 1)

    @staticmethod
    def _normalize_bm25(score: float) -> float:
        """Convert BM25 score to percentage (0-100, higher=better).

        Uses sigmoid-like s/(s+1)*100 to map [0,∞) → [0,100).
        """
        if score <= 0:
            return 0.0
        return round(score / (score + 1.0) * 100, 1)

    def bm25_search(self, query: str, k: int = 4) -> list[tuple[Document, float]]:
        """BM25 关键词检索，返回 (document, score) 列表。"""
        if self._bm25 is None or not self._bm25_docs:
            self._build_bm25_index()

        if self._bm25 is None or not self._bm25_docs:
            return []

        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        scored_docs = list(zip(self._bm25_docs, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return scored_docs[:k]

    def hybrid_search(self, query: str, k: int = 4) -> list[tuple[Document, dict]]:
        """
        混合检索：BM25 + 向量检索，用 RRF 融合排序。

        返回 (Document, scores_dict)，scores_dict 包含：
        - rrf: RRF 融合分数
        - bm25: BM25 原始分数（未命中则为 0）
        - vector: 向量相似度分数（未命中则为 0）

        RRF score = sum(weight / (rrf_k + rank)) for each ranker
        """
        rrf_k = 60  # RRF 常数，通常设 60

        # 两路检索
        vector_results = self.vectorstore_service.similarity_search_with_score(query, k=k)
        bm25_results = self.bm25_search(query, k=k)

        bm25_weight = self.settings.bm25_weight
        vector_weight = 1.0 - bm25_weight

        # 建立 RRF 分数映射（用 page_content 前 200 字符去重）
        rrf_scores: dict[str, float] = {}
        bm25_raw_scores: dict[str, float] = {}  # None-like: key absent = not found
        vector_raw_scores: dict[str, float] = {}  # None-like: key absent = not found
        doc_map: dict[str, Document] = {}

        # BM25 排名贡献
        for rank, (doc, raw_score) in enumerate(bm25_results):
            content_key = doc.page_content[:200]
            rrf_scores[content_key] = rrf_scores.get(content_key, 0.0) + bm25_weight / (rrf_k + rank + 1)
            bm25_raw_scores[content_key] = float(raw_score)
            doc_map[content_key] = doc

        # 向量检索排名贡献
        for rank, (doc, raw_score) in enumerate(vector_results):
            content_key = doc.page_content[:200]
            rrf_scores[content_key] = rrf_scores.get(content_key, 0.0) + vector_weight / (rrf_k + rank + 1)
            vector_raw_scores[content_key] = float(raw_score)
            doc_map[content_key] = doc

        # 按 RRF 分数降序排列
        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for content_key, rrf_score in sorted_items[:k]:
            # Normalize to 0-100 scale for display
            # Vector: raw score is distance (lower=better), convert to similarity
            # BM25: raw score is relevance (higher=better), apply sigmoid normalization
            raw_vec = vector_raw_scores.get(content_key)
            raw_bm25 = bm25_raw_scores.get(content_key)
            scores = {
                "rrf": rrf_score,
                "bm25": self._normalize_bm25(raw_bm25) if raw_bm25 is not None else 0.0,
                "vector": self._normalize_vector(raw_vec) if raw_vec is not None else 0.0,
            }
            results.append((doc_map[content_key], scores))

        logger.info(
            "Hybrid search: %d BM25 + %d vector → %d merged (weights: BM25=%.1f, Vector=%.1f)",
            len(bm25_results),
            len(vector_results),
            len(results),
            bm25_weight,
            vector_weight,
        )
        return results


_hybrid_retriever_service: HybridRetrieverService | None = None


def get_hybrid_retriever_service() -> HybridRetrieverService:
    global _hybrid_retriever_service
    if _hybrid_retriever_service is None:
        _hybrid_retriever_service = HybridRetrieverService()
    return _hybrid_retriever_service
