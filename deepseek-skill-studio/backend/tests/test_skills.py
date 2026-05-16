"""Tests for Skill CRUD and path traversal protection (P1-5)."""
import pytest


def _create_skill(client, name="test_skill"):
    return client.post("/skills", json={
        "name": name,
        "description": "A test skill",
        "rules": ["Be concise", "Use headings"],
    })


def test_list_skills_empty(client):
    res = client.get("/skills")
    assert res.status_code == 200
    assert res.json()["skills"] == []


def test_create_skill(client):
    res = _create_skill(client)
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "test_skill"
    assert "# Test Skill" in body["content"]
    assert "Be concise" in body["content"]


def test_create_skill_conflict(client):
    _create_skill(client)
    res = _create_skill(client)
    assert res.status_code == 409


def test_get_skill(client):
    _create_skill(client)
    res = client.get("/skills/test_skill")
    assert res.status_code == 200
    assert res.json()["name"] == "test_skill"


def test_get_skill_not_found(client):
    res = client.get("/skills/nonexistent")
    assert res.status_code == 404


def test_skill_name_sanitization(client):
    """Spaces and special chars are slugified on create."""
    res = client.post("/skills", json={
        "name": "My Cool Skill!",
        "description": "desc",
        "rules": ["rule one"],
    })
    assert res.status_code == 200
    assert res.json()["name"] == "my_cool_skill"


def test_safe_name_strips_traversal_chars():
    """_safe_name must reduce any traversal-looking string to a safe slug."""
    from routers.skills import _safe_name
    assert _safe_name("../settings") == "settings"
    assert _safe_name("../../etc/passwd") == "etc_passwd"
    assert _safe_name("foo/../bar") == "foo_bar"
    assert _safe_name("normal_name") == "normal_name"


def test_skill_get_with_dotdot_name_returns_404(client):
    """
    A path-traversal-looking name passed to _safe_name resolves to a safe slug
    that does not exist → 404 rather than serving an arbitrary file.

    FastAPI normalises '../' in *URL paths*, so we test the encoded form (%2F)
    which reaches our endpoint as the raw parameter value.
    """
    # FastAPI treats %2F in a path segment as a literal slash and re-routes,
    # so the safest integration test is a name with dots only (no slash).
    res = client.get("/skills/..settings")
    assert res.status_code in (400, 404)


def test_safe_name_empty_raises(client):
    """A name that sanitises to empty string must return 400."""
    from fastapi import HTTPException
    from routers.skills import _safe_name
    with pytest.raises(HTTPException) as exc_info:
        _safe_name("!!!@@@###")
    assert exc_info.value.status_code == 400


def test_update_skill(client):
    _create_skill(client)
    res = client.put("/skills/test_skill", json={"description": "Updated desc", "rules": ["New rule"]})
    assert res.status_code == 200
    assert "New rule" in res.json()["content"]


def test_delete_skill(client):
    _create_skill(client)
    res = client.delete("/skills/test_skill")
    assert res.status_code == 200
    assert client.get("/skills/test_skill").status_code == 404
