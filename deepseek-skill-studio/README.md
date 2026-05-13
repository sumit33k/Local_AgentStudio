# DeepSeek Local Skill Studio

Local UI for running Ollama + DeepSeek with reusable skills to generate DOCX, PPTX, and Markdown from prompts, uploaded files, or GitHub repositories.

## Prerequisites

Install these first:

- Ollama: https://ollama.com
- Python 3.10+
- Node.js 18+
- Git

## One-click start

### macOS / Linux

```bash
chmod +x start-mac-linux.sh
./start-mac-linux.sh
```

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start-windows.ps1
```

Open:

```text
http://localhost:3000
```

## What it does

- Runs a local FastAPI backend on port 8000
- Runs a Next.js UI on port 3000
- Connects to Ollama on port 11434
- Pulls `deepseek-r1:8b` if missing
- Lets you select skills
- Lets you upload files
- Lets you ingest public GitHub repos using repo URL
- Generates DOCX, PPTX, or Markdown output

## Skills included

- Document Writer
- Presentation Writer
- Codebase Analyzer
- Patent Alignment
- Audit Report

## Notes

For private GitHub repositories, use a local authenticated Git setup first, or clone the repo locally and upload relevant files. This starter version supports direct repo URL cloning using Git.


## Agent Studio delta

This enhanced version adds an Agent Studio layer:

- Agent templates in `backend/agents/agents.json`
- `/agents` endpoint to list available agents
- `/agent/run` endpoint to execute an agent
- `/agent/runs` endpoint to view recent run history
- Run logs saved locally in `backend/agent_runs`
- UI toggle between Skill Studio and Agent Studio
- Ollama compatibility fallback: tries `/api/chat`, then `/api/generate`
- CORS support for frontend ports `3000` and `3005`

Default agents:

1. Document Architect Agent
2. Presentation Strategist Agent
3. Codebase Analyst Agent
4. Patent Alignment Agent
5. Audit Workbench Agent

Run backend:

```bash
cd backend
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level debug
```

Run frontend on 3005:

```bash
cd frontend
npm run dev -- -p 3005
```

Open:

```text
http://localhost:3005
```
