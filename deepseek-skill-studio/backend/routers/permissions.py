"""
Permission management endpoints.

Tracks grant/deny decisions for named permissions, backed by flat JSON files
under backend/permissions/. Also exposes the policy catalogue.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agentstudio.permissions")

router = APIRouter(prefix="/permissions", tags=["permissions"])

# ── Paths ─────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.parent
PERMISSIONS_DIR = APP_DIR / "permissions"
DECISIONS_PATH = PERMISSIONS_DIR / "decisions.json"
POLICIES_PATH = PERMISSIONS_DIR / "policies.json"

# ── Lazy service singleton ────────────────────────────────────────────────

_permission_svc = None


def _get_svc():
    global _permission_svc
    if _permission_svc is None:
        from services.permission_service import PermissionService
        _permission_svc = PermissionService(
            decisions_path=DECISIONS_PATH,
            policies_path=POLICIES_PATH,
        )
    return _permission_svc


# ── Request models ────────────────────────────────────────────────────────

class GrantRequest(BaseModel):
    duration: Literal["once", "session", "always"]
    context: Optional[str] = None


class DenyRequest(BaseModel):
    context: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("")
async def list_permissions() -> Dict[str, Any]:
    """List all current permission decisions."""
    try:
        decisions = await _get_svc().list_decisions()
        return {"decisions": decisions}
    except Exception as exc:
        logger.error("Failed to list permissions: %s", exc)
        raise HTTPException(500, f"Could not load permission decisions: {exc}")


@router.get("/policies")
async def get_policies() -> Dict[str, Any]:
    """Return all default permission policies."""
    try:
        policies = await _get_svc().get_policies()
        return {"policies": policies}
    except Exception as exc:
        logger.error("Failed to load policies: %s", exc)
        raise HTTPException(500, f"Could not load permission policies: {exc}")


@router.get("/{permission}")
async def get_permission(permission: str) -> Dict[str, Any]:
    """Return the current decision for a single named permission."""
    try:
        decision = await _get_svc().get_decision(permission)
        if decision is None:
            raise HTTPException(404, f"No decision recorded for permission: {permission!r}")
        return {"permission": permission, "decision": decision}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get permission %r: %s", permission, exc)
        raise HTTPException(500, f"Could not retrieve permission decision: {exc}")


@router.post("/{permission}/grant")
async def grant_permission(permission: str, body: GrantRequest) -> Dict[str, Any]:
    """Grant a named permission for the specified duration."""
    if not permission.strip():
        raise HTTPException(400, "Permission name must not be empty.")
    try:
        result = await _get_svc().grant(
            permission=permission,
            duration=body.duration,
            context=body.context,
        )
        logger.info("Permission granted: %r (duration=%s)", permission, body.duration)
        return {"ok": True, "permission": permission, "decision": result}
    except Exception as exc:
        logger.error("Failed to grant permission %r: %s", permission, exc)
        raise HTTPException(500, f"Could not grant permission: {exc}")


@router.post("/{permission}/deny")
async def deny_permission(permission: str, body: DenyRequest) -> Dict[str, Any]:
    """Deny a named permission."""
    if not permission.strip():
        raise HTTPException(400, "Permission name must not be empty.")
    try:
        result = await _get_svc().deny(
            permission=permission,
            context=body.context,
        )
        logger.info("Permission denied: %r", permission)
        return {"ok": True, "permission": permission, "decision": result}
    except Exception as exc:
        logger.error("Failed to deny permission %r: %s", permission, exc)
        raise HTTPException(500, f"Could not deny permission: {exc}")


@router.delete("/{permission}")
async def revoke_permission(permission: str) -> Dict[str, Any]:
    """Revoke (remove) the decision for a named permission."""
    if not permission.strip():
        raise HTTPException(400, "Permission name must not be empty.")
    try:
        removed = await _get_svc().revoke(permission)
        if not removed:
            raise HTTPException(404, f"No decision found for permission: {permission!r}")
        logger.info("Permission revoked: %r", permission)
        return {"ok": True, "permission": permission}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to revoke permission %r: %s", permission, exc)
        raise HTTPException(500, f"Could not revoke permission: {exc}")
