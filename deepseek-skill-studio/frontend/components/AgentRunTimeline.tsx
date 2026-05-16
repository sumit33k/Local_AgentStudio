'use client';

import { useEffect, useState, useCallback } from 'react';

interface AgentRun {
  id?: string;
  timestamp?: string;
  created_at?: string;
  agent_id?: string;
  agent_name?: string;
  skill?: string;
  output_type?: string;
  output_file?: string;
  status?: string;
  duration_ms?: number;
}

interface Props {
  apiBase: string;
}

const OUTPUT_TYPE_ICON: Record<string, string> = {
  docx: '📄',
  pptx: '📊',
  md: '📝',
  pdf: '📋',
  txt: '📃',
};

export default function AgentRunTimeline({ apiBase }: Props) {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/agent/runs`);
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const data = await res.json();
      const list: AgentRun[] = Array.isArray(data) ? data : data.runs ?? [];
      // Sort newest first
      list.sort((a, b) => {
        const ta = new Date(a.timestamp ?? a.created_at ?? 0).getTime();
        const tb = new Date(b.timestamp ?? b.created_at ?? 0).getTime();
        return tb - ta;
      });
      setRuns(list);
      setLastUpdated(new Date());
    } catch (e: any) {
      setError(e.message ?? 'Failed to fetch agent runs');
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 30000);
    return () => clearInterval(interval);
  }, [fetchRuns]);

  const getTimestamp = (run: AgentRun): string => {
    const raw = run.timestamp ?? run.created_at;
    if (!raw) return '—';
    try {
      return new Date(raw).toLocaleString();
    } catch {
      return raw;
    }
  };

  const getOutputIcon = (run: AgentRun): string => {
    if (!run.output_type) return '📄';
    return OUTPUT_TYPE_ICON[run.output_type.toLowerCase()] ?? '📄';
  };

  const getDownloadUrl = (run: AgentRun): string | null => {
    if (!run.output_file) return null;
    return `${apiBase}/download/${encodeURIComponent(run.output_file)}`;
  };

  const getStatusBadge = (status?: string) => {
    if (!status) return null;
    const isOk = status === 'success' || status === 'completed' || status === 'done';
    return (
      <span
        className={`status ${isOk ? 'ok' : 'bad'}`}
        style={{ padding: '2px 10px', fontSize: 11 }}
      >
        <span className="status-dot" />
        {status}
      </span>
    );
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>📊</span>
          <div>
            <h2 style={{ margin: 0, fontSize: 17 }}>Agent Run Timeline</h2>
            {lastUpdated && (
              <p className="muted small" style={{ margin: 0 }}>
                {runs.length} run(s) · refreshes every 30s
              </p>
            )}
          </div>
        </div>
        <button
          className="icon-btn"
          onClick={fetchRuns}
          disabled={loading}
          title="Refresh"
        >
          {loading ? <span className="spinner" /> : '↻'}
        </button>
      </div>

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Loading */}
      {loading && runs.length === 0 && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
          <span className="spinner" style={{ margin: '0 auto 12px', display: 'block', width: 24, height: 24 }} />
          Loading runs...
        </div>
      )}

      {/* Empty */}
      {!loading && runs.length === 0 && !error && (
        <div className="kb-empty">
          <div style={{ fontSize: 34, marginBottom: 12 }}>📊</div>
          <p className="muted">No agent runs yet. Run an agent to see history here.</p>
        </div>
      )}

      {/* Timeline */}
      {runs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, position: 'relative' }}>
          {/* Vertical timeline line */}
          <div
            style={{
              position: 'absolute',
              left: 16,
              top: 20,
              bottom: 20,
              width: 2,
              background: 'var(--border)',
              zIndex: 0,
            }}
          />

          {runs.map((run, i) => {
            const downloadUrl = getDownloadUrl(run);
            return (
              <div
                key={run.id ?? i}
                style={{
                  display: 'flex',
                  gap: 16,
                  paddingBottom: i < runs.length - 1 ? 20 : 0,
                  position: 'relative',
                  zIndex: 1,
                }}
              >
                {/* Timeline dot */}
                <div
                  style={{
                    width: 34,
                    flexShrink: 0,
                    display: 'flex',
                    justifyContent: 'center',
                    paddingTop: 12,
                  }}
                >
                  <div
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: '50%',
                      background: run.status === 'error' ? 'var(--red-bg)' : 'var(--indigo-light)',
                      border: `2.5px solid ${run.status === 'error' ? 'var(--red)' : 'var(--indigo)'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 9,
                    }}
                  >
                    {getOutputIcon(run)}
                  </div>
                </div>

                {/* Run card */}
                <div
                  className="run"
                  style={{
                    flex: 1,
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--r-md)',
                    padding: '10px 14px',
                    background: 'var(--surface)',
                    borderTop: '1px solid var(--border)',
                  }}
                >
                  <div className="run-top">
                    <strong>{run.agent_name ?? run.agent_id ?? 'Unknown Agent'}</strong>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      {run.output_type && (
                        <span className="run-type">{run.output_type.toUpperCase()}</span>
                      )}
                      {getStatusBadge(run.status)}
                    </div>
                  </div>

                  {run.skill && (
                    <div className="run-model">Skill: {run.skill}</div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                    <small>{getTimestamp(run)}</small>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                      {run.duration_ms && (
                        <small style={{ color: 'var(--text-muted)' }}>
                          {(run.duration_ms / 1000).toFixed(1)}s
                        </small>
                      )}
                      {downloadUrl && (
                        <a
                          href={downloadUrl}
                          className="run-download"
                          target="_blank"
                          rel="noreferrer"
                          download
                        >
                          ⬇ Download
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
