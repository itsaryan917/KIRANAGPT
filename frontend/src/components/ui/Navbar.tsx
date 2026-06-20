'use client';

import { usePathname } from 'next/navigation';

export function Navbar() {
  const pathname = usePathname();

  return (
    <nav
      style={{
        background: 'rgba(12, 14, 23, 0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div
        style={{
          maxWidth: 1280,
          margin: '0 auto',
          padding: '0 24px',
          height: 60,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 34,
              height: 34,
              background: '#f59e0b',
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'Syne, sans-serif',
              fontWeight: 800,
              fontSize: 16,
              color: '#0a0f1e',
            }}
          >
            ₹
          </div>
          <div>
            <div
              style={{
                fontFamily: 'Syne, sans-serif',
                fontWeight: 700,
                fontSize: 17,
                color: 'var(--text-primary)',
                letterSpacing: '-0.03em',
              }}
            >
              KiraNA
            </div>
            <div
              style={{
                fontSize: 10,
                color: 'var(--text-muted)',
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                fontWeight: 500,
              }}
            >
              Underwriting Intelligence
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <a
            href="/"
            className={`nav-link${pathname === '/' ? ' active' : ''}`}
          >
            New Assessment
          </a>
          <a
            href="/history"
            className={`nav-link${pathname === '/history' ? ' active' : ''}`}
          >
            History
          </a>
          <div
            style={{
              padding: '5px 14px',
              background: 'var(--review-bg)',
              border: '1px solid rgba(99, 102, 241, 0.15)',
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--accent-dim)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              marginLeft: 8,
            }}
          >
            NBFC Officer
          </div>
        </div>
      </div>
    </nav>
  );
}
