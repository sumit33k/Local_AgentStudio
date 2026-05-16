'use client';

type Panel = 'chat' | 'agents' | 'skills' | 'openclaw' | 'security' | 'diagnostics' | 'tools' | 'runs';

interface NavItem {
  id: Panel;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat',        label: 'Chat',        icon: '💬' },
  { id: 'agents',      label: 'Agents',      icon: '📋' },
  { id: 'skills',      label: 'Skills',      icon: '🧰' },
  { id: 'openclaw',    label: 'OpenClaw',    icon: '🦞' },
  { id: 'security',    label: 'Security',    icon: '🔐' },
  { id: 'diagnostics', label: 'Diagnostics', icon: '🩺' },
  { id: 'tools',       label: 'Tools',       icon: '🔧' },
  { id: 'runs',        label: 'Runs',        icon: '📊' },
];

interface Props {
  activePanel: string;
  onPanelChange: (panel: string) => void;
  openClawRunning: boolean;
}

export default function Sidebar({ activePanel, onPanelChange, openClawRunning }: Props) {
  return (
    <nav
      style={{
        width: 220,
        flexShrink: 0,
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
        height: '100vh',
        position: 'sticky',
        top: 0,
        display: 'flex',
        flexDirection: 'column',
        padding: '0 0 16px',
        overflowY: 'auto',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '20px 16px 16px',
          borderBottom: '1px solid var(--border)',
          marginBottom: 8,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 4,
          }}
        >
          <span style={{ fontSize: 20 }}>🦞</span>
          <span
            style={{
              fontWeight: 800,
              fontSize: 14,
              letterSpacing: '-0.02em',
              color: 'var(--text)',
              lineHeight: 1.2,
            }}
          >
            Local AgentStudio
          </span>
        </div>
        <span
          className="hero-badge"
          style={{ marginBottom: 0, fontSize: 9, padding: '2px 8px' }}
        >
          Pro
        </span>
      </div>

      {/* Nav items */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          padding: '0 8px',
          flex: 1,
        }}
      >
        {NAV_ITEMS.map((item) => {
          const isActive = activePanel === item.id;
          const isOpenClaw = item.id === 'openclaw';

          return (
            <button
              key={item.id}
              onClick={() => onPanelChange(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 12px',
                borderRadius: 'var(--r-md)',
                border: 'none',
                background: isActive ? 'var(--accent)' : 'transparent',
                color: isActive ? '#fff' : 'var(--text-muted)',
                fontWeight: isActive ? 700 : 600,
                fontSize: 14,
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'background 150ms ease, color 150ms ease',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = '#f1f5f9';
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                  (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)';
                }
              }}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>{item.icon}</span>
              <span style={{ flex: 1 }}>{item.label}</span>

              {/* OpenClaw status dot */}
              {isOpenClaw && (
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: openClawRunning ? 'var(--green)' : '#94a3b8',
                    flexShrink: 0,
                    animation: openClawRunning ? 'pulse-green 2s infinite' : 'none',
                  }}
                  title={openClawRunning ? 'OpenClaw running' : 'OpenClaw stopped'}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: '12px 16px 0',
          borderTop: '1px solid var(--border)',
          marginTop: 8,
        }}
      >
        <p className="muted small" style={{ margin: 0, fontSize: 11, textAlign: 'center' }}>
          Local-first AI Agent Platform
        </p>
      </div>
    </nav>
  );
}
