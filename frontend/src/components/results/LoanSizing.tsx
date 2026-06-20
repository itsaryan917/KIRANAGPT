'use client';

import { useEffect, useState } from 'react';
import type { LoanSizing as LoanSizingType } from '../../types/underwriting';
import { formatINR } from '../../lib/format';

interface LoanSizingProps {
  data: LoanSizingType;
  decision: 'approve' | 'reject' | 'review';
}

function AnimatedAmount({ target }: { target: number }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const duration = 1400;

    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 4);
      setValue(Math.round(ease * target));
      if (p < 1) requestAnimationFrame(tick);
    };

    const raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return <>{formatINR(value)}</>;
}

export function LoanSizing({ data, decision }: LoanSizingProps) {
  const decisionConfig = {
    approve: {
      color: 'var(--success)',
      bg: 'var(--success-bg)',
      border: 'rgba(16,185,129,0.3)',
      label: 'SANCTIONED',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2.5" strokeLinecap="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ),
    },
    review: {
      color: 'var(--review)',
      bg: 'var(--review-bg)',
      border: 'rgba(99,102,241,0.3)',
      label: 'UNDER REVIEW',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--review)" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      ),
    },
    reject: {
      color: 'var(--danger)',
      bg: 'var(--danger-bg)',
      border: 'rgba(239,68,68,0.3)',
      label: 'DECLINED',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="2.5" strokeLinecap="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      ),
    },
  };

  const cfg = decisionConfig[decision];

  return (
    <div>
      {/* Decision badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 16px',
          background: cfg.bg,
          border: `1px solid ${cfg.border}`,
          borderRadius: 10,
          marginBottom: 16,
        }}
      >
        {cfg.icon}
        <span
          style={{
            fontFamily: 'Syne, sans-serif',
            fontWeight: 700,
            fontSize: 15,
            color: cfg.color,
            letterSpacing: '-0.01em',
          }}
        >
          Loan {cfg.label}
        </span>
        <div
          style={{
            marginLeft: 'auto',
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: '0.12em',
            color: cfg.color,
            background: `${cfg.color}15`,
            padding: '3px 10px',
            borderRadius: 4,
          }}
        >
          {cfg.label}
        </div>
      </div>

      {/* Recommended amount — hero */}
      <div
        style={{
          textAlign: 'center',
          padding: '24px 16px',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          marginBottom: 14,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: `radial-gradient(ellipse at 50% 120%, ${cfg.color}08 0%, transparent 70%)`,
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--text-muted)',
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}
        >
          Recommended Loan Amount
        </div>
        <div
          style={{
            fontFamily: 'Syne, sans-serif',
            fontSize: 38,
            fontWeight: 800,
            color: cfg.color,
            letterSpacing: '-0.03em',
            lineHeight: 1,
            marginBottom: 6,
          }}
        >
          <AnimatedAmount target={data.recommended} />
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {data.tenure_months}-month term · {data.interest_rate}% p.a.
        </div>
      </div>

      {/* Grid of metrics */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 10,
          marginBottom: 14,
        }}
      >
        {[
          { label: 'Minimum', value: data.minimum, muted: true },
          { label: 'Maximum', value: data.maximum, muted: true },
          { label: 'Monthly EMI', value: data.emi, muted: false },
          { label: 'Tenure', value: null, raw: `${data.tenure_months} months`, muted: false },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              padding: '12px 14px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
            }}
          >
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                fontWeight: 600,
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
                fontSize: 17,
                fontWeight: 700,
                color: item.muted ? 'var(--text-secondary)' : 'var(--text-primary)',
              }}
            >
              {item.value !== null ? formatINR(item.value) : item.raw}
            </div>
          </div>
        ))}
      </div>

      {/* Range bar */}
      <div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 10,
            color: 'var(--text-muted)',
            marginBottom: 6,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          <span>{formatINR(data.minimum)}</span>
          <span>Loan Range</span>
          <span>{formatINR(data.maximum)}</span>
        </div>
        <div
          style={{
            height: 6,
            background: 'var(--bg-elevated)',
            borderRadius: 3,
            position: 'relative',
          }}
        >
          {/* Range fill */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              right: 0,
              borderRadius: 3,
              background: `linear-gradient(90deg, var(--border-bright), ${cfg.color}40)`,
            }}
          />
          {/* Recommended marker */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              transform: 'translate(-50%, -50%)',
              left: `${((data.recommended - data.minimum) / (data.maximum - data.minimum)) * 100}%`,
              width: 14,
              height: 14,
              borderRadius: '50%',
              background: cfg.color,
              border: '3px solid var(--bg-card)',
              boxShadow: `0 0 8px ${cfg.color}`,
              transition: 'left 1s ease',
            }}
          />
        </div>
      </div>
    </div>
  );
}
