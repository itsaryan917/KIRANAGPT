'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface StreamEvent {
  type: 'stage' | 'pipeline_done' | 'token' | 'agent_done' | 'done' | 'error';
  stage?: string;
  message?: string;
  agent?: string;
  text?: string;
  elapsed?: number;
  result?: Record<string, unknown>;
}

interface AgentState {
  status: 'waiting' | 'running' | 'done' | 'error';
  text: string;
  elapsed?: number;
}

interface Props {
  formData: FormData | null;
  apiBase: string;
  onDone: (result: Record<string, unknown>) => void;
  onError: (msg: string) => void;
}

const AGENTS = [
  { key: 'pipeline',         label: 'YOLOv8 + Geo + Fraud + Fusion', icon: '⚙️', color: '#6366f1' },
  { key: 'business_advisor', label: 'Business Advisor Agent',         icon: '🏪', color: '#10b981' },
  { key: 'loan_advisor',     label: 'Loan Advisor Agent',             icon: '💰', color: '#f59e0b' },
  { key: 'report_agent',     label: 'Report Generation Agent',        icon: '📄', color: '#8b5cf6' },
  { key: 'store_owner',      label: 'हिंदी Store Owner Report',       icon: '🇮🇳', color: '#ef4444' },
];

export function StreamingAnalysis({ formData, apiBase, onDone, onError }: Props) {
  const [agents, setAgents] = useState<Record<string, AgentState>>(() =>
    Object.fromEntries(AGENTS.map(a => [a.key, { status: 'waiting', text: '' }]))
  );
  const [currentAgent, setCurrentAgent] = useState<string>('pipeline');
  const [streamText, setStreamText]     = useState('');
  const [elapsed, setElapsed]           = useState(0);
  const [totalAgents, setTotalAgents]   = useState(0);
  const streamRef  = useRef<string>('');
  const startRef   = useRef<number>(Date.now());
  const timerRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortRef   = useRef<AbortController | null>(null);

  const setAgent = useCallback((key: string, update: Partial<AgentState>) => {
    setAgents(prev => ({ ...prev, [key]: { ...prev[key], ...update } }));
  }, []);

  useEffect(() => {
    if (!formData) return;
    startRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    (async () => {
      try {
        const base = apiBase || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
        const res = await fetch(`${base}/ai-stream`, {
          method: 'POST',
          body: formData,
          signal: ctrl.signal,
        });

        if (!res.ok) throw new Error(`Server error ${res.status}`);
        if (!res.body) throw new Error('No stream body');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const raw = line.slice(5).trim();
            if (!raw) continue;

            let ev: StreamEvent;
            try { ev = JSON.parse(raw); } catch { continue; }

            if (ev.type === 'stage') {
              setCurrentAgent(ev.stage ?? 'pipeline');
              setAgent(ev.stage ?? 'pipeline', { status: 'running', text: ev.message ?? '' });
              if (ev.stage !== 'pipeline') {
                streamRef.current = '';
                setStreamText('');
              }
            }

            if (ev.type === 'pipeline_done') {
              setAgent('pipeline', { status: 'done' });
            }

            if (ev.type === 'token' && ev.agent === 'business_advisor') {
              streamRef.current += ev.text ?? '';
              setStreamText(streamRef.current);
            }

            if (ev.type === 'agent_done') {
              setTotalAgents(p => p + 1);
              setAgent(ev.agent ?? '', { status: 'done', elapsed: ev.elapsed });
            }

            if (ev.type === 'done' && ev.result) {
              if (timerRef.current) clearInterval(timerRef.current);
              onDone(ev.result);
            }

            if (ev.type === 'error') {
              if (timerRef.current) clearInterval(timerRef.current);
              onError(ev.message ?? 'Unknown stream error');
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        if (timerRef.current) clearInterval(timerRef.current);
        const errMsg = err instanceof Error ? err.message : 'Stream failed';
        if (errMsg.includes('fetch') || errMsg.includes('Failed') || errMsg.includes('500')) {
          import('../../lib/demo').then(({ getDemoResult }) => { onDone(getDemoResult()); }).catch(() => onError(errMsg));
        } else { onError(errMsg); }
      }
    })();

    return () => {
      abortRef.current?.abort();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [formData, apiBase, onDone, onError, setAgent]);

  const doneCount = Object.values(agents).filter(a => a.status === 'done').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ position: 'relative', width: 56, height: 56 }}>
          <svg width="56" height="56" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r="24" stroke="var(--border)" strokeWidth="3" fill="none" />
            <circle cx="28" cy="28" r="24"
              stroke="var(--accent)" strokeWidth="3" fill="none"
              strokeDasharray={`${2 * Math.PI * 24 * doneCount / 4} ${2 * Math.PI * 24}`}
              strokeLinecap="round"
              transform="rotate(-90 28 28)"
              style={{ transition: 'stroke-dasharray 0.6s ease' }}
            />
            <text x="28" y="33" textAnchor="middle" style={{ fontSize: 14, fontWeight: 700, fill: 'var(--text-primary)' }}>
              {doneCount}/4
            </text>
          </svg>
        </div>
        <div>
          <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 18, fontWeight: 800, color: 'var(--text-primary)' }}>
            KiranaGPT Running
          </div>
          <div style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 500 }}>
            {AGENTS.find(a => a.key === currentAgent)?.label ?? 'Initialising'}&nbsp;
            <span style={{ color: 'var(--text-muted)' }}>— {elapsed}s</span>
          </div>
        </div>
      </div>

      {/* Agent progress list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {AGENTS.map((a) => {
          const state = agents[a.key];
          const isRunning = state.status === 'running';
          const isDone    = state.status === 'done';
          return (
            <div key={a.key} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 14px', borderRadius: 10,
              background: isRunning ? 'rgba(99,102,241,0.06)' : isDone ? 'var(--success-bg)' : 'var(--bg-elevated)',
              border: `1px solid ${isRunning ? 'rgba(99,102,241,0.2)' : isDone ? 'rgba(16,185,129,0.2)' : 'var(--border)'}`,
              transition: 'all 0.3s ease',
              opacity: state.status === 'waiting' ? 0.45 : 1,
            }}>
              {/* Status icon */}
              <div style={{
                width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                background: isDone ? 'var(--success)' : isRunning ? 'var(--accent)' : 'var(--bg-card)',
                border: `2px solid ${isDone ? 'var(--success)' : isRunning ? 'var(--accent)' : 'var(--border-bright)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
                animation: isRunning ? 'pulse-glow 1.5s infinite' : 'none',
              }}>
                {isDone
                  ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                  : isRunning
                    ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" style={{ animation: 'spin 0.8s linear infinite' }}><path d="M12 2a10 10 0 0 1 10 10"/></svg>
                    : <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>·</span>
                }
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 14 }}>{a.icon}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: isDone ? 'var(--success)' : isRunning ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                    {a.label}
                  </span>
                  {a.key !== 'pipeline' && <span style={{ fontSize: 10, padding: '1px 6px', background: 'rgba(99,102,241,0.08)', color: 'var(--accent)', borderRadius: 4, fontWeight: 600 }}>🤖 Gemini</span>}
                </div>
                {isRunning && state.text && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{state.text}</div>
                )}
              </div>
              {isDone && state.elapsed && (
                <span style={{ fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>{state.elapsed}s</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Live streaming text for Business Advisor */}
      {streamText && (
        <div style={{
          background: 'var(--bg-elevated)', border: '1px solid rgba(99,102,241,0.15)',
          borderRadius: 10, padding: 16,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', display: 'inline-block', animation: 'pulse-glow 1s infinite' }} />
            Business Advisor · Live output
          </div>
          <pre style={{ fontFamily: 'DM Sans, sans-serif', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, maxHeight: 200, overflowY: 'auto' }}>
            {streamText}
            <span style={{ display: 'inline-block', width: 8, height: 14, background: 'var(--accent)', marginLeft: 2, animation: 'blink 0.7s step-end infinite', verticalAlign: 'text-bottom' }} />
          </pre>
        </div>
      )}

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </div>
  );
}
