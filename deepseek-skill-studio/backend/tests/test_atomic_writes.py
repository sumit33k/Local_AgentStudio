"""Tests that file writes are atomic (P1-6)."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_save_agents_is_atomic(client, agent_payload):
    """save_agents writes to a temp file first, then renames — never partial."""
    import routers.agents as ragents

    written_paths = []
    original_write = Path.write_text

    def spy_write(self, data, *args, **kwargs):
        written_paths.append(str(self))
        return original_write(self, data, *args, **kwargs)

    with patch.object(Path, "write_text", spy_write):
        client.post("/agents", json=agent_payload)

    # The write should go to a .tmp file, not directly to agents.json
    assert any(".tmp" in p for p in written_paths), (
        f"Expected a .tmp write but got: {written_paths}"
    )
    final_paths = [p for p in written_paths if not p.endswith(".tmp")]
    # No direct write to the final JSON path
    assert not any("agents.json" in p for p in final_paths), (
        "Detected a direct (non-atomic) write to agents.json"
    )


def test_save_settings_is_atomic(client):
    """save_settings must write to .tmp then rename."""
    written_paths = []
    original_write = Path.write_text

    def spy_write(self, data, *args, **kwargs):
        written_paths.append(str(self))
        return original_write(self, data, *args, **kwargs)

    with patch.object(Path, "write_text", spy_write):
        client.put("/settings", json={"ollama_model": "llama3"})

    assert any(".tmp" in p for p in written_paths), (
        "Expected atomic .tmp write for settings"
    )


def test_mcp_save_is_atomic(tmp_path):
    """McpService.save() must write to .tmp then rename."""
    from services.mcp_service import McpService

    configs_path = tmp_path / "mcp_configs.json"
    svc = McpService(configs_path)

    written_paths = []
    original_write = Path.write_text

    def spy_write(self, data, *args, **kwargs):
        written_paths.append(str(self))
        return original_write(self, data, *args, **kwargs)

    with patch.object(Path, "write_text", spy_write):
        svc.add_server("TestMCP", "npx", ["-y", "test"], {}, "test server")

    assert any(".tmp" in p for p in written_paths), (
        "Expected atomic .tmp write for mcp_configs"
    )
