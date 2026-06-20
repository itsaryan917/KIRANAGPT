'use client';

import { useEffect, useState } from 'react';
import type { FeatureScore } from '../../types/underwriting';

interface FeatureScoresProps {
  scores?: FeatureScore[]; // 🔥 made optional
}

const EXPLANATIONS: Record<string, string> = {
  visual_score: "Clear product visibility and optimal shelf layout.",
  geo_score: "Located in a high-footfall, commercially active zone.",
  fraud_score: "No major inconsistencies across images and location.",
  shelf_occupancy: "Shelves are well-stocked, indicating good inventory.",
  product_count: "High number of distinct products detected.",
  category_diversity: "Wide range of product categories available.",
  inventory_value_inr: "Significant stock depth indicating a healthy business.",
  market_share: "Strong local market presence compared to competitors."
};


function ScoreBar({ score, delay }: { score: FeatureScore; delay: number }) {
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      const start = performance.now();
      const duration = 900;

      const tick = (now: number) => {
        const p = Math.min((now - start) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        setAnimated(Math.round(ease * score.score));
        if (p < 1) requestAnimationFrame(tick);
      };

      requestAnimationFrame(tick);
    }, delay);

    return () => clearTimeout(timer);
  }, [score.score, delay]);

  const color =
    score.score >= 75
      ? 'var(--success)'
      : score.score >= 55
        ? 'var(--accent)'
        : 'var(--danger)';

  const grade =
    score.score >= 80 ? 'A' : score.score >= 65 ? 'B' : score.score >= 50 ? 'C' : 'D';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 0',
        borderBottom: '1px solid var(--border)',
        animation: `fadeIn 0.5s ease ${delay}ms both`,
      }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          background: `${color}15`,
          border: `1px solid ${color}30`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 12,
          fontWeight: 800,
          color,
          flexShrink: 0,
          fontFamily: 'Syne, sans-serif',
        }}
      >
        {grade}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 5,
          }}
        >
          <span
            style={{
              fontSize: 12,
              color: 'var(--text-secondary)',
            }}
          >
            {score.label || score.name}
          </span>
          <span
            style={{
              fontSize: 13,
              color,
              fontWeight: 700,
            }}
          >
            {animated}
          </span>
        </div>

        <div
          style={{
            height: 5,
            background: 'var(--bg-elevated)',
            borderRadius: 3,
            marginBottom: 6,
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${animated}%`,
              background: `linear-gradient(90deg, ${color}80, ${color})`,
              borderRadius: 3,
            }}
          />
        </div>
        
        {EXPLANATIONS[score.name] && (
          <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.3 }}>
            {EXPLANATIONS[score.name]}
          </div>
        )}
      </div>

      <div style={{ width: 36, textAlign: 'right' }}>
        <span
          style={{
            fontSize: 10,
            color: 'var(--text-muted)',
          }}
        >
          ×{score.weight?.toFixed(2) ?? "0.00"}
        </span>
      </div>
    </div>
  );
}

export function FeatureScores({ scores }: FeatureScoresProps) {

  // 🔥 SAFE FALLBACK
  const safeScores = scores ?? [];

  // 🔥 NO CRASH
  const weighted = safeScores.reduce(
    (acc, s) => acc + (s.score ?? 0) * (s.weight ?? 0),
    0
  );

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <span style={{ fontWeight: 600 }}>Feature Scores</span>
        <span>
          Weighted avg:{" "}
          <b>{safeScores.length ? weighted.toFixed(1) : "N/A"}</b>
        </span>
      </div>

      {safeScores.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          No feature scores available
        </div>
      ) : (
        safeScores.map((s, i) => (
          <ScoreBar key={s.name || i} score={s} delay={i * 80} />
        ))
      )}
    </div>
  );
}