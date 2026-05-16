# Product Structure — Local AgentStudio Pro

This document describes the high-level architecture, component breakdown, directory layout, and technology stack of Local AgentStudio Pro.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User's Browser / Desktop                    │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │         Next.js Frontend  (127.0.0.1:3000)               │  │
│   │  • Agent Studio UI    • Chat UI    • Knowledge Base UI   │  │
│   │  • Skill Manager      • Settings  • MCP Server UI        │  │
│   └─────────────────────┬────────────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────────┘
                          │ HTTP / SSE  (REST + FormData + streaming)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                FastAPI Backend  (127.0.0.1:8000)                │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ /agents  │  │ /skills  │  │ /chat    │  │ /knowledge-   │  │
│  │ /agent   │  │ /generate│  │ /health  │  │  base         │  │
│  │  /run    │  │          │  │          │  │               │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│                                                                 │
│  ┌──────────┐  ┌──────────────────┐  ┌────────────────────┐   │
│  │ /mcp/*   │  │ /openclaw/*      │  │ /settings          │   │
│  │          │  │                  │  │ /connectors/github │   │
│  └──────────┘  └──────────────────┘  └────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Services Layer                         │  │
│  │  LLMService  │  RAGService  │  MCPService                │  │
│  │  OpenClawRuntimeService     │  SkillScannerService        │  │
│  │  PermissionService          │  ConversationService        │  │
│  │  SkillInstallerService      │  AuditService               │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────┬──────────────┬───────────────┬────────────────┬─────────┘
       │              │               │                │
       ▼              ▼               ▼                ▼
  ┌─────────┐   ┌──────────┐  ┌────────────┐  ┌────────────────┐
  │ Ollama  │   │ Claude   │  │  ChromaDB  │  │ OpenClaw       │
  │ :11434  │   │  API     │  │ (embedded) │  │ Gateway        │
  │ (local) │   │ (remote) │  │            │  │ 127.0.0.1:18789│
  └─────────┘   └──────────┘  └────────────┘  └────────────────┘
                     also: OpenAI API, OpenAI-compatible providers
```

---

## Component Overview

### Next.js Frontend (port 3000)

A single-page application built with Next.js 14 and TypeScript. All UI logic lives in `app/page.tsx`. The frontend communicates with the FastAPI backend via REST, FormData (for file uploads), and Server-Sent Events (for streaming LLM output).

Key UI areas:
- **Agent Studio tab**: Configure and run agents; download generated DOCX/PPTX/MD files.
- **Chat tab**: Streaming chat with optional RAG context injection.
- **Skill Studio tab**: Generate content directly from a skill prompt without an agent.
- **Knowledge Base tab**: Upload documents, manage collections, run semantic search.
- **MCP Servers tab**: Add/remove MCP tool servers; browse and invoke tools.
- **Settings modal**: Configure LLM providers, API keys, and runtime options.
- **Context panel**: Upload files or import GitHub repository content as agent input.

### FastAPI Backend (port 8000)

A Python FastAPI application providing the REST API consumed by the frontend. Domain logic is split across routers and services:

- **Routers** handle HTTP concerns: request parsing, authentication-free access control, response shaping.
- **Services** contain business logic: LLM orchestration, vector search, MCP subprocess management, OpenClaw lifecycle, skill scanning and installation, permission enforcement, and audit logging.

Persistence is file-based: agents and skills are stored as JSON/Markdown files; ChromaDB handles vector data.

### OpenClaw Gateway (port 18789)

A Node.js process managed by `OpenClawRuntimeService`. OpenClaw provides:
- A workspace and session protocol for agent continuity across runs.
- A channel/tool abstraction that extends the MCP tool surface.
- Integration with Claude Code and other OpenClaw-compatible clients.

The gateway runs as a child process of the FastAPI backend and is bound exclusively to `127.0.0.1`.

### ChromaDB (embedded)

ChromaDB runs in-process inside the FastAPI backend (no separate server). Vector data is persisted to `backend/data/vector_db/`. It powers the RAG knowledge base: documents are chunked, embedded, and retrieved via semantic similarity search.

---

## How the Components Interact

1. **User opens the browser** at `http://127.0.0.1:3000`.
2. **Frontend fetches** available models, agents, skills, and health status from the backend.
3. **User triggers an agent run**: frontend POSTs to `/agent/run` with the prompt, agent ID, and any uploaded files.
4. **Backend resolves** the agent config, loads the skill prompt, optionally retrieves RAG context, and calls `LLMService`.
5. **LLMService** dispatches to the selected provider (Ollama / Claude / OpenAI / compatible).
6. **Streamed tokens** are returned to the frontend via SSE; on completion the output is saved to `backend/output/`.
7. **MCP tools** are invoked mid-run via `MCPService`, which manages stdio subprocesses for each configured MCP server.
8. **OpenClaw tools** are invoked via the OpenClaw gateway HTTP API when `openclaw_tools` permission is granted.
9. **Skill scanner** validates any newly installed skill before it is made available to agents.
10. **Permission service** records user decisions (allow/deny) and gates tool invocations accordingly.
11. **Audit service** appends structured log entries to `backend/audit/audit.log.jsonl` for every permission decision and tool invocation.

---

## Directory Structure

```
Local_AgentStudio/
├── CLAUDE.md                     Project instructions for Claude Code
├── docs/                         This documentation directory
│   ├── openclaw-native-integration.md
│   ├── product-structure.md
│   ├── skill-installer.md
│   ├── security-model.md
│   └── local-runtime.md
├── local-runtime/                Startup scripts and Docker Compose
│   ├── start-local-agentstudio.sh
│   ├── start-local-agentstudio.ps1
│   ├── start-openclaw-native.sh
│   ├── docker-compose.local.yml
│   └── .env.example
├── vendor/
│   └── openclaw/                 Git submodule — OpenClaw gateway
├── deepseek-skill-studio/        Main application
│   ├── backend/                  FastAPI (Python)
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── agents.py
│   │   │   ├── skills.py
│   │   │   ├── connectors.py
│   │   │   ├── rag.py
│   │   │   └── mcp_router.py
│   │   ├── services/
│   │   │   ├── llm_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── mcp_service.py
│   │   │   ├── openclaw_runtime_service.py
│   │   │   ├── openclaw_adapter_service.py
│   │   │   ├── skill_scanner_service.py   (planned)
│   │   │   ├── skill_installer_service.py (planned)
│   │   │   ├── permission_service.py      (planned)
│   │   │   └── conversation_service.py    (planned)
│   │   ├── skills/
│   │   │   ├── registry.json
│   │   │   ├── bundled/
│   │   │   ├── installed/
│   │   │   ├── openclaw/
│   │   │   └── quarantined/
│   │   ├── agents/
│   │   │   └── agents.json
│   │   ├── audit/
│   │   │   └── audit.log.jsonl
│   │   ├── permissions/
│   │   │   ├── decisions.json
│   │   │   └── policies.json
│   │   ├── conversations/
│   │   │   └── conversations.json
│   │   ├── output/              (gitignored)
│   │   ├── agent_runs/          (gitignored)
│   │   ├── data/vector_db/      (gitignored)
│   │   └── settings.json        (gitignored)
│   ├── frontend/                Next.js (TypeScript)
│   │   └── app/
│   │       ├── page.tsx
│   │       ├── layout.tsx
│   │       └── globals.css
│   └── start-mac-linux.sh
└── LocalLLM/                    Standalone Ollama chat (separate concern)
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend framework | Next.js | 14 |
| Frontend language | TypeScript | 5.x |
| Backend framework | FastAPI | 0.111+ |
| Backend language | Python | 3.10+ |
| Vector database | ChromaDB | embedded |
| LLM providers | Ollama, Claude API, OpenAI API, OpenAI-compatible | — |
| OpenClaw gateway | Node.js ESM module | 18+ |
| Persistence | JSON flat files + ChromaDB | — |
| Containerisation (optional) | Docker Compose | 2.x |
| Package manager (backend) | pip / venv | — |
| Package manager (frontend) | npm | 9+ |
