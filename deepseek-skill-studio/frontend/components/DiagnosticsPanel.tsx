'use client';

import { useEffect, useState, useCallback } from 'react';

interface DiagnosticItem {
  name: string;
  status: 'ok' | 'error' | 'warning' | 'unknown';
  message?: string;
  category?: string;
  suggested_fixes?: string[];
}

interface DiagnosticsData {
  items?: DiagnosticItem[];
  [key: string]: any;
}

const CATEGORY_ORDER = [
  'Backend',
  'Node.js',
  'Ollama',
  'Claude/OpenAI',
  'ChromaDB',
  'MCP',
  'Skills',
  'OpenClaw Vendor',
  'OpenClaw Runtime',
];

const STATUS_ICON: Record<string, string> = {
  ok: '✓',
  error: '✗',
  warning: '⚠',
  unknown: '?',
};

const STATUS_COLOR: Record<string, string> = {
  ok: 'var(--green)',
  error: 'var(--red)',
  warning: '#b45309',
  unknown: 'var(--text-muted)',
};

const STATUS_BG: Record<string, string> = {
  ok: 'var(--green-bg)',
  error: 'var(--red-bg)',
  warning: '#fffbeb',
  unknown: '#f8fafc',
};

function inferCategory(key: string): string {
  const lk = key.toLowerCase();
  if (lk.includes('ollama')) return 'Ollama';
  if (lk.includes('claude') || lk.includes('openai')) return 'Claude/OpenAI';
  if (lk.includes('chroma') || lk.includes('vector')) return 'ChromaDB';
  if (lk.includes('mcp')) return 'MCP';
  if (lk.includes('skill')) return 'Skills';
  if (lk.includes('openclaw') && lk.includes('vendor')) return 'OpenClaw Vendor';
  if (lk.includes('openclaw')) return 'OpenClaw Runtime';
  if (lk.includes('node')) return 'Node.js';
  if (lk.includes('backend') || lk.includes('api')) return 'Backend';
  return 'Backend';
}

function normalizeObject(raw: Record<string, any>): DiagnosticItem[] {
  return Object.entries(raw)
    .filter(([, v]) => v && typeof v === 'object' && 'status' in v)
    .map(([key, v]) => ({
      name: key,
      status: v.status ?? 'unknown',
      message: v.message ?? v.detail ?? undefined,
      category: v.category ?? inferCategory(key),
      suggested_fixes: Array.isArray(v.suggested_fixes) ? v.suggested_fixes : undefined,
    }));
}

interface Props {
  apiBase: string;
}

export default function DiagnosticsPanel({ apiBase }: Props) {
  const [data, setData] = useState<DiagnosticItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchDiagnostics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/diagnostics`);
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const raw: DiagnosticsData = await res.json();
      // Support both array response and {items: [...]} shape
      const items: DiagnosticItem[] = Array.isArray(raw) ? raw : (raw.items ?? normalizeObject(raw));
      setData(items);
      setLastUpdated(new Date());
    } catch (e: any) {
      setError(e.message ?? 'Failed to fetch diagnostics');
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchDiagnostics();
  }, [fetchDiagnostics]);

  // Group items by category
  const grouped = CATEGORY_ORDER.reduce<Record<string, DiagnosticItem[]>>((acc, cat) => {
    const items = data.filter((d) => (d.category ?? inferCategory(d.name)) === cat);
    if (items.length > 0) acc[cat] = items;
    return acc;
  }, {});

  // Catch items that don't fit a known category
  const knownCategories = new Set(CATEGORY_ORDER);
  const uncategorized = data.filter((d) => !knownCategories.has(d.category ?? inferCategory(d.name)));
  if (uncategorized.length > 0) {
    grouped['Other'] = uncategorized;
  }

  const totalOk = data.filter((d) => d.status === 'ok').length;
  const totalErr = data.filter((d) => d.status === 'error').length;
  const totalWarn = data.filter((d) => d.status === 'warning').length;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🩺</span>
          <div>
            <h2 style={{ margin: 0, fontSize: 17 }}>System Diagnostics</h2>
            {lastUpdated && (
              <p className="muted small" style={{ margin: 0 }}>
                Last checked {lastUpdated.toLocaleTimeString()}
              </p>
            )}
          </div>
        </div>
        <button
          className="icon-btn"
          onClick={fetchDiagnostics}
          disabled={loading}
          title="Refresh diagnostics"
        >
          {loading ? <span className="spinner" /> : '↻'}
        </button>
      </div>

      {/* Summary bar */}
      {data.length > 0 && (
        <div style={{ display: 'flex', gap: 10 }}>
          <span className="status ok" style={{ gap: 5 }}>
            <span className="status-dot" />
            {totalOk} OK
          </span>
          {totalErr > 0 && (
            <span className="status bad" style={{ gap: 5 }}>
              <span className="status-dot" />
              {totalErr} Error{totalErr !== 1 ? 's' : ''}
            </span>
          )}
          {totalWarn > 0 && (
            <span
              className="status"
              style={{
                background: '#fffbeb',
                color: '#b45309',
                border: '1px solid #fde68a',
                gap: 5,
              }}
            >
              <span className="status-dot" style={{ background: '#f59e0b' }} />
              {totalWarn} Warning{totalWarn !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      )}

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Loading state */}
      {loading && data.length === 0 && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
          <span className="spinner" style={{ margin: '0 auto 12px', display: 'block', width: 24, height: 24 }} />
          Running diagnostics...
        </div>
      )}

      {/* Grouped items */}
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category}>
          <div className="settings-label" style={{ marginBottom: 8 }}>{category}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map((item, i) => (
              <div
                key={item.name ?? i}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  padding: '10px 14px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--r-md)',
                  background: STATUS_BG[item.status] ?? '#f8fafc',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span
                    style={{
                      fontWeight: 700,
                      fontSize: 15,
                      color: STATUS_COLOR[item.status] ?? 'var(--text-muted)',
                      lineHeight: 1,
                    }}
                  >
                    {STATUS_ICON[item.status] ?? '?'}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{item.name}</span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 'var(--r-full)',
                      background: STATUS_COLOR[item.status] ?? 'var(--text-muted)',
                      color: '#fff',
                      textTransform: 'uppercase',
                    }}
                  >
                    {item.status}
                  </span>
                </div>
                {item.message && (
                  <p className="muted small" style={{ margin: 0, paddingLeft: 25 }}>{item.message}</p>
                )}
                {item.suggested_fixes && item.suggested_fixes.length > 0 && (
                  <div style={{ paddingLeft: 25 }}>
                    <p className="small" style={{ margin: '0 0 4px', fontWeight: 600, color: '#b45309' }}>
                      Suggested fixes:
                    </p>
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {item.suggested_fixes.map((fix, j) => (
                        <li key={j} className="small" style={{ color: 'var(--text-muted)', marginBottom: 2 }}>
                          {fix}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {!loading && data.length === 0 && !error && (
        <div className="kb-empty">
          <p className="muted">No diagnostic data available. Try refreshing.</p>
        </div>
      )}
    </div>
  );
}
