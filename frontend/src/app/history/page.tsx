'use client';

import { useEffect, useState } from 'react';
import { fetchHistory } from '../../lib/db';
import { HistoryTable } from '../../components/history/HistoryTable';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import type { HistoryRecord } from '../../types/underwriting';

export default function HistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<'supabase' | 'localStorage' | 'empty'>('empty');

  useEffect(() => {
    fetchHistory().then(rows => {
      setRecords(rows);
      if (rows.length > 0) {
        // Check if we fell back to localStorage
        const isFromLocal = typeof window !== 'undefined' &&
          localStorage.getItem('kirana_hackathon_history') !== null;
        setSource(isFromLocal ? 'localStorage' : 'supabase');
      } else {
        setSource('empty');
      }
      setLoading(false);
    });
  }, []);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '40px 16px 80px' }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.03em', marginBottom: 8 }}>
          Assessment History
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>
          All past KiranaGPT underwriting assessments
        </p>
      </div>

      {/* Data source indicator */}
      {!loading && (
        <div style={{
          marginBottom: 16, padding: '8px 14px',
          background: source === 'supabase' ? 'var(--success-bg)' : source === 'localStorage' ? 'var(--warning-bg)' : 'var(--bg-elevated)',
          border: `1px solid ${source === 'supabase' ? 'rgba(16,185,129,0.3)' : source === 'localStorage' ? 'var(--border-bright)' : 'var(--border)'}`,
          borderRadius: 8, fontSize: 12,
          color: source === 'supabase' ? 'var(--success)' : source === 'localStorage' ? 'var(--warning)' : 'var(--text-muted)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          {source === 'supabase' && '✅ Live data from Supabase'}
          {source === 'localStorage' && '⚠️ Showing local history (Supabase not configured — add keys to frontend/.env.local)'}
          {source === 'empty' && '📭 No assessments yet — run your first analysis on the home page'}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <LoadingSpinner size={32} />
        </div>
      ) : records.length > 0 ? (
        <HistoryTable records={records} />
      ) : (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>No assessments yet</div>
          <div style={{ fontSize: 13 }}>Run your first KiranaGPT analysis from the home page</div>
          <a href="/" style={{ display: 'inline-block', marginTop: 20, padding: '10px 24px', background: 'var(--accent)', color: '#fff', borderRadius: 8, fontSize: 13, fontWeight: 600, textDecoration: 'none' }}>
            Start Analysis →
          </a>
        </div>
      )}
    </div>
  );
}
