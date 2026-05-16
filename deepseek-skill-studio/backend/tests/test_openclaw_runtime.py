"""Tests for OpenClawRuntimeService.

Tests cover status reporting, vendor-path detection, subprocess launch
behaviour (shell=False), and graceful handling of missing dependencies.
All tests that would start real subprocesses use unittest.mock to remain
hermetic and fast.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from services.openclaw_runtime_service import OpenClawRuntimeService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vendor_missing(tmp_path: Path) -> OpenClawRuntimeService:
    """Service pointing at a vendor path that does not exist."""
    svc = OpenClawRuntimeService(port=18789)
    svc.vendor_path = tmp_path / "does_not_exist" / "openclaw"
    return svc


@pytest.fixture()
def vendor_present(tmp_path: Path) -> OpenClawRuntimeService:
    """Service pointing at a vendor path that has package.json."""
    vendor = tmp_path / "openclaw"
    vendor.mkdir(parents=True)
    (vendor / "package.json").write_text('{"name": "openclaw", "version": "0.1.0"}')
    (vendor / "openclaw.mjs").write_text("// stub")
    (vendor / "node_modules").mkdir()

    svc = OpenClawRuntimeService(port=18789)
    svc.vendor_path = vendor
    return svc


# ---------------------------------------------------------------------------
# Tests: installation detection
# ---------------------------------------------------------------------------


class TestInstallationDetection:
    def test_missing_vendor_path_returns_not_installed(
        self, vendor_missing: OpenClawRuntimeService
    ) -> None:
        """When vendor_path does not exist, get_status() reports installed=False."""
        status = vendor_missing.get_status()
        assert status["installed"] is False

    def test_vendor_present_returns_installed(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """When vendor_path contains package.json, get_status() reports installed=True."""
        status = vendor_present.get_status()
        assert status["installed"] is True


# ---------------------------------------------------------------------------
# Tests: running state
# ---------------------------------------------------------------------------


class TestRunningState:
    def test_not_running_initially(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """A freshly created service is not running."""
        assert vendor_present.is_running() is False
        status = vendor_present.get_status()
        assert status["running"] is False
        assert status["pid"] is None


# ---------------------------------------------------------------------------
# Tests: subprocess launch safety
# ---------------------------------------------------------------------------


class TestSubprocessLaunch:
    def test_start_uses_no_shell(self, vendor_present: OpenClawRuntimeService) -> None:
        """subprocess.Popen is called with shell=False (never shell=True)."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # simulate running
        mock_process.stdout = iter([])         # empty stdout

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch.object(vendor_present, "_node_available", return_value=True), \
             patch("asyncio.get_event_loop") as mock_loop:

            mock_loop.return_value.run_in_executor.return_value = MagicMock()

            import asyncio
            asyncio.run(vendor_present._launch(
                cmd=["node", str(vendor_present.vendor_path / "openclaw.mjs"),
                     "gateway", "--port", "18789"],
                cwd=vendor_present.vendor_path,
            ))

        mock_popen.assert_called_once()
        _args, kwargs = mock_popen.call_args
        assert kwargs.get("shell") is False, (
            "subprocess.Popen must be called with shell=False"
        )

    def test_popen_receives_list_not_string(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """The command passed to Popen is a list, not a shell string."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.stdout = iter([])

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch.object(vendor_present, "_node_available", return_value=True), \
             patch("asyncio.get_event_loop") as mock_loop:

            mock_loop.return_value.run_in_executor.return_value = MagicMock()

            import asyncio
            cmd = ["node", "openclaw.mjs", "gateway", "--port", "18789"]
            asyncio.run(vendor_present._launch(cmd=cmd, cwd=vendor_present.vendor_path))

        called_cmd = mock_popen.call_args[0][0]
        assert isinstance(called_cmd, list), (
            "Command must be passed as a list to prevent shell injection"
        )


# ---------------------------------------------------------------------------
# Tests: status dict shape
# ---------------------------------------------------------------------------


class TestStatusDict:
    def test_get_status_returns_dict(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """get_status() returns a dict."""
        status = vendor_present.get_status()
        assert isinstance(status, dict)

    def test_get_status_has_expected_keys(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """get_status() includes all required keys."""
        status = vendor_present.get_status()
        expected_keys = {
            "installed",
            "vendor_path",
            "dependency_status",
            "running",
            "pid",
            "gateway_url",
            "port",
            "last_started_at",
            "last_error",
            "log_tail",
        }
        assert expected_keys.issubset(status.keys()), (
            f"Missing keys: {expected_keys - status.keys()}"
        )

    def test_get_status_port_matches_init(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """The port reported in get_status() matches the port set at init."""
        assert vendor_present.get_status()["port"] == 18789

    def test_get_status_gateway_url_is_localhost(
        self, vendor_present: OpenClawRuntimeService
    ) -> None:
        """The gateway URL is always bound to 127.0.0.1."""
        url = vendor_present.get_status()["gateway_url"]
        assert "127.0.0.1" in url, (
            f"Gateway URL should be localhost-only, got: {url}"
        )
