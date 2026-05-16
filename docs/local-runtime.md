# Local Runtime

This document describes how to start Local AgentStudio Pro, what each startup script does, how to use Docker Compose, and how to troubleshoot common startup issues.

---

## Prerequisites

| Dependency | Minimum version | Required for |
|-----------|----------------|-------------|
| Python | 3.10 | FastAPI backend |
| Node.js | 18 LTS | Next.js frontend, OpenClaw gateway |
| npm | 9 | Frontend dependencies |
| Ollama | latest | Local LLM inference (optional) |
| Docker / Docker Compose | 24 / 2.x | Containerised deployment (optional) |

---

## Starting Local AgentStudio Pro

### Quick Start (macOS / Linux)

```bash
cd local-runtime
bash start-local-agentstudio.sh
```

This starts the FastAPI backend on `127.0.0.1:8000` and the Next.js frontend on `127.0.0.1:3000`. Press `Ctrl+C` to stop both.

### Quick Start (Windows)

```powershell
cd local-runtime
.\start-local-agentstudio.ps1
```

### Starting OpenClaw Gateway Separately

If you need the OpenClaw gateway independently of the main application:

```bash
cd local-runtime
bash start-openclaw-native.sh
```

The gateway starts on `127.0.0.1:18789`.

### Docker Compose

```bash
cd local-runtime
docker compose -f docker-compose.local.yml up --build
```

To run in detached mode:

```bash
docker compose -f docker-compose.local.yml up --build -d
```

To stop:

```bash
docker compose -f docker-compose.local.yml down
```

---

## Script Descriptions

### `start-local-agentstudio.sh`

**Platform:** macOS / Linux  
**Purpose:** Unified startup for development.

What it does:
1. Prints the Local AgentStudio Pro banner.
2. Checks for `python3` and `node` on PATH; prints a warning (but does not exit) if either is missing.
3. Checks for the Python virtual environment at `deepseek-skill-studio/backend/.venv`; prints a setup hint if missing.
4. Starts the FastAPI backend in the background: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`.
5. Starts the Next.js frontend in the background: `npm run dev` (Next.js respects `HOST=127.0.0.1`).
6. Traps `SIGINT` (Ctrl+C) to gracefully kill both background processes.
7. Prints the URLs: `http://127.0.0.1:3000` and `http://127.0.0.1:8000/docs`.
8. Waits for both processes, exiting when Ctrl+C is received.

Security note: The script never uses `0.0.0.0` and never passes user input to a shell expansion.

### `start-local-agentstudio.ps1`

**Platform:** Windows (PowerShell 5.1+ or PowerShell 7+)  
**Purpose:** Windows-equivalent of the bash script.

What it does:
1. Prints the banner.
2. Checks for `python` / `python3` and `node` using `Get-Command`.
3. Starts the FastAPI backend in a new PowerShell job.
4. Starts the Next.js frontend in a new PowerShell job.
5. Prints URLs and waits; pressing `Ctrl+C` stops the jobs.

### `start-openclaw-native.sh`

**Platform:** macOS / Linux  
**Purpose:** Start only the OpenClaw gateway subprocess.

What it does:
1. Checks that `node` is available.
2. Verifies that `vendor/openclaw/package.json` exists; exits with an error if not.
3. Warns if `vendor/openclaw/node_modules` is missing (run `npm install` inside `vendor/openclaw/`).
4. Starts the gateway: `node vendor/openclaw/openclaw.mjs gateway --port 18789`.
5. Binds exclusively to `127.0.0.1`.
6. Never uses `eval`, `$()`, or any dynamic shell expansion with external data.

---

## Docker Compose Option

`docker-compose.local.yml` defines three services:

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| `backend` | Built from `deepseek-skill-studio/backend` | `127.0.0.1:8000:8000` | FastAPI |
| `frontend` | Built from `deepseek-skill-studio/frontend` | `127.0.0.1:3000:3000` | Next.js |
| `openclaw` | Node.js 20 slim | `127.0.0.1:18789:18789` | OpenClaw gateway |

All ports are bound to `127.0.0.1` only — no service is reachable from the network.

### Persistent Volumes

The Compose file mounts the following host directories into the backend container so data survives container restarts:

```
deepseek-skill-studio/backend/data/       → /app/data/
deepseek-skill-studio/backend/agents/     → /app/agents/
deepseek-skill-studio/backend/skills/     → /app/skills/
deepseek-skill-studio/backend/output/     → /app/output/
deepseek-skill-studio/backend/agent_runs/ → /app/agent_runs/
deepseek-skill-studio/backend/conversations/ → /app/conversations/
deepseek-skill-studio/backend/permissions/  → /app/permissions/
deepseek-skill-studio/backend/audit/        → /app/audit/
```

`settings.json` is not mounted — configure the application via environment variables when using Docker.

---

## Environment Variables

Copy `.env.example` to `.env` in the `local-runtime/` directory before starting:

```bash
cp local-runtime/.env.example local-runtime/.env
```

Edit `.env` with your values. The startup scripts source this file automatically.

See [`.env.example`](../local-runtime/.env.example) for the full variable list with descriptions.

---

## Troubleshooting Startup Issues

### Backend fails to start: "No module named uvicorn"

The Python virtual environment is not activated or dependencies are not installed.

```bash
cd deepseek-skill-studio/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend fails to start: "Cannot find module 'next'"

Node.js dependencies are not installed.

```bash
cd deepseek-skill-studio/frontend
npm install
```

### Port 8000 already in use

Another process is using port 8000. Find and stop it:

```bash
# macOS / Linux
lsof -ti:8000 | xargs kill -9
# Windows
netstat -ano | findstr :8000
# then: taskkill /PID <pid> /F
```

### Port 3000 already in use

Same approach as port 8000, or set `PORT=3001` before starting Next.js.

### OpenClaw gateway fails: "vendor/openclaw/package.json not found"

The git submodule has not been initialised:

```bash
git submodule update --init vendor/openclaw
cd vendor/openclaw && npm install
```

### OpenClaw gateway fails: "node: command not found"

Install Node.js 18 LTS or later from https://nodejs.org.

### ChromaDB fails on first run: "sqlite3 version too old"

ChromaDB requires SQLite 3.35+. On older Ubuntu versions:

```bash
pip install pysqlite3-binary
```

Then add to the top of `main.py`:

```python
__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
```

### Frontend shows "Failed to fetch" for all API calls

The backend is not running, or `NEXT_PUBLIC_API_URL` points to the wrong address. Verify:

```bash
curl http://127.0.0.1:8000/health
```

If that fails, check the backend terminal for errors.
