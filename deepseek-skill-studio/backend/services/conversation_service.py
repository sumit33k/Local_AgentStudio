"""
Conversation Service — manages local and OpenClaw-backed conversations.

Conversations are persisted as a single JSON file (conversations.json).
All writes are atomic (write to .tmp then os.replace).

Schema
------
Conversation:
    id:          str (UUID)
    title:       str
    source:      "local" | "openclaw"
    created_at:  ISO-8601 str
    updated_at:  ISO-8601 str
    archived:    bool
    messages:    list[Message]

Message:
    id:          str (UUID)
    role:        "user" | "assistant" | "system"
    content:     str
    created_at:  ISO-8601 str
    metadata:    dict
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentstudio.conversation")

VALID_SOURCES = {"local", "openclaw"}
VALID_ROLES = {"user", "assistant", "system"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ConversationService:
    """
    CRUD + branch/export operations for conversations.

    Parameters
    ----------
    conversations_path:
        Full path to the conversations.json file.
    """

    def __init__(self, conversations_path: Path) -> None:
        self.conversations_path = conversations_path
        conversations_path.parent.mkdir(parents=True, exist_ok=True)

    # ── I/O ───────────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, dict]:
        """Return the conversations dict keyed by conversation id."""
        if not self.conversations_path.is_file():
            return {}
        try:
            raw = json.loads(
                self.conversations_path.read_text(encoding="utf-8")
            )
            # Tolerate both {"conversations": {...}} and flat {id: conv} forms
            if isinstance(raw, dict) and "conversations" in raw:
                return raw["conversations"]
            if isinstance(raw, dict):
                return raw
            return {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load conversations: %s", exc)
            return {}

    def _save(self, conversations: Dict[str, dict]) -> None:
        _atomic_write(
            self.conversations_path,
            json.dumps({"conversations": conversations}, indent=2, ensure_ascii=False),
        )

    # ── Create ────────────────────────────────────────────────────────────

    def create(self, title: str, source: str = "local") -> dict:
        """Create and persist a new conversation."""
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source '{source}'; must be one of {VALID_SOURCES}")

        conv: dict = {
            "id": _new_id(),
            "title": title or "New Conversation",
            "source": source,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "archived": False,
            "messages": [],
        }
        conversations = self._load()
        conversations[conv["id"]] = conv
        self._save(conversations)
        logger.info("Created conversation '%s' (id=%s)", conv["title"], conv["id"])
        return conv

    # ── Read ──────────────────────────────────────────────────────────────

    def get(self, conversation_id: str) -> dict:
        """Return a conversation by id, or raise KeyError."""
        conversations = self._load()
        if conversation_id not in conversations:
            raise KeyError(f"Conversation not found: {conversation_id}")
        return conversations[conversation_id]

    def list(self, include_archived: bool = False) -> List[dict]:
        """Return all conversations, sorted by updated_at descending."""
        conversations = self._load()
        items = list(conversations.values())
        if not include_archived:
            items = [c for c in items if not c.get("archived", False)]
        items.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return items

    # ── Mutate ────────────────────────────────────────────────────────────

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Append a message to an existing conversation and return the message."""
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'; must be one of {VALID_ROLES}")

        conversations = self._load()
        if conversation_id not in conversations:
            raise KeyError(f"Conversation not found: {conversation_id}")

        msg: dict = {
            "id": _new_id(),
            "role": role,
            "content": content,
            "created_at": _now_iso(),
            "metadata": metadata or {},
        }
        conversations[conversation_id]["messages"].append(msg)
        conversations[conversation_id]["updated_at"] = _now_iso()
        self._save(conversations)
        return msg

    def archive(self, conversation_id: str) -> None:
        """Mark a conversation as archived."""
        conversations = self._load()
        if conversation_id not in conversations:
            raise KeyError(f"Conversation not found: {conversation_id}")
        conversations[conversation_id]["archived"] = True
        conversations[conversation_id]["updated_at"] = _now_iso()
        self._save(conversations)
        logger.info("Archived conversation %s", conversation_id)

    # ── Export ────────────────────────────────────────────────────────────

    def export(self, conversation_id: str) -> str:
        """Return the conversation serialised as a JSON string."""
        conv = self.get(conversation_id)
        return json.dumps(conv, indent=2, ensure_ascii=False)

    # ── Branch ────────────────────────────────────────────────────────────

    def branch(self, conversation_id: str, from_message_idx: int) -> dict:
        """
        Create a new conversation that contains only the first
        *from_message_idx* messages of the source conversation.

        The branched conversation gets a new id and a title derived from
        the original.
        """
        source_conv = self.get(conversation_id)
        messages = source_conv.get("messages", [])

        if from_message_idx < 0 or from_message_idx > len(messages):
            raise ValueError(
                f"from_message_idx {from_message_idx} out of range "
                f"(conversation has {len(messages)} messages)"
            )

        branched_messages = [
            {**m, "id": _new_id()}  # new IDs to avoid collisions
            for m in messages[:from_message_idx]
        ]

        now = _now_iso()
        branch_conv: dict = {
            "id": _new_id(),
            "title": f"{source_conv.get('title', 'Conversation')} (branch)",
            "source": source_conv.get("source", "local"),
            "created_at": now,
            "updated_at": now,
            "archived": False,
            "messages": branched_messages,
            "branched_from": conversation_id,
            "branched_at_index": from_message_idx,
        }

        conversations = self._load()
        conversations[branch_conv["id"]] = branch_conv
        self._save(conversations)

        logger.info(
            "Branched conversation %s → %s (up to message %d)",
            conversation_id,
            branch_conv["id"],
            from_message_idx,
        )
        return branch_conv
