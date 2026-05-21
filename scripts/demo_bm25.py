"""
演示 BM25 混合检索的工作原理
展示中英文混合场景下的检索效果
"""

from app.services.hybrid_retriever_service import HybridRetrieverService
from app.services.vectorstore_service import VectorStoreService
from app.config import Settings
from langchain_core.documents import Document
from unittest.mock import MagicMock


def demo_bm25():
    """演示改进后的 BM25 检索效果（支持中文分词 + 复合词）"""
    print("=" * 70)
    print("BM25 混合检索演示（支持中文分词 + 复合词）")
    print("=" * 70)

    # 模拟 ChromaDB 中的文档
    sample_docs = [
        "Qwen2.5 is a powerful open-source large language model developed by Alibaba.",
        "千问是阿里巴巴开发的开源大语言模型，具有强大的多语言能力。",
        "FastAPI is a modern web framework for building APIs with Python3.11.",
        "LangChain 提供了一套工具用于构建 LLM 应用程序。",
        "我最喜欢的大模型是千问，它的中英混合能力很强。",
    ]

    # 1. 构造 mock vectorstore
    mock_vectorstore = MagicMock()
    mock_vectorstore.vectorstore._collection.get.return_value = {
        "documents": sample_docs,
        "metadatas": [{"source": f"doc_{i}"} for i in range(len(sample_docs))],
        "ids": [f"id_{i}" for i in range(len(sample_docs))],
    }

    mock_vs_service = MagicMock(spec=VectorStoreService)
    mock_vs_service.vectorstore = mock_vectorstore.vectorstore

    # 模拟向量检索结果（全部文档，降序相似度）
    def mock_similarity_search(query: str, k: int = 4):
        # 简单模拟：返回前 k 个文档，带伪造的相似度分数
        return [
            (Document(page_content=doc, metadata={"source": f"doc_{i}"}), 0.8 - i * 0.1)
            for i, doc in enumerate(sample_docs[:k])
        ]

    mock_vs_service.similarity_search_with_score = mock_similarity_search

    # 2. 构造 Settings
    settings = Settings(
        llm_provider="ollama",
        chroma_persist_dir="./test_chroma",
        docs_dir="./test_docs",
        bm25_weight=0.5,  # 50% BM25, 50% 向量
        _env_file=None,
    )

    # 3. 创建 HybridRetrieverService
    hybrid_service = HybridRetrieverService(
        vectorstore_service=mock_vs_service,
        settings=settings,
    )

    # 4. 测试不同查询
    test_queries = [
        ("Qwen2.5", "英文查询，复合词（数字+字母）"),
        ("Qwen2.5 LLM", "英文查询，复合词+关键词"),
        ("千问大模型", "中文查询，分词"),
        ("Qwen2.5 是 LLM 大模型", "中英混合查询"),
        ("FastAPI Python3.11", "英文复合词查询"),
    ]

    for query, description in test_queries:
        print(f"\n【{description}】")
        print(f"查询: {query}")
        print("-" * 70)

        # 显示分词结果
        tokens = HybridRetrieverService._tokenize(query)
        print(f"分词结果: {tokens}")

        # BM25 结果
        bm25_results = hybrid_service.bm25_search(query, k=3)
        print(f"\nBM25 检索结果 ({len(bm25_results)} 条):")
        for i, (doc, score) in enumerate(bm25_results):
            print(f"  {i+1}. BM25分数={score:.4f}")
            print(f"     内容: {doc.page_content[:65]}...")

        # 混合融合结果
        hybrid_results = hybrid_service.hybrid_search(query, k=2)
        print(f"\n混合检索结果 (RRF融合, k=2):")
        for i, (doc, rrf_score) in enumerate(hybrid_results):
            print(f"  {i+1}. RRF分数={rrf_score:.4f}")
            print(f"     内容: {doc.page_content[:65]}...")

    # 5. 演示权重调整
    print("\n" + "=" * 70)
    print("权重对比演示（同一查询，不同权重）")
    print("=" * 70)

    query = "千问大模型"
    print(f"\n查询: {query}")
    print(f"分词结果: {HybridRetrieverService._tokenize(query)}\n")

    for weight in [0.2, 0.5, 0.8]:
        settings.bm25_weight = weight
        hybrid_service = HybridRetrieverService(
            vectorstore_service=mock_vs_service,
            settings=settings,
        )
        results = hybrid_service.hybrid_search(query, k=2)
        print(f"权重 (BM25={weight}, Vector={1-weight}):")
        for i, (doc, rrf_score) in enumerate(results):
            print(f"  {i+1}. RRF={rrf_score:.4f}: {doc.page_content[:50]}...")

    print("\n" + "=" * 70)
    print("✅ 演示完成")
    print("=" * 70)


if __name__ == "__main__":
    demo_bm25()
