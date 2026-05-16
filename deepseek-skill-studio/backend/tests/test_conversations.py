"""Tests for ConversationService.

Covers conversation creation, message adding, listing, archiving, export,
and branching. All tests use tmp_path for file isolation.
"""

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import pytest
from services.conversation_service import ConversationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def svc(tmp_path: Path) -> ConversationService:
    conversations_file = tmp_path / "conversations.json"
    return ConversationService(conversations_file)


# ---------------------------------------------------------------------------
# Tests: create_conversation
# ---------------------------------------------------------------------------


def test_create_conversation(svc: ConversationService) -> None:
    """create_conversation() returns a dict with id, source, and empty messages."""
    conv = svc.create("Test Conversation", source="local")
    assert "id" in conv
    assert conv["title"] == "Test Conversation"
    assert conv["source"] == "local"
    assert conv["messages"] == []
    assert conv["archived"] is False


def test_get_conversation(svc: ConversationService) -> None:
    """get() retrieves a conversation by id."""
    conv = svc.create("Get Test")
    fetched = svc.get(conv["id"])
    assert fetched["id"] == conv["id"]
    assert fetched["title"] == "Get Test"


def test_get_nonexistent_raises(svc: ConversationService) -> None:
    """get() raises an exception for an unknown id."""
    with pytest.raises(Exception):
        svc.get("nonexistent-id")


# ---------------------------------------------------------------------------
# Tests: add_message
# ---------------------------------------------------------------------------


def test_add_message(svc: ConversationService) -> None:
    """add_message() returns the message and updates the conversation."""
    conv = svc.create("Msg Test")
    msg = svc.add_message(conv["id"], role="user", content="Hello")
    assert msg["role"] == "user"
    assert msg["content"] == "Hello"
    assert "id" in msg


def test_add_message_updates_conversation(svc: ConversationService) -> None:
    """After add_message(), the conversation contains the new message."""
    conv = svc.create("Update Test")
    svc.add_message(conv["id"], role="assistant", content="Hi there!")
    updated = svc.get(conv["id"])
    assert len(updated["messages"]) == 1
    assert updated["messages"][0]["content"] == "Hi there!"


def test_add_multiple_messages_preserves_order(svc: ConversationService) -> None:
    """Messages are stored in insertion order."""
    conv = svc.create("Order Test")
    svc.add_message(conv["id"], role="user", content="first")
    svc.add_message(conv["id"], role="assistant", content="second")
    svc.add_message(conv["id"], role="user", content="third")
    updated = svc.get(conv["id"])
    contents = [m["content"] for m in updated["messages"]]
    assert contents == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# Tests: list_conversations
# ---------------------------------------------------------------------------


def test_list_conversations_excludes_archived_by_default(
    svc: ConversationService,
) -> None:
    """Archived conversations are excluded from the default listing."""
    c1 = svc.create("Active")
    c2 = svc.create("To Archive")
    svc.archive(c2["id"])
    active = svc.list()
    ids = [c["id"] for c in active]
    assert c1["id"] in ids
    assert c2["id"] not in ids


def test_list_conversations_includes_archived_when_requested(
    svc: ConversationService,
) -> None:
    """include_archived=True returns archived conversations too."""
    c1 = svc.create("Active")
    c2 = svc.create("Archived")
    svc.archive(c2["id"])
    all_convs = svc.list(include_archived=True)
    ids = [c["id"] for c in all_convs]
    assert c1["id"] in ids
    assert c2["id"] in ids


# ---------------------------------------------------------------------------
# Tests: archive_conversation
# ---------------------------------------------------------------------------


def test_archive_conversation(svc: ConversationService) -> None:
    """archive() sets archived=True on the conversation."""
    conv = svc.create("Archive Me")
    svc.archive(conv["id"])
    fetched = svc.get(conv["id"])
    assert fetched["archived"] is True


def test_archive_excluded_from_default_list(svc: ConversationService) -> None:
    """Archived conversations do not appear in list() by default."""
    conv = svc.create("Archived")
    svc.archive(conv["id"])
    active = svc.list(include_archived=False)
    assert conv["id"] not in [c["id"] for c in active]


def test_archive_included_with_flag(svc: ConversationService) -> None:
    """Archived conversations appear when include_archived=True."""
    conv = svc.create("Archived")
    svc.archive(conv["id"])
    all_convs = svc.list(include_archived=True)
    assert conv["id"] in [c["id"] for c in all_convs]


# ---------------------------------------------------------------------------
# Tests: export_conversation
# ---------------------------------------------------------------------------


def test_export_conversation(svc: ConversationService) -> None:
    """export() returns a valid JSON string containing the conversation data."""
    conv = svc.create("Export Test")
    svc.add_message(conv["id"], role="user", content="Export this")
    exported = svc.export(conv["id"])
    data = json.loads(exported)
    assert data["title"] == "Export Test"
    assert len(data["messages"]) == 1


def test_export_is_valid_json(svc: ConversationService) -> None:
    """export() returns valid JSON."""
    conv = svc.create("JSON Test")
    svc.add_message(conv["id"], role="user", content="Hello")
    exported = svc.export(conv["id"])
    parsed = json.loads(exported)
    assert isinstance(parsed, dict)


def test_export_contains_messages(svc: ConversationService) -> None:
    """The exported JSON contains all added messages."""
    conv = svc.create("Msg Export")
    svc.add_message(conv["id"], role="user", content="Test message")
    exported = json.loads(svc.export(conv["id"]))
    assert any(
        m.get("content") == "Test message"
        for m in exported.get("messages", [])
    )


# ---------------------------------------------------------------------------
# Tests: branch_conversation
# ---------------------------------------------------------------------------


def test_branch_conversation(svc: ConversationService) -> None:
    """branch() creates a new conversation branched from the given message index."""
    conv = svc.create("Branch Base")
    svc.add_message(conv["id"], role="user", content="msg 0")
    svc.add_message(conv["id"], role="assistant", content="msg 1")
    svc.add_message(conv["id"], role="user", content="msg 2")
    branched = svc.branch(conv["id"], from_message_idx=2)
    assert branched["id"] != conv["id"]
    assert len(branched["messages"]) == 2


def test_branch_appears_in_list(svc: ConversationService) -> None:
    """A branched conversation is listed by list()."""
    conv = svc.create("Branch List")
    svc.add_message(conv["id"], role="user", content="msg 0")
    branch = svc.branch(conv["id"], from_message_idx=1)
    all_ids = [c["id"] for c in svc.list()]
    assert branch["id"] in all_ids


# ---------------------------------------------------------------------------
# Tests: persistence
# ---------------------------------------------------------------------------


def test_conversations_persist(tmp_path: Path) -> None:
    """Conversations written by one service instance are readable by the next."""
    f = tmp_path / "conversations.json"
    svc1 = ConversationService(f)
    conv = svc1.create("Persist Test")
    svc2 = ConversationService(f)
    fetched = svc2.get(conv["id"])
    assert fetched["title"] == "Persist Test"
