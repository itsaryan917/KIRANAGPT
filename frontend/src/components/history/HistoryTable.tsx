'use client';

import type { HistoryRecord } from '../../types/underwriting';
import { formatINR, formatDate, formatConfidence } from '../../lib/format';

interface HistoryTableProps {
  records: HistoryRecord[];
}

function DecisionBadge({ decision }: { decision: any }) {
  const norm = String(decision || 'review').toLowerCase();
  const map: Record<string, { label: string; cls: string }> = {
    approve: { label: 'APPROVE', cls: 'badge-approve' },
    approved: { label: 'APPROVE', cls: 'badge-approve' },
    reject: { label: 'REJECT', cls: 'badge-reject' },
    rejected: { label: 'REJECT', cls: 'badge-reject' },
    review: { label: 'REVIEW', cls: 'badge-review' },
    conditional_approve: { label: 'REVIEW', cls: 'badge-review' },
    refer_to_branch: { label: 'REVIEW', cls: 'badge-review' },
  };
  const { label, cls } = map[norm] || { label: String(decision).toUpperCase(), cls: 'badge-review' };
  return (
    <span
      className={cls}
      style={{
        fontSize: 10,
        fontWeight: 800,
        letterSpacing: '0.08em',
        padding: '3px 10px',
        borderRadius: 4,
        display: 'inline-block',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
}

function RiskBar({ score }: { score: number }) {
  const color =
    score < 35
      ? 'var(--success)'
      : score < 60
      ? 'var(--warning)'
      : 'var(--danger)';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div
        style={{
          width: 56,
          height: 4,
          background: 'var(--bg-elevated)',
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${score}%`,
            background: color,
            borderRadius: 2,
          }}
        />
      </div>
      <span
        style={{ fontSize: 12, color, fontWeight: 600, fontFamily: 'Syne, sans-serif' }}
      >
        {score}
      </span>
    </div>
  );
}

export function HistoryTable({ records }: HistoryTableProps) {
  if (records.length === 0) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: '64px 24px',
          color: 'var(--text-muted)',
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 12,
        }}
      >
        <svg
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--border-bright)"
          strokeWidth="1.5"
          style={{ display: 'block', margin: '0 auto 16px' }}
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
        <div
          style={{
            fontFamily: 'Syne, sans-serif',
            fontWeight: 600,
            fontSize: 16,
            color: 'var(--text-secondary)',
            marginBottom: 6,
          }}
        >
          No assessments yet
        </div>
        <div style={{ fontSize: 13 }}>
          Submit your first underwriting case to see history here.
        </div>
      </div>
    );
  }

  const cols = [
    { label: 'Case ID', width: '9%' },
    { label: 'Store', width: '18%' },
    { label: 'Owner', width: '14%' },
    { label: 'Monthly Rev.', width: '13%' },
    { label: 'Loan Amount', width: '13%' },
    { label: 'Confidence', width: '11%' },
    { label: 'Risk', width: '11%' },
    { label: 'Decision', width: '8%' },
    { label: 'Date', width: '13%' },
  ];

  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
      }}
    >
      {/* Table header */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: cols.map((c) => c.width).join(' '),
          padding: '10px 20px',
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border-bright)',
        }}
      >
        {cols.map((col) => (
          <div
            key={col.label}
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}
          >
            {col.label}
          </div>
        ))}
      </div>

      {/* Rows */}
      {records.map((rec, i) => (
        <div
          key={rec.id}
          style={{
            display: 'grid',
            gridTemplateColumns: cols.map((c) => c.width).join(' '),
            padding: '13px 20px',
            borderBottom:
              i < records.length - 1 ? '1px solid var(--border)' : 'none',
            transition: 'background 0.15s',
            animation: `fadeIn 0.4s ease ${i * 40}ms both`,
            alignItems: 'center',
          }}
          onMouseEnter={(e) =>
            ((e.currentTarget as HTMLDivElement).style.background =
              'var(--bg-card-hover)')
          }
          onMouseLeave={(e) =>
            ((e.currentTarget as HTMLDivElement).style.background = 'transparent')
          }
        >
          {/* Case ID */}
          <div>
            <code
              style={{
                fontSize: 11,
                color: 'var(--accent)',
                fontFamily: 'monospace',
                background: 'var(--accent-glow)',
                padding: '2px 6px',
                borderRadius: 3,
              }}
            >
              {rec.id}
            </code>
          </div>

          {/* Store */}
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              paddingRight: 8,
            }}
          >
            {rec.store_name}
          </div>

          {/* Owner */}
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-secondary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              paddingRight: 8,
            }}
          >
            {rec.owner_name}
          </div>

          {/* Revenue */}
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--accent)',
              fontFamily: 'Syne, sans-serif',
            }}
          >
            {formatINR(rec.monthly_revenue)}
          </div>

          {/* Loan */}
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--text-primary)',
              fontFamily: 'Syne, sans-serif',
            }}
          >
            {formatINR(rec.loan_amount)}
          </div>

          {/* Confidence */}
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color:
                rec.confidence >= 0.75
                  ? 'var(--success)'
                  : rec.confidence >= 0.58
                  ? 'var(--warning)'
                  : 'var(--danger)',
            }}
          >
            {formatConfidence(rec.confidence)}
          </div>

          {/* Risk */}
          <RiskBar score={rec.risk_score} />

          {/* Decision */}
          <div>
            <DecisionBadge decision={rec.decision} />
          </div>

          {/* Date */}
          <div
            style={{
              fontSize: 11,
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
            }}
          >
            {formatDate(rec.created_at)}
          </div>
        </div>
      ))}
    </div>
  );
}
