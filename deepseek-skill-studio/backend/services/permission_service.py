"""
Permission Service — manages user permission decisions for Local AgentStudio.

Permission decisions are persisted to decisions.json. Default policies are
read from policies.json. All file writes are atomic (tmp → replace).
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("agentstudio.permission")

# ---------------------------------------------------------------------------
# Supported permissions
# ---------------------------------------------------------------------------

PERMISSIONS: list = [
    "read_files",
    "write_files",
    "execute_shell",
    "network",
    "browser",
    "github",
    "mcp_tools",
    "secrets",
    "memory",
    "rag",
    "package_install",
    "generate_files",
    "system_access",
    "openclaw_runtime",
    "openclaw_gateway",
    "openclaw_sessions",
    "openclaw_channels",
    "openclaw_tools",
]

VALID_DURATIONS = {"once", "session", "always"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PermissionDecision:
    allowed: bool
    duration: str   # "once" | "session" | "always" | "denied"
    reason: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _load_json(path: Path, default: dict) -> dict:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load %s: %s", path, exc)
    return default


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PermissionService:
    """
    Manages fine-grained permission decisions for operations within the
    Local AgentStudio platform.

    Parameters
    ----------
    decisions_path:
        Path to decisions.json (user grant/deny records).
    policies_path:
        Path to policies.json (default policy per permission).
    """

    def __init__(self, decisions_path: Path, policies_path: Path) -> None:
        self.decisions_path = decisions_path
        self.policies_path = policies_path

        # In-memory "session" grants that are NOT persisted
        self._session_grants: Dict[str, PermissionDecision] = {}
        # One-time grants cleared after first check
        self._once_grants: Dict[str, PermissionDecision] = {}

    # ── Internal I/O ──────────────────────────────────────────────────────

    def _load_decisions(self) -> dict:
        return _load_json(self.decisions_path, {})

    def _save_decisions(self, decisions: dict) -> None:
        _atomic_write(self.decisions_path, json.dumps(decisions, indent=2))

    def _load_policies(self) -> dict:
        return _load_json(self.policies_path, {})

    # ── Public API ─────────────────────────────────────────────────────────

    def check(self, permission: str, context: str = "") -> PermissionDecision:
        """
        Check whether *permission* is currently allowed.

        Resolution order:
        1. One-time in-memory grant (consumed)
        2. Session grant (in-memory, survives until restart)
        3. Persistent "always" grant in decisions.json
        4. Persistent deny
        5. Default policy from policies.json
        6. Default deny
        """
        if permission not in PERMISSIONS:
            logger.warning("Unknown permission requested: %s", permission)
            return PermissionDecision(
                allowed=False,
                duration="denied",
                reason=f"Unknown permission: {permission}",
            )

        # 1. One-time grant
        if permission in self._once_grants:
            decision = self._once_grants.pop(permission)
            logger.info("Permission '%s' consumed (once grant)", permission)
            return decision

        # 2. Session grant
        if permission in self._session_grants:
            return self._session_grants[permission]

        # 3 & 4. Persistent decisions
        decisions = self._load_decisions()
        if permission in decisions:
            rec = decisions[permission]
            allowed = rec.get("allowed", False)
            duration = rec.get("duration", "denied")
            reason = rec.get("reason", "")
            return PermissionDecision(allowed=allowed, duration=duration, reason=reason)

        # 5. Default policy
        default = self.load_policy(permission)
        if default == "allow":
            return PermissionDecision(
                allowed=True, duration="always", reason="default policy"
            )
        if default == "deny":
            return PermissionDecision(
                allowed=False, duration="denied", reason="default policy deny"
            )

        # 6. Deny by default
        return PermissionDecision(
            allowed=False,
            duration="denied",
            reason="no policy; denied by default",
        )

    def grant(self, permission: str, duration: str, context: str = "") -> None:
        """
        Grant *permission* for the given *duration*.

        - "once"    → in-memory, consumed on next check
        - "session" → in-memory, lost on restart
        - "always"  → persisted to decisions.json
        """
        if permission not in PERMISSIONS:
            raise ValueError(f"Unknown permission: {permission}")
        if duration not in VALID_DURATIONS:
            raise ValueError(f"Invalid duration '{duration}'; must be one of {VALID_DURATIONS}")

        logger.info("Granting '%s' (duration=%s)", permission, duration)
        decision = PermissionDecision(
            allowed=True,
            duration=duration,
            reason=context or f"granted at {datetime.now(timezone.utc).isoformat()}",
        )

        if duration == "once":
            self._once_grants[permission] = decision
        elif duration == "session":
            self._session_grants[permission] = decision
        else:  # always
            decisions = self._load_decisions()
            decisions[permission] = {
                "allowed": True,
                "duration": duration,
                "reason": decision.reason,
                "granted_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_decisions(decisions)
            # Mirror into session cache for fast reads
            self._session_grants[permission] = decision

    def deny(self, permission: str, context: str = "") -> None:
        """Persistently deny *permission*."""
        if permission not in PERMISSIONS:
            raise ValueError(f"Unknown permission: {permission}")

        logger.info("Denying '%s'", permission)
        decisions = self._load_decisions()
        decisions[permission] = {
            "allowed": False,
            "duration": "denied",
            "reason": context or f"denied at {datetime.now(timezone.utc).isoformat()}",
            "denied_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_decisions(decisions)
        # Remove any session/once grants
        self._session_grants.pop(permission, None)
        self._once_grants.pop(permission, None)

    def revoke(self, permission: str) -> None:
        """Remove any persistent decision for *permission* (returns to policy default)."""
        if permission not in PERMISSIONS:
            raise ValueError(f"Unknown permission: {permission}")

        logger.info("Revoking persistent decision for '%s'", permission)
        decisions = self._load_decisions()
        decisions.pop(permission, None)
        self._save_decisions(decisions)
        self._session_grants.pop(permission, None)
        self._once_grants.pop(permission, None)

    def list_decisions(self) -> dict:
        """Return the current persistent decision map."""
        return self._load_decisions()

    def load_policy(self, permission: str) -> str:
        """
        Return the default policy string for *permission* from policies.json.

        Returns "deny" if the permission is not listed.
        """
        policies = self._load_policies()
        return policies.get(permission, "deny")
