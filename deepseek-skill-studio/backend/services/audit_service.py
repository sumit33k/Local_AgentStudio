"""
Audit Service — append-only JSONL audit log for security-relevant events.

Log file: deepseek-skill-studio/backend/audit/audit.log.jsonl

All writes are append-only. Secret values in the *details* dict are
automatically masked before persistence.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("agentstudio.audit")

# Keys whose values must be redacted
_SECRET_KEY_FRAGMENTS = {"token", "key", "password", "secret", "api_key", "auth", "credential"}

VALID_EVENT_TYPES = {
    "openclaw_start",
    "openclaw_stop",
    "dependency_install",
    "skill_import",
    "skill_scan",
    "permission_decision",
    "tool_call",
    "mcp_tool_call",
    "openclaw_session_message",
    "file_write",
    "generated_output",
}


# ---------------------------------------------------------------------------
# Masking helper
# ---------------------------------------------------------------------------


def _mask_secrets(obj: Any, _depth: int = 0) -> Any:
    """
    Recursively mask values whose dict-key name suggests a secret.

    Limits recursion to 8 levels to avoid unbounded work.
    """
    if _depth > 8:
        return obj

    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(frag in k_lower for frag in _SECRET_KEY_FRAGMENTS):
                out[k] = "***"
            else:
                out[k] = _mask_secrets(v, _depth + 1)
        return out

    if isinstance(obj, list):
        return [_mask_secrets(item, _depth + 1) for item in obj]

    return obj


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AuditService:
    """
    Writes audit events as newline-delimited JSON to *log_path*.

    Usage::

        audit = AuditService(Path("backend/audit/audit.log.jsonl"))
        audit.log("skill_scan", {"name": "my-skill", "risk": "low"})
        recent = audit.get_recent(50)
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Write ──────────────────────────────────────────────────────────────

    def log(
        self,
        event_type: str,
        details: Dict[str, Any],
        user: str = "local",
    ) -> None:
        """
        Append one JSONL event record.

        Secrets are masked before writing. Unknown event types are accepted
        but logged at WARNING level.
        """
        if event_type not in VALID_EVENT_TYPES:
            logger.warning("Audit: unrecognised event_type '%s'", event_type)

        safe_details = _mask_secrets(details)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user": user,
            "details": safe_details,
        }

        try:
            line = json.dumps(record, ensure_ascii=False, default=str)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.error("Failed to write audit log: %s", exc)

    # ── Read ───────────────────────────────────────────────────────────────

    def get_recent(self, n: int = 100) -> List[dict]:
        """
        Return the last *n* parsed JSONL records from the audit log.

        Lines that cannot be parsed as JSON are silently skipped.
        """
        if not self.log_path.is_file():
            return []

        try:
            raw_lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.warning("Could not read audit log: %s", exc)
            return []

        # Take last n lines
        tail = raw_lines[-n:] if len(raw_lines) > n else raw_lines
        results: List[dict] = []
        for line in tail:
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass

        return results
