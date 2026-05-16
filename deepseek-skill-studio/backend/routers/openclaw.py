"""
OpenClaw integration endpoints.

Manages the OpenClaw gateway runtime, skill import, session proxying,
and tool discovery from the vendored OpenClaw installation.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agentstudio.openclaw")

router = APIRouter(prefix="/openclaw", tags=["openclaw"])

# ── Path constants ────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.parent
# vendor/openclaw lives three directories above the backend/ folder:
#   backend/ -> deepseek-skill-studio/ -> Local_AgentStudio/ -> repo root -> vendor/openclaw
VENDOR_PATH = (APP_DIR.parent.parent.parent / "vendor" / "openclaw").resolve()
SETTINGS_PATH = APP_DIR / "settings.json"

# ── Lazy service singletons ───────────────────────────────────────────────

_runtime_svc = None
_adapter_svc = None
_installer_svc = None
_scanner_svc = None
_audit_svc = None


def _get_runtime():
    global _runtime_svc
    if _runtime_svc is None:
        from services.openclaw_runtime_service import OpenClawRuntimeService
        _runtime_svc = OpenClawRuntimeService()
    return _runtime_svc


def _get_adapter():
    global _adapter_svc
    if _adapter_svc is None:
        from services.openclaw_adapter_service import OpenClawAdapterService
        _adapter_svc = OpenClawAdapterService()
    return _adapter_svc


def _get_installer():
    global _installer_svc
    if _installer_svc is None:
        from services.skill_installer_service import SkillInstallerService
        _installer_svc = SkillInstallerService()
    return _installer_svc


def _get_scanner():
    global _scanner_svc
    if _scanner_svc is None:
        from services.skill_scanner_service import SkillScannerService
        _scanner_svc = SkillScannerService()
    return _scanner_svc


def _get_audit():
    global _audit_svc
    if _audit_svc is None:
        from services.audit_service import AuditService
        _audit_svc = AuditService()
    return _audit_svc


# ── Settings helpers ──────────────────────────────────────────────────────

_OPENCLAW_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "vendor_path": "../../vendor/openclaw",
    "gateway_url": "http://127.0.0.1:18789",
    "gateway_port": 18789,
    "auto_start": False,
    "managed_runtime": True,
    "import_workspace_skills": True,
    "expose_sessions": True,
    "expose_tools": True,
    "sandbox_mode": "balanced",
    "log_level": "info",
}


def _load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(settings: Dict[str, Any]) -> None:
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)


def _get_openclaw_settings() -> Dict[str, Any]:
    stored = _load_settings()
    return {**_OPENCLAW_DEFAULTS, **stored.get("openclaw", {})}


def _gateway_url() -> str:
    return _get_openclaw_settings().get("gateway_url", _OPENCLAW_DEFAULTS["gateway_url"])


# ── Request / response models ─────────────────────────────────────────────

class InstallDepsRequest(BaseModel):
    confirmed: bool = False


class OpenClawSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    gateway_url: Optional[str] = None
    gateway_port: Optional[int] = None
    auto_start: Optional[bool] = None
    managed_runtime: Optional[bool] = None
    import_workspace_skills: Optional[bool] = None
    expose_sessions: Optional[bool] = None
    expose_tools: Optional[bool] = None
    sandbox_mode: Optional[str] = None
    log_level: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Return OpenClaw runtime status."""
    try:
        status = await _get_runtime().get_status()
        return status
    except Exception as exc:
        logger.warning("Could not fetch openclaw status: %s", exc)
        return {"running": False, "error": str(exc)}


@router.post("/install-dependencies")
async def install_dependencies(body: InstallDepsRequest) -> Dict[str, Any]:
    """
    Install npm dependencies for OpenClaw.
    Requires body.confirmed=true as an explicit opt-in guard.
    """
    if not body.confirmed:
        raise HTTPException(
            400,
            "Set confirmed=true in the request body to proceed with dependency installation.",
        )
    audit = _get_audit()
    try:
        result = await _get_installer().install_npm_dependencies(VENDOR_PATH)
        await audit.log(
            event_type="openclaw.install_dependencies",
            detail={"vendor_path": str(VENDOR_PATH), "result": result},
        )
        logger.info("OpenClaw npm dependencies installed")
        return {"ok": True, "detail": result}
    except Exception as exc:
        logger.error("OpenClaw dependency install failed: %s", exc)
        raise HTTPException(500, f"Dependency installation failed: {exc}")


@router.post("/start")
async def start_gateway() -> Dict[str, Any]:
    """Start the OpenClaw gateway process."""
    audit = _get_audit()
    try:
        result = await _get_runtime().start()
        await audit.log(event_type="openclaw.start", detail={"result": result})
        logger.info("OpenClaw gateway started")
        return {"ok": True, "detail": result}
    except Exception as exc:
        logger.error("OpenClaw start failed: %s", exc)
        raise HTTPException(500, f"Failed to start OpenClaw gateway: {exc}")


@router.post("/stop")
async def stop_gateway() -> Dict[str, Any]:
    """Stop the OpenClaw gateway process."""
    audit = _get_audit()
    try:
        result = await _get_runtime().stop()
        await audit.log(event_type="openclaw.stop", detail={"result": result})
        logger.info("OpenClaw gateway stopped")
        return {"ok": True, "detail": result}
    except Exception as exc:
        logger.error("OpenClaw stop failed: %s", exc)
        raise HTTPException(500, f"Failed to stop OpenClaw gateway: {exc}")


@router.post("/restart")
async def restart_gateway() -> Dict[str, Any]:
    """Restart the OpenClaw gateway process."""
    audit = _get_audit()
    try:
        result = await _get_runtime().restart()
        await audit.log(event_type="openclaw.restart", detail={"result": result})
        logger.info("OpenClaw gateway restarted")
        return {"ok": True, "detail": result}
    except Exception as exc:
        logger.error("OpenClaw restart failed: %s", exc)
        raise HTTPException(500, f"Failed to restart OpenClaw gateway: {exc}")


@router.get("/logs")
async def get_logs() -> Dict[str, Any]:
    """Return the last 100 lines of the OpenClaw log tail."""
    try:
        lines = await _get_runtime().tail_logs(n=100)
        return {"lines": lines}
    except Exception as exc:
        logger.warning("Could not retrieve openclaw logs: %s", exc)
        return {"lines": [], "error": str(exc)}


@router.get("/settings")
def get_openclaw_settings() -> Dict[str, Any]:
    """Return the openclaw section of main settings (with defaults applied)."""
    return _get_openclaw_settings()


@router.put("/settings")
def update_openclaw_settings(body: OpenClawSettingsUpdate) -> Dict[str, Any]:
    """Merge provided values into the openclaw settings section."""
    all_settings = _load_settings()
    current_oc = _get_openclaw_settings()
    updates = body.model_dump(exclude_none=True)
    merged = {**current_oc, **updates}
    all_settings["openclaw"] = merged
    _save_settings(all_settings)
    return merged


@router.get("/skills")
async def list_openclaw_skills() -> Dict[str, Any]:
    """List skills found in vendor/openclaw/skills/."""
    skills_path = VENDOR_PATH / "skills"
    if not skills_path.exists():
        return {"skills": [], "vendor_path": str(VENDOR_PATH), "skills_dir_exists": False}
    try:
        skills = await _get_scanner().scan_directory(skills_path)
        return {"skills": skills, "vendor_path": str(VENDOR_PATH), "skills_dir_exists": True}
    except Exception as exc:
        logger.error("Skill scan failed: %s", exc)
        raise HTTPException(500, f"Failed to scan openclaw skills: {exc}")


@router.post("/import-skills")
async def import_openclaw_skills() -> Dict[str, Any]:
    """Scan vendor/openclaw/skills/ then import them into Local AgentStudio."""
    audit = _get_audit()
    skills_path = VENDOR_PATH / "skills"
    if not skills_path.exists():
        raise HTTPException(
            404,
            f"OpenClaw skills directory not found: {skills_path}. "
            "Ensure the vendor/openclaw directory is present.",
        )
    try:
        scanned = await _get_scanner().scan_directory(skills_path)
        result = await _get_installer().import_skills(scanned)
        await audit.log(
            event_type="openclaw.import_skills",
            detail={"scanned": len(scanned), "imported": result.get("imported", 0)},
        )
        logger.info("Imported %s OpenClaw skill(s)", result.get("imported", 0))
        return {"ok": True, "scanned": len(scanned), **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Skill import failed: %s", exc)
        raise HTTPException(500, f"Skill import failed: {exc}")


@router.get("/sessions")
async def list_sessions() -> Dict[str, Any]:
    """List active sessions from the OpenClaw gateway, or return empty if offline."""
    try:
        sessions = await _get_adapter().list_sessions(_gateway_url())
        return {"sessions": sessions}
    except Exception as exc:
        logger.warning("Could not list openclaw sessions (gateway may be offline): %s", exc)
        return {"sessions": [], "gateway_offline": True, "error": str(exc)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Get details for a single OpenClaw session."""
    try:
        session = await _get_adapter().get_session(_gateway_url(), session_id)
        if session is None:
            raise HTTPException(404, f"Session not found: {session_id}")
        return session
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Could not retrieve session %s: %s", session_id, exc)
        raise HTTPException(500, f"Failed to retrieve session: {exc}")


@router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, body: SendMessageRequest) -> Dict[str, Any]:
    """Send a message to an OpenClaw session."""
    if not body.content or not body.content.strip():
        raise HTTPException(400, "Message content must not be empty.")
    try:
        response = await _get_adapter().send_message(
            _gateway_url(), session_id, body.content
        )
        return {"ok": True, "response": response}
    except Exception as exc:
        logger.error("Failed to send message to session %s: %s", session_id, exc)
        raise HTTPException(500, f"Failed to send message: {exc}")


@router.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """List all tools exposed by the OpenClaw gateway."""
    try:
        tools = await _get_adapter().list_tools(_gateway_url())
        return {"tools": tools}
    except Exception as exc:
        logger.warning("Could not list openclaw tools (gateway may be offline): %s", exc)
        return {"tools": [], "gateway_offline": True, "error": str(exc)}


@router.get("/diagnostics")
async def run_diagnostics() -> Dict[str, Any]:
    """Run diagnostics against OpenClaw runtime and return the results dict."""
    from services.diagnostics_service import DiagnosticsService
    svc = DiagnosticsService()
    try:
        results = await svc.run_openclaw_diagnostics(VENDOR_PATH, _gateway_url())
        return results
    except Exception as exc:
        logger.error("Diagnostics failed: %s", exc)
        raise HTTPException(500, f"Diagnostics failed: {exc}")
