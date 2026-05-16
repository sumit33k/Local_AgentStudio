# OpenClaw Native Integration

This document describes how Local AgentStudio Pro embeds OpenClaw as a native runtime, how the two systems are configured together, and what security measures apply.

---

## Overview

Local AgentStudio Pro ships OpenClaw as a **git submodule** vendored at `vendor/openclaw/`. The FastAPI backend manages the OpenClaw gateway subprocess through `OpenClawRuntimeService`, meaning users do not need to install or configure OpenClaw separately—it starts automatically alongside the main application.

---

## Vendoring OpenClaw as a Git Submodule

The submodule is declared in `.gitmodules` and lives at:

```
Local_AgentStudio/
└── vendor/
    └── openclaw/          ← git submodule
        ├── package.json
        ├── openclaw.mjs
        └── node_modules/  (populated after npm install)
```

### Initial Setup

When cloning the repository for the first time, initialise the submodule:

```bash
git clone --recurse-submodules <repo-url>
# or, if already cloned without --recurse-submodules:
git submodule update --init vendor/openclaw
```

Then install Node.js dependencies for the gateway:

```bash
cd vendor/openclaw
npm install
```

### Updating OpenClaw

To pull the latest pinned version of the OpenClaw submodule:

```bash
git submodule update --remote vendor/openclaw
```

This advances the submodule pointer to the latest commit on its tracking branch. Commit the updated pointer so other contributors receive the same version:

```bash
git add vendor/openclaw
git commit -m "chore: update openclaw submodule to latest"
```

---

## Runtime Manager Service

`deepseek-skill-studio/backend/services/openclaw_runtime_service.py` implements `OpenClawRuntimeService`, which:

1. **Resolves the vendor path** by walking up from `services/` → `backend/` → `deepseek-skill-studio/` → `Local_AgentStudio/` → `vendor/openclaw/`.
2. **Checks installation** by testing for `vendor/openclaw/package.json`.
3. **Starts the gateway** using `subprocess.Popen` with `shell=False`:
   - Primary: `node vendor/openclaw/openclaw.mjs gateway --port 18789`
   - Fallback: `npx openclaw gateway --port 18789`
4. **Drains logs** from stdout/stderr into an in-memory ring buffer (500 lines) with basic secret masking before storage.
5. **Stops the gateway** with `SIGTERM` (5-second grace period, then `SIGKILL`).
6. **Health checks** by `GET /status` against the gateway URL.

The service is instantiated once at application startup and exposed via the `/openclaw/*` API routes.

---

## Port Assignments

| Service              | Bind address    | Port  | Protocol |
|----------------------|-----------------|-------|----------|
| FastAPI backend      | 127.0.0.1       | 8000  | HTTP     |
| Next.js frontend     | 127.0.0.1       | 3000  | HTTP     |
| OpenClaw gateway     | 127.0.0.1       | 18789 | HTTP     |

All three services bind exclusively to the loopback interface. No port is exposed on `0.0.0.0` in development mode.

---

## Log Locations

| Source           | Where to find logs                                               |
|------------------|------------------------------------------------------------------|
| FastAPI backend  | Terminal where `uvicorn` was started                             |
| OpenClaw gateway | `GET /openclaw/logs` endpoint (returns the last 50 log lines)   |
| Frontend (Next)  | Terminal where `npm run dev` was started                         |

The `/openclaw/logs` endpoint streams the in-memory ring buffer held by `OpenClawRuntimeService`. Logs are not written to disk by default; restart the application to reset the buffer.

### Enabling Persistent OpenClaw Logs

Set `OPENCLAW_STATE_DIR` to a writable path (e.g. `~/.openclaw`) and OpenClaw will write its own log files there:

```
~/.openclaw/
├── gateway.log
└── sessions/
```

---

## Settings Mapping

Local AgentStudio settings (`backend/settings.json`) are mapped to OpenClaw gateway environment variables at startup:

| Local AgentStudio setting | OpenClaw env var          | Notes                                      |
|---------------------------|---------------------------|--------------------------------------------|
| `openclaw_gateway_port`   | `OPENCLAW_PORT`           | Defaults to 18789                          |
| `openclaw_state_dir`      | `OPENCLAW_STATE_DIR`      | Defaults to `~/.openclaw`                  |
| `ollama_base_url`         | `OLLAMA_BASE_URL`         | Passed through for model resolution        |
| `claude_api_key`          | `ANTHROPIC_API_KEY`       | Never logged; masked in status responses   |
| `openai_api_key`          | `OPENAI_API_KEY`          | Never logged; masked in status responses   |

API keys are injected into the subprocess environment at launch time and never stored in the OpenClaw state directory.

---

## Security Considerations

- **Loopback-only binding**: OpenClaw gateway listens on `127.0.0.1:18789` only. It is never reachable from the network without an explicit port-forwarding rule.
- **No `shell=True`**: The gateway is launched via `subprocess.Popen` with `shell=False`. All arguments are passed as a list; no user input is interpolated into the command.
- **Log masking**: Bearer tokens and `key=value` patterns matching secret keywords are replaced with `***` before lines enter the log buffer.
- **API keys in env only**: Sensitive values are passed in the subprocess environment, not as command-line arguments (which would appear in `ps` output).
- **Submodule pinning**: The submodule is pinned to a specific commit, preventing supply-chain updates from arriving without a deliberate `git submodule update --remote` and code review.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `installed=False` in `/openclaw/status` | `vendor/openclaw/package.json` missing | Run `git submodule update --init vendor/openclaw` |
| `dependency_status=missing` | `node_modules` absent | Run `npm install` inside `vendor/openclaw/` |
| `running=False` after start | `node` not on PATH | Install Node.js 18+ |
| Gateway returns 503 | Port 18789 already in use | Change `OPENCLAW_GATEWAY_PORT` in `.env` |
| Logs show `SIGKILL` | Gateway did not respond to SIGTERM in 5s | Check gateway stderr for crash details |
