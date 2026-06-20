'use client';

import React from 'react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  componentName?: string;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: '' };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error.message };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[ErrorBoundary] ${this.props.componentName ?? 'Component'} crashed:`, error, info);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div style={{
          padding: '16px 20px',
          background: 'var(--danger-bg)',
          border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: 10,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0, marginTop: 1 }}>
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--danger)', marginBottom: 4 }}>
              {this.props.componentName ?? 'Component'} failed to render
            </div>
            <div style={{ fontSize: 12, color: 'var(--danger)', opacity: 0.8 }}>
              {this.state.errorMessage}
            </div>
            <button
              onClick={() => this.setState({ hasError: false, errorMessage: '' })}
              style={{
                marginTop: 10, padding: '5px 12px', fontSize: 11, fontWeight: 600,
                background: 'none', border: '1px solid rgba(239,68,68,0.4)',
                borderRadius: 6, color: 'var(--danger)', cursor: 'pointer',
              }}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
