import apiClient from './client';

export interface BenchmarkListItem {
  filename: string;
  timestamp_utc: string;
  k: number;
  use_query_rewrite: boolean;
  is_comparison: boolean;
}

export interface BenchmarkResult {
  timestamp_utc: string;
  dataset: string;
  metadata: {
    git_commit: string | null;
    dataset_sha256: string | null;
    llm_provider: string;
    model_name: string;
    embedding_model: string;
    chunk_size: number;
    chunk_overlap: number;
    bm25_weight: number;
    k: number;
    use_query_rewrite: boolean;
  };
  k: number;
  use_query_rewrite: boolean;
  summary: BenchmarkSummary;
  results: BenchmarkCaseResult[];
}

export interface BenchmarkSummary {
  total_cases: number;
  answerable_cases: number;
  unanswerable_cases: number;
  source_hit_rate: number;
  mrr: number;
  keyword_recall: number;
  precision_at_k: number;
  chunk_hit_rate_at_1: number;
  chunk_hit_rate_at_k: number;
  chunk_full_hit_rate_at_1: number;
  chunk_full_hit_rate_at_k: number;
  rank1_keyword_recall: number;
  ndcg_at_k: number;
  unanswerable_retrieved_any_rate: number;
  unanswerable_keyword_false_positive_rate: number;
  by_language: Record<string, GroupMetrics>;
  by_category: Record<string, GroupMetrics>;
}

export interface GroupMetrics {
  cases: number;
  answerable_cases: number;
  unanswerable_cases: number;
  source_hit_rate: number;
  mrr: number;
  keyword_recall: number;
  chunk_hit_rate_at_1: number;
  rank1_keyword_recall: number;
  ndcg_at_k: number;
  unanswerable_keyword_false_positive_rate: number;
}

export interface BenchmarkCaseResult {
  id: string;
  language: string;
  category: string;
  question: string;
  answerable: boolean;
  source_hit: boolean;
  reciprocal_rank: number;
  keyword_recall: number | null;
  chunk_hit_at_1: boolean;
  chunk_hit_at_k: boolean;
  ndcg_at_k: number;
}

export async function listBenchmarkResults(): Promise<BenchmarkListItem[]> {
  const res = await apiClient.get('/benchmark/results');
  return res.data;
}

export async function getBenchmarkResult(filename: string): Promise<BenchmarkResult> {
  const res = await apiClient.get(`/benchmark/results/${encodeURIComponent(filename)}`);
  return res.data;
}
