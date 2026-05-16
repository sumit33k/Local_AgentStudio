"""Tests for ConversationService."""
import sys
import json
from pathlib import Path

_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from services.conversation_service import ConversationService


@pytest.fixture()
def svc(tmp_path):
    conversations_file = tmp_path / "conversations.json"
    return ConversationService(conversations_file)


def test_create_conversation(svc):
    conv = svc.create("Test Conversation", source="local")
    assert "id" in conv
    assert conv["title"] == "Test Conversation"
    assert conv["source"] == "local"
    assert conv["messages"] == []
    assert conv["archived"] is False


def test_get_conversation(svc):
    conv = svc.create("Get Test")
    fetched = svc.get(conv["id"])
    assert fetched["id"] == conv["id"]
    assert fetched["title"] == "Get Test"


def test_get_nonexistent_raises(svc):
    with pytest.raises(Exception):
        svc.get("nonexistent-id")


def test_add_message(svc):
    conv = svc.create("Msg Test")
    msg = svc.add_message(conv["id"], role="user", content="Hello")
    assert msg["role"] == "user"
    assert msg["content"] == "Hello"
    assert "id" in msg


def test_list_conversations_excludes_archived_by_default(svc):
    c1 = svc.create("Active")
    c2 = svc.create("To Archive")
    svc.archive(c2["id"])
    active = svc.list()
    ids = [c["id"] for c in active]
    assert c1["id"] in ids
    assert c2["id"] not in ids


def test_list_conversations_includes_archived_when_requested(svc):
    c1 = svc.create("Active")
    c2 = svc.create("Archived")
    svc.archive(c2["id"])
    all_convs = svc.list(include_archived=True)
    ids = [c["id"] for c in all_convs]
    assert c1["id"] in ids
    assert c2["id"] in ids


def test_archive_conversation(svc):
    conv = svc.create("Archive Me")
    svc.archive(conv["id"])
    fetched = svc.get(conv["id"])
    assert fetched["archived"] is True


def test_export_conversation(svc):
    conv = svc.create("Export Test")
    svc.add_message(conv["id"], role="user", content="Export this")
    exported = svc.export(conv["id"])
    data = json.loads(exported)
    assert data["title"] == "Export Test"
    assert len(data["messages"]) == 1


def test_branch_conversation(svc):
    conv = svc.create("Branch Base")
    svc.add_message(conv["id"], role="user", content="msg 0")
    svc.add_message(conv["id"], role="assistant", content="msg 1")
    svc.add_message(conv["id"], role="user", content="msg 2")
    branched = svc.branch(conv["id"], from_message_idx=2)
    assert branched["id"] != conv["id"]
    assert len(branched["messages"]) == 2


def test_conversations_persist(tmp_path):
    f = tmp_path / "conversations.json"
    svc1 = ConversationService(f)
    conv = svc1.create("Persist Test")
    svc2 = ConversationService(f)
    fetched = svc2.get(conv["id"])
    assert fetched["title"] == "Persist Test"
