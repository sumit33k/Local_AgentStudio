"""
Diagnostics Service — comprehensive system health check for Local AgentStudio.

Checks Python environment, Node.js, Ollama, Claude/OpenAI configuration,
ChromaDB, MCP servers, skills, and the OpenClaw vendor installation.

Secrets are never included in output.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agentstudio.diagnostics")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_value(settings: dict, key: str) -> bool:
    """Return True if *key* exists, is non-empty, and is not the mask string."""
    v = settings.get(key, "")
    return bool(v) and str(v).strip() not in ("", "***", "null", "None")


def _check_node_version() -> Optional[str]:
    """Return node version string or None if not found."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _count_skills(app_dir: Path) -> Dict[str, Any]:
    skills_dir = app_dir / "skills"
    count = 0
    dirs: List[str] = []

    if skills_dir.is_dir():
        for sub in skills_dir.iterdir():
            if sub.is_dir():
                dirs.append(sub.name)
                if (sub / "SKILL.md").is_file():
                    count += 1
        # Also check installed/ sub-structure
        for category in ("installed", "openclaw", "bundled"):
            cat_dir = skills_dir / category
            if cat_dir.is_dir():
                for sub in cat_dir.iterdir():
                    if sub.is_dir() and (sub / "SKILL.md").is_file():
                        count += 1

    return {"count": count, "dirs": dirs}


def _count_mcp_servers(app_dir: Path) -> int:
    mcp_config = app_dir / "mcp_configs.json"
    if not mcp_config.is_file():
        return 0
    try:
        import json
        data = json.loads(mcp_config.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data.get("servers", data))
    except (OSError, Exception):
        pass
    return 0


def _collect_log_locations(app_dir: Path) -> Dict[str, str]:
    audit_log = app_dir / "audit" / "audit.log.jsonl"
    output_dir = app_dir / "output"
    runs_dir = app_dir / "agent_runs"
    return {
        "audit_log": str(audit_log),
        "output_dir": str(output_dir),
        "agent_runs_dir": str(runs_dir),
        "backend_dir": str(app_dir),
    }


async def _check_ollama(ollama_url: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                return {"reachable": True, "models_count": len(models)}
            return {"reachable": False, "models_count": 0, "status_code": resp.status_code}
    except Exception as exc:
        return {"reachable": False, "models_count": 0, "error": type(exc).__name__}


async def _check_chromadb(app_dir: Path) -> Dict[str, Any]:
    vector_db = app_dir / "data" / "vector_db"
    try:
        import chromadb  # type: ignore
        client = await asyncio.to_thread(
            chromadb.PersistentClient,
            path=str(vector_db),
        )
        collections = await asyncio.to_thread(client.list_collections)
        return {"available": True, "collections_count": len(collections)}
    except ImportError:
        return {"available": False, "error": "chromadb not installed"}
    except Exception as exc:
        return {"available": False, "error": str(exc)[:200]}


async def _check_openclaw_gateway(gateway_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{gateway_url}/status")
            return resp.status_code < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DiagnosticsService:
    """
    Runs a comprehensive suite of health checks and returns a structured dict.

    Parameters
    ----------
    settings:
        The current application settings dict (sensitive fields may be masked).
    vendor_path:
        Path to the vendor/openclaw directory.
    """

    def __init__(self, settings: dict, vendor_path: Path) -> None:
        self.settings = settings
        self.vendor_path = vendor_path

        _services_dir = Path(__file__).parent
        self.app_dir: Path = _services_dir.parent  # backend/

        openclaw_port = settings.get("openclaw_port", 18789)
        self.openclaw_gateway_url = f"http://127.0.0.1:{openclaw_port}"

    async def run_all(self) -> dict:
        """
        Execute all diagnostic checks concurrently and return a consolidated dict.
        No secrets are included in the result.
        """
        (
            node_version,
            ollama_status,
            chromadb_status,
            openclaw_gateway_reachable,
        ) = await asyncio.gather(
            asyncio.to_thread(_check_node_version),
            _check_ollama(
                self.settings.get("ollama_base_url", "http://127.0.0.1:11434")
            ),
            _check_chromadb(self.app_dir),
            _check_openclaw_gateway(self.openclaw_gateway_url),
        )

        skills_status = await asyncio.to_thread(_count_skills, self.app_dir)
        mcp_servers_count = await asyncio.to_thread(_count_mcp_servers, self.app_dir)
        log_locations = await asyncio.to_thread(_collect_log_locations, self.app_dir)

        # OpenClaw vendor checks (sync, fast)
        vendor_present = self.vendor_path.is_dir()
        pkg_json_present = (self.vendor_path / "package.json").is_file()
        node_modules_present = (self.vendor_path / "node_modules").is_dir()

        # Configuration presence (never include the actual values)
        claude_configured = _has_value(self.settings, "claude_api_key")
        openai_configured = _has_value(self.settings, "openai_api_key")

        result = {
            "backend_health": {
                "status": "ok",
                "python_version": sys.version,
                "app_dir": str(self.app_dir),
            },
            "node_available": node_version is not None,
            "node_version": node_version,
            "ollama_status": ollama_status,
            "claude_configured": claude_configured,
            "openai_configured": openai_configured,
            "chromadb_status": chromadb_status,
            "mcp_status": {"servers_count": mcp_servers_count},
            "skills_status": skills_status,
            "openclaw_vendor_present": vendor_present,
            "openclaw_package_json_present": pkg_json_present,
            "openclaw_node_modules_present": node_modules_present,
            "openclaw_gateway_reachable": openclaw_gateway_reachable,
            "openclaw_gateway_url": self.openclaw_gateway_url,
            "recent_errors": self._collect_recent_errors(),
            "log_locations": log_locations,
            "suggested_fixes": self._suggest_fixes(
                node_version=node_version,
                ollama_status=ollama_status,
                claude_configured=claude_configured,
                openai_configured=openai_configured,
                chromadb_status=chromadb_status,
                vendor_present=vendor_present,
                pkg_json_present=pkg_json_present,
                node_modules_present=node_modules_present,
                openclaw_gateway_reachable=openclaw_gateway_reachable,
            ),
        }
        return result

    def _collect_recent_errors(self) -> List[str]:
        """Read recent error lines from the audit log (non-blocking)."""
        audit_log = self.app_dir / "audit" / "audit.log.jsonl"
        errors: List[str] = []
        if not audit_log.is_file():
            return errors
        try:
            import json as _json
            lines = audit_log.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines[-200:]):
                try:
                    rec = _json.loads(line)
                    if "error" in str(rec.get("details", {})).lower():
                        errors.append(
                            f"[{rec.get('timestamp', '')}] {rec.get('event_type', '')}: "
                            f"{str(rec.get('details', ''))[:200]}"
                        )
                        if len(errors) >= 10:
                            break
                except Exception:
                    pass
        except OSError:
            pass
        return list(reversed(errors))

    @staticmethod
    def _suggest_fixes(
        *,
        node_version: Optional[str],
        ollama_status: dict,
        claude_configured: bool,
        openai_configured: bool,
        chromadb_status: dict,
        vendor_present: bool,
        pkg_json_present: bool,
        node_modules_present: bool,
        openclaw_gateway_reachable: bool,
    ) -> List[str]:
        fixes: List[str] = []

        if not node_version:
            fixes.append(
                "Node.js not found on PATH. Install Node.js 18+ from https://nodejs.org to enable OpenClaw."
            )

        if not ollama_status.get("reachable"):
            fixes.append(
                "Ollama is not reachable. Start Ollama with `ollama serve` or install from https://ollama.ai."
            )
        elif ollama_status.get("models_count", 0) == 0:
            fixes.append(
                "Ollama is running but no models are installed. Run `ollama pull deepseek-r1:8b` to get started."
            )

        if not claude_configured and not openai_configured and not ollama_status.get("reachable"):
            fixes.append(
                "No LLM provider is configured. Add an Ollama installation, a Claude API key, or an OpenAI API key in Settings."
            )

        if not chromadb_status.get("available"):
            fixes.append(
                "ChromaDB is not available. Run `pip install chromadb` in the backend virtual environment."
            )

        if not vendor_present:
            fixes.append(
                "OpenClaw vendor directory not found at vendor/openclaw/. "
                "Initialise the submodule: `git submodule update --init --recursive`."
            )
        elif not pkg_json_present:
            fixes.append(
                "OpenClaw package.json missing in vendor/openclaw/. The submodule may be incomplete."
            )
        elif not node_modules_present:
            fixes.append(
                "OpenClaw dependencies not installed. Run `npm install` inside vendor/openclaw/."
            )
        elif not openclaw_gateway_reachable:
            fixes.append(
                "OpenClaw vendor is present but gateway is not running. "
                "Start it from the OpenClaw settings panel or via `node vendor/openclaw/openclaw.mjs gateway`."
            )

        return fixes
