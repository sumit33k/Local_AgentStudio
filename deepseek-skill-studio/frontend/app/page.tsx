'use client';

import { useEffect, useState } from 'react';

const API = 'http://127.0.0.1:8000';

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
  const [agents, setAgents] = useState<AgentMap>({});
  const [agentId, setAgentId] = useState('doc_architect');
  const [runs, setRuns] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [createPrompt, setCreatePrompt] = useState('Create an agent that analyzes a GitHub repo and produces a patent-alignment technical presentation.');
  const [creatingAgent, setCreatingAgent] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    refreshAll();
  }, []);

  function refreshAll() {
    fetch(`${API}/agents`).then(r => r.json()).then(d => setAgents(d.agents || {})).catch(() => {});
    fetch(`${API}/agent/runs`).then(r => r.json()).then(d => setRuns(d.runs || [])).catch(() => {});
    fetch(`${API}/health`).then(r => r.json()).then(d => setHealth(d)).catch(() => {});
    fetch(`${API}/models`).then(r => r.json()).then(d => {
      const installed = d.models || [];
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
      fetch(`${API}/agent/runs`).then(r => r.json()).then(d => setRuns(d.runs || [])).catch(() => {});
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    if (!chatInput.trim()) return;
    const userMessage: ChatMessage = { role: 'user', content: chatInput };
    const nextHistory = [...chatMessages, userMessage];
    setChatMessages(nextHistory);
    setChatInput('');
    setLoading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('message', userMessage.content);
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

  return (
    <main className="container">
      <div className="hero">
        <div>
          <h1>DeepSeek Agent Studio</h1>
          <p className="muted">Create local agents on demand, chat with selected agents, or generate DOCX, PPTX, and Markdown from uploads or GitHub repositories.</p>
        </div>
        <div className={health?.ollama_ok ? 'status ok' : 'status bad'}>
          Ollama: {health?.ollama_ok ? 'Connected' : 'Not connected'}
        </div>
      </div>

      <div className="tabs">
        <button className={mode === 'agent' ? 'active' : ''} onClick={() => setMode('agent')}>Agent Mode</button>
        <button className={mode === 'chat' ? 'active' : ''} onClick={() => setMode('chat')}>Chat Mode</button>
        <button className={mode === 'studio' ? 'active' : ''} onClick={() => setMode('studio')}>Skill Mode</button>
      </div>

      <div className="layout">
        <section className="card maincard">
          <div className="grid">
            <div className="row">
              <label>Installed Ollama Model</label>
              <select value={model} onChange={(e) => setModel(e.target.value)}>
                {models.length === 0 && <option value={model}>{model}</option>}
                {models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="row">
              <label>Selected Agent</label>
              <select value={agentId} onChange={(e) => applyAgent(e.target.value)}>
                {Object.entries(agents).map(([id, agent]) => <option key={id} value={id}>{agent.name}</option>)}
              </select>
            </div>
          </div>

          <div className="builder">
            <div className="row">
              <label>Create Agent on Demand</label>
              <textarea className="smallArea" value={createPrompt} onChange={(e) => setCreatePrompt(e.target.value)} />
            </div>
            <button className="secondary" onClick={createAgent} disabled={creatingAgent}>{creatingAgent ? 'Creating Agent...' : 'Create Agent from Prompt'}</button>
          </div>

          {mode === 'agent' && (
            <>
              <label>Available Agents</label>
              <div className="agentGrid">
                {Object.entries(agents).map(([id, agent]) => (
                  <button key={id} className={agentId === id ? 'agent activeAgent' : 'agent'} onClick={() => applyAgent(id)}>
                    <strong>{agent.name}</strong>
                    <span>{agent.description}</span>
                  </button>
                ))}
              </div>
              {selectedAgent && <p className="muted small">Uses skill: {selectedAgent.default_skill} | Default output: {selectedAgent.default_output}</p>}
            </>
          )}

          {mode === 'studio' && (
            <div className="row"><label>Skill</label><select value={skillName} onChange={(e) => setSkillName(e.target.value)}>
              {(skills.length ? skills : ['document_writer', 'presentation_writer', 'codebase_analyzer', 'patent_alignment', 'audit_report']).map((s) => <option key={s} value={s}>{s}</option>)}
            </select></div>
          )}

          {mode === 'chat' ? (
            <div className="chatBox">
              <div className="chatHeader">
                <strong>Chat Window</strong>
                <span>{selectedAgent ? `Agent: ${selectedAgent.name}` : 'General Chat'}</span>
              </div>
              <div className="messages">
                {chatMessages.length === 0 && <p className="muted">Ask a question, request analysis, or discuss uploaded/GitHub context with the selected agent.</p>}
                {chatMessages.map((m, idx) => (
                  <div key={idx} className={m.role === 'user' ? 'bubble userBubble' : 'bubble assistantBubble'}>
                    <strong>{m.role === 'user' ? 'You' : 'Agent'}</strong>
                    <div>{m.content}</div>
                  </div>
                ))}
              </div>
              <div className="chatInput">
                <textarea className="smallArea" placeholder="Type your message..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) sendChat(); }} />
                <button className="primary" onClick={sendChat} disabled={loading}>{loading ? 'Thinking...' : 'Send Chat'}</button>
              </div>
            </div>
          ) : (
            <>
              <div className="row">
                <label>Prompt</label>
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
              </div>

              <div className="grid">
                <div className="row"><label>Output</label><select value={outputType} onChange={(e) => setOutputType(e.target.value)}>
                  <option value="docx">Word Document (.docx)</option>
                  <option value="pptx">PowerPoint (.pptx)</option>
                  <option value="md">Markdown (.md)</option>
                </select></div>
              </div>
            </>
          )}

          <div className="sourcePanel">
            <h2>Context Sources</h2>
            <div className="grid">
              <div className="row"><label>GitHub Repo URL</label><input placeholder="https://github.com/user/repo.git" value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} /></div>
              <div className="row"><label>Branch Optional</label><input placeholder="main" value={githubBranch} onChange={(e) => setGithubBranch(e.target.value)} /></div>
            </div>

            <div className="grid">
              <div className="row"><label>Include Paths Optional</label><input placeholder="backend,src,docs" value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} /></div>
              <div className="row"><label>Exclude Paths</label><input value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} /></div>
            </div>

            <div className="row"><label>Upload Files</label><input type="file" multiple onChange={(e) => setFiles(e.target.files)} /></div>
          </div>

          {mode !== 'chat' && <button className="primary" onClick={generate} disabled={loading}>{loading ? 'Running...' : mode === 'agent' ? 'Run Agent' : 'Generate'}</button>}

          {error && <p className="error">{error}</p>}
          {downloadUrl && <p><a className="download" href={downloadUrl}>Download generated file</a></p>}
          {rawMarkdown && <div className="preview">{rawMarkdown}</div>}
        </section>

        <aside className="card sidecard">
          <h2>Run History</h2>
          {runs.length === 0 && <p className="muted">No agent runs yet.</p>}
          {runs.map((run) => (
            <div key={run.run_id} className="run">
              <strong>{run.agent_name || run.agent_id}</strong>
              <span>{run.output_type} | {run.model}</span>
              <small>{run.timestamp}</small>
              {run.download_file && <a href={`${API}/download/${run.download_file}`}>Download</a>}
            </div>
          ))}
        </aside>
      </div>
    </main>
  );
}
