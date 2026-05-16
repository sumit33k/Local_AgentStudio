"""Agent CRUD endpoints."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

APP_DIR = Path(__file__).parent.parent
AGENTS_DIR = APP_DIR / "agents"
AGENTS_DIR.mkdir(exist_ok=True)


def agent_file() -> Path:
    return AGENTS_DIR / "agents.json"


def load_agents() -> Dict[str, Any]:
    path = agent_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_agents(agents: Dict[str, Any]) -> None:
    path = agent_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(agents, indent=2), encoding="utf-8")
    tmp.replace(path)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug[:60] or f"agent_{uuid.uuid4().hex[:8]}"


# ── Pydantic models ─────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: str = ""
    default_skill: str = "document_writer"
    default_output: str = "md"
    system_addendum: str = ""
    allowed_tools: List[str] = ["files", "github", "docx", "pptx", "markdown", "chat"]


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_skill: Optional[str] = None
    default_output: Optional[str] = None
    system_addendum: Optional[str] = None
    allowed_tools: Optional[List[str]] = None


# ── Endpoints ───────────────────────────────────────────────────────────

@router.get("/agents")
def list_agents():
    return {"agents": load_agents()}


@router.post("/agents")
def create_agent(body: AgentCreate):
    agents = load_agents()
    base_id = slugify(body.name)
    agent_id = base_id
    counter = 2
    while agent_id in agents:
        agent_id = f"{base_id}_{counter}"
        counter += 1
    spec = {
        **body.model_dump(),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    agents[agent_id] = spec
    save_agents(agents)
    return {"agent_id": agent_id, "agent": spec}


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    agents = load_agents()
    if agent_id not in agents:
        raise HTTPException(404, f"Agent not found: {agent_id}")
    return {"agent_id": agent_id, "agent": agents[agent_id]}


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentUpdate):
    agents = load_agents()
    if agent_id not in agents:
        raise HTTPException(404, f"Agent not found: {agent_id}")
    updates = body.model_dump(exclude_none=True)
    agents[agent_id].update(updates)
    save_agents(agents)
    return {"agent_id": agent_id, "agent": agents[agent_id]}


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    agents = load_agents()
    if agent_id not in agents:
        raise HTTPException(404, f"Agent not found: {agent_id}")
    del agents[agent_id]
    save_agents(agents)
    return {"deleted": agent_id}
