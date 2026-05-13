'use client';

import { useEffect, useRef, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000` : 'http://127.0.0.1:8000');

type Agent = {
  name: string;
  description: string;
  default_output: string;
  default_skill: string;
  system_addendum?: string;
};
type AgentMap = Record<string, Agent>;
type Mode = 'agent' | 'chat' | 'studio';
type ChatMessage = { role: 'user' | 'assistant'; content: string };

/** Minimal HTML-safe markdown renderer (no external deps). */
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
    .replace(/(<li>.*?<\/li>\n?)+/gs, (m) => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

export default function Home() {
  const [mode, setMode] = useState<Mode>('agent');
  const [prompt, setPrompt] = useState('Analyze the uploaded repo or files and create an executive-ready deliverable.');
  const [skillName, setSkillName] = useState('document_writer');
  const [outputType, setOutputType] = useState('docx');
  const [model, setModel] = useState('deepseek-r1:8b');
  const [models, setModels] = useState<string[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [githubUrl, setGithubUrl] = useState('');
  const [githubBranch, setGithubBranch] = useState('');
  const [includePaths, setIncludePaths] = useState('');
  const [excludePaths, setExcludePaths] = useState('node_modules,.git,dist,build,.venv,__pycache__');
  const [files, setFiles] = useState<FileList | null>(null);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [rawMarkdown, setRawMarkdown] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [agents, setAgents] = useState<AgentMap>({});
  const [agentId, setAgentId] = useState('doc_architect');
  const [runs, setRuns] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [createPrompt, setCreatePrompt] = useState('Create an agent that analyzes a GitHub repo and produces a patent-alignment technical presentation.');
  const [creatingAgent, setCreatingAgent] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [contextOpen, setContextOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { refreshAll(); }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(''), 4000);
    return () => clearTimeout(t);
  }, [success]);

  function refreshAll() {
    fetch(`${API}/agents`).then(r => r.json()).then(d => setAgents(d.agents || {})).catch(() => {});
    fetch(`${API}/agent/runs`).then(r => r.json()).then(d => setRuns(d.runs || [])).catch(() => {});
    fetch(`${API}/health`).then(r => r.json()).then(d => setHealth(d)).catch(() => {});
    fetch(`${API}/models`).then(r => r.json()).then(d => {
      const installed: string[] = d.models || [];
      setModels(installed);
      if (installed.length && !installed.includes(model)) setModel(installed[0]);
    }).catch(() => {});
    fetch(`${API}/skills`).then(r => r.json()).then(d => setSkills(d.skills || [])).catch(() => {});
  }

  function applyAgent(id: string) {
    setAgentId(id);
    const agent = agents[id];
    if (agent) setOutputType(agent.default_output || 'md');
  }

  function appendSharedForm(form: FormData) {
    form.append('model', model);
    form.append('github_url', githubUrl);
    form.append('github_branch', githubBranch);
    form.append('include_paths', includePaths);
    form.append('exclude_paths', excludePaths);
    if (files) Array.from(files).forEach((f) => form.append('files', f));
  }

  async function createAgent() {
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
      setSuccess(`Agent "${data.agent?.name || data.agent_id}" created successfully!`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreatingAgent(false);
    }
  }

  async function generate() {
    setLoading(true);
    setError('');
    setDownloadUrl('');
    setRawMarkdown('');

    const form = new FormData();
    form.append('prompt', prompt);
    form.append('output_type', outputType);
    appendSharedForm(form);
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

  async function sendChat() {
    if (!chatInput.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content: chatInput };
    const nextHistory = [...chatMessages, userMsg];
    setChatMessages(nextHistory);
    setChatInput('');
    setLoading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('message', userMsg.content);
      form.append('agent_id', agentId);
      form.append('history_json', JSON.stringify(chatMessages));
      appendSharedForm(form);
      const res = await fetch(`${API}/chat`, { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Chat failed');
      setChatMessages([...nextHistory, { role: 'assistant', content: data.reply || '' }]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const selectedAgent = agents[agentId];
  const hasContext = !!(githubUrl || (files && files.length > 0));

  return (
    <main className="container">
      {success && <div className="toast toast-success">✓ {success}</div>}

      <div className="hero">
        <div>
          <div className="hero-badge">Local AI</div>
          <h1>Agent Studio</h1>
          <p className="muted">
            Create agents on demand, chat with context, or generate DOCX/PPTX/MD from uploads and GitHub repos.
          </p>
        </div>
        <div className="hero-actions">
          <div className={health?.ollama_ok ? 'status ok' : 'status bad'}>
            <span className="status-dot" />
            Ollama {health?.ollama_ok ? 'Connected' : 'Offline'}
          </div>
          <button className="icon-btn" onClick={refreshAll} title="Refresh data">↻</button>
        </div>
      </div>

      <div className="tabs">
        <button className={mode === 'agent'  ? 'tab active' : 'tab'} onClick={() => setMode('agent')}>
          <span className="tab-icon">⚡</span> Agent Mode
        </button>
        <button className={mode === 'chat'   ? 'tab active' : 'tab'} onClick={() => setMode('chat')}>
          <span className="tab-icon">💬</span> Chat Mode
        </button>
        <button className={mode === 'studio' ? 'tab active' : 'tab'} onClick={() => setMode('studio')}>
          <span className="tab-icon">🛠</span> Skill Studio
        </button>
      </div>

      <div className="layout">
        <section className="card maincard">

          {/* Model + agent selectors */}
          <div className="grid">
            <div className="row">
              <label>Ollama Model</label>
              <select value={model} onChange={(e) => setModel(e.target.value)}>
                {models.length === 0 && <option value={model}>{model}</option>}
                {models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="row">
              <label>Active Agent</label>
              <select value={agentId} onChange={(e) => applyAgent(e.target.value)}>
                {Object.entries(agents).map(([id, a]) => (
                  <option key={id} value={id}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Agent creator */}
          <div className="builder">
            <div className="builder-header">
              <span className="builder-icon">✨</span>
              <strong>Create Agent from Prompt</strong>
            </div>
            <div className="row">
              <textarea
                className="smallArea"
                value={createPrompt}
                onChange={(e) => setCreatePrompt(e.target.value)}
                placeholder="Describe the agent you want to create…"
              />
            </div>
            <button className="secondary" onClick={createAgent} disabled={creatingAgent}>
              {creatingAgent ? <><span className="spinner" /> Creating…</> : 'Create Agent'}
            </button>
          </div>

          {/* Agent grid (agent mode) */}
          {mode === 'agent' && (
            <>
              <label>Available Agents</label>
              <div className="agentGrid">
                {Object.entries(agents).map(([id, agent]) => (
                  <button
                    key={id}
                    className={agentId === id ? 'agent activeAgent' : 'agent'}
                    onClick={() => applyAgent(id)}
                  >
                    <div className="agent-header">
                      <strong>{agent.name}</strong>
                      <span className="agent-badge">{agent.default_output}</span>
                    </div>
                    <span>{agent.description}</span>
                  </button>
                ))}
              </div>
              {selectedAgent && (
                <p className="muted small agent-meta">
                  Skill: <strong>{selectedAgent.default_skill}</strong> · Default output: <strong>{selectedAgent.default_output.toUpperCase()}</strong>
                </p>
              )}
            </>
          )}

          {/* Skill selector (studio mode) */}
          {mode === 'studio' && (
            <div className="row">
              <label>Skill</label>
              <select value={skillName} onChange={(e) => setSkillName(e.target.value)}>
                {(skills.length
                  ? skills
                  : ['document_writer', 'presentation_writer', 'codebase_analyzer', 'patent_alignment', 'audit_report']
                ).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          )}

          {/* Chat window */}
          {mode === 'chat' ? (
            <div className="chatBox">
              <div className="chatHeader">
                <div className="chatHeader-left">
                  <span className="chat-avatar">🤖</span>
                  <div>
                    <strong>{selectedAgent ? selectedAgent.name : 'General Chat'}</strong>
                    {selectedAgent && <div className="chatHeader-sub">{selectedAgent.default_skill}</div>}
                  </div>
                </div>
                {chatMessages.length > 0 && (
                  <button className="clear-btn" onClick={() => setChatMessages([])}>Clear</button>
                )}
              </div>

              <div className="messages">
                {chatMessages.length === 0 && (
                  <div className="chat-empty">
                    <div className="chat-empty-icon">💬</div>
                    <p>Ask a question or discuss uploaded / GitHub context with the selected agent.</p>
                    <p className="muted small">Ctrl+Enter to send</p>
                  </div>
                )}
                {chatMessages.map((m, idx) => (
                  <div key={idx} className={m.role === 'user' ? 'bubble userBubble' : 'bubble assistantBubble'}>
                    <strong>{m.role === 'user' ? 'You' : (selectedAgent?.name || 'Assistant')}</strong>
                    <div dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                  </div>
                ))}
                {loading && (
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
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendChat(); }}
                />
                <button className="primary" onClick={sendChat} disabled={loading}>
                  {loading ? <span className="spinner white" /> : 'Send'}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="row">
                <label>Prompt</label>
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
              </div>
              <div className="grid">
                <div className="row">
                  <label>Output Format</label>
                  <select value={outputType} onChange={(e) => setOutputType(e.target.value)}>
                    <option value="docx">Word Document (.docx)</option>
                    <option value="pptx">PowerPoint (.pptx)</option>
                    <option value="md">Markdown (.md)</option>
                  </select>
                </div>
              </div>
            </>
          )}

          {/* Context sources (collapsible) */}
          <div className="sourcePanel">
            <button className="panel-toggle" onClick={() => setContextOpen(!contextOpen)}>
              <span>
                Context Sources
                {hasContext && <span className="context-badge">●</span>}
              </span>
              <span className="toggle-arrow">{contextOpen ? '▲' : '▼'}</span>
            </button>

            {contextOpen && (
              <div className="panel-body">
                <div className="grid">
                  <div className="row">
                    <label>GitHub Repo URL</label>
                    <input
                      placeholder="https://github.com/user/repo.git"
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                    />
                  </div>
                  <div className="row">
                    <label>Branch (optional)</label>
                    <input placeholder="main" value={githubBranch} onChange={(e) => setGithubBranch(e.target.value)} />
                  </div>
                </div>
                <div className="grid">
                  <div className="row">
                    <label>Include Paths (optional)</label>
                    <input placeholder="backend,src,docs" value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} />
                  </div>
                  <div className="row">
                    <label>Exclude Paths</label>
                    <input value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} />
                  </div>
                </div>
                <div className="row">
                  <label>Upload Files</label>
                  <div className="file-upload">
                    <input type="file" multiple id="file-input" onChange={(e) => setFiles(e.target.files)} />
                    <label htmlFor="file-input" className="file-label">
                      📎 {files && files.length > 0
                        ? `${files.length} file${files.length > 1 ? 's' : ''} selected`
                        : 'Choose files to upload…'}
                    </label>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Run / Generate button */}
          {mode !== 'chat' && (
            <button className="primary" onClick={generate} disabled={loading}>
              {loading
                ? <><span className="spinner white" /> Running…</>
                : mode === 'agent' ? '⚡ Run Agent' : '🛠 Generate'}
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
              <div className="preview">{rawMarkdown}</div>
            </div>
          )}
        </section>

        {/* Run history sidebar */}
        <aside className="card sidecard">
          <div className="sidebar-header">
            <h2>Run History</h2>
            {runs.length > 0 && <span className="run-count">{runs.length}</span>}
          </div>
          {runs.length === 0 && <p className="muted">No agent runs yet.</p>}
          {runs.map((run) => (
            <div key={run.run_id} className="run">
              <div className="run-top">
                <strong>{run.agent_name || run.agent_id}</strong>
                <span className="run-type">{run.output_type}</span>
              </div>
              <span className="run-model">{run.model}</span>
              <small>{new Date(run.timestamp).toLocaleString()}</small>
              {run.download_file && (
                <a href={`${API}/download/${run.download_file}`} className="run-download">⬇ Download</a>
              )}
            </div>
          ))}
        </aside>
      </div>
    </main>
  );
}
