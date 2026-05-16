"""Tests for PermissionService.

Covers initial state, granting, denying, revoking, and persistence of
permission decisions across service instances.
"""

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from services.permission_service import PermissionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def decisions_path(tmp_path: Path) -> Path:
    """Return a path to a temporary decisions.json that does not yet exist."""
    return tmp_path / "decisions.json"


@pytest.fixture()
def policies_path(tmp_path: Path) -> Path:
    """Write a minimal policies.json and return its path."""
    policies = {
        "read_files": "allow_once",
        "write_files": "deny",
        "execute_shell": "deny",
        "network": "allow_session",
        "rag": "always_allow",
    }
    p = tmp_path / "policies.json"
    p.write_text(json.dumps(policies))
    return p


@pytest.fixture()
def service(decisions_path: Path, policies_path: Path) -> PermissionService:
    return PermissionService(
        decisions_path=decisions_path,
        policies_path=policies_path,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_initial_state_empty(self, service: PermissionService) -> None:
        """A freshly created service has no persisted decisions."""
        decisions = service.get_all_decisions()
        assert decisions == {}


class TestGrant:
    def test_grant_allows(self, service: PermissionService) -> None:
        """Granting 'network' with 'allow_session' makes check return allowed=True."""
        service.grant("network", "allow_session")
        result = service.check("network")

        assert result.allowed is True

    def test_grant_always_allow(self, service: PermissionService) -> None:
        """Granting 'rag' with 'always_allow' makes check return allowed=True."""
        service.grant("rag", "always_allow")
        result = service.check("rag")

        assert result.allowed is True

    def test_grant_persists_to_disk(
        self, service: PermissionService, decisions_path: Path
    ) -> None:
        """A granted decision is written to the decisions.json file."""
        service.grant("network", "always_allow")

        raw = json.loads(decisions_path.read_text())
        assert raw.get("network") == "always_allow"


class TestDeny:
    def test_deny_blocks(self, service: PermissionService) -> None:
        """Denying 'execute_shell' makes check return allowed=False."""
        service.deny("execute_shell")
        result = service.check("execute_shell")

        assert result.allowed is False

    def test_deny_persists_to_disk(
        self, service: PermissionService, decisions_path: Path
    ) -> None:
        """A denied decision is written to the decisions.json file."""
        service.deny("write_files")

        raw = json.loads(decisions_path.read_text())
        assert raw.get("write_files") == "deny"


class TestRevoke:
    def test_revoke_clears(self, service: PermissionService) -> None:
        """Revoking a previously granted permission removes the decision."""
        service.grant("network", "always_allow")
        service.revoke("network")

        decisions = service.get_all_decisions()
        assert "network" not in decisions

    def test_revoke_nonexistent_is_noop(self, service: PermissionService) -> None:
        """Revoking a permission that was never set does not raise."""
        service.revoke("execute_shell")  # should not raise
        assert "execute_shell" not in service.get_all_decisions()


class TestPersistence:
    def test_decisions_persist(
        self, decisions_path: Path, policies_path: Path
    ) -> None:
        """A granted decision survives creating a new PermissionService from the same file."""
        # First instance — grant a decision
        svc1 = PermissionService(
            decisions_path=decisions_path,
            policies_path=policies_path,
        )
        svc1.grant("network", "always_allow")

        # Second instance — loads from the same file
        svc2 = PermissionService(
            decisions_path=decisions_path,
            policies_path=policies_path,
        )
        result = svc2.check("network")

        assert result.allowed is True

    def test_deny_persists_across_instances(
        self, decisions_path: Path, policies_path: Path
    ) -> None:
        """A denied decision survives creating a new PermissionService instance."""
        svc1 = PermissionService(
            decisions_path=decisions_path,
            policies_path=policies_path,
        )
        svc1.deny("execute_shell")

        svc2 = PermissionService(
            decisions_path=decisions_path,
            policies_path=policies_path,
        )
        result = svc2.check("execute_shell")

        assert result.allowed is False
