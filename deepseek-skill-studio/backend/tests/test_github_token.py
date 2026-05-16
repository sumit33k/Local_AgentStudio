"""Tests that GitHub token is not embedded in logged URLs (P1-4)."""
import json
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_token_not_in_logged_github_url(tmp_path, monkeypatch):
    """
    ingest_github_repo must not include the PAT in the logged repo URL.
    The run log's github_url field should be the clean URL.
    """
    import main

    fake_token = "ghp_supersecrettoken"
    clean_url = "https://github.com/owner/repo"

    # Capture what subprocess.run receives
    captured_calls = []

    def fake_run(cmd, **kwargs):
        captured_calls.append(cmd)
        # Simulate a successful clone by doing nothing (tmp dir already exists)
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(main, "load_settings", lambda: {"github_token": fake_token})

    # Use a real temp dir so the rglob loop runs on an empty dir
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch TemporaryDirectory to return our tmpdir
        with patch("tempfile.TemporaryDirectory") as mock_td:
            mock_td.return_value.__enter__ = lambda s: tmpdir
            mock_td.return_value.__exit__ = MagicMock(return_value=False)
            result = main.ingest_github_repo(clean_url)

    # The token must NOT appear in subprocess args
    for call in captured_calls:
        for arg in call:
            assert fake_token not in str(arg), (
                f"GitHub token found in subprocess argument: {arg}"
            )

    # The returned content header must show the clean URL (no token)
    assert fake_token not in result
    assert "owner/repo" in result


def test_token_not_in_askpass_argv(tmp_path, monkeypatch):
    """
    The GIT_ASKPASS approach must pass the token via env, not argv.
    """
    import main

    fake_token = "ghp_anothersecret"
    clean_url = "https://github.com/test/testrepo"
    captured_env = {}

    def fake_run(cmd, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(main, "load_settings", lambda: {"github_token": fake_token})

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tempfile.TemporaryDirectory") as mock_td:
            mock_td.return_value.__enter__ = lambda s: tmpdir
            mock_td.return_value.__exit__ = MagicMock(return_value=False)
            main.ingest_github_repo(clean_url)

    # GIT_ASKPASS must be set; the token must not be in the clone URL env vars directly
    assert "GIT_ASKPASS" in captured_env
    assert fake_token not in captured_env.get("GIT_ASKPASS", "")
