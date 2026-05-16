"""
Diagnostics endpoints.

Surfaces backend health information and optional deep checks via
DiagnosticsService. The /quick endpoint is intended for lightweight polling;
the root /diagnostics endpoint runs a full battery of checks.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("agentstudio.diagnostics")

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

# ── Lazy service singleton ────────────────────────────────────────────────

_diag_svc = None


def _get_svc():
    global _diag_svc
    if _diag_svc is None:
        from services.diagnostics_service import DiagnosticsService
        _diag_svc = DiagnosticsService()
    return _diag_svc


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("")
async def run_diagnostics() -> Dict[str, Any]:
    """
    Run all diagnostics and return the results dict.

    Checks may include: backend reachability, LLM provider connectivity,
    OpenClaw gateway status, ChromaDB vector store, disk space, and
    dependency versions. Individual check failures do not raise HTTP errors —
    they are captured in the results dict under each check's key.
    """
    try:
        results = await _get_svc().run_all()
        return results
    except Exception as exc:
        logger.error("Diagnostics run failed: %s", exc)
        raise HTTPException(500, f"Diagnostics run failed: {exc}")


@router.get("/quick")
async def quick_health() -> Dict[str, Any]:
    """
    Quick health check returning only backend status and OpenClaw gateway status.
    Suitable for lightweight polling by the frontend.
    """
    try:
        result = await _get_svc().run_quick()
        return result
    except Exception as exc:
        logger.error("Quick diagnostics failed: %s", exc)
        # For a health-check endpoint, return degraded status rather than raising,
        # so callers always get a parseable response.
        return {
            "backend": {"status": "error", "error": str(exc)},
            "openclaw": {"status": "unknown"},
        }
