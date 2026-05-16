# CLAUDE.md — Local AgentStudio

> Project-specific architecture notes, commands, conventions, and safety rules for Claude Code sessions.

---

## Application Overview

**Name:** Local AgentStudio  
**Purpose:** Local-first AI agent platform supporting Ollama, Claude API, OpenAI API, and OpenAI-compatible providers. Users create agents backed by skills (prompt templates), ingest context from uploaded files or GitHub repos, run LLM-powered generation tasks, manage a RAG knowledge base, and connect MCP tool servers.  
**Repo location:** `deepseek-skill-studio/` (main app); `LocalLLM/` (standalone Ollama chat, separate concern)

---

## Architecture

```
deepseek-skill-studio/
├── backend/          FastAPI (Python 3.x)
│   ├── main.py       App entry point, core routes, helpers
│   ├── routers/      Domain-split API routers
│   │   ├── agents.py         Agent CRUD  (/agents)
│   │   ├── skills.py         Skill CRUD  (/skills)
│   │   ├── connectors.py     Settings + GitHub  (/settings, /connectors/github)
│   │   ├── rag.py            Knowledge base  (/knowledge-base)
│   │   └── mcp_router.py     MCP servers + tools  (/mcp)
│   ├── services/
│   │   ├── llm_service.py    Multi-provider LLM abstraction (Ollama/Claude/OpenAI)
│   │   ├── rag_service.py    ChromaDB vector store + chunking
│   │   └── mcp_service.py    MCP server config + stdio tool calling
│   ├── agents/agents.json    Agent definitions (file-based persistence)
│   ├── skills/{name}/SKILL.md  Skill prompt files
│   ├── output/               Generated DOCX/PPTX/MD files (gitignored)
│   ├── agent_runs/           Run logs as JSON (gitignored)
│   ├── data/vector_db/       ChromaDB persistent store (gitignored)
│   └── settings.json         User config with API keys (gitignored)
└── frontend/         Next.js 14 / TypeScript
    └── app/
        ├── page.tsx      Single-page app (1204 lines; all logic here)
        ├── layout.tsx    Root layout
        └── globals.css   Design tokens + all component styles
```

**API style:** REST + FormData for multipart uploads + SSE for streaming  
**Persistence:** Flat JSON files (agents, skills, MCP configs) + ChromaDB (vectors)  
**Auth:** None — local-first, single-user  
**LLM providers:** Ollama (local), Claude API, OpenAI API, OpenAI-compatible (switchable via settings)

---

## Common Commands

### Backend

```bash
cd deepseek-skill-studio/backend

# Install dependencies (first time)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run development server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Run tests (when they exist)
pytest tests/ -v
```

### Frontend

```bash
cd deepseek-skill-studio/frontend

# Install
npm install

# Dev server (port 3000)
npm run dev

# Production build + start
npm run build && npm run start

# Type check
npx tsc --noEmit
```

### Unified startup (macOS/Linux)

```bash
cd deepseek-skill-studio
bash start-mac-linux.sh
```

---

## API Endpoint Map

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Provider status, installed Ollama models |
| GET | /models | List Ollama models |
| POST | /chat | Streaming or non-streaming chat (FormData) |
| POST | /agent/run | Run agent → generate DOCX/PPTX/MD |
| GET | /agent/runs | List recent run history (max 50) |
| POST | /agent/create | Create agent from natural language (legacy) |
| POST | /generate | Skill-based generation (no agent) |
| GET | /download/{filename} | Download generated output file |
| GET/POST/PUT/DELETE | /agents[/{id}] | Agent CRUD |
| GET/POST/PUT/DELETE | /skills[/{name}] | Skill CRUD |
| GET/PUT | /settings | App settings (sensitive fields masked) |
| GET | /connectors/github/status | GitHub auth check |
| GET | /connectors/github/repos | List user repos |
| GET | /connectors/github/repos/{owner}/{repo}/branches | List branches |
| GET/POST/DELETE | /knowledge-base/collections[/{name}] | KB collections |
| GET/POST/DELETE | /knowledge-base/{col}/documents[/{name}] | KB documents |
| POST | /knowledge-base/{col}/search | Semantic search |
| GET/POST/PUT/DELETE | /mcp/servers[/{id}] | MCP server CRUD |
| GET | /mcp/servers/{id}/tools | List tools from server |
| GET | /mcp/tools | All tools from all servers |
| POST | /mcp/tools/call | Invoke a tool |
| GET | /mcp/presets | Built-in MCP preset templates |

---

## Frontend State Architecture

The entire app is a single React component in `app/page.tsx`. Key state groups:

- **Core:** `mode`, `model`, `models`, `skills`, `agents`, `health`
- **Agent mode:** `prompt`, `outputType`, `downloadUrl`, `rawMarkdown`, `agentId`
- **Chat mode:** `chatMessages`, `chatInput`, `streamEnabled`, `useRag`
- **Studio mode:** `skillName`, `showSkillCreator`, `newSkill*`
- **Knowledge Base:** `kbDocs`, `kbCollection`, `kbCollections`, `kbFiles`
- **Connectors:** `mcpServers`, `mcpTools`, `mcpPresets`, `githubStatus`
- **Settings:** `settings`, `settingsDraft`, `settingsOpen`
- **Context:** `githubUrl`, `githubBranch`, `files`, `contextOpen`

API base URL: `process.env.NEXT_PUBLIC_API_URL` or `window.location.hostname:8000` at runtime.

---

## Domain Language (Ubiquitous Language)

| Term | Meaning |
|------|---------|
| **Agent** | A named configuration combining a Skill, output format, system instructions, and allowed tools |
| **Skill** | A prompt template (SKILL.md) that defines how an agent should respond |
| **Run / Agent Run** | A single execution of an agent producing a downloadable output |
| **Knowledge Base (KB)** | ChromaDB-backed collection of chunked + embedded documents for RAG |
| **RAG** | Retrieval-Augmented Generation — semantic search over KB to enrich prompts |
| **Collection** | A named ChromaDB namespace within the Knowledge Base |
| **MCP Server** | An external process exposing tools via the Model Context Protocol |
| **MCP Tool** | A callable capability exposed by an MCP server (e.g., GitHub search, file read) |
| **Context** | Files uploaded or GitHub repo content provided as input to an agent or chat |
| **Provider** | LLM backend: ollama, claude, openai, or openai_compat |
| **Skill Studio** | The tab for generating output using a skill directly (without an agent) |
| **Chunk** | A text segment from a document stored in the vector DB |
| **Preset** | A pre-built MCP server configuration (GitHub MCP, Brave Search, etc.) |

---

## Coding Conventions

### Backend (Python)

- FastAPI with Pydantic models for request bodies
- Routers in `routers/`; business logic in `services/`
- Settings loaded via `load_settings()` helper; never access `settings.json` directly in routers
- Use `HTTPException(status_code, detail)` for user-facing errors
- Sensitive settings (API keys) are always masked in GET /settings responses
- File paths use `pathlib.Path` throughout
- All LLM calls go through `LLMService` — never call Ollama/Claude/OpenAI SDK directly in routes
- Async endpoints for I/O-bound work; wrap sync I/O in `asyncio.to_thread()`

### Frontend (TypeScript / React)

- TypeScript interfaces defined at top of page.tsx
- API calls use native `fetch` — always check `res.ok` before updating state
- Use `FormData` for multipart endpoints; `JSON.stringify` for JSON endpoints
- Success/error feedback: `setSuccess(msg)` / `setError(msg)` — errors should be cleared on retry
- Custom markdown renderer `renderMarkdown()` for displaying LLM output

---

## Safety Rules

### Never do these without explicit confirmation:

1. **Do not delete files in `output/` or `agent_runs/`** — these are user-generated artifacts
2. **Do not modify `settings.json`** — contains user API keys; it is gitignored
3. **Do not push API keys or tokens** — `settings.json` is gitignored by design
4. **Do not change the CORS default** without understanding the deployment context
5. **Do not add `shell=True` to subprocess calls** — injection risk
6. **Do not use sync `requests` library in async FastAPI handlers** — blocks the event loop
7. **Do not log full exception objects** that include API keys or tokens from settings

### Known security issues to fix (do not work around):

- `/download/{filename}`: path traversal vulnerability — validate path is inside OUTPUT_DIR
- GitHub token injected into git clone URL — switch to credential helper approach
- Skill/agent names from URL parameters need path traversal validation

---

## Known Architecture Gaps (as of audit)

| Gap | File | Priority |
|-----|------|----------|
| Blocking I/O in async handlers (git clone, sync requests) | main.py:154-194, 402-441 | P0 |
| Path traversal in /download/{filename} | main.py:592-597 | P0 |
| No res.ok check in deleteMcpServer | page.tsx:509-514 | P1 |
| No res.ok check in createNewCollection | page.tsx:468-478 | P1 |
| Zero test coverage | — | P1 |
| Non-atomic file writes (agents.json, settings.json, mcp_configs.json) | routers/ | P1 |
| Skill name path traversal | routers/skills.py | P1 |
| rag_chunk_overlap missing from settings UI | page.tsx settings modal | P2 |
| allowed_tools not editable in agent edit modal | page.tsx | P2 |
| page.tsx is 1204 lines — should be decomposed | page.tsx | P2 |

---

## Test Strategy (when adding tests)

```
backend/tests/
  test_agents.py        # Agent CRUD, slug collision, missing agent 404
  test_skills.py        # Skill CRUD, name sanitization, path traversal
  test_settings.py      # Masked fields not overwritten by "***"
  test_download.py      # Path traversal blocked, valid UUID works
  test_rag.py           # Upload → search round-trip
  conftest.py           # FastAPI TestClient, temp directories
```

Run with: `pytest backend/tests/ -v`

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ALLOW_ALL` | `true` | Set to `false` to restrict CORS to localhost |
| `ALLOWED_ORIGINS` | (none) | Comma-separated allowed origins (overrides CORS_ALLOW_ALL) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `deepseek-r1:8b` | Default Ollama model |
| `NEXT_PUBLIC_API_URL` | (auto) | Frontend API base URL; auto-resolves to `:8000` |

---

## Git Branches

- `main` — stable
- `claude/audit-transactions-dna-nRLSi` — audit and remediation work
