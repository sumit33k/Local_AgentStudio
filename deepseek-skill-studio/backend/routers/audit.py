"""
Audit log endpoints.

Provides query and export access to the structured audit event log produced
by AuditService. All writes to the audit log happen via the service itself
(called from other routers); these endpoints are read-only.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

logger = logging.getLogger("agentstudio.audit")

router = APIRouter(prefix="/audit", tags=["audit"])

# ── Lazy service singleton ────────────────────────────────────────────────

_audit_svc = None


def _get_svc():
    global _audit_svc
    if _audit_svc is None:
        from services.audit_service import AuditService
        _audit_svc = AuditService()
    return _audit_svc


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/events")
async def list_audit_events(
    n: int = Query(default=100, ge=1, le=10_000, description="Number of most-recent events to return"),
    event_type: Optional[str] = Query(default=None, description="Filter by event_type (exact match)"),
) -> Dict[str, Any]:
    """
    Return the last *n* audit events, optionally filtered by event_type.
    Events are returned in reverse-chronological order (newest first).
    """
    try:
        events: List[Dict] = await _get_svc().get_events(n=n, event_type=event_type)
        return {
            "count": len(events),
            "n_requested": n,
            "event_type_filter": event_type,
            "events": events,
        }
    except Exception as exc:
        logger.error("Failed to retrieve audit events: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(500, f"Could not retrieve audit events: {exc}")


@router.get("/export")
async def export_audit_log() -> FileResponse:
    """
    Download the raw audit.log.jsonl file as an attachment.
    Each line is a JSON-encoded audit event.
    """
    try:
        log_path: Path = await _get_svc().get_log_path()
    except Exception as exc:
        logger.error("Could not locate audit log for export: %s", exc)
        from fastapi import HTTPException
        raise HTTPException(500, f"Could not locate audit log: {exc}")

    if not log_path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Audit log file not found. No events have been recorded yet.")

    return FileResponse(
        path=log_path,
        media_type="application/x-ndjson",
        filename="audit.log.jsonl",
        headers={"Content-Disposition": 'attachment; filename="audit.log.jsonl"'},
    )
