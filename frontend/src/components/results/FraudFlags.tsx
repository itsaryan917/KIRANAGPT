'use client';

import type { FraudFlag } from '../../types/underwriting';

interface FraudFlagsProps {
  flags: FraudFlag[];
}

const SEVERITY_CONFIG = {
  low: {
    color: 'var(--warning)',
    bg: 'var(--warning-bg)',
    border: 'rgba(245,158,11,0.25)',
    label: 'LOW',
    icon: '◎',
  },
  medium: {
    color: '#fb923c',
    bg: 'rgba(251,146,60,0.1)',
    border: 'rgba(251,146,60,0.25)',
    label: 'MED',
    icon: '◉',
  },
  high: {
    color: 'var(--danger)',
    bg: 'var(--danger-bg)',
    border: 'rgba(239,68,68,0.25)',
    label: 'HIGH',
    icon: '⬟',
  },
  critical: {
    color: '#dc2626',
    bg: 'rgba(220,38,38,0.12)',
    border: 'rgba(220,38,38,0.35)',
    label: 'CRIT',
    icon: '▲',
  },
};

export function FraudFlags({ flags }: FraudFlagsProps) {
  return (
    <div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 14,
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--danger)"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        <span
          style={{
            fontFamily: 'Syne, sans-serif',
            fontWeight: 600,
            fontSize: 14,
            color: 'var(--text-primary)',
          }}
        >
          Risk Signals
        </span>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: 11,
            fontWeight: 700,
            color: flags.length === 0 ? 'var(--success)' : 'var(--danger)',
            background:
              flags.length === 0 ? 'var(--success-bg)' : 'var(--danger-bg)',
            border: `1px solid ${flags.length === 0 ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            padding: '2px 10px',
            borderRadius: 20,
          }}
        >
          {flags.length === 0 ? 'CLEAN' : `${flags.length} FLAG${flags.length > 1 ? 'S' : ''}`}
        </span>
      </div>

      {flags.length === 0 ? (
        <div
          style={{
            padding: '18px 16px',
            background: 'var(--success-bg)',
            border: '1px solid rgba(16,185,129,0.2)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--success)"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span style={{ fontSize: 13, color: 'var(--success)', fontWeight: 500 }}>
            No fraud signals detected. Store profile is consistent.
          </span>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {flags.map((flag, i) => {
            const cfg = SEVERITY_CONFIG[flag.severity];
            return (
              <div
                key={i}
                style={{
                  padding: '12px 14px',
                  background: cfg.bg,
                  border: `1px solid ${cfg.border}`,
                  borderRadius: 8,
                  display: 'flex',
                  gap: 12,
                  alignItems: 'flex-start',
                  animation: `fadeIn 0.4s ease ${i * 100}ms both`,
                }}
              >
                <span
                  style={{
                    color: cfg.color,
                    fontSize: 14,
                    lineHeight: 1,
                    marginTop: 1,
                    flexShrink: 0,
                  }}
                >
                  {cfg.icon}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      marginBottom: 3,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 800,
                        color: cfg.color,
                        letterSpacing: '0.1em',
                        background: `${cfg.color}20`,
                        padding: '1px 7px',
                        borderRadius: 3,
                      }}
                    >
                      {cfg.label}
                    </span>
                    <code
                      style={{
                        fontSize: 11,
                        color: cfg.color,
                        fontFamily: 'monospace',
                        opacity: 0.8,
                      }}
                    >
                      {flag.code}
                    </code>
                  </div>
                  <p
                    style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.5,
                      margin: 0,
                    }}
                  >
                    {flag.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
