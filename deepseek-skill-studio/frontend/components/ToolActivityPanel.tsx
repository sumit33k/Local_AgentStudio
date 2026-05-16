'use client';

import { useEffect, useState, useCallback } from 'react';

interface McpTool {
  name: string;
  description?: string;
  server_id?: string;
  server_name?: string;
  input_schema?: Record<string, any>;
}

interface ToolCallEvent {
  id?: string;
  timestamp: string;
  event_type: string;
  details?: Record<string, any> | string;
}

interface Props {
  apiBase: string;
}

export default function ToolActivityPanel({ apiBase }: Props) {
  const [tools, setTools] = useState<McpTool[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCallEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTools = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/mcp/tools`);
      if (!res.ok) return;
      const data = await res.json();
      setTools(Array.isArray(data) ? data : data.tools ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const fetchToolCalls = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/audit/events?event_type=tool_call&n=20`);
      if (!res.ok) return;
      const data = await res.json();
      setToolCalls(Array.isArray(data) ? data : data.events ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([fetchTools(), fetchToolCalls()]);
    } catch (e: any) {
      setError(e.message ?? 'Failed to load tool data');
    } finally {
      setLoading(false);
    }
  }, [fetchTools, fetchToolCalls]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Group tools by server
  const toolsByServer = tools.reduce<Record<string, McpTool[]>>((acc, tool) => {
    const server = tool.server_name ?? tool.server_id ?? 'Unknown Server';
    if (!acc[server]) acc[server] = [];
    acc[server].push(tool);
    return acc;
  }, {});

  const formatDetails = (details?: Record<string, any> | string): string => {
    if (!details) return '';
    if (typeof details === 'string') return details.slice(0, 120);
    try {
      const entries = Object.entries(details).slice(0, 4);
      return entries.map(([k, v]) => `${k}: ${String(v)}`).join(' · ');
    } catch {
      return JSON.stringify(details).slice(0, 120);
    }
  };

  const getToolName = (ev: ToolCallEvent): string => {
    if (!ev.details) return '—';
    if (typeof ev.details === 'string') return ev.details.split(' ')[0] ?? '—';
    return (ev.details as any).tool ?? (ev.details as any).tool_name ?? '—';
  };

  const getToolServer = (ev: ToolCallEvent): string => {
    if (!ev.details || typeof ev.details === 'string') return '—';
    return (ev.details as any).server ?? (ev.details as any).server_id ?? '—';
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🔧</span>
          <div>
            <h2 style={{ margin: 0, fontSize: 17 }}>Tool Activity</h2>
            <p className="muted small" style={{ margin: 0 }}>
              {tools.length} tool(s) across {Object.keys(toolsByServer).length} server(s)
            </p>
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

      {error && <div className="error">{error}</div>}

      {/* Available MCP Tools */}
      <div>
        <div className="settings-label" style={{ marginBottom: 12 }}>Available MCP Tools</div>

        {tools.length === 0 && !loading && (
          <div className="kb-empty">
            <p className="muted">No MCP tools found. Add MCP servers in the Connectors tab.</p>
          </div>
        )}

        {Object.entries(toolsByServer).map(([server, serverTools]) => (
          <div key={server} style={{ marginBottom: 16 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 8,
                padding: '6px 10px',
                background: 'var(--accent-light)',
                borderRadius: 'var(--r-sm)',
              }}
            >
              <span style={{ fontSize: 14 }}>🖥</span>
              <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--accent)' }}>{server}</span>
              <span
                style={{
                  marginLeft: 'auto',
                  fontSize: 11,
                  fontWeight: 700,
                  color: 'var(--indigo)',
                  background: '#fff',
                  padding: '1px 8px',
                  borderRadius: 'var(--r-full)',
                }}
              >
                {serverTools.length} tool{serverTools.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="mcp-tools-grid">
              {serverTools.map((tool, i) => (
                <div key={tool.name ?? i} className="mcp-tool-card">
                  <strong>{tool.name}</strong>
                  {tool.description && (
                    <span className="muted" style={{ fontSize: 11, lineHeight: 1.4 }}>
                      {tool.description.length > 80
                        ? tool.description.slice(0, 80) + '…'
                        : tool.description}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Recent Tool Calls */}
      <div>
        <div className="settings-label" style={{ marginBottom: 12 }}>
          Recent Tool Calls ({toolCalls.length})
        </div>

        {toolCalls.length === 0 ? (
          <div className="kb-empty">
            <p className="muted">No tool calls recorded yet.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)', whiteSpace: 'nowrap' }}>
                    Time
                  </th>
                  <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)' }}>
                    Tool
                  </th>
                  <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)' }}>
                    Server
                  </th>
                  <th style={{ textAlign: 'left', padding: '8px 10px', fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-label)' }}>
                    Details
                  </th>
                </tr>
              </thead>
              <tbody>
                {toolCalls.map((ev, i) => (
                  <tr
                    key={ev.id ?? i}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: i % 2 === 0 ? 'var(--surface)' : '#fafbfc',
                    }}
                  >
                    <td style={{ padding: '8px 10px', color: 'var(--text-muted)', whiteSpace: 'nowrap', fontSize: 12 }}>
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </td>
                    <td style={{ padding: '8px 10px' }}>
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: 12,
                          background: '#f1f5f9',
                          padding: '2px 8px',
                          borderRadius: 'var(--r-sm)',
                          fontFamily: '"Fira Code", Consolas, monospace',
                        }}
                      >
                        {getToolName(ev)}
                      </span>
                    </td>
                    <td style={{ padding: '8px 10px', fontSize: 12, color: 'var(--text-muted)' }}>
                      {getToolServer(ev)}
                    </td>
                    <td style={{ padding: '8px 10px', fontSize: 12, color: 'var(--text-muted)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {formatDetails(ev.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
