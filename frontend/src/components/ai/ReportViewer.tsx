'use client';

import { useRef } from 'react';

interface Props {
  markdown: string;
  storeId?: string;
}

// Simple markdown → HTML converter (no external lib needed)
function mdToHtml(md: string): string {
  return md
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^---$/gm, '<hr/>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[h|u|l|h|p|c])(.+)$/gm, '<p>$1</p>');
}

const PRINT_STYLES = `
  body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 12px; color: #0f172a; line-height: 1.6; padding: 32px; max-width: 800px; margin: 0 auto; }
  h1 { font-size: 22px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
  h2 { font-size: 16px; font-weight: 700; color: #1e293b; margin-top: 20px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
  h3 { font-size: 13px; font-weight: 600; color: #334155; margin-top: 14px; }
  p  { margin: 8px 0; }
  ul { margin: 6px 0 6px 18px; }
  li { margin-bottom: 3px; }
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 16px 0; }
  strong { color: #0f172a; }
  code { font-family: monospace; background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 11px; }
  em { color: #475569; }
  @page { margin: 24mm; }
  @media print { body { padding: 0; } }
`;

export function ReportViewer({ markdown, storeId }: Props) {
  const previewRef = useRef<HTMLDivElement>(null);

  const downloadMarkdown = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `KiranaGPT_Report_${storeId ?? Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const printAsPdf = () => {
    const html = mdToHtml(markdown);
    const win = window.open('', '_blank');
    if (!win) { alert('Please allow popups to generate PDF'); return; }
    win.document.write(`
      <!DOCTYPE html><html><head>
        <meta charset="utf-8">
        <title>KiranaGPT Report</title>
        <style>${PRINT_STYLES}</style>
      </head><body>
        ${html}
        <script>window.onload=()=>{window.print();window.close();}<\/script>
      </body></html>
    `);
    win.document.close();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 10 }}>
        <button
          onClick={downloadMarkdown}
          style={{ padding: '7px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          ⬇ Download .md
        </button>
        <button
          onClick={printAsPdf}
          style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', borderRadius: 8, fontSize: 12, color: '#fff', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
        >
          🖨 Download PDF
        </button>
      </div>
      <div
        ref={previewRef}
        style={{ padding: 20, background: 'var(--bg-elevated)', borderRadius: 10, border: '1px solid var(--border)', fontFamily: 'monospace', fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 560, overflowY: 'auto' }}
      >
        {markdown}
      </div>
    </div>
  );
}
