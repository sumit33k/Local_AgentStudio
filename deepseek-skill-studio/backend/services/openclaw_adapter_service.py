"""
OpenClaw Adapter Service — communicates with a running OpenClaw gateway.

All HTTP calls use httpx.AsyncClient. Connection errors are caught and
returned as dicts/lists with an "error" field so callers never see raw
exceptions from the gateway boundary.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("agentstudio.openclaw_adapter")

_SECRET_MASK = "***"


def _build_headers(token: str) -> dict:
    if token:
        return {"Authorization": f"Bearer {_SECRET_MASK if not token else token}"}
    return {}


def _real_headers(token: str) -> dict:
    """Return actual auth headers (token value not logged elsewhere)."""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


class OpenClawAdapterService:
    """
    High-level async client for the OpenClaw gateway REST API.

    Parameters
    ----------
    gateway_url:
        Base URL of the running gateway, e.g. "http://127.0.0.1:18789".
    token:
        Optional bearer token for gateway authentication.
        Never logged or included in error messages.
    """

    def __init__(self, gateway_url: str, token: str = "") -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self._token = token

    # ── Internal helpers ───────────────────────────────────────────────────

    def _client(self, timeout: float = 10.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.gateway_url,
            headers=_real_headers(self._token),
            timeout=timeout,
        )

    @staticmethod
    def _err(exc: Exception, context: str = "") -> dict:
        msg = f"{context}: {type(exc).__name__}" if context else type(exc).__name__
        logger.warning("OpenClaw adapter error — %s", msg)
        return {"error": msg}

    # ── Public API methods ─────────────────────────────────────────────────

    async def get_status(self) -> dict:
        """GET /status — gateway health."""
        try:
            async with self._client(timeout=5.0) as c:
                resp = await c.get("/status")
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            return self._err(exc, "get_status")

    async def list_sessions(self) -> list:
        """GET /api/sessions — list all sessions, normalised to list[dict]."""
        try:
            async with self._client() as c:
                resp = await c.get("/api/sessions")
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("list_sessions failed: %s", type(exc).__name__)
            return []

        if isinstance(data, list):
            return [self._normalize_session(s) for s in data]
        if isinstance(data, dict):
            # Some gateways wrap in {"sessions": [...]}
            sessions = data.get("sessions") or data.get("data") or []
            return [self._normalize_session(s) for s in sessions]
        return []

    @staticmethod
    def _normalize_session(raw: Any) -> dict:
        if not isinstance(raw, dict):
            return {"id": str(raw), "title": str(raw)}
        return {
            "id": raw.get("id") or raw.get("session_id", ""),
            "title": raw.get("title") or raw.get("name", ""),
            "created_at": raw.get("created_at") or raw.get("createdAt", ""),
            "updated_at": raw.get("updated_at") or raw.get("updatedAt", ""),
            "source": "openclaw",
        }

    async def list_skills(self) -> list:
        """
        GET /api/skills — list skills from the gateway.
        Falls back to scanning vendor/openclaw/skills/ directory.
        """
        try:
            async with self._client() as c:
                resp = await c.get("/api/skills")
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    return [self.normalize_skill(s) for s in data]
                if isinstance(data, dict):
                    skills = data.get("skills") or data.get("data") or []
                    return [self.normalize_skill(s) for s in skills]
        except Exception as exc:
            logger.info(
                "list_skills gateway call failed (%s); falling back to filesystem",
                type(exc).__name__,
            )

        # Filesystem fallback — derive vendor path from this file's location
        _services_dir = Path(__file__).parent
        _backend_dir = _services_dir.parent
        _root_dir = _backend_dir.parent.parent
        vendor_path = _root_dir / "vendor" / "openclaw"
        return self.import_workspace_skills(vendor_path)

    async def send_message(self, session_id: str, content: str) -> dict:
        """POST to the session's message endpoint."""
        if not session_id:
            return {"error": "session_id is required"}
        payload = {"content": content, "role": "user"}
        try:
            async with self._client(timeout=30.0) as c:
                resp = await c.post(f"/api/sessions/{session_id}/messages", json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            return self._err(exc, f"send_message(session={session_id})")

    async def get_session_history(self, session_id: str) -> list:
        """GET /api/sessions/{session_id}/messages."""
        if not session_id:
            return []
        try:
            async with self._client() as c:
                resp = await c.get(f"/api/sessions/{session_id}/messages")
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("messages") or []
        except Exception as exc:
            logger.warning("get_session_history failed: %s", type(exc).__name__)
            return []

    async def list_tools(self) -> list:
        """GET /api/tools — list tools available in the gateway."""
        try:
            async with self._client() as c:
                resp = await c.get("/api/tools")
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("tools") or []
        except Exception as exc:
            logger.warning("list_tools failed: %s", type(exc).__name__)
            return []

    # ── Filesystem skill import ────────────────────────────────────────────

    def import_workspace_skills(self, vendor_path: Path) -> list:
        """
        Scan vendor_path/skills/ for directories containing SKILL.md files.

        Returns a list of skill dicts with keys:
            name, content, source="openclaw", path
        """
        skills_dir = vendor_path / "skills"
        if not skills_dir.is_dir():
            logger.debug("OpenClaw skills directory not found: %s", skills_dir)
            return []

        results: list = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                results.append(
                    {
                        "name": skill_dir.name,
                        "content": content,
                        "source": "openclaw",
                        "path": str(skill_md),
                    }
                )
            except OSError as exc:
                logger.warning("Could not read %s: %s", skill_md, exc)

        logger.info("Imported %d skills from %s", len(results), skills_dir)
        return results

    # ── Skill normalisation ────────────────────────────────────────────────

    def normalize_skill(self, raw: Any) -> dict:
        """
        Map an OpenClaw gateway skill payload to Local AgentStudio format.

        OpenClaw format (observed):
            { id, name, description, prompt/content, tags, ... }

        AgentStudio format:
            { name, content, description, source }
        """
        if not isinstance(raw, dict):
            return {
                "name": str(raw),
                "content": "",
                "description": "",
                "source": "openclaw",
            }

        name = (
            raw.get("name")
            or raw.get("id")
            or raw.get("slug")
            or "unnamed"
        )
        content = (
            raw.get("content")
            or raw.get("prompt")
            or raw.get("template")
            or raw.get("body")
            or ""
        )
        description = (
            raw.get("description")
            or raw.get("summary")
            or ""
        )
        return {
            "name": name,
            "content": content,
            "description": description,
            "source": "openclaw",
            "tags": raw.get("tags") or [],
            "original": raw,
        }
