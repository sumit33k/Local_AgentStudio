# Skill Installer

This document describes how skills are discovered, installed, validated, and managed in Local AgentStudio Pro.

---

## Overview

A **skill** is a prompt template (stored as `SKILL.md`) that defines how an agent should respond to a given task. The skill installer handles importing skills from multiple sources, validating them with the skill scanner, and registering them in the skill registry.

---

## How the Unified Skill System Works

Every skill, regardless of source, is normalised to the same on-disk format:

```
backend/skills/<state>/<skill-name>/
└── SKILL.md
```

The **skill registry** (`backend/skills/registry.json`) tracks metadata for every known skill:

```json
{
  "document_writer": {
    "name": "document_writer",
    "display_name": "Document Writer",
    "state": "bundled",
    "source": "bundled",
    "source_url": null,
    "risk_level": "low",
    "installed_at": "2025-01-01T00:00:00Z",
    "enabled": true,
    "openclaw_native": false,
    "checksum": "sha256:abc123..."
  }
}
```

On startup, the backend reconciles the filesystem with `registry.json`, adding missing entries and flagging orphaned directories.

---

## Supported Skill Sources

### 1. ZIP Archive

Upload a `.zip` file containing a `SKILL.md` at its root or inside a single top-level directory. The installer:
1. Extracts the archive to a temporary directory.
2. Rejects any entry whose resolved path escapes the extraction root (path-traversal protection).
3. Passes `SKILL.md` content to the skill scanner.
4. Moves the skill to `installed/` on success or `quarantined/` on critical findings.

### 2. Local Folder

Point the installer at a directory on the local filesystem containing a `SKILL.md`. Useful for development: the skill is copied (not symlinked) into `installed/` so the registry always has a stable snapshot.

### 3. GitHub URL

Provide a GitHub repository URL (optionally with `@branch` or `@tag` suffix). The installer:
1. Resolves the URL to a raw `SKILL.md` download link via the GitHub API.
2. Downloads the file content.
3. Scans it before writing anything to disk.

The GitHub token from `settings.json` is used for private repositories and to avoid rate limits. It is injected as a header, never interpolated into a URL or shell command.

### 4. Pasted SKILL.md

Paste raw Markdown text directly into the skill creator UI. The backend receives it as a string, scans it, and creates the skill directory if the scan passes.

### 5. OpenClaw Workspace

Skills defined inside an OpenClaw workspace (at `vendor/openclaw/skills/` or referenced via the gateway's skill registry API) can be imported into Local AgentStudio. The installer:
1. Reads the OpenClaw skill manifest via `GET /skills` on the gateway.
2. Downloads each `SKILL.md` from the gateway.
3. Scans and installs them under `skills/openclaw/<name>/`.
4. Marks them `openclaw_native: true` in the registry.

---

## Skill States

| State | Directory | Meaning |
|-------|-----------|---------|
| `bundled` | `skills/bundled/` | Ships with Local AgentStudio; read-only; always available |
| `installed` | `skills/installed/` | User-installed from any source; passed scanner; enabled by default |
| `enabled` | (registry flag) | Skill is available to agents; subset of installed + bundled |
| `disabled` | (registry flag) | Skill exists on disk but is excluded from agent selection |
| `openclaw_native` | `skills/openclaw/` | Imported from an OpenClaw workspace; managed by OpenClaw |
| `imported` | `skills/installed/` | Installed from external source (GitHub, ZIP, paste); `source_url` set |
| `quarantined` | `skills/quarantined/` | Failed security scan; not available to agents; preserved for review |

A skill can have multiple concurrent descriptors. For example, an `openclaw_native` skill that has been explicitly `enabled` is both `openclaw_native` and `enabled`.

---

## Skill Registry

**Location:** `backend/skills/registry.json`

The registry is the single source of truth for skill metadata. It is read on every agent run and updated after every install, enable/disable, or uninstall operation.

Registry entry fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Slug identifier (filesystem-safe) |
| `display_name` | string | Human-readable name shown in UI |
| `state` | string | One of the states listed above |
| `source` | string | `bundled`, `zip`, `folder`, `github`, `paste`, `openclaw` |
| `source_url` | string \| null | Original URL if applicable |
| `risk_level` | string | `low`, `medium`, `high`, `critical` from scanner |
| `installed_at` | ISO 8601 | When the skill was first installed |
| `enabled` | bool | Whether the skill is available to agents |
| `openclaw_native` | bool | True if managed by OpenClaw |
| `checksum` | string | SHA-256 of the SKILL.md content at install time |

---

## Skill Install Directories

```
backend/skills/
├── registry.json          Skill metadata registry
├── bundled/               Read-only bundled skills
│   ├── document_writer/
│   │   └── SKILL.md
│   └── presentation_writer/
│       └── SKILL.md
├── installed/             User-installed skills
│   └── <skill-name>/
│       └── SKILL.md
├── openclaw/              Skills imported from OpenClaw
│   └── <skill-name>/
│       └── SKILL.md
└── quarantined/           Skills that failed security scan
    └── <skill-name>/
        ├── SKILL.md
        └── scan-report.json
```

---

## Security Scanning Process

Every skill passes through `SkillScannerService` before installation. The scanner analyses the raw Markdown content for dangerous patterns.

### Pattern Categories

| Category | Examples | Default severity |
|----------|---------|-----------------|
| Shell execution | `rm -rf`, `chmod 777`, `mkfs`, `dd if=` | critical |
| Remote code execution | `curl | bash`, `wget | sh`, `eval $(...)` | high |
| Credential theft | `~/.ssh/id_rsa`, `~/.aws/credentials`, `cat /etc/passwd` | high |
| Encoded payloads | `-EncodedCommand`, `base64 -d | bash`, `frombase64` | high |
| Network exfiltration | `curl -X POST ... --data @/etc/`, `nc -e` | high |
| Suspicious paths | `/proc/self`, `/dev/mem`, `../../` | medium |
| Obfuscation | Excessive URL encoding, null-byte injection | medium |

### Risk Levels

| Level | Meaning | Auto-quarantine |
|-------|---------|----------------|
| `low` | No suspicious patterns found | No |
| `medium` | Patterns present but may be legitimate documentation | No (warning shown) |
| `high` | Patterns strongly suggest malicious intent | No (requires explicit user confirmation) |
| `critical` | Patterns that would cause immediate harm if executed | Yes |

Quarantined skills are stored in `skills/quarantined/` alongside a `scan-report.json` explaining the findings. Users can review and manually promote a quarantined skill after investigation.

---

## Mapping External Skill Formats

### ChatGPT Custom GPT Instructions

Paste the "System Prompt" / "Instructions" field content into the skill creator. The installer wraps it in a minimal `SKILL.md` template with the source noted as `paste`.

### Claude System Prompts

Same process as ChatGPT — paste the system prompt. Claude-specific formatting (XML tags, `<thinking>` blocks) is preserved as-is.

### Claude Code Slash Commands

Claude Code slash commands are Markdown files with a specific front-matter format. The installer detects the front-matter and strips it, using the `description` field as the skill's display name.

### OpenClaw Skills

OpenClaw workspace skills are imported natively via the gateway API (see "OpenClaw Workspace" source above). They appear in the UI with an "OpenClaw" badge and can be used like any other skill.
