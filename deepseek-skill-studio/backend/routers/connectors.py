"""Settings + GitHub connector endpoints."""
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

APP_DIR = Path(__file__).parent.parent
SETTINGS_PATH = APP_DIR / "settings.json"

DEFAULTS: Dict[str, Any] = {
    "llm_provider": "ollama",
    "ollama_base_url": "http://127.0.0.1:11434",
    "ollama_model": "deepseek-r1:8b",
    "ollama_embedding_model": "nomic-embed-text",
    "claude_api_key": "",
    "claude_model": "claude-sonnet-4-6",
    "openai_api_key": "",
    "openai_model": "gpt-4o",
    "openai_base_url": "",
    "github_token": "",
    "rag_enabled": True,
    "rag_top_k": 5,
    "rag_chunk_size": 1000,
    "rag_chunk_overlap": 200,
}

_SENSITIVE = {"claude_api_key", "openai_api_key", "github_token"}


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return dict(DEFAULTS)
    try:
        stored = json.loads(SETTINGS_PATH.read_text())
        return {**DEFAULTS, **stored}
    except Exception:
        return dict(DEFAULTS)


def save_settings(settings: Dict[str, Any]) -> None:
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2))
    tmp.replace(SETTINGS_PATH)


def mask_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    masked = dict(settings)
    for key in _SENSITIVE:
        if masked.get(key):
            masked[key] = "***"
    return masked


# ── Settings endpoints ──────────────────────────────────────────────────

@router.get("/settings")
def get_settings():
    return mask_settings(load_settings())


class SettingsUpdate(BaseModel):
    llm_provider: str = None
    ollama_base_url: str = None
    ollama_model: str = None
    ollama_embedding_model: str = None
    claude_api_key: str = None
    claude_model: str = None
    openai_api_key: str = None
    openai_model: str = None
    openai_base_url: str = None
    github_token: str = None
    rag_enabled: bool = None
    rag_top_k: int = None
    rag_chunk_size: int = None
    rag_chunk_overlap: int = None


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    current = load_settings()
    updates = body.model_dump(exclude_none=True)
    for key, val in updates.items():
        # Don't overwrite sensitive keys with the masked placeholder
        if key in _SENSITIVE and val == "***":
            continue
        current[key] = val
    save_settings(current)
    return mask_settings(current)


# ── GitHub connector ────────────────────────────────────────────────────

def _get_github(settings: Dict):
    try:
        from github import Github, GithubException
    except ImportError:
        raise HTTPException(500, "PyGithub not installed")
    token = settings.get("github_token", "")
    if not token:
        raise HTTPException(400, "GitHub token not configured. Add it in Settings.")
    return Github(token)


@router.get("/connectors/github/status")
def github_status():
    settings = load_settings()
    gh = _get_github(settings)
    try:
        user = gh.get_user()
        return {"ok": True, "login": user.login, "name": user.name}
    except Exception:
        raise HTTPException(401, "GitHub authentication failed. Check your Personal Access Token in Settings.")


@router.get("/connectors/github/repos")
def github_repos():
    settings = load_settings()
    gh = _get_github(settings)
    try:
        user = gh.get_user()
        repos = [
            {
                "full_name": r.full_name,
                "name": r.name,
                "private": r.private,
                "description": r.description,
                "default_branch": r.default_branch,
                "url": r.html_url,
            }
            for r in user.get_repos(sort="updated")[:50]
        ]
        return {"repos": repos}
    except Exception:
        raise HTTPException(500, "Could not retrieve repositories. Check your GitHub token permissions.")


@router.get("/connectors/github/repos/{owner}/{repo}/branches")
def github_branches(owner: str, repo: str):
    settings = load_settings()
    gh = _get_github(settings)
    try:
        r = gh.get_repo(f"{owner}/{repo}")
        branches = [b.name for b in r.get_branches()]
        return {"branches": branches, "default": r.default_branch}
    except Exception:
        raise HTTPException(500, "Could not retrieve branches. Verify the repository name and token permissions.")
