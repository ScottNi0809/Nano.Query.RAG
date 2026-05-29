from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.services.hybrid_retriever_service import get_hybrid_retriever_service
from app.services.llm_service import LLMService
from app.services.query_rewrite_service import QueryRewriteService


DEFAULT_DATASET = Path(__file__).resolve().parent / "datasets" / "sample_eval.jsonl"
LEGACY_DATASET = Path(__file__).resolve().parent / "sample_eval.jsonl"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
COMPARABLE_METRICS = (
    "source_hit_rate",
    "mrr",
    "keyword_recall",
    "precision_at_k",
    "chunk_hit_rate_at_1",
    "chunk_hit_rate_at_k",
    "chunk_full_hit_rate_at_1",
    "chunk_full_hit_rate_at_k",
    "rank1_keyword_recall",
    "ndcg_at_k",
    "unanswerable_keyword_false_positive_rate",
)


@dataclass(frozen=True)
class EvalCase:
    id: str
    language: str
    category: str
    question: str
    expected_answer: str
    expected_sources: list[str]
    expected_keywords: list[str]
    false_positive_keywords: list[str]
    answerable: bool


def normalize_text(value: str) -> str:
    return "".join(value.lower().split())


def normalize_source(value: str | None) -> str:
    if not value:
        return ""
    return Path(value).name.lower()


def source_matches(actual: str | None, expected: str) -> bool:
    actual_name = normalize_source(actual)
    expected_name = normalize_source(expected)
    return actual_name == expected_name or actual_name.endswith(f"_{expected_name}")


def load_cases(dataset_path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with dataset_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {dataset_path}:{line_number}: {exc}") from exc

            cases.append(
                EvalCase(
                    id=raw["id"],
                    language=raw.get("language", "unknown"),
                    category=raw.get("category", "uncategorized"),
                    question=raw["question"],
                    expected_answer=raw.get("expected_answer", ""),
                    expected_sources=list(raw.get("expected_sources", [])),
                    expected_keywords=list(raw.get("expected_keywords", [])),
                    false_positive_keywords=list(raw.get("false_positive_keywords", [])),
                    answerable=bool(raw.get("answerable", True)),
                )
            )
    return cases


def resolve_dataset_path(path_arg: str | None) -> Path:
    if path_arg:
        return Path(path_arg).resolve()
    if DEFAULT_DATASET.exists():
        return DEFAULT_DATASET
    return LEGACY_DATASET


def chunk_source(document: Any) -> str:
    metadata = getattr(document, "metadata", {}) or {}
    return metadata.get("file_name") or metadata.get("source") or metadata.get("file_path") or "unknown"


def keyword_hits(expected_keywords: list[str], text: str) -> tuple[list[str], list[str]]:
    normalized_text = normalize_text(text)
    found: list[str] = []
    missing: list[str] = []
    for keyword in expected_keywords:
        if normalize_text(keyword) in normalized_text:
            found.append(keyword)
        else:
            missing.append(keyword)
    return found, missing


def keyword_recall(expected_keywords: list[str], text: str) -> float | None:
    if not expected_keywords:
        return None
    found, _ = keyword_hits(expected_keywords, text)
    return len(found) / len(expected_keywords)


def relevant_rank(retrieved_sources: list[str], expected_sources: list[str]) -> int | None:
    if not expected_sources:
        return None
    for index, source in enumerate(retrieved_sources, start=1):
        if any(source_matches(source, expected) for expected in expected_sources):
            return index
    return None


def dcg(relevances: list[float]) -> float:
    return sum(relevance / math.log2(index + 2) for index, relevance in enumerate(relevances))


def ndcg(relevances: list[float]) -> float:
    ideal = sorted(relevances, reverse=True)
    ideal_dcg = dcg(ideal)
    return dcg(relevances) / ideal_dcg if ideal_dcg else 0.0


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def build_metadata(dataset_path: Path, k: int, use_query_rewrite: bool) -> dict[str, Any]:
    settings = get_settings()
    return {
        "git_commit": git_commit(),
        "dataset_sha256": file_sha256(dataset_path),
        "llm_provider": settings.llm_provider,
        "model_name": settings.model_name,
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "bm25_weight": settings.bm25_weight,
        "k": k,
        "use_query_rewrite": use_query_rewrite,
    }


async def rewrite_query(question: str, enabled: bool) -> list[str]:
    if not enabled:
        return [question]

    service = QueryRewriteService(LLMService().get_chat_model())
    result = await service.rewrite(question)
    return result.queries


async def retrieve_chunks(question: str, k: int, use_query_rewrite: bool) -> tuple[list[str], list[tuple[Any, dict[str, float]]]]:
    retriever = get_hybrid_retriever_service()
    queries = await rewrite_query(question, use_query_rewrite)

    seen_content: set[str] = set()
    merged: list[tuple[Any, dict[str, float]]] = []
    for query in queries:
        for document, scores in retriever.hybrid_search(query, k=k):
            content = getattr(document, "page_content", "") or ""
            content_key = content[:200]
            if content_key in seen_content:
                continue
            seen_content.add(content_key)
            merged.append((document, scores))

    merged.sort(key=lambda item: item[1].get("rrf", 0.0), reverse=True)
    return queries, merged[:k]


async def evaluate_case(case: EvalCase, k: int, use_query_rewrite: bool) -> dict[str, Any]:
    queries, top_results = await retrieve_chunks(case.question, k, use_query_rewrite)

    retrieved_sources = [chunk_source(document) for document, _ in top_results]
    chunk_texts = [(getattr(document, "page_content", "") or "") for document, _ in top_results]
    context_text = "\n\n".join(chunk_texts)
    found_keywords, missing_keywords = keyword_hits(case.expected_keywords, context_text)
    false_positive_found, false_positive_missing = keyword_hits(case.false_positive_keywords, context_text)
    first_rank = relevant_rank(retrieved_sources, case.expected_sources)

    chunk_keyword_recalls = [keyword_recall(case.expected_keywords, text) for text in chunk_texts]
    chunk_keyword_recalls_numeric = [recall or 0.0 for recall in chunk_keyword_recalls]
    rank1_keyword_recall = chunk_keyword_recalls_numeric[0] if chunk_keyword_recalls_numeric else 0.0
    chunk_hit_at_1 = rank1_keyword_recall > 0.0
    chunk_full_hit_at_1 = rank1_keyword_recall == 1.0 if case.expected_keywords else False
    chunk_hit_at_k = any(recall > 0.0 for recall in chunk_keyword_recalls_numeric)
    chunk_full_hit_at_k = any(recall == 1.0 for recall in chunk_keyword_recalls_numeric) if case.expected_keywords else False
    ndcg_at_k = ndcg(chunk_keyword_recalls_numeric)

    relevant_chunks = 0
    for (document, _), text in zip(top_results, chunk_texts, strict=False):
        source = chunk_source(document)
        chunk_recall = keyword_recall(case.expected_keywords, text) or 0.0
        if any(source_matches(source, expected) for expected in case.expected_sources) or chunk_recall > 0.0:
            relevant_chunks += 1

    score_rrf_values = [float(scores.get("rrf", 0.0)) for _, scores in top_results]
    score_bm25_values = [float(scores.get("bm25", 0.0)) for _, scores in top_results]
    score_vector_values = [float(scores.get("vector", 0.0)) for _, scores in top_results]

    return {
        "id": case.id,
        "language": case.language,
        "category": case.category,
        "question": case.question,
        "answerable": case.answerable,
        "queries": queries,
        "expected_sources": case.expected_sources,
        "retrieved_sources": retrieved_sources,
        "source_hit": first_rank is not None,
        "first_relevant_rank": first_rank,
        "reciprocal_rank": 1.0 / first_rank if first_rank else 0.0,
        "expected_keywords": case.expected_keywords,
        "keywords_found": found_keywords,
        "keywords_missing": missing_keywords,
        "keyword_recall": len(found_keywords) / len(case.expected_keywords) if case.expected_keywords else None,
        "chunk_hit_at_1": chunk_hit_at_1,
        "chunk_hit_at_k": chunk_hit_at_k,
        "chunk_full_hit_at_1": chunk_full_hit_at_1,
        "chunk_full_hit_at_k": chunk_full_hit_at_k,
        "rank1_keyword_recall": rank1_keyword_recall,
        "ndcg_at_k": ndcg_at_k,
        "precision_at_k": relevant_chunks / len(top_results) if top_results else 0.0,
        "false_positive_keywords": case.false_positive_keywords,
        "false_positive_keywords_found": false_positive_found,
        "false_positive_keywords_missing": false_positive_missing,
        "unanswerable_keyword_false_positive": (not case.answerable) and bool(false_positive_found),
        "max_score_rrf": max(score_rrf_values, default=0.0),
        "max_score_bm25": max(score_bm25_values, default=0.0),
        "max_score_vector": max(score_vector_values, default=0.0),
        "top_chunks": [
            {
                "rank": index,
                "source": chunk_source(document),
                "score_rrf": float(scores.get("rrf", 0.0)),
                "score_bm25": float(scores.get("bm25", 0.0)),
                "score_vector": float(scores.get("vector", 0.0)),
                "keyword_recall": chunk_keyword_recalls_numeric[index - 1],
                "preview": (getattr(document, "page_content", "") or "")[:300],
            }
            for index, (document, scores) in enumerate(top_results, start=1)
        ],
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [result for result in results if result["answerable"]]
    unanswerable = [result for result in results if not result["answerable"]]
    keyword_recalls = [result["keyword_recall"] for result in answerable if result["keyword_recall"] is not None]

    return {
        "total_cases": len(results),
        "answerable_cases": len(answerable),
        "unanswerable_cases": len(unanswerable),
        "source_hit_rate": average([1.0 if result["source_hit"] else 0.0 for result in answerable]),
        "mrr": average([result["reciprocal_rank"] for result in answerable]),
        "keyword_recall": average(keyword_recalls),
        "precision_at_k": average([result["precision_at_k"] for result in answerable]),
        "chunk_hit_rate_at_1": average([1.0 if result["chunk_hit_at_1"] else 0.0 for result in answerable]),
        "chunk_hit_rate_at_k": average([1.0 if result["chunk_hit_at_k"] else 0.0 for result in answerable]),
        "chunk_full_hit_rate_at_1": average([1.0 if result["chunk_full_hit_at_1"] else 0.0 for result in answerable]),
        "chunk_full_hit_rate_at_k": average([1.0 if result["chunk_full_hit_at_k"] else 0.0 for result in answerable]),
        "rank1_keyword_recall": average([result["rank1_keyword_recall"] for result in answerable]),
        "ndcg_at_k": average([result["ndcg_at_k"] for result in answerable]),
        "unanswerable_retrieved_any_rate": average([1.0 if result["retrieved_sources"] else 0.0 for result in unanswerable]),
        "unanswerable_keyword_false_positive_rate": average([
            1.0 if result["unanswerable_keyword_false_positive"] else 0.0 for result in unanswerable
        ]),
        "unanswerable_max_score_rrf": average([result["max_score_rrf"] for result in unanswerable]),
        "unanswerable_max_score_bm25": average([result["max_score_bm25"] for result in unanswerable]),
        "unanswerable_max_score_vector": average([result["max_score_vector"] for result in unanswerable]),
        "by_language": group_summary(results, "language"),
        "by_category": group_summary(results, "category"),
    }


def group_summary(results: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups[str(result[key])].append(result)

    output: dict[str, Any] = {}
    for group_name, group_results in sorted(groups.items()):
        answerable = [result for result in group_results if result["answerable"]]
        unanswerable = [result for result in group_results if not result["answerable"]]
        keyword_recalls = [result["keyword_recall"] for result in answerable if result["keyword_recall"] is not None]
        output[group_name] = {
            "cases": len(group_results),
            "answerable_cases": len(answerable),
            "unanswerable_cases": len(unanswerable),
            "source_hit_rate": average([1.0 if result["source_hit"] else 0.0 for result in answerable]),
            "mrr": average([result["reciprocal_rank"] for result in answerable]),
            "keyword_recall": average(keyword_recalls),
            "chunk_hit_rate_at_1": average([1.0 if result["chunk_hit_at_1"] else 0.0 for result in answerable]),
            "rank1_keyword_recall": average([result["rank1_keyword_recall"] for result in answerable]),
            "ndcg_at_k": average([result["ndcg_at_k"] for result in answerable]),
            "unanswerable_keyword_false_positive_rate": average([
                1.0 if result["unanswerable_keyword_false_positive"] else 0.0 for result in unanswerable
            ]),
        }
    return output


def metric_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for metric in COMPARABLE_METRICS:
        before_value = before.get(metric)
        after_value = after.get(metric)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            deltas[metric] = float(after_value) - float(before_value)
    return deltas


def grouped_delta(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in sorted(set(baseline) | set(variant)):
        output[key] = metric_delta(baseline.get(key, {}), variant.get(key, {}))
    return output


def compare_summaries(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary_delta": metric_delta(baseline, variant),
        "by_language_delta": grouped_delta(baseline.get("by_language", {}), variant.get("by_language", {})),
        "by_category_delta": grouped_delta(baseline.get("by_category", {}), variant.get("by_category", {})),
    }


def print_summary(dataset_path: Path, k: int, use_query_rewrite: bool, summary: dict[str, Any]) -> None:
    print(f"Dataset: {dataset_path}")
    print(f"Top-K: {k}")
    print(f"Query rewrite: {'enabled' if use_query_rewrite else 'disabled'}")
    print()
    print(f"Total cases: {summary['total_cases']}")
    print(f"Answerable cases: {summary['answerable_cases']}")
    print(f"Unanswerable cases: {summary['unanswerable_cases']}")
    print(f"Source Hit Rate@{k}: {summary['source_hit_rate']:.3f}")
    print(f"MRR@{k}: {summary['mrr']:.3f}")
    print(f"Keyword Recall@{k}: {summary['keyword_recall']:.3f}")
    print(f"Precision@{k}: {summary['precision_at_k']:.3f}")
    print(f"Chunk Hit Rate@1: {summary['chunk_hit_rate_at_1']:.3f}")
    print(f"Chunk Hit Rate@{k}: {summary['chunk_hit_rate_at_k']:.3f}")
    print(f"Chunk Full Hit Rate@1: {summary['chunk_full_hit_rate_at_1']:.3f}")
    print(f"Chunk Full Hit Rate@{k}: {summary['chunk_full_hit_rate_at_k']:.3f}")
    print(f"Rank-1 Keyword Recall: {summary['rank1_keyword_recall']:.3f}")
    print(f"NDCG@{k}: {summary['ndcg_at_k']:.3f}")
    print(f"Unanswerable Retrieved-Any Rate@{k}: {summary['unanswerable_retrieved_any_rate']:.3f}")
    print(f"Unanswerable Keyword False Positive Rate@{k}: {summary['unanswerable_keyword_false_positive_rate']:.3f}")
    print(f"Unanswerable Avg Max RRF Score: {summary['unanswerable_max_score_rrf']:.4f}")
    print()
    print_group_summary("By language", summary["by_language"])
    print()
    print_group_summary("By category", summary["by_category"])


def print_group_summary(title: str, grouped_summary: dict[str, Any]) -> None:
    print(f"{title}:")
    for group_name, metrics in grouped_summary.items():
        print(
            f"  {group_name}: cases={metrics['cases']}, "
            f"source_hit_rate={metrics['source_hit_rate']:.3f}, "
            f"mrr={metrics['mrr']:.3f}, "
            f"keyword_recall={metrics['keyword_recall']:.3f}, "
            f"chunk_hit@1={metrics['chunk_hit_rate_at_1']:.3f}, "
            f"rank1_recall={metrics['rank1_keyword_recall']:.3f}"
        )


def print_delta(title: str, delta: dict[str, Any]) -> None:
    print(title)
    for metric, value in delta.get("summary_delta", {}).items():
        print(f"  {metric}: {value:+.3f}")


def write_results(payload: dict[str, Any], prefix: str = "eval") -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{prefix}_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Also persist to SQLite for history tracking
    from app.services.eval_store import save_eval

    save_eval(payload)

    return path


async def run_eval(dataset_path: Path, k: int, use_query_rewrite: bool) -> dict[str, Any]:
    cases = load_cases(dataset_path)
    results = [await evaluate_case(case, k, use_query_rewrite) for case in cases]
    summary = summarize(results)
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "dataset": str(dataset_path),
        "metadata": build_metadata(dataset_path, k, use_query_rewrite),
        "k": k,
        "use_query_rewrite": use_query_rewrite,
        "summary": summary,
        "results": results,
    }


async def run(args: argparse.Namespace) -> int:
    dataset_path = resolve_dataset_path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    if args.compare_query_rewrite and args.use_query_rewrite:
        print("--compare-query-rewrite already runs both modes; omit --use-query-rewrite.", file=sys.stderr)
        return 1

    if args.seed:
        print("Seeding ChromaDB with docs/...")
        seed_documents()
        print()

    if args.compare_query_rewrite:
        baseline = await run_eval(dataset_path, args.k, use_query_rewrite=False)
        variant = await run_eval(dataset_path, args.k, use_query_rewrite=True)
        comparison = compare_summaries(baseline["summary"], variant["summary"])
        payload = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "dataset": str(dataset_path),
            "k": args.k,
            "baseline": baseline,
            "with_query_rewrite": variant,
            "comparison": comparison,
        }
        print("Baseline (query rewrite disabled)")
        print_summary(dataset_path, args.k, False, baseline["summary"])
        print()
        print("With query rewrite enabled")
        print_summary(dataset_path, args.k, True, variant["summary"])
        print()
        print_delta("Delta (query rewrite - baseline):", comparison)
        if args.write_results:
            result_path = write_results(payload, prefix="eval_compare_query_rewrite")
            print()
            print(f"Wrote detailed comparison results: {result_path}")
        return 0

    payload = await run_eval(dataset_path, args.k, args.use_query_rewrite)
    print_summary(dataset_path, args.k, args.use_query_rewrite, payload["summary"])

    if args.compare_to:
        baseline_path = Path(args.compare_to).resolve()
        baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        comparison = compare_summaries(baseline_payload["summary"], payload["summary"])
        payload["comparison_to"] = str(baseline_path)
        payload["comparison"] = comparison
        print()
        print_delta(f"Delta (current - {baseline_path.name}):", comparison)

    if args.write_results:
        result_path = write_results(payload)
        print()
        print(f"Wrote detailed results: {result_path}")
    return 0


def seed_documents() -> None:
    """Clear ChromaDB and re-ingest all docs from the configured docs_dir.

    This ensures a deterministic, reproducible vectorstore state before
    evaluation, regardless of which machine or working directory is used.
    """
    from app.services.document_service import DocumentService
    from app.services.vectorstore_service import get_vectorstore_service

    settings = get_settings()
    vectorstore_service = get_vectorstore_service()

    # Clear existing collection
    collection = vectorstore_service.vectorstore._collection
    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)
        print(f"  Cleared {len(existing_ids)} existing chunks from ChromaDB.")

    # Load and ingest docs
    doc_service = DocumentService(settings)
    documents = doc_service.load_directory()
    if not documents:
        print(f"  Warning: No documents found in {settings.docs_dir}")
        return

    chunks = doc_service.split_documents(documents)
    vectorstore_service.add_documents(chunks)
    print(f"  Ingested {len(chunks)} chunks from {len(documents)} documents.")

    # Refresh BM25 index
    retriever = get_hybrid_retriever_service()
    retriever.refresh_index()
    print("  BM25 index rebuilt.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval-level RAG evaluation.")
    parser.add_argument("--dataset", help="Path to JSONL eval dataset.")
    parser.add_argument("--k", type=int, default=4, help="Number of chunks to evaluate per query.")
    parser.add_argument(
        "--use-query-rewrite",
        action="store_true",
        help="Enable LLM-based query rewrite before retrieval. Disabled by default for deterministic baseline runs.",
    )
    parser.add_argument(
        "--compare-query-rewrite",
        action="store_true",
        help="Run both query rewrite disabled and enabled, then print metric deltas.",
    )
    parser.add_argument("--compare-to", help="Path to a previous eval result JSON to compare against.")
    parser.add_argument("--write-results", action="store_true", help="Write detailed JSON results to backend/evals/results/.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Re-ingest docs/ into ChromaDB before running eval. Ensures reproducible vectorstore state.",
    )
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())