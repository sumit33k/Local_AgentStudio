"""Shared pytest fixtures for Local AgentStudio backend tests."""
import json
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Patch paths BEFORE importing the app so tests are hermetic
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    """
    Redirect every data directory to a tmp_path subtree so tests never touch
    real output/, agent_runs/, agents/, skills/, or data/ directories.
    """
    import main as app_module

    dirs = {
        "OUTPUT_DIR": tmp_path / "output",
        "RUNS_DIR": tmp_path / "agent_runs",
        "AGENTS_DIR": tmp_path / "agents",
        "SKILLS_DIR": tmp_path / "skills",
        "VECTOR_DB_PATH": tmp_path / "vector_db",
        "SETTINGS_PATH": tmp_path / "settings.json",
        "MCP_CONFIGS_PATH": tmp_path / "mcp_configs.json",
    }
    for name, path in dirs.items():
        if name not in ("SETTINGS_PATH", "MCP_CONFIGS_PATH"):
            path.mkdir(parents=True)
        monkeypatch.setattr(app_module, name, path)

    # Also patch inside routers that cache their own copies of the paths
    import routers.agents as ragents
    import routers.connectors as rconn
    import routers.skills as rskills

    monkeypatch.setattr(ragents, "AGENTS_DIR", dirs["AGENTS_DIR"])
    monkeypatch.setattr(rconn, "SETTINGS_PATH", dirs["SETTINGS_PATH"])
    monkeypatch.setattr(rskills, "SKILLS_DIR", dirs["SKILLS_DIR"])

    yield


@pytest.fixture()
def client(_isolated_dirs):
    import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def agent_payload():
    return {
        "name": "Test Agent",
        "description": "A test agent",
        "default_skill": "document_writer",
        "default_output": "md",
        "system_addendum": "Be helpful.",
        "allowed_tools": ["files", "markdown"],
    }
