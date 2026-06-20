'use client';

import { useEffect, useRef, useState } from 'react';
import type { UnderwritingResult } from '../../types/underwriting';
import { formatINR, formatDate, formatConfidence } from '../../lib/format';
import { ConfidenceMeter } from './ConfidenceMeter';
import { FraudFlags } from './FraudFlags';
import { LoanSizing } from './LoanSizing';
import { FeatureScores } from './FeatureScores';

interface ResultCardProps {
  result: UnderwritingResult;
}

function AnimatedNumber({
  target,
  prefix = '',
  suffix = '',
  formatter,
}: {
  target: number;
  prefix?: string;
  suffix?: string;
  formatter?: (v: number) => string;
}) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const duration = 1200;

    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 4);
      setValue(Math.round(ease * target));
      if (p < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [target]);

  return (
    <>
      {prefix}
      {formatter ? formatter(value) : value.toLocaleString('en-IN')}
      {suffix}
    </>
  );
}

const DECISION_CONFIG = {
  approve: {
    color: 'var(--success)',
    bg: 'var(--success-bg)',
    border: 'rgba(16,185,129,0.2)',
    label: 'APPROVE',
    glow: 'rgba(16,185,129,0.15)',
  },
  review: {
    color: 'var(--review)',
    bg: 'var(--review-bg)',
    border: 'rgba(99,102,241,0.2)',
    label: 'MANUAL REVIEW',
    glow: 'rgba(99,102,241,0.15)',
  },
  reject: {
    color: 'var(--danger)',
    bg: 'var(--danger-bg)',
    border: 'rgba(239,68,68,0.2)',
    label: 'REJECT',
    glow: 'rgba(239,68,68,0.15)',
  },
};

export function ResultCard({ result }: ResultCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const cfg = DECISION_CONFIG[result.decision?.toLowerCase() as keyof typeof DECISION_CONFIG] || DECISION_CONFIG.review;

  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return (
    <div
      ref={ref}
      style={{
        animation: 'slideUp 0.6s ease forwards',
        scrollMarginTop: 80,
      }}
    >
      {/* Header strip */}
      <div
        style={{
          padding: '20px 28px',
          background: 'var(--bg-card)',
          border: `1px solid ${cfg?.border || "#ccc"}`,
          borderBottom: 'none',
          borderRadius: '12px 12px 0 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Glow */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: `radial-gradient(ellipse at 0% 50%, ${cfg.glow} 0%, transparent 60%)`,
            pointerEvents: 'none',
          }}
        />

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div
              style={{
                fontFamily: 'Syne, sans-serif',
                fontSize: 22,
                fontWeight: 800,
                color: 'var(--text-primary)',
                letterSpacing: '-0.03em',
              }}
            >
              {result.store_name}
            </div>
            <div
              style={{
                padding: '3px 12px',
                background: cfg.bg,
                border: `1px solid ${cfg?.border || "#ccc"}`,
                borderRadius: 20,
                fontSize: 11,
                fontWeight: 800,
                color: cfg.color,
                letterSpacing: '0.08em',
              }}
            >
              {cfg.label}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
            <span>{result.owner_name}</span>
            <span style={{ color: 'var(--border-bright)' }}>·</span>
            <span>Case #{result.id}</span>
            <span style={{ color: 'var(--border-bright)' }}>·</span>
            <span>{formatDate(result.created_at)}</span>
            <span style={{ color: 'var(--border-bright)' }}>·</span>
            <span>{result.images_count} images analysed</span>
          </div>
        </div>

        {/* Risk score */}
        <div
          style={{
            textAlign: 'center',
            padding: '10px 20px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 10,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: 'var(--text-muted)',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              marginBottom: 2,
            }}
          >
            Risk Score
          </div>
          <div
            style={{
              fontFamily: 'Syne, sans-serif',
              fontSize: 32,
              fontWeight: 800,
              color:
                result.risk_score < 35
                  ? 'var(--success)'
                  : result.risk_score < 60
                    ? 'var(--warning)'
                    : 'var(--danger)',
              letterSpacing: '-0.04em',
              lineHeight: 1,
            }}
          >
            <AnimatedNumber target={result.risk_score} />
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>/ 100</div>
        </div>
      </div>

      {/* KPI bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          background: 'var(--bg-secondary)',
          border: `1px solid ${cfg?.border || "#ccc"}`,
          borderTop: `1px solid var(--border)`,
          borderBottom: 'none',
        }}
      >
        {[
          {
            label: 'Daily Sales',
            isRange: true,
            min: Math.round(result.monthly_revenue / 30 * 0.8),
            max: Math.round(result.monthly_revenue / 30 * 1.2),
            formatter: (v: number) => formatINR(v),
            accent: true,
          },
          {
            label: 'Monthly Revenue',
            isRange: true,
            min: Math.round(result.monthly_revenue * 0.9),
            max: Math.round(result.monthly_revenue * 1.1),
            formatter: (v: number) => formatINR(v),
            accent: false,
          },
          {
            label: 'Monthly Income',
            isRange: true,
            min: Math.round(result.monthly_profit * 0.9),
            max: Math.round(result.monthly_profit * 1.1),
            formatter: (v: number) => formatINR(v),
            accent: false,
          },
          {
            label: 'Confidence',
            value: result.confidence * 100,
            formatter: (v: number) => `${v.toFixed(1)}%`,
            accent: false,
          },
          {
            label: 'Fraud Flags',
            value: result.fraud_flags.length,
            formatter: (v: number) => String(v),
            accent: false,
            danger: result.fraud_flags.length > 0,
          },
        ].map((item, i) => (
          <div
            key={item.label}
            style={{
              padding: '16px 20px',
              borderRight: i < 4 ? '1px solid var(--border)' : 'none',
              position: 'relative',
            }}
          >
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                marginBottom: 4,
              }}
            >
              {item.label}
            </div>
            <div
              style={{
                fontFamily: 'Syne, sans-serif',
                fontSize: 18,
                fontWeight: 800,
                color: item.danger
                  ? 'var(--danger)'
                  : item.accent
                    ? 'var(--accent)'
                    : 'var(--text-primary)',
                letterSpacing: '-0.02em',
                lineHeight: 1,
                whiteSpace: 'nowrap',
              }}
            >
              {item.isRange ? (
                <>
                  <AnimatedNumber target={item.min!} formatter={item.formatter} />
                  {' - '}
                  <AnimatedNumber target={item.max!} formatter={item.formatter} />
                </>
              ) : (
                <AnimatedNumber target={item.value!} formatter={item.formatter} />
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Main content grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 0,
          border: `1px solid ${cfg?.border || "#ccc"}`,
          borderRadius: '0 0 12px 12px',
          overflow: 'hidden',
        }}
      >
        {/* Left column */}
        <div
          style={{
            padding: 24,
            borderRight: '1px solid var(--border)',
            background: 'var(--bg-card)',
            display: 'flex',
            flexDirection: 'column',
            gap: 28,
          }}
        >
          {/* Confidence */}
          <div>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: 16,
              }}
            >
              Underwriting Confidence
            </div>
            <ConfidenceMeter value={result.confidence} />
          </div>

          <div
            style={{ height: 1, background: 'var(--border)' }}
          />

          {/* Feature scores */}
          <FeatureScores scores={result.feature_scores} />
        </div>

        {/* Right column */}
        <div
          style={{
            background: 'var(--bg-card)',
            display: 'flex',
            flexDirection: 'column',
            gap: 0,
          }}
        >
          <div style={{ padding: 24, borderBottom: '1px solid var(--border)' }}>
            <LoanSizing data={result.loan_sizing} decision={result.decision} />
          </div>
          <div style={{ padding: 24 }}>
            <FraudFlags flags={result.fraud_flags} />
          </div>
        </div>
      </div>

      {/* Location footer */}
      <div
        style={{
          marginTop: 12,
          padding: '10px 16px',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 12,
          color: 'var(--text-muted)',
        }}
      >
        <svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
          <circle cx="12" cy="12" r="9" />
        </svg>
        GPS verified:{' '}
        <code style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
          {result.location?.lat?.toFixed(6) ?? "N/A"}, {result.location?.lng?.toFixed(6) ?? "N/A"}
        </code>
        {result.location.accuracy && (
          <span style={{ marginLeft: 4 }}>
            · ±{Math.round(result.location.accuracy)}m accuracy
          </span>
        )}
        <span style={{ marginLeft: 'auto' }}>
          Confidence: {formatConfidence(result.confidence)}
        </span>
      </div>

      {/* Cost comparison */}
      <div style={{ marginTop: 20, padding: '12px 16px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10, display: 'flex', borderLeft: '3px solid var(--accent)' }}>
        <div style={{ flex: 1, borderRight: '1px solid var(--border)', paddingRight: 16 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--danger)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Traditional NBFC</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>14 days · 15 docs · ₹5,000</div>
        </div>
        <div style={{ flex: 1, paddingLeft: 16 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--success)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>KiranaGPT</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--success)' }}>60 seconds · 0 docs · ₹0.50</div>
        </div>
      </div>

      {/* WhatsApp share */}
      <button
        onClick={() => {
          const msg = `KiranaGPT Assessment\n\nDecision: ${(result.decision ?? '').toUpperCase()}\nMonthly Revenue: ₹${(result.monthly_revenue ?? 0).toLocaleString('en-IN')}\nConfidence: ${Math.round((result.confidence ?? 0) * 100)}%\n\nPowered by KiranaGPT — AI credit underwriting for kirana stores`;
          window.open(`https://wa.me/?text=${encodeURIComponent(msg)}`, '_blank');
        }}
        style={{ width: '100%', marginTop: 10, padding: '11px 16px', background: '#25D366', border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.121.558 4.112 1.528 5.836L0 24l6.335-1.527A11.956 11.956 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-1.893 0-3.662-.527-5.175-1.439l-.371-.22-3.764.908.922-3.663-.239-.388A9.946 9.946 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>
        Share via WhatsApp
      </button>

    </div>
  );
}
