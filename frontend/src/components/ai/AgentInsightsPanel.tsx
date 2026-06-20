'use client';

import { useState } from 'react';
import { ReportViewer } from './ReportViewer';
import type { UnderwritingResult } from '../../types/underwriting';

interface Props {
  result: UnderwritingResult & {
    business_insights?: BusinessInsights;
    loan_advice?: LoanAdvice;
    report_markdown?: string;
    hindi_store_report?: string;
    agent_elapsed_s?: number;
    agents_run?: string[];
  };
}

interface BusinessInsights {
  business_health_score: number;
  health_grade: string;
  top_problems: string[];
  top_opportunities: string[];
  inventory_recommendations: Array<{ category: string; action: string; reason: string }>;
  revenue_growth_strategy: string;
  expected_revenue_increase_pct: number;
  risk_assessment: string;
  quick_wins: string[];
  long_term_plays: string[];
  fallback?: boolean;
}

interface LoanAdvice {
  recommended_loan_inr: number;
  minimum_loan_inr: number;
  maximum_loan_inr: number;
  reasoning: string;
  key_strengths: string[];
  key_risks: string[];
  suggested_tenure_months: number;
  interest_rate_pct: number;
  monthly_emi_inr: number;
  approval_conditions: string;
  lender_verdict: string;
  next_steps: string;
  fallback?: boolean;
}

type Tab = 'business' | 'loan' | 'report' | 'hindi';

const VERDICT_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  APPROVE: { color: 'var(--success)', bg: 'var(--success-bg)', label: '✅ Approve' },
  CONDITIONAL_APPROVE: { color: 'var(--warning)', bg: 'var(--warning-bg)', label: '⚠️ Conditional' },
  REFER_TO_BRANCH: { color: 'var(--review)', bg: 'var(--review-bg)', label: '📋 Refer to Branch' },
  REJECT: { color: 'var(--danger)', bg: 'var(--danger-bg)', label: '❌ Reject' },
};

function HealthBar({ score }: { score: number }) {
  const color = score >= 75 ? 'var(--success)' : score >= 50 ? '#f59e0b' : 'var(--danger)';
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
        <span>Business Health</span>
        <span style={{ fontWeight: 600, color }}>{score}/100</span>
      </div>
      <div style={{ height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${score}%`,
            background: color,
            borderRadius: 3,
            transition: 'width 1s ease',
          }}
        />
      </div>
    </div>
  );
}

export function AgentInsightsPanel({ result }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('business');
  // Robust null-guards — never crash even if agent returned partial/undefined data
  const biz  = result.business_insights  ?? {} as BusinessInsights;
  const loan = result.loan_advice ?? {} as LoanAdvice;
  const report = result.report_markdown;

  if (!biz && !loan && !report) return null;

  const verdict = loan?.lender_verdict || 'REFER_TO_BRANCH';
  const verdictStyle = VERDICT_STYLE[verdict] || VERDICT_STYLE.REFER_TO_BRANCH;

  const tabs: Array<{ id: Tab; label: string; icon: string }> = [
    { id: 'business', label: 'Business Advisor', icon: '🏪' },
    { id: 'loan', label: 'Loan Advisor', icon: '💰' },
    { id: 'report', label: 'Full Report', icon: '📄' },
    { id: 'hindi', label: 'हिंदी रिपोर्ट', icon: '🇮🇳' },
  ];

  return (
    <div
      style={{
        marginTop: 32,
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 14,
        overflow: 'hidden',
        animation: 'slideUp 0.5s ease forwards',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '14px 20px',
          background: 'rgba(99,102,241,0.04)',
          borderBottom: '1px solid rgba(99,102,241,0.12)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
        <div>
          <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
            KiranaGPT AI Insights
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {result.agents_run?.length || 3} agents · {result.agent_elapsed_s ? `${result.agent_elapsed_s}s` : 'completed'}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
            AI Verdict:
          </span>
          <span
            style={{
              padding: '3px 10px',
              borderRadius: 20,
              fontSize: 11,
              fontWeight: 700,
              background: verdictStyle.bg,
              color: verdictStyle.color,
            }}
          >
            {verdictStyle.label}
          </span>
        </div>
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-secondary)',
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              padding: '12px 8px',
              fontSize: 13,
              fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-secondary)',
              background: activeTab === tab.id ? 'var(--bg-card)' : 'transparent',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              transition: 'all 0.15s',
            }}
          >
            <span>{tab.icon}</span>
            <span style={{ display: 'none' }}>{tab.label}</span>
            <span style={{ fontSize: 12 }}>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ background: 'var(--bg-card)', padding: 24 }}>
        {/* BUSINESS TAB */}
        {activeTab === 'business' && biz && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Health score */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 20,
                padding: 16,
                background: 'var(--bg-secondary)',
                borderRadius: 10,
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    fontFamily: 'Syne, sans-serif',
                    fontSize: 40,
                    fontWeight: 800,
                    color:
                      biz.business_health_score >= 75
                        ? 'var(--success)'
                        : biz.business_health_score >= 50
                        ? '#f59e0b'
                        : 'var(--danger)',
                    lineHeight: 1,
                  }}
                >
                  {biz.business_health_score}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>/ 100</div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                  Grade {biz.health_grade} — Business Health Score
                </div>
                <HealthBar score={biz.business_health_score} />
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                  Expected revenue increase: <strong style={{ color: 'var(--success)' }}>+{biz.expected_revenue_increase_pct}%</strong> with recommendations
                </div>
              </div>
            </div>

            {/* 2-col grid: problems + opportunities */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--danger)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                  ⚠ Top Problems
                </div>
                {biz.top_problems?.map((p, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 13,
                      color: 'var(--text-secondary)',
                      padding: '6px 0',
                      borderBottom: '1px solid var(--border)',
                      display: 'flex',
                      gap: 8,
                    }}
                  >
                    <span style={{ color: 'var(--danger)', flexShrink: 0 }}>›</span>
                    {p}
                  </div>
                ))}
              </div>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--success)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                  ✓ Opportunities
                </div>
                {biz.top_opportunities?.map((o, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 13,
                      color: 'var(--text-secondary)',
                      padding: '6px 0',
                      borderBottom: '1px solid var(--border)',
                      display: 'flex',
                      gap: 8,
                    }}
                  >
                    <span style={{ color: 'var(--success)', flexShrink: 0 }}>✓</span>
                    {o}
                  </div>
                ))}
              </div>
            </div>

            {/* Inventory recommendations */}
            {biz.inventory_recommendations?.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
                  📦 Inventory Recommendations
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {biz.inventory_recommendations.map((rec, i) => (
                    <div
                      key={i}
                      style={{
                        padding: '10px 14px',
                        background: 'var(--bg-elevated)',
                        borderRadius: 8,
                        display: 'flex',
                        gap: 12,
                        alignItems: 'flex-start',
                      }}
                    >
                      <span
                        style={{
                          padding: '2px 8px',
                          background: 'rgba(99,102,241,0.08)',
                          color: 'var(--accent)',
                          borderRadius: 4,
                          fontSize: 10,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {rec.category}
                      </span>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{rec.action}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{rec.reason}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Strategy */}
            <div
              style={{
                padding: '14px 16px',
                background: 'rgba(99,102,241,0.04)',
                border: '1px solid rgba(99,102,241,0.12)',
                borderRadius: 10,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', marginBottom: 6 }}>
                🚀 Revenue Growth Strategy
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                {biz.revenue_growth_strategy}
              </p>
            </div>

            {/* Quick wins */}
            {biz.quick_wins?.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {biz.quick_wins.map((w, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '8px 12px',
                      background: 'var(--success-bg)',
                      borderRadius: 8,
                      fontSize: 12,
                      color: 'var(--success)',
                      display: 'flex',
                      gap: 6,
                      alignItems: 'center',
                    }}
                  >
                    <span>⚡</span> {w}
                  </div>
                ))}
              </div>
            )}

            {biz.fallback && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', padding: '8px 0' }}>
                * Heuristic analysis (AI unavailable — set GEMINI_API_KEY in .env for full insights)
              </div>
            )}
          </div>
        )}

        {/* LOAN TAB */}
        {activeTab === 'loan' && loan && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Amount header */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 12,
              }}
            >
              {[
                { label: 'Recommended Loan', value: `₹${(loan.recommended_loan_inr || 0).toLocaleString('en-IN')}`, highlight: true },
                { label: 'Minimum', value: `₹${(loan.minimum_loan_inr || 0).toLocaleString('en-IN')}`, highlight: false },
                { label: 'Maximum', value: `₹${(loan.maximum_loan_inr || 0).toLocaleString('en-IN')}`, highlight: false },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: '14px 16px',
                    background: item.highlight ? 'rgba(16,185,129,0.06)' : 'var(--bg-secondary)',
                    border: item.highlight ? '1px solid rgba(16,185,129,0.2)' : '1px solid var(--border)',
                    borderRadius: 10,
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>
                    {item.label}
                  </div>
                  <div
                    style={{
                      fontFamily: 'Syne, sans-serif',
                      fontSize: item.highlight ? 22 : 16,
                      fontWeight: 800,
                      color: item.highlight ? 'var(--success)' : 'var(--text-primary)',
                    }}
                  >
                    {item.value}
                  </div>
                </div>
              ))}
            </div>

            {/* EMI row */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: 12,
              }}
            >
              {[
                { label: 'Monthly EMI', value: `₹${(loan.monthly_emi_inr || 0).toLocaleString('en-IN')}` },
                { label: 'Tenure', value: `${loan.suggested_tenure_months || 12} months` },
                { label: 'Interest Rate', value: `${loan.interest_rate_pct || 18}% p.a.` },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: '12px 16px',
                    background: 'var(--bg-secondary)',
                    borderRadius: 10,
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>
                    {item.label}
                  </div>
                  <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {item.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Reasoning */}
            <div
              style={{
                padding: 16,
                background: 'var(--bg-elevated)',
                borderRadius: 10,
                border: '1px solid var(--border)',
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                Lender Reasoning
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, margin: 0 }}>
                {loan.reasoning}
              </p>
            </div>

            {/* Strengths + Risks */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--success)', marginBottom: 8 }}>Key Strengths</div>
                {loan.key_strengths?.map((s, i) => (
                  <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 6, marginBottom: 6 }}>
                    <span style={{ color: 'var(--success)' }}>✓</span> {s}
                  </div>
                ))}
              </div>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--danger)', marginBottom: 8 }}>Key Risks</div>
                {loan.key_risks?.map((r, i) => (
                  <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 6, marginBottom: 6 }}>
                    <span style={{ color: 'var(--danger)' }}>!</span> {r}
                  </div>
                ))}
              </div>
            </div>

            {/* Conditions */}
            {loan.approval_conditions && loan.approval_conditions !== 'None' && (
              <div
                style={{
                  padding: '10px 14px',
                  background: 'var(--warning-bg)',
                  border: '1px solid rgba(245,158,11,0.2)',
                  borderRadius: 8,
                  fontSize: 12,
                  color: 'var(--warning)',
                  display: 'flex',
                  gap: 8,
                }}
              >
                <span>📋</span>
                <span><strong>Conditions:</strong> {loan.approval_conditions}</span>
              </div>
            )}

            {/* Next steps */}
            {loan.next_steps && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0' }}>
                Next steps: {loan.next_steps}
              </div>
            )}

            {loan.fallback && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
                * Heuristic analysis (set GEMINI_API_KEY in .env for AI-generated reasoning)
              </div>
            )}
          </div>
        )}

        {/* REPORT TAB */}
        {activeTab === 'report' && (
          <div>
            {report ? (
              <ReportViewer markdown={report} storeId='KGT' />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                Report not available. Use the /ai-insights endpoint to generate.
              </div>
            )}
          </div>
        )}

        {/* HINDI STORE OWNER REPORT TAB */}
        {activeTab === 'hindi' && (
          <div>
            <div style={{ marginBottom: 14, padding: '10px 14px', background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.12)', borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
              🇮🇳 यह रिपोर्ट दुकानदार के लिए है — सरल हिंदी में उनके assessment का विवरण
            </div>
            {result.hindi_store_report ? (
              <div style={{ padding: 20, background: 'var(--bg-elevated)', borderRadius: 10, border: '1px solid var(--border)', fontSize: 15, color: 'var(--text-primary)', lineHeight: 2, whiteSpace: 'pre-wrap', fontFamily: 'sans-serif' }}>
                {result.hindi_store_report}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 32, marginBottom: 12 }}>🇮🇳</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>हिंदी रिपोर्ट उपलब्ध नहीं है</div>
                <div style={{ fontSize: 12 }}>Run the full AI pipeline to generate the Hindi store owner report.</div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
