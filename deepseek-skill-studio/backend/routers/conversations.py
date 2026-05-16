"""
Conversation management endpoints.

Conversations are persistent chat histories that can originate from local
chat sessions or from the OpenClaw gateway. They support archiving, branching,
and JSON export.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("agentstudio.conversations")

router = APIRouter(prefix="/conversations", tags=["conversations"])

# ── Paths ─────────────────────────────────────────────────────────────────

APP_DIR = Path(__file__).parent.parent
CONVERSATIONS_DIR = APP_DIR / "conversations"
CONVERSATIONS_PATH = CONVERSATIONS_DIR / "conversations.json"

# ── Lazy service singleton ────────────────────────────────────────────────

_conv_svc = None


def _get_svc():
    global _conv_svc
    if _conv_svc is None:
        from services.conversation_service import ConversationService
        _conv_svc = ConversationService(conversations_path=CONVERSATIONS_PATH)
    return _conv_svc


# ── Request models ────────────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    title: str
    source: Literal["local", "openclaw"] = "local"


class AddMessageRequest(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class BranchRequest(BaseModel):
    from_message_idx: int


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("")
async def list_conversations(
    include_archived: bool = Query(default=False, description="Include archived conversations"),
) -> Dict[str, Any]:
    """List all conversations, optionally including archived ones."""
    try:
        conversations = await _get_svc().list_conversations(include_archived=include_archived)
        return {"conversations": conversations, "count": len(conversations)}
    except Exception as exc:
        logger.error("Failed to list conversations: %s", exc)
        raise HTTPException(500, f"Could not list conversations: {exc}")


@router.post("", status_code=201)
async def create_conversation(body: CreateConversationRequest) -> Dict[str, Any]:
    """Create a new conversation with the given title and source."""
    if not body.title.strip():
        raise HTTPException(400, "Conversation title must not be empty.")
    try:
        conversation = await _get_svc().create_conversation(
            title=body.title.strip(),
            source=body.source,
        )
        return conversation
    except Exception as exc:
        logger.error("Failed to create conversation: %s", exc)
        raise HTTPException(500, f"Could not create conversation: {exc}")


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Return a single conversation by ID."""
    try:
        conv = await _get_svc().get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(404, f"Conversation not found: {conversation_id}")
        return conv
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get conversation %s: %s", conversation_id, exc)
        raise HTTPException(500, f"Could not retrieve conversation: {exc}")


@router.post("/{conversation_id}/messages", status_code=201)
async def add_message(conversation_id: str, body: AddMessageRequest) -> Dict[str, Any]:
    """Append a message to an existing conversation."""
    if not body.role.strip():
        raise HTTPException(400, "Message role must not be empty.")
    if not body.content.strip():
        raise HTTPException(400, "Message content must not be empty.")
    try:
        result = await _get_svc().add_message(
            conversation_id=conversation_id,
            role=body.role,
            content=body.content,
            metadata=body.metadata or {},
        )
        if result is None:
            raise HTTPException(404, f"Conversation not found: {conversation_id}")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to add message to conversation %s: %s", conversation_id, exc)
        raise HTTPException(500, f"Could not add message: {exc}")


@router.post("/{conversation_id}/archive")
async def archive_conversation(conversation_id: str) -> Dict[str, Any]:
    """Mark a conversation as archived (soft delete)."""
    try:
        result = await _get_svc().archive_conversation(conversation_id)
        if result is None:
            raise HTTPException(404, f"Conversation not found: {conversation_id}")
        return {"ok": True, "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to archive conversation %s: %s", conversation_id, exc)
        raise HTTPException(500, f"Could not archive conversation: {exc}")


@router.get("/{conversation_id}/export")
async def export_conversation(conversation_id: str):
    """Export a conversation as a JSON file attachment."""
    import json
    from fastapi.responses import Response

    try:
        conv = await _get_svc().get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(404, f"Conversation not found: {conversation_id}")
        payload = json.dumps(conv, indent=2, ensure_ascii=False).encode("utf-8")
        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in conv.get("title", conversation_id)
        )[:60]
        filename = f"conversation_{safe_title}.json"
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to export conversation %s: %s", conversation_id, exc)
        raise HTTPException(500, f"Could not export conversation: {exc}")


@router.post("/{conversation_id}/branch", status_code=201)
async def branch_conversation(conversation_id: str, body: BranchRequest) -> Dict[str, Any]:
    """
    Create a new conversation that is a copy of this one up to the message at
    from_message_idx (exclusive). The branch is a new conversation with its own ID.
    """
    if body.from_message_idx < 0:
        raise HTTPException(400, "from_message_idx must be >= 0.")
    try:
        branched = await _get_svc().branch_conversation(
            conversation_id=conversation_id,
            from_message_idx=body.from_message_idx,
        )
        if branched is None:
            raise HTTPException(404, f"Conversation not found: {conversation_id}")
        return branched
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to branch conversation %s: %s", conversation_id, exc)
        raise HTTPException(500, f"Could not branch conversation: {exc}")
