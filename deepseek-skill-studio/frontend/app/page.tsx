'use client';

import { useEffect, useRef, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://127.0.0.1:8000');

// ── Types ─────────────────────────────────────────────────────────────────

type Mode = 'agent' | 'chat' | 'studio' | 'knowledge' | 'connectors';
type ChatMessage = { role: 'user' | 'assistant'; content: string; ragSources?: string[] };
type Agent = { name: string; description: string; default_output: string; default_skill: string; system_addendum?: string; allowed_tools?: string[] };
type AgentMap = Record<string, Agent>;
type McpServer = { id: string; name: string; command: string; args: string[]; env: Record<string, string>; enabled: boolean; description: string };
type McpTool = { name: string; description: string; inputSchema: any; server_id: string; server_name: string };
type KbDoc = { filename: string; chunk_count: number };
type Settings = {
  llm_provider: string; ollama_base_url: string; ollama_model: string; ollama_embedding_model: string;
  claude_api_key: string; claude_model: string; openai_api_key: string; openai_model: string;
  openai_base_url: string; github_token: string; rag_enabled: boolean; rag_top_k: number;
  rag_chunk_size: number; rag_chunk_overlap: number;
};

// ── Markdown renderer ─────────────────────────────────────────────────────

function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*?<\/li>\n?)+/gs, m => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

// ── Confirm dialog ────────────────────────────────────────────────────────

function ConfirmDialog({ message, onConfirm, onCancel }: {
  message: string; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal confirm-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-body" style={{ textAlign: 'center', paddingTop: 8 }}>
          <p style={{ margin: '0 0 20px', fontSize: 15 }}>{message}</p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button className="secondary" style={{ width: 'auto', padding: '9px 24px' }} onClick={onCancel}>Cancel</button>
            <button className="primary danger-btn" style={{ width: 'auto', padding: '9px 24px' }} onClick={onConfirm}>Delete</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Default settings ──────────────────────────────────────────────────────

const DEFAULT_SETTINGS: Settings = {
  llm_provider: 'ollama', ollama_base_url: 'http://127.0.0.1:11434',
  ollama_model: 'deepseek-r1:8b', ollama_embedding_model: 'nomic-embed-text',
  claude_api_key: '', claude_model: 'claude-sonnet-4-6',
  openai_api_key: '', openai_model: 'gpt-4o', openai_base_url: '',
  github_token: '', rag_enabled: true, rag_top_k: 5,
  rag_chunk_size: 1000, rag_chunk_overlap: 200,
};

// ════════════════════════════════════════════════════════════════════════════
export default function Home() {
  // ── Core state ────────────────────────────────────────────────────────────
  const [mode, setMode] = useState<Mode>('agent');
  const [model, setModel] = useState('');
  const [models, setModels] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [agents, setAgents] = useState<AgentMap>({});
  const [agentId, setAgentId] = useState('doc_architect');
  const [runs, setRuns] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // ── Agent mode ────────────────────────────────────────────────────────────
  const [agentPrompt, setAgentPrompt] = useState('Analyze the uploaded context and create an executive-ready deliverable.');
  const [studioPrompt, setStudioPrompt] = useState('Generate output using the selected skill.');
  // Unified accessor so generate() works for both tabs
  const prompt = mode === 'studio' ? studioPrompt : agentPrompt;
  const setPrompt = mode === 'studio' ? setStudioPrompt : setAgentPrompt;
  const [outputType, setOutputType] = useState('docx');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [rawMarkdown, setRawMarkdown] = useState('');
  const [createPrompt, setCreatePrompt] = useState('');
  const [creatingAgent, setCreatingAgent] = useState(false);
  const [editingAgentId, setEditingAgentId] = useState('');
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  // ── Chat mode ─────────────────────────────────────────────────────────────
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [useRag, setUseRag] = useState(false);
  const [streamEnabled, setStreamEnabled] = useState(true);
  const [ragCollection, setRagCollection] = useState('default');

  // ── Studio mode ───────────────────────────────────────────────────────────
  const [skillName, setSkillName] = useState('document_writer');
  const [showSkillCreator, setShowSkillCreator] = useState(false);
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillDesc, setNewSkillDesc] = useState('');
  const [newSkillRules, setNewSkillRules] = useState(['', '', '']);

  // ── Knowledge Base ────────────────────────────────────────────────────────
  const [kbDocs, setKbDocs] = useState<KbDoc[]>([]);
  const [kbCollection, setKbCollection] = useState('default');
  const [kbCollections, setKbCollections] = useState<string[]>([]);
  const [kbFiles, setKbFiles] = useState<FileList | null>(null);
  const [kbLoading, setKbLoading] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');

  // ── Connectors ────────────────────────────────────────────────────────────
  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [mcpTools, setMcpTools] = useState<Record<string, McpTool[]>>({});
  const [mcpPresets, setMcpPresets] = useState<any[]>([]);
  const [addMcpOpen, setAddMcpOpen] = useState(false);
  const [newMcp, setNewMcp] = useState({ name: '', command: '', args: '', env: '', description: '' });
  const [mcpLoading, setMcpLoading] = useState<Record<string, boolean>>({});
  const [githubStatus, setGithubStatus] = useState<any>(null);
  const [githubRepos, setGithubRepos] = useState<any[]>([]);

  // ── Settings ──────────────────────────────────────────────────────────────
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [settingsDraft, setSettingsDraft] = useState<Settings>(DEFAULT_SETTINGS);
  const [savingSettings, setSavingSettings] = useState(false);

  // ── Context sources ───────────────────────────────────────────────────────
  const [contextOpen, setContextOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [githubBranch, setGithubBranch] = useState('');
  const [includePaths, setIncludePaths] = useState('');
  const [excludePaths, setExcludePaths] = useState('node_modules,.git,dist,build,.venv,__pycache__');
  const [files, setFiles] = useState<FileList | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Confirm dialog ────────────────────────────────────────────────────────
  const [confirmState, setConfirmState] = useState<{ message: string; resolve: (v: boolean) => void } | null>(null);

  function confirmAction(message: string): Promise<boolean> {
    return new Promise(resolve => setConfirmState({ message, resolve }));
  }

  function handleConfirm(result: boolean) {
    confirmState?.resolve(result);
    setConfirmState(null);
  }

  // ── Effects ───────────────────────────────────────────────────────────────

  useEffect(() => { refreshAll(); }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(''), 4000);
    return () => clearTimeout(t);
  }, [success]);

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(''), 8000);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    if (mode === 'knowledge') refreshKnowledgeBase();
    if (mode === 'connectors') { refreshMcpServers(); fetchMcpPresets(); }
  }, [mode, kbCollection]);

  // ── Data fetching ─────────────────────────────────────────────────────────

  function refreshAll() {
    fetch(`${API}/agents`).then(r => r.json()).then(d => setAgents(d.agents || {})).catch(() => {});
    fetch(`${API}/agent/runs`).then(r => r.json()).then(d => setRuns(d.runs || [])).catch(() => {});
    fetch(`${API}/health`).then(r => r.json()).then(d => {
      setHealth(d);
    }).catch(() => {});
    fetch(`${API}/models`).then(r => r.json()).then(d => {
      const installed: string[] = d.models || [];
      setModels(installed);
      if (installed.length && !model) setModel(installed[0]);
    }).catch(() => {});
    fetch(`${API}/skills`).then(r => r.json()).then(d => setSkills(d.skills || [])).catch(() => {});
    fetch(`${API}/settings`).then(r => r.json()).then(d => {
      setSettings(d);
      setSettingsDraft(d);
    }).catch(() => {});
    fetch(`${API}/knowledge-base/collections`).then(r => r.json()).then(d => {
      const cols: string[] = d.collections || [];
      if (!cols.includes('default')) cols.unshift('default');
      setKbCollections(cols);
    }).catch(() => {});
  }

  function refreshKnowledgeBase() {
    setKbLoading(true);
    fetch(`${API}/knowledge-base/${kbCollection}/documents`)
      .then(r => r.json()).then(d => setKbDocs(d.documents || [])).catch(() => setKbDocs([]))
      .finally(() => setKbLoading(false));
  }

  function refreshMcpServers() {
    fetch(`${API}/mcp/servers`).then(r => r.json()).then(d => setMcpServers(d.servers || [])).catch(() => {});
  }

  function fetchMcpPresets() {
    fetch(`${API}/mcp/presets`).then(r => r.json()).then(d => setMcpPresets(d.presets || [])).catch(() => {});
  }

  function checkGitHub() {
    fetch(`${API}/connectors/github/status`).then(r => r.json()).then(d => {
      setGithubStatus(d);
      if (d.ok) {
        fetch(`${API}/connectors/github/repos`).then(r => r.json()).then(rd => setGithubRepos(rd.repos || [])).catch(() => {});
      }
    }).catch(e => setGithubStatus({ ok: false, error: String(e) }));
  }

  // ── Settings ──────────────────────────────────────────────────────────────

  async function saveSettings() {
    setSavingSettings(true);
    try {
      const res = await fetch(`${API}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsDraft),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Save failed');
      setSettings(data);
      setSettingsDraft(data);
      setSettingsOpen(false);
      setSuccess('Settings saved!');
      refreshAll();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSavingSettings(false);
    }
  }

  // ── Agent operations ──────────────────────────────────────────────────────

  function applyAgent(id: string) {
    setAgentId(id);
    const agent = agents[id];
    if (agent) setOutputType(agent.default_output || 'md');
  }

  async function createAgentFromPrompt() {
    if (!createPrompt.trim()) return;
    setCreatingAgent(true);
    setError('');
    try {
      const form = new FormData();
      form.append('creation_prompt', createPrompt);
      form.append('model', model);
      const res = await fetch(`${API}/agent/create`, { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Agent creation failed');
      setAgents(data.agents || {});
      setAgentId(data.agent_id);
      setOutputType(data.agent?.default_output || 'md');
      setMode('agent');
      setCreatePrompt('');
      setSuccess(`Agent "${data.agent?.name || data.agent_id}" created!`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreatingAgent(false);
    }
  }

  async function saveAgentEdit() {
    if (!editingAgentId || !editingAgent) return;
    try {
      const res = await fetch(`${API}/agents/${editingAgentId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingAgent),
      });
      if (!res.ok) throw new Error('Update failed');
      const data = await res.json();
      setAgents(prev => ({ ...prev, [editingAgentId]: data.agent }));
      setEditingAgentId('');
      setEditingAgent(null);
      setSuccess('Agent updated!');
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function deleteAgent(id: string) {
    if (!await confirmAction(`Delete agent "${agents[id]?.name}"?`)) return;
    try {
      const res = await fetch(`${API}/agents/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      setAgents(prev => { const n = { ...prev }; delete n[id]; return n; });
      if (agentId === id) setAgentId(Object.keys(agents).filter(k => k !== id)[0] || '');
      setSuccess('Agent deleted');
    } catch (e: any) {
      setError(e.message);
    }
  }

  // ── Generate (agent/studio) ───────────────────────────────────────────────

  async function generate() {
    setLoading(true); setError(''); setDownloadUrl(''); setRawMarkdown('');
    const form = new FormData();
    form.append('prompt', prompt);
    form.append('output_type', outputType);
    form.append('model', model);
    form.append('github_url', githubUrl);
    form.append('github_branch', githubBranch);
    form.append('include_paths', includePaths);
    form.append('exclude_paths', excludePaths);
    form.append('use_rag', String(useRag));
    form.append('rag_collection', ragCollection);
    if (files) Array.from(files).forEach(f => form.append('files', f));
    if (mode === 'agent') form.append('agent_id', agentId);
    else form.append('skill_name', skillName);
    try {
      const endpoint = mode === 'agent' ? '/agent/run' : '/generate';
      const res = await fetch(`${API}${endpoint}`, { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Generation failed');
      setDownloadUrl(`${API}${data.download_url}`);
      setRawMarkdown(data.raw_markdown || '');
      setSuccess('Output generated — ready to download!');
      fetch(`${API}/agent/runs`).then(r => r.json()).then(d => setRuns(d.runs || [])).catch(() => {});
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────

  async function sendChat() {
    if (!chatInput.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content: chatInput };
    const nextHistory = [...chatMessages, userMsg];
    setChatMessages(nextHistory);
    setChatInput('');
    setLoading(true);
    setError('');

    const form = new FormData();
    form.append('message', userMsg.content);
    form.append('agent_id', agentId);
    form.append('model', model);
    form.append('history_json', JSON.stringify(chatMessages));
    form.append('use_rag', String(useRag));
    form.append('rag_collection', ragCollection);
    form.append('stream', String(streamEnabled));
    form.append('github_url', githubUrl);
    form.append('github_branch', githubBranch);
    form.append('include_paths', includePaths);
    form.append('exclude_paths', excludePaths);
    if (files) Array.from(files).forEach(f => form.append('files', f));

    if (streamEnabled) {
      // Add placeholder for streaming response
      setChatMessages([...nextHistory, { role: 'assistant', content: '' }]);
      let accumulated = '';
      let ragSources: string[] = [];
      try {
        const res = await fetch(`${API}/chat`, { method: 'POST', body: form });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Chat failed' }));
          throw new Error(err.detail || 'Chat failed');
        }
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const payload = JSON.parse(line.slice(6));
              if (payload.type === 'text') {
                accumulated += payload.chunk;
                setChatMessages(prev => {
                  const msgs = [...prev];
                  msgs[msgs.length - 1] = { role: 'assistant', content: accumulated };
                  return msgs;
                });
              } else if (payload.type === 'done') {
                ragSources = (payload.rag_sources || []).map((s: any) => s.filename);
              } else if (payload.type === 'error') {
                throw new Error(payload.message);
              }
            } catch (parseErr: any) {
              if (parseErr.message && !parseErr.message.includes('JSON')) throw parseErr;
            }
          }
        }
        if (ragSources.length > 0) {
          setChatMessages(prev => {
            const msgs = [...prev];
            msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ragSources };
            return msgs;
          });
        }
      } catch (e: any) {
        setError(e.message);
        setChatMessages(prev => prev.slice(0, -1));
      } finally {
        setLoading(false);
      }
    } else {
      try {
        const res = await fetch(`${API}/chat`, { method: 'POST', body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Chat failed');
        const ragSources = (data.rag_sources || []).map((s: any) => s.filename);
        setChatMessages([...nextHistory, { role: 'assistant', content: data.reply || '', ragSources }]);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
  }

  // ── Skill creator ─────────────────────────────────────────────────────────

  async function createSkill() {
    if (!newSkillName.trim() || !newSkillDesc.trim()) return;
    const rules = newSkillRules.filter(r => r.trim());
    if (rules.length === 0) return;
    try {
      const res = await fetch(`${API}/skills`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newSkillName, description: newSkillDesc, rules }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Create failed');
      setSkills(prev => [...prev, data.name].sort());
      setSkillName(data.name);
      setShowSkillCreator(false);
      setNewSkillName(''); setNewSkillDesc(''); setNewSkillRules(['', '', '']);
      setSuccess(`Skill "${data.name}" created!`);
    } catch (e: any) {
      setError(e.message);
    }
  }

  // ── Knowledge Base ────────────────────────────────────────────────────────

  async function uploadKbFiles() {
    if (!kbFiles || kbFiles.length === 0) return;
    setKbLoading(true);
    setError('');
    const form = new FormData();
    Array.from(kbFiles).forEach(f => form.append('files', f));
    try {
      const res = await fetch(`${API}/knowledge-base/${kbCollection}/upload`, { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');
      const ok = (data.results as any[]).filter(r => r.chunks > 0);
      const failed = (data.results as any[]).filter(r => r.chunks === 0 && r.error);
      if (failed.length > 0) {
        setError(`${failed.length} file(s) failed to embed: ${failed.map((r: any) => `${r.filename} (${r.error})`).join(', ')}`);
      }
      if (ok.length > 0) setSuccess(`Indexed ${ok.length} file(s) into "${kbCollection}"`);
      setKbFiles(null);
      refreshKnowledgeBase();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setKbLoading(false);
    }
  }

  async function deleteKbDoc(filename: string) {
    if (!await confirmAction(`Remove "${filename}" from knowledge base?`)) return;
    try {
      await fetch(`${API}/knowledge-base/${kbCollection}/documents/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      setSuccess('Document removed');
      refreshKnowledgeBase();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function createNewCollection() {
    if (!newCollectionName.trim()) return;
    const form = new FormData();
    form.append('name', newCollectionName);
    try {
      const res = await fetch(`${API}/knowledge-base/collections`, { method: 'POST', body: form });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Create failed' }));
        throw new Error(data.detail || 'Create failed');
      }
      setKbCollections(prev => [...prev, newCollectionName]);
      setKbCollection(newCollectionName);
      setNewCollectionName('');
      setSuccess(`Collection "${newCollectionName}" created`);
    } catch (e: any) { setError(e.message); }
  }

  // ── MCP ───────────────────────────────────────────────────────────────────

  async function addMcpServer(fromPreset?: any) {
    const data = fromPreset || {
      name: newMcp.name,
      command: newMcp.command,
      args: newMcp.args.split(' ').filter(Boolean),
      env: Object.fromEntries(
        newMcp.env.split('\n').filter(l => l.includes('=')).map(l => {
          const [k, ...v] = l.split('=');
          return [k.trim(), v.join('=').trim()];
        })
      ),
      description: newMcp.description,
    };
    try {
      const res = await fetch(`${API}/mcp/servers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error('Add failed');
      setSuccess(`MCP server "${data.name}" added`);
      setAddMcpOpen(false);
      setNewMcp({ name: '', command: '', args: '', env: '', description: '' });
      refreshMcpServers();
    } catch (e: any) { setError(e.message); }
  }

  async function deleteMcpServer(id: string) {
    if (!confirmAction('Remove this MCP server?')) return;
    try {
      const res = await fetch(`${API}/mcp/servers/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Delete failed' }));
        throw new Error(data.detail || 'Delete failed');
      }
      setSuccess('Server removed');
      refreshMcpServers();
    } catch (e: any) { setError(e.message); }
  }

  async function listMcpTools(serverId: string) {
    setMcpLoading(prev => ({ ...prev, [serverId]: true }));
    try {
      const res = await fetch(`${API}/mcp/servers/${serverId}/tools`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to list tools');
      setMcpTools(prev => ({ ...prev, [serverId]: data.tools || [] }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setMcpLoading(prev => ({ ...prev, [serverId]: false }));
    }
  }

  // ── Computed ──────────────────────────────────────────────────────────────

  const selectedAgent = agents[agentId];
  const hasContext = !!(githubUrl || (files && files.length > 0));
  const providerLabel = health?.provider ? health.provider.charAt(0).toUpperCase() + health.provider.slice(1) : 'Ollama';

  // ════════════════════════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════════════════════════

  return (
    <main className="container">
      {success && <div className="toast toast-success">✓ {success}</div>}

      {confirmState && (
        <ConfirmDialog
          message={confirmState.message}
          onConfirm={() => handleConfirm(true)}
          onCancel={() => handleConfirm(false)}
        />
      )}

      {/* ── Settings Modal ─────────────────────────────────────────────── */}
      {settingsOpen && (
        <div className="modal-overlay" onClick={() => setSettingsOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>⚙ Settings</h2>
              <button className="icon-btn" onClick={() => setSettingsOpen(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="settings-section">
                <label className="settings-label">LLM Provider</label>
                <div className="provider-grid">
                  {['ollama', 'claude', 'openai', 'openai_compat'].map(p => (
                    <button
                      key={p}
                      className={settingsDraft.llm_provider === p ? 'provider-btn active' : 'provider-btn'}
                      onClick={() => setSettingsDraft(d => ({ ...d, llm_provider: p }))}
                    >
                      {p === 'ollama' ? '🦙 Ollama' : p === 'claude' ? '🟣 Claude' : p === 'openai' ? '🟢 OpenAI' : '⚙ OpenAI-Compat'}
                    </button>
                  ))}
                </div>
              </div>

              {settingsDraft.llm_provider === 'ollama' && (
                <div className="settings-section">
                  <div className="row"><label>Ollama URL</label>
                    <input value={settingsDraft.ollama_base_url} onChange={e => setSettingsDraft(d => ({ ...d, ollama_base_url: e.target.value }))} /></div>
                  <div className="row"><label>Default Model</label>
                    <input value={settingsDraft.ollama_model} onChange={e => setSettingsDraft(d => ({ ...d, ollama_model: e.target.value }))} /></div>
                  <div className="row"><label>Embedding Model</label>
                    <input value={settingsDraft.ollama_embedding_model} onChange={e => setSettingsDraft(d => ({ ...d, ollama_embedding_model: e.target.value }))} placeholder="nomic-embed-text" /></div>
                </div>
              )}

              {settingsDraft.llm_provider === 'claude' && (
                <div className="settings-section">
                  <div className="row"><label>API Key</label>
                    <input type="password" value={settingsDraft.claude_api_key} onChange={e => setSettingsDraft(d => ({ ...d, claude_api_key: e.target.value }))} placeholder="sk-ant-..." /></div>
                  <div className="row"><label>Model</label>
                    <select value={settingsDraft.claude_model} onChange={e => setSettingsDraft(d => ({ ...d, claude_model: e.target.value }))}>
                      <option value="claude-opus-4-7">claude-opus-4-7</option>
                      <option value="claude-sonnet-4-6">claude-sonnet-4-6</option>
                      <option value="claude-haiku-4-5-20251001">claude-haiku-4-5-20251001</option>
                    </select></div>
                </div>
              )}

              {(settingsDraft.llm_provider === 'openai' || settingsDraft.llm_provider === 'openai_compat') && (
                <div className="settings-section">
                  <div className="row"><label>API Key</label>
                    <input type="password" value={settingsDraft.openai_api_key} onChange={e => setSettingsDraft(d => ({ ...d, openai_api_key: e.target.value }))} placeholder="sk-..." /></div>
                  <div className="row"><label>Model</label>
                    <input value={settingsDraft.openai_model} onChange={e => setSettingsDraft(d => ({ ...d, openai_model: e.target.value }))} placeholder="gpt-4o" /></div>
                  <div className="row"><label>Base URL {settingsDraft.llm_provider === 'openai' ? '(optional)' : '(required)'}</label>
                    <input value={settingsDraft.openai_base_url} onChange={e => setSettingsDraft(d => ({ ...d, openai_base_url: e.target.value }))} placeholder="http://localhost:1234/v1" /></div>
                </div>
              )}

              <div className="settings-section">
                <label className="settings-label">GitHub</label>
                <div className="row"><label>Personal Access Token</label>
                  <input type="password" value={settingsDraft.github_token} onChange={e => setSettingsDraft(d => ({ ...d, github_token: e.target.value }))} placeholder="ghp_..." /></div>
              </div>

              <div className="settings-section">
                <label className="settings-label">Knowledge Base (RAG)</label>
                <div className="grid">
                  <div className="row"><label>Top-K results</label>
                    <input type="number" value={settingsDraft.rag_top_k} min={1} max={20} onChange={e => setSettingsDraft(d => ({ ...d, rag_top_k: +e.target.value }))} /></div>
                  <div className="row"><label>Chunk size (chars)</label>
                    <input type="number" value={settingsDraft.rag_chunk_size} min={200} max={4000} onChange={e => setSettingsDraft(d => ({ ...d, rag_chunk_size: +e.target.value }))} /></div>
                  <div className="row"><label>Chunk overlap (chars)</label>
                    <input type="number" value={settingsDraft.rag_chunk_overlap} min={0} max={1000} onChange={e => setSettingsDraft(d => ({ ...d, rag_chunk_overlap: +e.target.value }))} /></div>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="secondary" onClick={() => setSettingsOpen(false)}>Cancel</button>
              <button className="primary" style={{ width: 'auto', padding: '10px 28px' }} onClick={saveSettings} disabled={savingSettings}>
                {savingSettings ? <span className="spinner white" /> : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Agent Modal ───────────────────────────────────────────── */}
      {editingAgentId && editingAgent && (
        <div className="modal-overlay" onClick={() => { setEditingAgentId(''); setEditingAgent(null); }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>✏ Edit Agent</h2>
              <button className="icon-btn" onClick={() => { setEditingAgentId(''); setEditingAgent(null); }}>✕</button>
            </div>
            <div className="modal-body">
              <div className="row"><label>Name</label>
                <input value={editingAgent.name} onChange={e => setEditingAgent(a => a ? { ...a, name: e.target.value } : a)} /></div>
              <div className="row"><label>Description</label>
                <textarea className="smallArea" value={editingAgent.description} onChange={e => setEditingAgent(a => a ? { ...a, description: e.target.value } : a)} /></div>
              <div className="row"><label>Skill</label>
                <select value={editingAgent.default_skill} onChange={e => setEditingAgent(a => a ? { ...a, default_skill: e.target.value } : a)}>
                  {skills.map(s => <option key={s} value={s}>{s}</option>)}
                </select></div>
              <div className="row"><label>Default Output</label>
                <select value={editingAgent.default_output} onChange={e => setEditingAgent(a => a ? { ...a, default_output: e.target.value } : a)}>
                  <option value="docx">Word Document</option>
                  <option value="pptx">PowerPoint</option>
                  <option value="md">Markdown</option>
                </select></div>
              <div className="row"><label>System Instructions</label>
                <textarea value={editingAgent.system_addendum || ''} onChange={e => setEditingAgent(a => a ? { ...a, system_addendum: e.target.value } : a)} /></div>
              <div className="row">
                <label>Allowed Tools</label>
                <div className="tools-grid">
                  {['files', 'github', 'docx', 'pptx', 'markdown', 'chat'].map(tool => {
                    const checked = (editingAgent.allowed_tools || []).includes(tool);
                    return (
                      <label key={tool} className="tool-checkbox">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const current = editingAgent.allowed_tools || [];
                            const next = checked ? current.filter(t => t !== tool) : [...current, tool];
                            setEditingAgent(a => a ? { ...a, allowed_tools: next } : a);
                          }}
                        />
                        <span>{tool}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="secondary" onClick={() => { setEditingAgentId(''); setEditingAgent(null); }}>Cancel</button>
              <button className="primary" style={{ width: 'auto', padding: '10px 28px' }} onClick={saveAgentEdit}>Save</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="hero">
        <div>
          <div className="hero-badge">Local AI</div>
          <h1>Agent Studio</h1>
          <p className="muted">Multi-provider AI with agents, skills, MCP tools, and knowledge base.</p>
        </div>
        <div className="hero-actions">
          <div className={health?.ollama_ok || health?.provider !== 'ollama' ? 'status ok' : 'status bad'}>
            <span className="status-dot" />
            {providerLabel} {health?.ollama_ok || health?.provider !== 'ollama' ? 'Connected' : 'Offline'}
          </div>
          <button className="icon-btn" onClick={refreshAll} title="Refresh">↻</button>
          <button className="icon-btn" onClick={() => { setSettingsDraft(settings); setSettingsOpen(true); }} title="Settings">⚙</button>
        </div>
      </div>

      {/* ── Tabs ──────────────────────────────────────────────────────── */}
      <div className="tabs">
        {([['agent', '⚡', 'Agent Mode'], ['chat', '💬', 'Chat'], ['studio', '🛠', 'Skill Studio'], ['knowledge', '📚', 'Knowledge Base'], ['connectors', '🔌', 'Connectors']] as [Mode, string, string][]).map(([m, icon, label]) => (
          <button key={m} className={mode === m ? 'tab active' : 'tab'} onClick={() => setMode(m)}>
            <span className="tab-icon">{icon}</span> {label}
          </button>
        ))}
      </div>

      <div className="layout">
        <section className="card maincard">

          {/* ── Model selector (always visible) ───────────────────────── */}
          {mode !== 'knowledge' && mode !== 'connectors' && (
            <div className="grid">
              <div className="row">
                <label>Model</label>
                {settings.llm_provider === 'ollama' ? (
                  models.length > 0 ? (
                    <select value={model} onChange={e => setModel(e.target.value)}>
                      {models.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  ) : (
                    <input value={model} onChange={e => setModel(e.target.value)} placeholder={health?.default_model || 'Model name'} />
                  )
                ) : (
                  <div className="provider-model-badge">
                    <span className="agent-badge" style={{ fontSize: 12, padding: '4px 10px' }}>
                      {settings.llm_provider === 'claude' ? settings.claude_model : settings.openai_model}
                    </span>
                    <span className="muted small">configured in Settings</span>
                  </div>
                )}
              </div>
              <div className="row">
                <label>Active Agent</label>
                <select value={agentId} onChange={e => applyAgent(e.target.value)}>
                  {Object.entries(agents).map(([id, a]) => (
                    <option key={id} value={id}>{a.name}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* ══════════════════════════ AGENT TAB ═══════════════════════ */}
          {mode === 'agent' && (
            <>
              {/* Agent creation panel */}
              <div className="builder">
                <div className="builder-header">
                  <span className="builder-icon">✨</span>
                  <strong>Create Agent from Prompt</strong>
                </div>
                <textarea
                  className="smallArea"
                  value={createPrompt}
                  onChange={e => setCreatePrompt(e.target.value)}
                  placeholder="Describe the agent you want to create…"
                />
                <button className="secondary" onClick={createAgentFromPrompt} disabled={creatingAgent || !createPrompt.trim()}>
                  {creatingAgent ? <><span className="spinner" /> Creating…</> : '✨ Create Agent'}
                </button>
              </div>

              {/* Agent grid */}
              <label>Available Agents</label>
              <div className="agentGrid">
                {Object.entries(agents).map(([id, agent]) => (
                  <div key={id} className={agentId === id ? 'agent activeAgent agent-card' : 'agent agent-card'} onClick={() => applyAgent(id)}>
                    <div className="agent-header">
                      <strong>{agent.name}</strong>
                      <span className="agent-badge">{agent.default_output}</span>
                    </div>
                    <span className="agent-desc">{agent.description}</span>
                    <div className="agent-actions" onClick={e => e.stopPropagation()}>
                      <button className="agent-action-btn" onClick={() => { setEditingAgentId(id); setEditingAgent({ ...agent }); }}>✏ Edit</button>
                      <button className="agent-action-btn danger" onClick={() => deleteAgent(id)}>✕ Delete</button>
                    </div>
                  </div>
                ))}
              </div>
              {selectedAgent && (
                <p className="muted small agent-meta">
                  Skill: <strong>{selectedAgent.default_skill}</strong> · Output: <strong>{selectedAgent.default_output.toUpperCase()}</strong>
                </p>
              )}

              <div className="row"><label>Prompt</label>
                <textarea value={prompt} onChange={e => setPrompt(e.target.value)} /></div>
              <div className="grid">
                <div className="row"><label>Output Format</label>
                  <select value={outputType} onChange={e => setOutputType(e.target.value)}>
                    <option value="docx">Word Document (.docx)</option>
                    <option value="pptx">PowerPoint (.pptx)</option>
                    <option value="md">Markdown (.md)</option>
                  </select>
                </div>
                <div className="row"><label>Knowledge Base Collection</label>
                  <div className="rag-toggle-row">
                    <label className="toggle-label">
                      <input type="checkbox" checked={useRag} onChange={e => setUseRag(e.target.checked)} />
                      <span>Use RAG</span>
                    </label>
                    {useRag && (
                      <select value={ragCollection} onChange={e => setRagCollection(e.target.value)}>
                        {kbCollections.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ══════════════════════════ CHAT TAB ════════════════════════ */}
          {mode === 'chat' && (
            <div className="chatBox">
              <div className="chatHeader">
                <div className="chatHeader-left">
                  <span className="chat-avatar">🤖</span>
                  <div>
                    <strong>{selectedAgent ? selectedAgent.name : 'General Chat'}</strong>
                    <div className="chatHeader-sub">{providerLabel} · {model || 'default'}</div>
                  </div>
                </div>
                <div className="chat-controls">
                  <label className="toggle-label small">
                    <input type="checkbox" checked={streamEnabled} onChange={e => setStreamEnabled(e.target.checked)} />
                    <span>Stream</span>
                  </label>
                  <label className="toggle-label small">
                    <input type="checkbox" checked={useRag} onChange={e => setUseRag(e.target.checked)} />
                    <span>RAG</span>
                  </label>
                  {chatMessages.length > 0 && (
                    <button className="clear-btn" onClick={() => setChatMessages([])}>Clear</button>
                  )}
                </div>
              </div>

              <div className="messages">
                {chatMessages.length === 0 && (
                  <div className="chat-empty">
                    <div className="chat-empty-icon">💬</div>
                    <p>Start a conversation with {selectedAgent?.name || 'the assistant'}.</p>
                    <p className="muted small">Ctrl+Enter to send · Toggle Stream for real-time output · Toggle RAG to use uploaded documents</p>
                  </div>
                )}
                {chatMessages.map((m, idx) => (
                  <div key={idx} className={m.role === 'user' ? 'bubble userBubble' : 'bubble assistantBubble'}>
                    <strong>{m.role === 'user' ? 'You' : (selectedAgent?.name || 'Assistant')}</strong>
                    <div dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                    {m.ragSources && m.ragSources.length > 0 && (
                      <div className="rag-sources">
                        📚 Sources: {m.ragSources.map(s => <span key={s} className="rag-chip">{s}</span>)}
                      </div>
                    )}
                  </div>
                ))}
                {loading && !streamEnabled && (
                  <div className="bubble assistantBubble">
                    <strong>{selectedAgent?.name || 'Assistant'}</strong>
                    <div className="typing-dots"><span /><span /><span /></div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="chatInput">
                <textarea
                  className="smallArea"
                  placeholder="Type your message… (Ctrl+Enter to send)"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendChat(); }}
                />
                <button className="primary" onClick={sendChat} disabled={loading || !chatInput.trim()}>
                  {loading ? <span className="spinner white" /> : 'Send'}
                </button>
              </div>
            </div>
          )}

          {/* ═══════════════════════ SKILL STUDIO TAB ═══════════════════ */}
          {mode === 'studio' && (
            <>
              <div className="skill-header">
                <div className="row" style={{ flex: 1 }}>
                  <label>Skill</label>
                  <select value={skillName} onChange={e => setSkillName(e.target.value)}>
                    {skills.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <button className="secondary" style={{ marginTop: 20 }} onClick={() => setShowSkillCreator(v => !v)}>
                  {showSkillCreator ? 'Cancel' : '+ New Skill'}
                </button>
              </div>

              {showSkillCreator && (
                <div className="builder">
                  <div className="builder-header"><span className="builder-icon">🛠</span><strong>Create New Skill</strong></div>
                  <div className="row"><label>Skill Name (slug)</label>
                    <input value={newSkillName} onChange={e => setNewSkillName(e.target.value)} placeholder="my_skill" /></div>
                  <div className="row"><label>Description (one sentence)</label>
                    <input value={newSkillDesc} onChange={e => setNewSkillDesc(e.target.value)} placeholder="What this skill does…" /></div>
                  <label>Rules</label>
                  {newSkillRules.map((rule, i) => (
                    <div key={i} className="rule-row">
                      <input value={rule} onChange={e => setNewSkillRules(rs => rs.map((r, j) => j === i ? e.target.value : r))}
                        placeholder={`Rule ${i + 1}…`} />
                      {newSkillRules.length > 1 && (
                        <button className="icon-btn" onClick={() => setNewSkillRules(rs => rs.filter((_, j) => j !== i))}>✕</button>
                      )}
                    </div>
                  ))}
                  <button className="secondary small-btn" onClick={() => setNewSkillRules(rs => [...rs, ''])}>+ Add Rule</button>
                  <button className="primary" onClick={createSkill} disabled={!newSkillName.trim() || !newSkillDesc.trim()}>Create Skill</button>
                </div>
              )}

              <div className="row"><label>Prompt</label>
                <textarea value={prompt} onChange={e => setPrompt(e.target.value)} /></div>
              <div className="grid">
                <div className="row"><label>Output Format</label>
                  <select value={outputType} onChange={e => setOutputType(e.target.value)}>
                    <option value="docx">Word Document (.docx)</option>
                    <option value="pptx">PowerPoint (.pptx)</option>
                    <option value="md">Markdown (.md)</option>
                  </select>
                </div>
                <div className="row"><label>RAG</label>
                  <div className="rag-toggle-row">
                    <label className="toggle-label">
                      <input type="checkbox" checked={useRag} onChange={e => setUseRag(e.target.checked)} />
                      <span>Use Knowledge Base</span>
                    </label>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ════════════════════ KNOWLEDGE BASE TAB ════════════════════ */}
          {mode === 'knowledge' && (
            <div className="kb-tab">
              <div className="kb-header">
                <h2>📚 Knowledge Base</h2>
                <p className="muted">Upload documents to enable semantic search (RAG) across your agents and chat.</p>
              </div>

              {/* Collection selector */}
              <div className="kb-collections">
                <label>Collection</label>
                <div className="collection-row">
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flex: 1 }}>
                    <select value={kbCollection} onChange={e => { setKbCollection(e.target.value); }} style={{ flex: 1 }}>
                      {kbCollections.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    {kbCollection !== 'default' && (
                      <button
                        className="agent-action-btn danger"
                        title="Delete this collection"
                        onClick={async () => {
                          if (!await confirmAction(`Delete collection "${kbCollection}" and all its documents?`)) return;
                          try {
                            const res = await fetch(`${API}/knowledge-base/collections/${encodeURIComponent(kbCollection)}`, { method: 'DELETE' });
                            if (!res.ok) {
                              const d = await res.json().catch(() => ({ detail: 'Delete failed' }));
                              throw new Error(d.detail || 'Delete failed');
                            }
                            setKbCollections(prev => prev.filter(c => c !== kbCollection));
                            setKbCollection('default');
                            setSuccess(`Collection "${kbCollection}" deleted`);
                          } catch (e: any) { setError(e.message); }
                        }}
                      >✕ Delete</button>
                    )}
                  </div>
                  <div className="new-collection-row">
                    <input value={newCollectionName} onChange={e => setNewCollectionName(e.target.value)}
                      placeholder="New collection name…" onKeyDown={e => e.key === 'Enter' && createNewCollection()} />
                    <button className="secondary" onClick={createNewCollection} disabled={!newCollectionName.trim()}>+ Create</button>
                  </div>
                </div>
              </div>

              {/* File upload */}
              <div className="kb-upload-area">
                <div className="file-upload">
                  <input type="file" multiple id="kb-file-input" accept=".txt,.md,.pdf,.py,.js,.ts,.json,.csv,.yaml,.yml"
                    onChange={e => setKbFiles(e.target.files)} />
                  <label htmlFor="kb-file-input" className="file-label kb-file-label">
                    📎 {kbFiles && kbFiles.length > 0
                      ? `${kbFiles.length} file${kbFiles.length > 1 ? 's' : ''} selected`
                      : 'Choose files to embed (txt, md, py, js, json, csv…)'}
                  </label>
                </div>
                <button className="primary" onClick={uploadKbFiles} disabled={kbLoading || !kbFiles || kbFiles.length === 0}>
                  {kbLoading ? <><span className="spinner white" /> Indexing…</> : '⬆ Embed & Index'}
                </button>
              </div>

              {/* Document list */}
              <div className="kb-docs">
                <div className="kb-docs-header">
                  <strong>Indexed Documents</strong>
                  <span className="run-count">{kbDocs.length}</span>
                  <button className="icon-btn" onClick={refreshKnowledgeBase} style={{ marginLeft: 8 }}>↻</button>
                </div>
                {kbLoading && <div className="muted">Loading…</div>}
                {!kbLoading && kbDocs.length === 0 && (
                  <div className="kb-empty">
                    <p className="muted">No documents indexed yet. Upload files above to get started.</p>
                    <p className="muted small">Tip: Enable "RAG" toggle in Chat or Agent mode to use indexed documents.</p>
                  </div>
                )}
                {kbDocs.map(doc => (
                  <div key={doc.filename} className="kb-doc-item">
                    <div className="kb-doc-info">
                      <span className="kb-doc-name">📄 {doc.filename}</span>
                      <span className="kb-doc-chunks">{doc.chunk_count} chunks</span>
                    </div>
                    <button className="agent-action-btn danger" onClick={() => deleteKbDoc(doc.filename)}>✕ Remove</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ══════════════════════ CONNECTORS TAB ══════════════════════ */}
          {mode === 'connectors' && (
            <div className="connectors-tab">
              {/* MCP Servers section */}
              <div className="connector-section">
                <div className="connector-section-header">
                  <h2>🔌 MCP Servers</h2>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="secondary" onClick={() => setAddMcpOpen(v => !v)}>
                      {addMcpOpen ? 'Cancel' : '+ Add Server'}
                    </button>
                  </div>
                </div>
                <p className="muted">Configure MCP (Model Context Protocol) servers to give agents access to tools like GitHub, web search, databases, and more.</p>

                {/* Add server form */}
                {addMcpOpen && (
                  <div className="builder">
                    <div className="builder-header"><span className="builder-icon">🔌</span><strong>Add MCP Server</strong></div>

                    {/* Presets */}
                    {mcpPresets.length > 0 && (
                      <div className="preset-grid">
                        <label className="muted small">Quick presets:</label>
                        {mcpPresets.map(preset => (
                          <button key={preset.name} className="preset-btn" onClick={() => addMcpServer(preset)}>
                            {preset.name}
                          </button>
                        ))}
                      </div>
                    )}

                    <div className="row"><label>Name</label>
                      <input value={newMcp.name} onChange={e => setNewMcp(m => ({ ...m, name: e.target.value }))} placeholder="My MCP Server" /></div>
                    <div className="row"><label>Command</label>
                      <input value={newMcp.command} onChange={e => setNewMcp(m => ({ ...m, command: e.target.value }))} placeholder="npx" /></div>
                    <div className="row"><label>Args (space-separated)</label>
                      <input value={newMcp.args} onChange={e => setNewMcp(m => ({ ...m, args: e.target.value }))} placeholder="-y @modelcontextprotocol/server-github" /></div>
                    <div className="row"><label>Env vars (KEY=VALUE, one per line)</label>
                      <textarea className="smallArea" value={newMcp.env} onChange={e => setNewMcp(m => ({ ...m, env: e.target.value }))} placeholder="GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_TOKEN}" /></div>
                    <div className="row"><label>Description</label>
                      <input value={newMcp.description} onChange={e => setNewMcp(m => ({ ...m, description: e.target.value }))} /></div>
                    <button className="primary" onClick={() => addMcpServer()} disabled={!newMcp.name || !newMcp.command}>Add Server</button>
                  </div>
                )}

                {/* Server list */}
                {mcpServers.length === 0 && !addMcpOpen && (
                  <div className="connector-empty">
                    <p className="muted">No MCP servers configured.</p>
                    <p className="muted small">Add servers like GitHub MCP, Brave Search, SQLite, or custom tools to extend agent capabilities.</p>
                  </div>
                )}
                {mcpServers.map(server => (
                  <div key={server.id} className="mcp-server-card">
                    <div className="mcp-server-header">
                      <div className="mcp-server-info">
                        <div className={mcpTools[server.id] ? 'mcp-server-status-dot connected' : 'mcp-server-status-dot'} />
                        <div>
                          <strong>{server.name}</strong>
                          {server.description && <div className="muted small">{server.description}</div>}
                          <code className="mcp-command">{server.command} {server.args.join(' ')}</code>
                        </div>
                      </div>
                      <div className="mcp-server-actions">
                        <button
                          className="secondary"
                          onClick={() => listMcpTools(server.id)}
                          disabled={mcpLoading[server.id]}
                        >
                          {mcpLoading[server.id] ? <span className="spinner" /> : '⚡ List Tools'}
                        </button>
                        <button className="agent-action-btn danger" onClick={() => deleteMcpServer(server.id)}>✕</button>
                      </div>
                    </div>

                    {mcpTools[server.id] && (
                      <div className="mcp-tools">
                        <div className="muted small" style={{ marginBottom: 6 }}>{mcpTools[server.id].length} tools available:</div>
                        <div className="mcp-tools-grid">
                          {mcpTools[server.id].map(tool => (
                            <div key={tool.name} className="mcp-tool-card">
                              <strong>{tool.name}</strong>
                              <span className="muted small">{tool.description}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* GitHub section */}
              <div className="connector-section">
                <div className="connector-section-header">
                  <h2>🐙 GitHub Connector</h2>
                  <button className="secondary" onClick={checkGitHub}>Test Connection</button>
                </div>
                {!settings.github_token ? (
                  <p className="muted">Add your GitHub Personal Access Token in <button className="link-btn" onClick={() => { setSettingsDraft(settings); setSettingsOpen(true); }}>Settings</button> to enable private repo access.</p>
                ) : githubStatus ? (
                  <div>
                    {githubStatus.ok ? (
                      <>
                        <div className="status ok" style={{ width: 'fit-content', marginBottom: 12 }}>
                          <span className="status-dot" /> Connected as {githubStatus.login}
                        </div>
                        {githubRepos.length > 0 && (
                          <div className="repo-list">
                            {githubRepos.slice(0, 20).map(repo => (
                              <div key={repo.full_name} className="repo-item">
                                <div>
                                  <strong>{repo.name}</strong>
                                  {repo.private && <span className="agent-badge" style={{ marginLeft: 6 }}>private</span>}
                                  {repo.description && <div className="muted small">{repo.description}</div>}
                                </div>
                                <button className="secondary" onClick={() => {
                                  setGithubUrl(`https://github.com/${repo.full_name}`);
                                  setMode('agent');
                                  setContextOpen(true);
                                  setSuccess(`Repo "${repo.full_name}" set as context`);
                                }}>Use Repo</button>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="error">GitHub connection failed. Check your token in Settings.</div>
                    )}
                  </div>
                ) : (
                  <p className="muted">Click "Test Connection" to verify your GitHub token and browse your repositories.</p>
                )}
              </div>
            </div>
          )}

          {/* ── Context sources (agent + studio + chat tabs) ───────────── */}
          {mode !== 'knowledge' && mode !== 'connectors' && (
            <div className="sourcePanel">
              <button className="panel-toggle" onClick={() => setContextOpen(!contextOpen)}>
                <span>Context Sources {hasContext && <span className="context-badge">●</span>}</span>
                <span className="toggle-arrow">{contextOpen ? '▲' : '▼'}</span>
              </button>
              {contextOpen && (
                <div className="panel-body">
                  <div className="grid">
                    <div className="row"><label>GitHub Repo URL</label>
                      <input placeholder="https://github.com/user/repo.git" value={githubUrl} onChange={e => setGithubUrl(e.target.value)} /></div>
                    <div className="row"><label>Branch (optional)</label>
                      <input placeholder="main" value={githubBranch} onChange={e => setGithubBranch(e.target.value)} /></div>
                  </div>
                  <div className="grid">
                    <div className="row"><label>Include Paths</label>
                      <input placeholder="backend,src,docs" value={includePaths} onChange={e => setIncludePaths(e.target.value)} /></div>
                    <div className="row"><label>Exclude Paths</label>
                      <input value={excludePaths} onChange={e => setExcludePaths(e.target.value)} /></div>
                  </div>
                  <div className="row"><label>Upload Files</label>
                    <div className="file-upload">
                      <input type="file" multiple id="file-input" onChange={e => setFiles(e.target.files)} />
                      <label htmlFor="file-input" className="file-label">
                        📎 {files && files.length > 0 ? `${files.length} file(s) selected` : 'Choose files…'}
                      </label>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Run button (agent + studio) ────────────────────────────── */}
          {(mode === 'agent' || mode === 'studio') && (
            <button className="primary" onClick={generate} disabled={loading}>
              {loading ? <><span className="spinner white" /> Running…</> : mode === 'agent' ? '⚡ Run Agent' : '🛠 Generate'}
            </button>
          )}

          {error && <div className="error"><strong>Error:</strong> {error}</div>}

          {downloadUrl && (
            <div className="download-section">
              <a className="download" href={downloadUrl}>⬇ Download {outputType.toUpperCase()} file</a>
            </div>
          )}

          {rawMarkdown && (
            <div className="preview-section">
              <div className="preview-header">
                <strong>Output Preview</strong>
                <span className="muted small">{rawMarkdown.length.toLocaleString()} chars</span>
              </div>
              <div className="preview rendered-preview" dangerouslySetInnerHTML={{ __html: renderMarkdown(rawMarkdown) }} />
            </div>
          )}
        </section>

        {/* ── Run history sidebar (agent / chat / studio tabs only) ─── */}
        {mode !== 'knowledge' && mode !== 'connectors' && <aside className="card sidecard">
          <div className="sidebar-header">
            <h2>Run History</h2>
            {runs.length > 0 && <span className="run-count">{runs.length}</span>}
          </div>
          {runs.length === 0 && <p className="muted">No agent runs yet.</p>}
          {runs.map(run => (
            <div key={run.run_id} className="run">
              <div className="run-top">
                <strong>{run.agent_name || run.agent_id}</strong>
                <span className="run-type">{run.output_type}</span>
              </div>
              <span className="run-model">{run.model}</span>
              {run.rag_sources?.length > 0 && <span className="muted small">📚 {run.rag_sources.length} RAG source(s)</span>}
              <small>{new Date(run.timestamp).toLocaleString()}</small>
              {run.download_file && (
                <a href={`${API}/download/${run.download_file}`} className="run-download">⬇ Download</a>
              )}
            </div>
          ))}
        </aside>}
      </div>
    </main>
  );
}
