'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from './Sidebar';
import OpenClawPanel from './OpenClawPanel';
import SecurityCenter from './SecurityCenter';
import DiagnosticsPanel from './DiagnosticsPanel';
import SkillManager from './SkillManager';
import ToolActivityPanel from './ToolActivityPanel';
import AgentRunTimeline from './AgentRunTimeline';

type Panel = 'chat' | 'agents' | 'skills' | 'openclaw' | 'security' | 'diagnostics' | 'tools' | 'runs';

interface Props {
  apiBase: string;
}

const PANEL_LINKS: { id: Panel; label: string; icon: string; description: string }[] = [
  { id: 'chat',        icon: '💬', label: 'Chat',        description: 'Chat with your LLM using RAG and MCP tools' },
  { id: 'agents',      icon: '📋', label: 'Agents',      description: 'Create and manage AI agents' },
  { id: 'skills',      icon: '🧰', label: 'Skills',      description: 'Manage skill prompt templates' },
  { id: 'openclaw',    icon: '🦞', label: 'OpenClaw',    description: 'OpenClaw runtime gateway and sessions' },
  { id: 'security',    icon: '🔐', label: 'Security',    description: 'Permissions and audit log' },
  { id: 'diagnostics', icon: '🩺', label: 'Diagnostics', description: 'System health and diagnostics' },
  { id: 'tools',       icon: '🔧', label: 'Tools',       description: 'MCP tool activity and monitoring' },
  { id: 'runs',        icon: '📊', label: 'Runs',        description: 'Agent run history and downloads' },
];

export default function AppShell({ apiBase }: Props) {
  const [activePanel, setActivePanel] = useState<Panel>('openclaw');
  const [openClawRunning, setOpenClawRunning] = useState(false);

  const pollOpenClawStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/openclaw/status`);
      if (!res.ok) return;
      const data = await res.json();
      setOpenClawRunning(!!data.running);
    } catch {
      // Silently fail — UI still works without it
    }
  }, [apiBase]);

  useEffect(() => {
    pollOpenClawStatus();
    const interval = setInterval(pollOpenClawStatus, 15000);
    return () => clearInterval(interval);
  }, [pollOpenClawStatus]);

  const renderPanel = () => {
    switch (activePanel) {
      case 'openclaw':
        return <OpenClawPanel apiBase={apiBase} />;
      case 'security':
        return <SecurityCenter apiBase={apiBase} />;
      case 'diagnostics':
        return <DiagnosticsPanel apiBase={apiBase} />;
      case 'skills':
        return <SkillManager apiBase={apiBase} />;
      case 'tools':
        return <ToolActivityPanel apiBase={apiBase} />;
      case 'runs':
        return <AgentRunTimeline apiBase={apiBase} />;
      default:
        return <WelcomePanel onNavigate={setActivePanel} openClawRunning={openClawRunning} />;
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        minHeight: '100vh',
        background: 'var(--bg)',
      }}
    >
      {/* Sidebar: fixed 220px */}
      <Sidebar
        activePanel={activePanel}
        onPanelChange={(p) => setActivePanel(p as Panel)}
        openClawRunning={openClawRunning}
      />

      {/* Main content area */}
      <main
        style={{
          flex: 1,
          minWidth: 0,
          padding: '28px 28px 40px',
          overflowY: 'auto',
        }}
      >
        {renderPanel()}
      </main>
    </div>
  );
}

/* ── Welcome / dashboard panel ────────────────────────────────────────── */
interface WelcomePanelProps {
  onNavigate: (panel: Panel) => void;
  openClawRunning: boolean;
}

function WelcomePanel({ onNavigate, openClawRunning }: WelcomePanelProps) {
  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      {/* Hero */}
      <div className="hero" style={{ marginBottom: 32 }}>
        <div>
          <div className="hero-badge">Local AgentStudio Pro</div>
          <h1>Welcome back 👋</h1>
          <p className="muted">
            Your local-first AI agent platform. Select a panel from the sidebar or jump to a section below.
          </p>
        </div>
        <div
          className={`status ${openClawRunning ? 'ok' : 'bad'}`}
          style={{ flexShrink: 0 }}
        >
          <span className="status-dot" />
          OpenClaw {openClawRunning ? 'Running' : 'Stopped'}
        </div>
      </div>

      {/* Panel grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 14,
        }}
      >
        {PANEL_LINKS.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            style={{
              textAlign: 'left',
              background: 'var(--surface)',
              border: '1.5px solid var(--border)',
              borderRadius: 'var(--r-lg)',
              padding: '18px 16px',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              transition: 'border-color 150ms ease, box-shadow 150ms ease, background 150ms ease',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = 'var(--indigo)';
              el.style.background = 'var(--indigo-light)';
              el.style.boxShadow = 'var(--shadow-sm)';
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement;
              el.style.borderColor = 'var(--border)';
              el.style.background = 'var(--surface)';
              el.style.boxShadow = 'none';
            }}
          >
            <span style={{ fontSize: 26, lineHeight: 1 }}>{item.icon}</span>
            <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{item.label}</span>
            <span
              className="muted"
              style={{ fontSize: 12, lineHeight: 1.4, fontWeight: 400 }}
            >
              {item.description}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
