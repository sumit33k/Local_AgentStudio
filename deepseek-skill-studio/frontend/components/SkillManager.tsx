'use client';

import { useEffect, useState, useCallback } from 'react';

interface Skill {
  name: string;
  source?: string;
  status?: string;
  description?: string;
}

interface OpenClawSkill {
  name: string;
  description?: string;
  source?: string;
  content?: string;
}

interface ScanResult {
  name?: string;
  description?: string;
  rules?: string[];
  valid?: boolean;
  error?: string;
}

interface Props {
  apiBase: string;
}

export default function SkillManager({ apiBase }: Props) {
  const [activeTab, setActiveTab] = useState<'installed' | 'openclaw' | 'import'>('installed');
  const [skills, setSkills] = useState<Skill[]>([]);
  const [openClawSkills, setOpenClawSkills] = useState<OpenClawSkill[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [importContent, setImportContent] = useState('');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);
  const [installing, setInstalling] = useState<string | null>(null);
  const [importingAll, setImportingAll] = useState(false);

  const fetchSkills = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/skills`);
      if (!res.ok) return;
      const data = await res.json();
      setSkills(Array.isArray(data) ? data : data.skills ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const fetchOpenClawSkills = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/openclaw/skills`);
      if (!res.ok) return;
      const data = await res.json();
      setOpenClawSkills(Array.isArray(data) ? data : data.skills ?? []);
    } catch {
      // non-critical
    }
  }, [apiBase]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    await Promise.all([fetchSkills(), fetchOpenClawSkills()]);
    setLoading(false);
  }, [fetchSkills, fetchOpenClawSkills]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const clearMessages = () => {
    setError(null);
    setSuccess(null);
  };

  const scanContent = async () => {
    if (!importContent.trim()) return;
    setScanning(true);
    setScanResult(null);
    clearMessages();
    try {
      // Parse SKILL.md locally for a preview
      const lines = importContent.split('\n');
      const nameLine = lines.find((l) => l.startsWith('# '));
      const name = nameLine ? nameLine.replace('# ', '').trim() : 'Unknown';
      const descLine = lines.find((l) => l.trim() && !l.startsWith('#'));
      setScanResult({ name, description: descLine?.trim(), valid: true });
    } catch (e: any) {
      setScanResult({ valid: false, error: e.message ?? 'Invalid SKILL.md content' });
    } finally {
      setScanning(false);
    }
  };

  const installFromContent = async () => {
    if (!importContent.trim() || !scanResult?.valid) return;
    setInstalling('paste');
    clearMessages();
    try {
      const skillName = scanResult?.name ?? 'imported-skill';
      const res = await fetch(`${apiBase}/skills`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: skillName, content: importContent }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Install failed');
      }
      setSuccess(`Skill "${skillName}" installed successfully.`);
      setImportContent('');
      setScanResult(null);
      await fetchSkills();
      setActiveTab('installed');
    } catch (e: any) {
      setError(e.message ?? 'Failed to install skill');
    } finally {
      setInstalling(null);
    }
  };

  const importSingleOpenClawSkill = async (sk: OpenClawSkill) => {
    setInstalling(sk.name);
    clearMessages();
    try {
      const res = await fetch(`${apiBase}/openclaw/import-skills`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skills: [sk.name] }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Import failed');
      }
      setSuccess(`Skill "${sk.name}" imported.`);
      await fetchSkills();
    } catch (e: any) {
      setError(e.message ?? 'Failed to import skill');
    } finally {
      setInstalling(null);
    }
  };

  const importAllOpenClawSkills = async () => {
    setImportingAll(true);
    clearMessages();
    try {
      const res = await fetch(`${apiBase}/openclaw/import-skills`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? 'Import all failed');
      }
      const data = await res.json();
      setSuccess(data.message ?? `Imported ${openClawSkills.length} skill(s).`);
      await fetchSkills();
      setActiveTab('installed');
    } catch (e: any) {
      setError(e.message ?? 'Failed to import skills');
    } finally {
      setImportingAll(false);
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🧰</span>
          <div>
            <h2 style={{ margin: 0, fontSize: 17 }}>Skill Manager</h2>
            <p className="muted small" style={{ margin: 0 }}>Manage installed and OpenClaw skills</p>
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

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === 'installed' ? 'active' : ''}`}
          onClick={() => setActiveTab('installed')}
        >
          <span className="tab-icon">📦</span> Installed ({skills.length})
        </button>
        <button
          className={`tab ${activeTab === 'openclaw' ? 'active' : ''}`}
          onClick={() => setActiveTab('openclaw')}
        >
          <span className="tab-icon">🦞</span> OpenClaw ({openClawSkills.length})
        </button>
        <button
          className={`tab ${activeTab === 'import' ? 'active' : ''}`}
          onClick={() => setActiveTab('import')}
        >
          <span className="tab-icon">⬇</span> Import
        </button>
      </div>

      {/* Feedback */}
      {error && <div className="error">{error}</div>}
      {success && (
        <div style={{ color: 'var(--green)', background: 'var(--green-bg)', border: '1px solid var(--green-border)', padding: '10px 16px', borderRadius: 'var(--r-md)', fontSize: 14 }}>
          {success}
        </div>
      )}

      {/* Installed Skills Tab */}
      {activeTab === 'installed' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {skills.length === 0 ? (
            <div className="kb-empty">
              <p className="muted">No skills installed. Import one from the Import tab or OpenClaw.</p>
            </div>
          ) : (
            skills.map((sk, i) => (
              <div key={sk.name ?? i} className="kb-doc-item">
                <div className="kb-doc-info">
                  <span style={{ fontSize: 16 }}>📄</span>
                  <div>
                    <div className="kb-doc-name">{sk.name}</div>
                    {sk.description && <p className="muted small" style={{ margin: 0 }}>{sk.description}</p>}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {sk.source && (
                    <span className="kb-doc-chunks">{sk.source}</span>
                  )}
                  {sk.status && (
                    <span
                      className={`status ${sk.status === 'active' ? 'ok' : 'bad'}`}
                      style={{ padding: '2px 10px', fontSize: 11 }}
                    >
                      <span className="status-dot" />
                      {sk.status}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* OpenClaw Skills Tab */}
      {activeTab === 'openclaw' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {openClawSkills.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                className="secondary"
                style={{ width: 'auto', padding: '8px 18px' }}
                onClick={importAllOpenClawSkills}
                disabled={importingAll}
              >
                {importingAll ? <span className="spinner" /> : '⬇ Import All'}
              </button>
            </div>
          )}

          {openClawSkills.length === 0 ? (
            <div className="kb-empty">
              <p className="muted">No OpenClaw skills available. Make sure the OpenClaw runtime is running.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {openClawSkills.map((sk, i) => (
                <div key={sk.name ?? i} className="kb-doc-item">
                  <div className="kb-doc-info">
                    <span style={{ fontSize: 16 }}>🦞</span>
                    <div>
                      <div className="kb-doc-name">{sk.name}</div>
                      {sk.description && <p className="muted small" style={{ margin: 0 }}>{sk.description}</p>}
                    </div>
                  </div>
                  <button
                    className="secondary"
                    style={{ width: 'auto', padding: '6px 14px', fontSize: 12 }}
                    onClick={() => importSingleOpenClawSkill(sk)}
                    disabled={installing === sk.name || importingAll}
                  >
                    {installing === sk.name ? <span className="spinner" /> : '⬇ Import'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Import Tab */}
      {activeTab === 'import' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="row">
            <label>Paste SKILL.md Content</label>
            <textarea
              value={importContent}
              onChange={(e) => {
                setImportContent(e.target.value);
                setScanResult(null);
              }}
              placeholder="# My Skill&#10;&#10;Describe what this skill does...&#10;&#10;## Rules&#10;- Rule 1&#10;- Rule 2"
              style={{ minHeight: 180, fontFamily: '"Fira Code", Consolas, monospace', fontSize: 13 }}
            />
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="secondary"
              style={{ width: 'auto', padding: '9px 18px' }}
              onClick={scanContent}
              disabled={scanning || !importContent.trim()}
            >
              {scanning ? <span className="spinner" /> : '🔍 Scan'}
            </button>
            <button
              className="primary"
              style={{ flex: 1 }}
              onClick={installFromContent}
              disabled={!!installing || !scanResult?.valid}
            >
              {installing === 'paste' ? <span className="spinner white" /> : '⬇ Install Skill'}
            </button>
          </div>

          {/* Scan result preview */}
          {scanResult && (
            <div
              style={{
                border: `1px solid ${scanResult.valid ? 'var(--green-border)' : 'var(--red-border)'}`,
                borderRadius: 'var(--r-md)',
                padding: '14px 16px',
                background: scanResult.valid ? 'var(--green-bg)' : 'var(--red-bg)',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: 6, color: scanResult.valid ? 'var(--green)' : 'var(--red)' }}>
                {scanResult.valid ? '✓ Valid SKILL.md' : '✗ Invalid content'}
              </div>
              {scanResult.name && <div className="small"><strong>Name:</strong> {scanResult.name}</div>}
              {scanResult.description && <div className="small muted" style={{ marginTop: 4 }}>{scanResult.description}</div>}
              {scanResult.error && <div className="small" style={{ color: 'var(--red)', marginTop: 4 }}>{scanResult.error}</div>}
            </div>
          )}

          {/* Import from OpenClaw shortcut */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <p className="muted small" style={{ marginBottom: 8 }}>
              Or import directly from the OpenClaw runtime:
            </p>
            <button
              className="secondary"
              style={{ width: 'auto', padding: '9px 18px' }}
              onClick={importAllOpenClawSkills}
              disabled={importingAll || openClawSkills.length === 0}
            >
              {importingAll ? <span className="spinner" /> : `🦞 Import All from OpenClaw (${openClawSkills.length})`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
