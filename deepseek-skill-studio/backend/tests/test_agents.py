"""Tests for Agent CRUD endpoints."""


def test_list_agents_empty(client):
    res = client.get("/agents")
    assert res.status_code == 200
    assert res.json() == {"agents": {}}


def test_create_agent(client, agent_payload):
    res = client.post("/agents", json=agent_payload)
    assert res.status_code == 200
    body = res.json()
    assert "agent_id" in body
    assert body["agent"]["name"] == "Test Agent"


def test_get_agent(client, agent_payload):
    agent_id = client.post("/agents", json=agent_payload).json()["agent_id"]
    res = client.get(f"/agents/{agent_id}")
    assert res.status_code == 200
    assert res.json()["agent"]["name"] == "Test Agent"


def test_get_agent_not_found(client):
    res = client.get("/agents/nonexistent_agent")
    assert res.status_code == 404


def test_update_agent(client, agent_payload):
    agent_id = client.post("/agents", json=agent_payload).json()["agent_id"]
    res = client.put(f"/agents/{agent_id}", json={"name": "Updated Agent"})
    assert res.status_code == 200
    assert res.json()["agent"]["name"] == "Updated Agent"
    # Other fields preserved
    assert res.json()["agent"]["description"] == agent_payload["description"]


def test_delete_agent(client, agent_payload):
    agent_id = client.post("/agents", json=agent_payload).json()["agent_id"]
    res = client.delete(f"/agents/{agent_id}")
    assert res.status_code == 200
    assert res.json() == {"deleted": agent_id}
    # Verify gone
    assert client.get(f"/agents/{agent_id}").status_code == 404


def test_agent_slug_collision(client, agent_payload):
    """Creating two agents with the same name produces different IDs."""
    id1 = client.post("/agents", json=agent_payload).json()["agent_id"]
    id2 = client.post("/agents", json=agent_payload).json()["agent_id"]
    assert id1 != id2
    # Both exist
    assert client.get(f"/agents/{id1}").status_code == 200
    assert client.get(f"/agents/{id2}").status_code == 200


def test_allowed_tools_persisted(client):
    payload = {
        "name": "Tool Agent",
        "description": "Has specific tools",
        "default_skill": "document_writer",
        "default_output": "md",
        "allowed_tools": ["files", "github"],
    }
    agent_id = client.post("/agents", json=payload).json()["agent_id"]
    stored = client.get(f"/agents/{agent_id}").json()["agent"]
    assert stored["allowed_tools"] == ["files", "github"]
