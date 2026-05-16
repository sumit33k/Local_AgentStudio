"""Tests for settings GET/PUT — sensitive field masking invariant (P1)."""


def test_settings_returns_defaults(client):
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert "llm_provider" in body
    assert body["llm_provider"] == "ollama"


def test_sensitive_fields_masked_after_save(client):
    """Saving an API key must return '***' in the response but preserve the real value."""
    client.put("/settings", json={"claude_api_key": "sk-ant-realkey123"})
    res = client.get("/settings")
    assert res.json()["claude_api_key"] == "***"


def test_masked_placeholder_does_not_overwrite_real_key(client):
    """Sending '***' for a sensitive field must NOT overwrite the stored value."""
    # First, set a real key
    client.put("/settings", json={"claude_api_key": "sk-ant-realkey123"})
    # Now send *** (as the frontend does when it re-submits settings)
    client.put("/settings", json={"claude_api_key": "***"})
    # The real key should still be there (verify by checking that settings file has it)
    import routers.connectors as rconn
    stored = rconn.load_settings()
    assert stored["claude_api_key"] == "sk-ant-realkey123"


def test_github_token_masked(client):
    client.put("/settings", json={"github_token": "ghp_realtoken"})
    res = client.get("/settings")
    assert res.json()["github_token"] == "***"


def test_non_sensitive_fields_not_masked(client):
    client.put("/settings", json={"ollama_model": "llama3.1"})
    res = client.get("/settings")
    assert res.json()["ollama_model"] == "llama3.1"


def test_rag_chunk_overlap_saved(client):
    """rag_chunk_overlap must be persisted and returned correctly."""
    client.put("/settings", json={"rag_chunk_overlap": 150})
    res = client.get("/settings")
    assert res.json()["rag_chunk_overlap"] == 150
