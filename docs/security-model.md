# Security Model

Local AgentStudio Pro is a local-first application. It runs entirely on `127.0.0.1` and processes your data without sending it to third parties, except when you configure a cloud LLM provider (Claude API, OpenAI API). This document describes the permission system, skill security scanner, audit logging, and best practices.

---

## Permission System

### Permission Types

| Permission | Scope | Default policy |
|-----------|-------|---------------|
| `read_files` | Read files from the local filesystem | `allow_once` |
| `write_files` | Write or modify files on the local filesystem | `deny` |
| `execute_shell` | Run shell commands or subprocesses | `deny` |
| `network` | Make outbound HTTP/HTTPS requests | `allow_session` |
| `browser` | Control a local browser instance | `deny` |
| `github` | Access GitHub API with stored token | `allow_session` |
| `mcp_tools` | Invoke tools via MCP server | `allow_once` |
| `secrets` | Read secrets or API keys from settings | `deny` |
| `memory` | Read or write persistent memory store | `allow_session` |
| `rag` | Query the knowledge base (read-only) | `always_allow` |
| `package_install` | Install npm/pip packages | `deny` |
| `generate_files` | Write to `output/` directory | `always_allow` |
| `system_access` | Read OS-level info (env vars, process list) | `deny` |
| `openclaw_runtime` | Start/stop OpenClaw gateway subprocess | `allow_once` |
| `openclaw_gateway` | Make requests to the OpenClaw gateway | `allow_session` |
| `openclaw_sessions` | Create or join OpenClaw sessions | `allow_session` |
| `openclaw_channels` | Create or join OpenClaw channels (multi-user) | `deny` |
| `openclaw_tools` | Invoke tools exposed by the OpenClaw gateway | `allow_session` |

### Default Policies

Default policies are loaded from `backend/permissions/policies.json`. They define the starting behaviour before the user makes any explicit decision:

| Policy value | Meaning |
|-------------|---------|
| `always_allow` | Never prompt; always permitted |
| `allow_session` | Permitted for this session; prompt again on next startup |
| `allow_once` | Prompt each time this permission is required |
| `deny` | Blocked; user must explicitly grant |

---

## User Decision Flow

When a skill or tool requests a permission, the permission service checks `backend/permissions/decisions.json` for an existing decision. If no decision exists (or the decision has expired), the user is prompted:

```
┌─────────────────────────────────────────────────────────────┐
│  Permission Request                                         │
│                                                             │
│  Skill "data-analyst" is requesting:                        │
│  execute_shell — Run shell commands or subprocesses         │
│                                                             │
│  [Allow Once]  [Allow for Session]  [Always Allow]  [Deny] │
└─────────────────────────────────────────────────────────────┘
```

### Decision Values

| Decision | Key in decisions.json | Behaviour |
|----------|----------------------|-----------|
| `allow_once` | `"allow_once"` | Permitted for this single invocation; not persisted |
| `allow_session` | `"allow_session"` | Permitted until application restart; stored with `expires: null` |
| `always_allow` | `"always_allow"` | Persisted indefinitely; no further prompts |
| `deny` | `"deny"` | Blocked; persisted; no further prompts |
| `revoke` | (action, not stored) | Removes the existing decision; permission returns to default policy |

### Decision Persistence

Persisted decisions are stored in `backend/permissions/decisions.json`:

```json
{
  "network": "always_allow",
  "execute_shell": "deny",
  "openclaw_gateway": "allow_session"
}
```

`allow_once` decisions are never written to disk. `allow_session` decisions are written to disk but are cleared on next startup (identified by a session token).

---

## Skill Scanner and Risk Levels

`SkillScannerService` analyses every `SKILL.md` before it is made available to agents. See [skill-installer.md](./skill-installer.md) for the full pattern table.

### Risk Level Definitions

| Risk level | Safe to install? | User action required |
|-----------|-----------------|---------------------|
| `low` | Yes | None |
| `medium` | With caution | Warning shown; user confirms |
| `high` | Requires review | Explicit confirmation with reason displayed |
| `critical` | No | Auto-quarantined; cannot be installed without manual override |

### What Happens to a Critical Skill

1. The skill content is written to `skills/quarantined/<name>/SKILL.md`.
2. A scan report is written to `skills/quarantined/<name>/scan-report.json`.
3. The registry entry is created with `state: "quarantined"`.
4. An audit log entry is written with `event: "skill_quarantined"`.
5. The skill is not available to agents or in the skill selector UI.

To manually review and promote a quarantined skill:
1. Inspect `skills/quarantined/<name>/scan-report.json`.
2. Review the `SKILL.md` content.
3. If satisfied, use the admin API (`POST /skills/<name>/unquarantine`) or move the directory manually.
4. The scanner re-runs on promotion; a second critical finding blocks promotion.

---

## Audit Logging

All security-relevant events are appended to `backend/audit/audit.log.jsonl` as newline-delimited JSON.

### Logged Events

| Event | Logged fields |
|-------|--------------|
| `permission_requested` | permission, skill, decision, timestamp |
| `permission_granted` | permission, decision_type, timestamp |
| `permission_denied` | permission, reason, timestamp |
| `permission_revoked` | permission, timestamp |
| `skill_installed` | skill_name, source, risk_level, timestamp |
| `skill_quarantined` | skill_name, risk_level, findings, timestamp |
| `tool_invoked` | tool_name, server, permission_used, timestamp |
| `openclaw_started` | pid, port, timestamp |
| `openclaw_stopped` | pid, timestamp |
| `settings_changed` | changed_keys (values never logged), timestamp |

### Example Log Entry

```json
{"event": "skill_quarantined", "skill_name": "evil-writer", "risk_level": "critical", "findings": [{"pattern": "rm -rf /", "severity": "critical", "line": 42}], "timestamp": "2025-01-15T10:23:45Z"}
```

### What Is Never Logged

- API key values or any secret field values.
- Full file contents passed as context.
- LLM prompt or response text.
- OpenClaw session tokens.

---

## Quarantined vs Allowed Skills

```
Install request
      │
      ▼
  Scanner runs
      │
      ├─ risk_level = low ─────────────────────────► installed/  (enabled)
      │
      ├─ risk_level = medium ──► warn user ──► user confirms ──► installed/
      │                                    └─► user cancels ──► not installed
      │
      ├─ risk_level = high ────► explicit confirmation + reason shown
      │                      └─► confirmed ──► installed/  (disabled by default)
      │                      └─► rejected  ──► not installed
      │
      └─ risk_level = critical ────────────────────► quarantined/  (blocked)
```

---

## Best Practices for Local-First Security

1. **Review skills before installing.** Read the `SKILL.md` content yourself—even low-risk skills should be inspected if they come from an untrusted source.

2. **Keep `deny` for destructive permissions.** The defaults deny `execute_shell`, `write_files`, `package_install`, and `system_access`. Do not change these to `always_allow` unless you fully trust the skill.

3. **Use `allow_session` rather than `always_allow`** for permissions you only need temporarily. Session-scoped decisions expire on restart.

4. **Do not expose ports on 0.0.0.0.** The startup scripts bind all services to `127.0.0.1`. Do not override this without a firewall in place.

5. **Rotate API keys if they appear in logs.** The audit logger masks secrets, but if you believe a key was exposed (e.g. via a skill that exfiltrated it), revoke and regenerate it immediately.

6. **Review `audit.log.jsonl` periodically.** Unexpected permission grants or tool invocations may indicate a compromised skill.

7. **Pin the OpenClaw submodule.** Do not run `git submodule update --remote` automatically in CI or startup scripts. Review the changelog before updating.

8. **Keep `settings.json` gitignored.** It is excluded from version control by default. Never add it to `.gitignore` exceptions or commit it.
