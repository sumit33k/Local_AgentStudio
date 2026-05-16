'use client';

import { useEffect, useState, useCallback } from 'react';

type Decision = 'allowed' | 'denied' | 'unset';
type Duration = 'once' | 'session' | 'always';

interface Permission {
  id: string;
  name: string;
  description?: string;
  decision: Decision;
}

interface AuditEvent {
  id?: string;
  timestamp: string;
  event_type: string;
  details?: Record<string, any> | string;
}

interface Props {
  apiBase: string;
}

const DECISION_COLOR: Record<Decision, string> = {
  allowed: 'var(--green)',
  denied: 'var(--red)',
  unset: 'var(--text-muted)',
};

const DECISION_BG: Record<Decision, string> = {
  allowed: 'var(--green-bg)',
  denied: 'var(--red-bg)',
  unset: '#f8fafc',
};

const DECISION_BORDER: Record<Decision, string> = {
  allowed: 'var(--green-border)',
  denied: 'var(--red-border)',
  unset: 'var(--border)',
};

export default function SecurityCenter({ apiBase }: Props) {
  const [activeTab, setActiveTab] = useState<'permissions' | 'audit'>('permissions');
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [loadingPerms, setLoadingPerms] = useState(false);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selectedDuration, setSelectedDuration] = useState<Record<string, Duration>>({});

  const fetchPermissions = useCallback(async () => {
    setLoadingPerms(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/permissions`);
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const data = await res.json();
      setPermissions(Array.isArray(data) ? data : data.permissions ?? []);
    } catch (e: any) {
      setError(e.message ?? 'Failed to fetch permissions');
    } finally {
      setLoadingPerms(false);
    }
  }, [apiBase]);

  const fetchAuditEvents = useCallback(async () => {
    setLoadingAudit(true);
    try {
      const res = await fetch(`${apiBase}/audit/events?n=50`);
      if (!res.ok) return;
      const data = await res.json();
      setAuditEvents(Array.isArray(data) ? data : data.events ?? []);
    } catch {
      // non-critical
    } finally {
      setLoadingAudit(false);
    }
  }, [apiBase]);

  useEffect(() => {
    fetchPermissions();
    fetchAuditEvents();
  }, [fetchPermissions, fetchAuditEvents]);

  // Auto-refresh audit log every 30s
  useEffect(() => {
    const interval = setInterval(fetchAuditEvents, 30000);
    return () => clearInterval(interval);
  }, [fetchAuditEvents]);

  const getDuration = (permId: string): Duration =>
    selectedDuration[permId] ?? 'session';

  const setDuration = (permId: string, dur: Duration) =>
    setSelectedDuration((prev) => ({ ...prev, [permId]: dur }));

  const grantPermission = async (permId: string) => {
    const dur = getDuration(permId);
    setActionLoading(`grant-${permId}`);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/permissions/${encodeURIComponent(permId)}/grant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration: dur }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Grant failed');
      }
      await fetchPermissions();
    } catch (e: any) {
      setError(e.message ?? 'Failed to grant permission');
    } finally {
      setActionLoading(null);
    }
  };

  const denyPermission = async (permId: string) => {
    setActionLoading(`deny-${permId}`);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/permissions/${encodeURIComponent(permId)}/deny`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Deny failed');
      }
      await fetchPermissions();
    } catch (e: any) {
      setError(e.message ?? 'Failed to deny permission');
    } finally {
      setActionLoading(null);
    }
  };

  const formatDetails = (details?: Record<string, any> | string): string => {
    if (!details) return '';
    if (typeof details === 'string') return details;
    try {
      const entries = Object.entries(details).slice(0, 3);
      return entries.map(([k, v]) => `${k}: ${String(v)}`).join(' · ');
    } catch {
      return JSON.stringify(details).slice(0, 80);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 22 }}>🔐</span>
        <div>
          <h2 style={{ margin: 0, fontSize: 17 }}>Security Center</h2>
          <p className="muted small" style={{ margin: 0 }}>Permissions and audit log</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === 'permissions' ? 'active' : ''}`}
          onClick={() => setActiveTab('permissions')}
        >
          <span className="tab-icon">🔑</span> Permissions
        </button>
        <button
          className={`tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <span className="tab-icon">📋</span> Audit Log
        </button>
      </div>

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Permissions Tab */}
      {activeTab === 'permissions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="muted small">{permissions.length} permission(s) configured</span>
            <button
              className="icon-btn"
              onClick={fetchPermissions}
              disabled={loadingPerms}
              title="Refresh"
            >
              {loadingPerms ? <span className="spinner" /> : '↻'}
            </button>
          </div>

          {permissions.length === 0 && !loadingPerms && (
            <div className="kb-empty">
              <p className="muted">No permissions configured.</p>
            </div>
          )}

          {permissions.map((perm) => (
            <div
              key={perm.id}
              style={{
                border: `1px solid ${DECISION_BORDER[perm.decision]}`,
                borderRadius: 'var(--r-lg)',
                padding: '14px 16px',
                background: DECISION_BG[perm.decision],
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{perm.name}</div>
                  {perm.description && (
                    <p className="muted small" style={{ margin: '3px 0 0' }}>{perm.description}</p>
                  )}
                </div>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: 'var(--r-full)',
                    background: DECISION_COLOR[perm.decision],
                    color: '#fff',
                    textTransform: 'uppercase',
                    flexShrink: 0,
                  }}
                >
                  {perm.decision}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <select
                  value={getDuration(perm.id)}
                  onChange={(e) => setDuration(perm.id, e.target.value as Duration)}
                  style={{ width: 'auto', padding: '5px 10px', fontSize: 13 }}
                >
                  <option value="once">Once</option>
                  <option value="session">Session</option>
                  <option value="always">Always</option>
                </select>

                <button
                  className="secondary"
                  style={{ width: 'auto', padding: '6px 14px', fontSize: 12 }}
                  onClick={() => grantPermission(perm.id)}
                  disabled={!!actionLoading}
                >
                  {actionLoading === `grant-${perm.id}` ? <span className="spinner" /> : '✓ Grant'}
                </button>

                <button
                  className="secondary"
                  style={{
                    width: 'auto',
                    padding: '6px 14px',
                    fontSize: 12,
                    color: 'var(--red)',
                    borderColor: 'var(--red-border)',
                  }}
                  onClick={() => denyPermission(perm.id)}
                  disabled={!!actionLoading}
                >
                  {actionLoading === `deny-${perm.id}` ? <span className="spinner" /> : '✗ Deny'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Audit Log Tab */}
      {activeTab === 'audit' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="muted small">{auditEvents.length} event(s) · auto-refreshes every 30s</span>
            <button
              className="icon-btn"
              onClick={fetchAuditEvents}
              disabled={loadingAudit}
              title="Refresh"
            >
              {loadingAudit ? <span className="spinner" /> : '↻'}
            </button>
          </div>

          {auditEvents.length === 0 && !loadingAudit && (
            <div className="kb-empty">
              <p className="muted">No audit events recorded.</p>
            </div>
          )}

          {auditEvents.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)', whiteSpace: 'nowrap' }}>
                      Timestamp
                    </th>
                    <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)' }}>
                      Event Type
                    </th>
                    <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)' }}>
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {auditEvents.map((ev, i) => (
                    <tr
                      key={ev.id ?? i}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        background: i % 2 === 0 ? 'var(--surface)' : '#fafbfc',
                      }}
                    >
                      <td style={{ padding: '8px 10px', color: 'var(--text-muted)', whiteSpace: 'nowrap', fontSize: 12 }}>
                        {new Date(ev.timestamp).toLocaleString()}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span
                          style={{
                            background: 'var(--accent-light)',
                            color: 'var(--indigo)',
                            fontSize: 11,
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 'var(--r-full)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {ev.event_type}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--text-muted)', fontSize: 12, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {formatDetails(ev.details)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
