import { useState } from 'react';
import { FileTextOutlined, DownOutlined, UpOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { SourceInfo } from '@/api/chat';

interface SourceCitationProps {
  sources: SourceInfo[];
}

export default function SourceCitation({ sources }: SourceCitationProps) {
  const [expanded, setExpanded] = useState(false);
  const { t } = useTranslation();

  // Scores are pre-normalized to 0-100 by the backend
  // Vector: similarity percentage (higher = more similar)
  // BM25: keyword relevance percentage (higher = more relevant)

  return (
    <div className="source-citation">
      <button
        className="source-citation-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        <FileTextOutlined />
        <span>
          {t('chat.sources')} ({sources.length})
        </span>
        {expanded ? <UpOutlined /> : <DownOutlined />}
      </button>

      {expanded && (
        <div className="source-citation-list">
          {sources.map((source, index) => (
            <SourceItem
              key={index}
              source={source}
              index={index}
              normBm25={source.score_bm25 !== undefined ? Math.round(source.score_bm25) : undefined}
              normVector={source.score_vector !== undefined ? Math.round(source.score_vector) : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceItem({ source, index, normBm25, normVector }: {
  source: SourceInfo;
  index: number;
  normBm25?: number;
  normVector?: number;
}) {
  const [showContent, setShowContent] = useState(false);
  const fileName = source.title || source.file_path?.split('/').pop() || `Source ${index + 1}`;
  const hasSplitScores = normBm25 !== undefined || normVector !== undefined;

  return (
    <div className="source-item">
      <button className="source-item-header" onClick={() => setShowContent(!showContent)}>
        <span className="source-item-index">{index + 1}</span>
        <span className="source-item-name">{fileName}</span>
        {hasSplitScores && (
          <span className="source-scores">
            <span className={`source-score-badge score-vector ${scoreClass(normVector)}`} title="Vector similarity">
              Vec {normVector ?? 0}
            </span>
            <span className={`source-score-badge score-bm25 ${scoreClass(normBm25)}`} title="BM25 keyword match">
              BM25 {normBm25 ?? 0}
            </span>
          </span>
        )}
      </button>
      {showContent && source.preview && (
        <div className="source-item-content">
          <p>{source.preview}</p>
        </div>
      )}
    </div>
  );
}

function scoreClass(score?: number): string {
  if (score === undefined) return 'score-low';
  if (score >= 80) return 'score-high';
  if (score >= 50) return 'score-mid';
  return 'score-low';
}
