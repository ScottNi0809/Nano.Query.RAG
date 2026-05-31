import { useState, useCallback, useEffect, useRef } from 'react';
import { InfoCircleOutlined, ExperimentOutlined, CheckCircleOutlined, CloseCircleOutlined, PlayCircleOutlined, LoadingOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { listBenchmarkResults, getBenchmarkResult, runBenchmark } from '@/api/benchmark';
import type { BenchmarkListItem, BenchmarkResult, GroupMetrics } from '@/api/benchmark';

/* ---- helpers ---- */

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function scoreLevel(v: number, inverted = false): 'excellent' | 'good' | 'fair' | 'poor' {
  const s = inverted ? 1 - v : v;
  if (s >= 0.9) return 'excellent';
  if (s >= 0.7) return 'good';
  if (s >= 0.5) return 'fair';
  return 'poor';
}

const CORE_METRICS = [
  'source_hit_rate',
  'mrr',
  'keyword_recall',
  'precision_at_k',
  'ndcg_at_k',
  'chunk_hit_rate_at_1',
  'chunk_hit_rate_at_k',
  'chunk_full_hit_rate_at_1',
  'chunk_full_hit_rate_at_k',
  'rank1_keyword_recall',
] as const;

const GROUP_METRICS = [
  'source_hit_rate',
  'mrr',
  'keyword_recall',
  'ndcg_at_k',
  'chunk_hit_rate_at_1',
  'rank1_keyword_recall',
] as const;

/* ---- Tooltip component ---- */

function Tooltip({ text }: { text: string }) {
  const [visible, setVisible] = useState(false);
  const iconRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const handleEnter = () => {
    if (iconRef.current) {
      const rect = iconRef.current.getBoundingClientRect();
      setPos({ top: rect.top - 8, left: rect.left + rect.width / 2 });
    }
    setVisible(true);
  };

  return (
    <span
      className="bm-tooltip-wrap"
      ref={iconRef}
      onMouseEnter={handleEnter}
      onMouseLeave={() => setVisible(false)}
    >
      <InfoCircleOutlined className="bm-tooltip-icon" />
      {visible && (
        <span
          className="bm-tooltip-popup"
          style={{ position: 'fixed', top: pos.top, left: pos.left, transform: 'translate(-50%, -100%)' }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

/* ---- Gauge bar ---- */

function GaugeBar({ value, inverted = false }: { value: number; inverted?: boolean }) {
  const level = scoreLevel(value, inverted);
  const widthPct = Math.min(Math.max(value * 100, 0), 100);
  return (
    <div className="bm-gauge">
      <div className={`bm-gauge-fill bm-gauge-${level}`} style={{ width: `${widthPct}%` }} />
    </div>
  );
}

/* ---- Metric card ---- */

function MetricCard({ metricKey, value, t, inverted = false }: {
  metricKey: string;
  value: number;
  t: (k: string) => string;
  inverted?: boolean;
}) {
  const level = scoreLevel(value, inverted);
  return (
    <div className={`bm-metric-card bm-level-${level}`}>
      <div className="bm-metric-header">
        <span className="bm-metric-name">{t(`benchmark.metric_${metricKey}`)}</span>
        <Tooltip text={t(`benchmark.metric_${metricKey}_tip`)} />
      </div>
      <div className="bm-metric-value">{pct(value)}</div>
      <GaugeBar value={value} inverted={inverted} />
      <span className={`bm-level-badge bm-badge-${level}`}>{t(`benchmark.level_${level}`)}</span>
    </div>
  );
}

/* ---- Group table ---- */

function GroupTable({ title, data, t }: {
  title: string;
  data: Record<string, GroupMetrics>;
  t: (k: string) => string;
}) {
  const groups = Object.entries(data);
  if (groups.length === 0) return null;

  return (
    <div className="bm-group-section">
      <h3 className="bm-section-title">{title}</h3>
      <div className="bm-table-wrap">
        <table className="bm-table">
          <thead>
            <tr>
              <th></th>
              <th>{t('benchmark.cases')}</th>
              {GROUP_METRICS.map((m) => (
                <th key={m}>
                  <span className="bm-th-inner">
                    {t(`benchmark.metric_${m}`)}
                    <Tooltip text={t(`benchmark.metric_${m}_tip`)} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map(([name, metrics]) => (
              <tr key={name}>
                <td className="bm-group-name">{name}</td>
                <td className="bm-group-cases">
                  <span className="bm-cases-badge">{metrics.cases}</span>
                </td>
                {GROUP_METRICS.map((m) => {
                  const v = (metrics as unknown as Record<string, number>)[m] ?? 0;
                  const level = scoreLevel(v);
                  return (
                    <td key={m}>
                      <span className={`bm-cell-value bm-cell-${level}`}>{pct(v)}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---- Case breakdown ---- */

function CaseBreakdown({ results, t }: {
  results: BenchmarkResult['results'];
  t: (k: string) => string;
}) {
  if (!results || results.length === 0) return null;
  return (
    <div className="bm-group-section">
      <h3 className="bm-section-title">{t('benchmark.caseBreakdown')}</h3>
      <div className="bm-table-wrap">
        <table className="bm-table bm-case-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Question</th>
              <th>Lang</th>
              <th>Category</th>
              <th>
                <span className="bm-th-inner">
                  Source Hit
                  <Tooltip text={t('benchmark.metric_source_hit_rate_tip')} />
                </span>
              </th>
              <th>
                <span className="bm-th-inner">
                  RR
                  <Tooltip text={t('benchmark.metric_mrr_tip')} />
                </span>
              </th>
              <th>
                <span className="bm-th-inner">
                  NDCG
                  <Tooltip text={t('benchmark.metric_ndcg_at_k_tip')} />
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {results.map((c) => (
              <tr key={c.id} className={c.answerable ? '' : 'bm-row-unanswerable'}>
                <td className="bm-case-id">{c.id}</td>
                <td className="bm-case-question">{c.question}</td>
                <td>{c.language}</td>
                <td><span className="bm-category-badge">{c.category}</span></td>
                <td>
                  {c.source_hit
                    ? <CheckCircleOutlined className="bm-icon-pass" />
                    : <CloseCircleOutlined className="bm-icon-fail" />}
                </td>
                <td>
                  <span className={`bm-cell-value bm-cell-${scoreLevel(c.reciprocal_rank)}`}>
                    {c.reciprocal_rank.toFixed(2)}
                  </span>
                </td>
                <td>
                  <span className={`bm-cell-value bm-cell-${scoreLevel(c.ndcg_at_k)}`}>
                    {c.ndcg_at_k.toFixed(2)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ============================================================
   Main page
   ============================================================ */

export default function BenchmarkPage() {
  const { t } = useTranslation();
  const [list, setList] = useState<BenchmarkListItem[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const fetchList = useCallback(async (selectNewest = false) => {
    try {
      const items = await listBenchmarkResults();
      const nonComp = items.filter((i) => !i.is_comparison);
      setList(nonComp);
      if (selectNewest && nonComp.length > 0) {
        setSelected(nonComp[0].filename);
      }
      return nonComp;
    } catch { /* ignore */ }
    return [];
  }, []);

  const handleRunEval = useCallback(async () => {
    setRunning(true);
    try {
      const res = await runBenchmark(4, false);
      if (res.success) {
        await fetchList(true);
      }
    } catch { /* ignore */ }
    setRunning(false);
  }, [fetchList]);

  // Initialize on mount
  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      const items = await listBenchmarkResults();
      const nonComp = items.filter((i) => !i.is_comparison);
      if (isMounted) {
        setList(nonComp);
        if (nonComp.length > 0 && !selectedRef.current) {
          setSelected(nonComp[0].filename);
        }
      }
    };
    init().catch(() => { /* ignore */ });
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const data = await getBenchmarkResult(selected);
        if (!cancelled) setResult(data);
      } catch { /* ignore */ } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [selected]);

  if (loading && !result) {
    return (
      <div className="bm-page">
        <div className="bm-empty">{t('benchmark.loading')}</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="bm-page">
        <div className="bm-header">
          <div>
            <h1 className="bm-title"><ExperimentOutlined /> {t('benchmark.title')}</h1>
            <p className="bm-subtitle">{t('benchmark.subtitle')}</p>
          </div>
          <button className="bm-run-btn" onClick={handleRunEval} disabled={running}>
            {running ? <LoadingOutlined spin /> : <PlayCircleOutlined />}
            {running ? t('benchmark.running') : t('benchmark.runEval')}
          </button>
        </div>
        <div className="bm-empty">{t('benchmark.noResults')}</div>
      </div>
    );
  }

  const s = result.summary;
  const meta = result.metadata;

  return (
    <div className="bm-page">
      {/* Header + Selector */}
      <div className="bm-header">
        <div>
          <h1 className="bm-title"><ExperimentOutlined /> {t('benchmark.title')}</h1>
          <p className="bm-subtitle">{t('benchmark.subtitle')}</p>
        </div>
        <div className="bm-header-actions">
          <button className="bm-run-btn" onClick={handleRunEval} disabled={running}>
            {running ? <LoadingOutlined spin /> : <PlayCircleOutlined />}
            {running ? t('benchmark.running') : t('benchmark.runEval')}
          </button>
          <button className="bm-refresh-btn" onClick={() => fetchList(true)} title={t('benchmark.refresh')}>
            <ReloadOutlined />
          </button>
          {list.length > 1 && (
            <select
              className="bm-select"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {list.map((item) => (
                <option key={item.filename} value={item.filename}>
                  {new Date(item.timestamp_utc).toLocaleString()} — K={item.k}
                  {item.use_query_rewrite ? ' (rewrite)' : ''}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Case Stats */}
      <div className="bm-stats-row">
        <div className="bm-stat-card">
          <span className="bm-stat-label">{t('benchmark.total')}</span>
          <span className="bm-stat-value">{s.total_cases}</span>
          <span className="bm-stat-unit">{t('benchmark.cases')}</span>
        </div>
        <div className="bm-stat-card bm-stat-answerable">
          <span className="bm-stat-label">{t('benchmark.answerable')}</span>
          <span className="bm-stat-value">{s.answerable_cases}</span>
          <span className="bm-stat-unit">{t('benchmark.cases')}</span>
        </div>
        <div className="bm-stat-card bm-stat-unanswerable">
          <span className="bm-stat-label">{t('benchmark.unanswerable')}</span>
          <span className="bm-stat-value">{s.unanswerable_cases}</span>
          <span className="bm-stat-unit">{t('benchmark.cases')}</span>
        </div>
      </div>

      {/* Core Metrics Grid */}
      <h3 className="bm-section-title">{t('benchmark.overallPerformance')}</h3>
      <div className="bm-metrics-grid">
        {CORE_METRICS.map((m) => (
          <MetricCard
            key={m}
            metricKey={m}
            value={(s as unknown as Record<string, number>)[m] ?? 0}
            t={t}
          />
        ))}
        {s.unanswerable_cases > 0 && (
          <MetricCard
            metricKey="unanswerable_keyword_false_positive_rate"
            value={s.unanswerable_keyword_false_positive_rate}
            t={t}
            inverted
          />
        )}
      </div>

      {/* By Language */}
      <GroupTable title={t('benchmark.byLanguage')} data={s.by_language} t={t} />

      {/* By Category */}
      <GroupTable title={t('benchmark.byCategory')} data={s.by_category} t={t} />

      {/* Case Breakdown */}
      <CaseBreakdown results={result.results} t={t} />

      {/* Metadata */}
      <div className="bm-group-section">
        <h3 className="bm-section-title">{t('benchmark.metadata')}</h3>
        <div className="bm-meta-grid">
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.runAt')}</span>
            <span className="bm-meta-value">{new Date(result.timestamp_utc).toLocaleString()}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.model')}</span>
            <span className="bm-meta-value">{meta.model_name}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.embedding')}</span>
            <span className="bm-meta-value">{meta.embedding_model}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.chunkSize')}</span>
            <span className="bm-meta-value">{meta.chunk_size}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.chunkOverlap')}</span>
            <span className="bm-meta-value">{meta.chunk_overlap}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.bm25Weight')}</span>
            <span className="bm-meta-value">{meta.bm25_weight}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">Top-K</span>
            <span className="bm-meta-value">{meta.k}</span>
          </div>
          <div className="bm-meta-item">
            <span className="bm-meta-label">{t('benchmark.queryRewrite')}</span>
            <span className="bm-meta-value">
              {meta.use_query_rewrite ? t('benchmark.enabled') : t('benchmark.disabled')}
            </span>
          </div>
          {meta.git_commit && (
            <div className="bm-meta-item">
              <span className="bm-meta-label">{t('benchmark.commit')}</span>
              <span className="bm-meta-value bm-meta-mono">{meta.git_commit.slice(0, 8)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
