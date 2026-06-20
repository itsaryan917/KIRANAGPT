'use client';

import { useEffect, useState } from 'react';

interface ConfidenceMeterProps {
  value: number; // 0-1
}

export function ConfidenceMeter({ value }: ConfidenceMeterProps) {
  const [animated, setAnimated] = useState(0);
  const pct = Math.round(value * 100);

  useEffect(() => {
    const start = performance.now();
    const duration = 1200;

    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setAnimated(Math.round(ease * pct));
      if (progress < 1) requestAnimationFrame(tick);
    };

    const raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [pct]);

  const color =
    value >= 0.75
      ? 'var(--success)'
      : value >= 0.58
      ? 'var(--warning)'
      : 'var(--danger)';

  const label =
    value >= 0.75 ? 'High Confidence' : value >= 0.58 ? 'Moderate' : 'Low Confidence';

  // Segments: 20 arcs
  const total = 20;
  const filled = Math.round((animated / 100) * total);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 14,
      }}
    >
      {/* Arc gauge */}
      <div style={{ position: 'relative', width: 180, height: 100 }}>
        <svg
          viewBox="0 0 180 100"
          width="180"
          height="100"
          style={{ overflow: 'visible' }}
        >
          {/* Background arc */}
          <path
            d="M 10 90 A 80 80 0 0 1 170 90"
            fill="none"
            stroke="var(--bg-elevated)"
            strokeWidth="14"
            strokeLinecap="round"
          />
          {/* Filled arc */}
          <path
            d="M 10 90 A 80 80 0 0 1 170 90"
            fill="none"
            stroke={color}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray="251.2"
            strokeDashoffset={251.2 - (animated / 100) * 251.2}
            style={{
              transition: 'stroke-dashoffset 0.05s linear, stroke 0.5s ease',
              filter: `drop-shadow(0 0 6px ${color})`,
            }}
          />
          {/* Tick marks */}
          {Array.from({ length: total + 1 }).map((_, i) => {
            const angle = -180 + (i / total) * 180;
            const rad = (angle * Math.PI) / 180;
            const cx = 90 + 80 * Math.cos(rad);
            const cy = 90 + 80 * Math.sin(rad);
            const ix = 90 + 68 * Math.cos(rad);
            const iy = 90 + 68 * Math.sin(rad);
            return (
              <line
                key={i}
                x1={cx}
                y1={cy}
                x2={ix}
                y2={iy}
                stroke={i <= filled ? color : 'var(--border)'}
                strokeWidth={i % 5 === 0 ? 2.5 : 1.5}
                style={{ transition: 'stroke 0.3s ease' }}
              />
            );
          })}
          {/* Center value */}
          <text
            x="90"
            y="76"
            textAnchor="middle"
            fill={color}
            fontSize="28"
            fontFamily="Syne, sans-serif"
            fontWeight="700"
          >
            {animated}%
          </text>
        </svg>
      </div>

      {/* Label */}
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color,
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          padding: '4px 14px',
          background: `${color}18`,
          border: `1px solid ${color}40`,
          borderRadius: 20,
        }}
      >
        {label}
      </div>

      {/* Bar segments */}
      <div
        style={{
          display: 'flex',
          gap: 3,
          width: '100%',
        }}
      >
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 5,
              borderRadius: 2,
              background: i < filled ? color : 'var(--border)',
              transition: `background 0.3s ease ${i * 30}ms`,
              boxShadow: i < filled ? `0 0 4px ${color}` : 'none',
            }}
          />
        ))}
      </div>
    </div>
  );
}
