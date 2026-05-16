'use client';

import { useEffect, useState, useCallback } from 'react';

interface OpenClawStatus {
  installed: boolean;
  running: boolean;
  pid: number | null;
  gateway_url: string | null;
  port: number | null;
  last_started_at: string | null;
  last_error: string | null;
  log_tail: string[];
  dependency_status: string;
}

interface OpenClawSkill {
  name: string;
  description?: string;
  source?: string;
}

interface OpenClawSession {
  id: string;
  started_at?: string;
  status?: string;
  agent?: string;
}

interface Props {
  apiBase: string;
}

export default function OpenClawPanel({ apiBase }: Props) {
  const [status, setStatus] = useState<OpenClawStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [sessions, setSessions] = useState<OpenClawSession[]>([]);
  const [skills, setSkills] = useState<OpenClawSkill[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importMsg, setImportMsg] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/openclaw/status`);
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const data = await res.json();
      setStatus(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? 'Failed to fetch OpenClaw status');
    }
  }, [apiBase]);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/openclaw/logs`);
      if (!res.ok) return;
      const data = await res.json();
      setLogs(Array.isArray(data) ? data : data.logs ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/openclaw/sessions`);
      if (!res.ok) return;
      const data = await res.json();
      setSessions(Array.isArray(data) ? data : data.sessions ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const fetchSkills = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/openclaw/skills`);
      if (!res.ok) return;
      const data = await res.json();
      setSkills(Array.isArray(data) ? data : data.skills ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await fetchStatus();
    await fetchLogs();
    await fetchSessions();
    await fetchSkills();
    setLoading(false);
  }, [fetchStatus, fetchLogs, fetchSessions, fetchSkills]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 10000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const runAction = async (action: 'start' | 'stop' | 'restart') => {
    setActionLoading(action);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/openclaw/${action}`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Action "${action}" failed`);
      }
      await refreshAll();
    } catch (e: any) {
      setError(e.message ?? `Failed to ${action} OpenClaw`);
    } finally {
      setActionLoading(null);
    }
  };

  const importAllSkills = async () => {
    setActionLoading('import');
    setImportMsg(null);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/openclaw/import-skills`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Import failed');
      }
      const data = await res.json();
      setImportMsg(data.message ?? `Imported ${skills.length} skill(s)`);
    } catch (e: any) {
      setError(e.message ?? 'Failed to import skills');
    } finally {
      setActionLoading(null);
    }
  };

  const logLines = logs.length > 0 ? logs : (status?.log_tail ?? []);
  const displayLogs = logLines.slice(-20);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🦞</span>
          <div>
            <h2 style={{ margin: 0, fontSize: 17 }}>OpenClaw Runtime</h2>
            <p className="muted small" style={{ margin: 0 }}>Agent gateway and session manager</p>
          </div>
        </div>
        <button
          className="icon-btn"
          onClick={refreshAll}
          disabled={loading}
          title="Refresh"
        >
          {loading ? <span className="spinner" /> : '↻'}
        </button>
      </div>

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Status badges */}
      {status && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          <span className={`status ${status.installed ? 'ok' : 'bad'}`}>
            <span className="status-dot" />
            {status.installed ? 'Installed' : 'Not Installed'}
          </span>
          <span className={`status ${status.running ? 'ok' : 'bad'}`}>
            <span className="status-dot" />
            {status.running ? 'Running' : 'Stopped'}
          </span>
          {status.pid && (
            <span className="status ok">
              <span className="status-dot" />
              PID {status.pid}
            </span>
          )}
        </div>
      )}

      {/* Info grid */}
      {status && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          {status.gateway_url && (
            <div className="builder">
              <label>Gateway URL</label>
              <p className="muted small" style={{ margin: '4px 0 0' }}>
                <a href={status.gateway_url} target="_blank" rel="noreferrer" style={{ color: 'var(--indigo)' }}>
                  {status.gateway_url}
                </a>
              </p>
            </div>
          )}
          {status.port && (
            <div className="builder">
              <label>Port</label>
              <p className="muted small" style={{ margin: '4px 0 0' }}>{status.port}</p>
            </div>
          )}
          {status.dependency_status && (
            <div className="builder" style={{ gridColumn: '1 / -1' }}>
              <label>Dependency Status</label>
              <p className="muted small" style={{ margin: '4px 0 0' }}>{status.dependency_status}</p>
            </div>
          )}
          {status.last_started_at && (
            <div className="builder">
              <label>Last Started</label>
              <p className="muted small" style={{ margin: '4px 0 0' }}>
                {new Date(status.last_started_at).toLocaleString()}
              </p>
            </div>
          )}
          {status.last_error && (
            <div className="builder" style={{ gridColumn: '1 / -1' }}>
              <label>Last Error</label>
              <p style={{ margin: '4px 0 0', color: 'var(--red)', fontSize: 13 }}>{status.last_error}</p>
            </div>
          )}
        </div>
      )}

      {/* Controls */}
      <div style={{ display: 'flex', gap: 10 }}>
        <button
          className="secondary"
          style={{ width: 'auto', padding: '9px 18px' }}
          onClick={() => runAction('start')}
          disabled={!!actionLoading || status?.running === true}
        >
          {actionLoading === 'start' ? <span className="spinner" /> : '▶ Start'}
        </button>
        <button
          className="secondary"
          style={{ width: 'auto', padding: '9px 18px' }}
          onClick={() => runAction('stop')}
          disabled={!!actionLoading || status?.running === false}
        >
          {actionLoading === 'stop' ? <span className="spinner" /> : '■ Stop'}
        </button>
        <button
          className="secondary"
          style={{ width: 'auto', padding: '9px 18px' }}
          onClick={() => runAction('restart')}
          disabled={!!actionLoading}
        >
          {actionLoading === 'restart' ? <span className="spinner" /> : '↺ Restart'}
        </button>
      </div>

      {/* Log tail */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <label>Log Tail</label>
          <span className="muted small">{displayLogs.length} lines</span>
        </div>
        <div
          className="preview"
          style={{ maxHeight: 220, overflowY: 'auto', fontSize: 12, lineHeight: 1.5 }}
        >
          {displayLogs.length === 0
            ? <span style={{ color: '#64748b' }}>No logs available.</span>
            : displayLogs.map((line, i) => (
                <div key={i}>{line}</div>
              ))
          }
        </div>
      </div>

      {/* Sessions */}
      {sessions.length > 0 && (
        <div>
          <label style={{ display: 'block', marginBottom: 8 }}>Active Sessions ({sessions.length})</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sessions.map((s) => (
              <div key={s.id} className="kb-doc-item">
                <div className="kb-doc-info">
                  <span style={{ fontSize: 14 }}>🖥</span>
                  <span className="kb-doc-name">{s.id}</span>
                  {s.agent && <span className="muted small">Agent: {s.agent}</span>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {s.status && (
                    <span className={`status ${s.status === 'active' ? 'ok' : 'bad'}`} style={{ padding: '3px 10px', fontSize: 11 }}>
                      <span className="status-dot" />
                      {s.status}
                    </span>
                  )}
                  {s.started_at && (
                    <span className="muted small">{new Date(s.started_at).toLocaleTimeString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills from OpenClaw */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <label>OpenClaw Skills ({skills.length})</label>
          <button
            className="secondary"
            style={{ width: 'auto', padding: '6px 14px', fontSize: 12 }}
            onClick={importAllSkills}
            disabled={!!actionLoading || skills.length === 0}
          >
            {actionLoading === 'import' ? <span className="spinner" /> : '⬇ Import All'}
          </button>
        </div>
        {importMsg && (
          <div style={{ color: 'var(--green)', background: 'var(--green-bg)', border: '1px solid var(--green-border)', padding: '8px 14px', borderRadius: 'var(--r-md)', fontSize: 13, marginBottom: 8 }}>
            {importMsg}
          </div>
        )}
        {skills.length === 0 ? (
          <p className="muted small">No OpenClaw skills found.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {skills.map((sk, i) => (
              <div key={sk.name ?? i} className="kb-doc-item">
                <div className="kb-doc-info">
                  <span style={{ fontSize: 14 }}>🧰</span>
                  <span className="kb-doc-name">{sk.name}</span>
                  {sk.description && <span className="muted small">{sk.description}</span>}
                </div>
                {sk.source && <span className="muted small">{sk.source}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
