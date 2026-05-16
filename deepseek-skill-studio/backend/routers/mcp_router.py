"""MCP server configuration and tool-calling endpoints."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

APP_DIR = Path(__file__).parent.parent
MCP_CONFIGS_PATH = APP_DIR / "mcp_configs.json"


def _get_mcp_service():
    from services.mcp_service import McpService
    return McpService(MCP_CONFIGS_PATH)


# ── Pydantic models ─────────────────────────────────────────────────────

class ServerCreate(BaseModel):
    name: str
    command: str
    args: List[str] = []
    env: Dict[str, str] = {}
    description: str = ""
    enabled: bool = True


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class ToolCall(BaseModel):
    server_id: str
    tool_name: str
    arguments: Dict[str, Any] = {}


# ── Server management ───────────────────────────────────────────────────

@router.get("/mcp/servers")
def list_servers():
    svc = _get_mcp_service()
    return {"servers": svc.list_servers()}


@router.post("/mcp/servers")
def add_server(body: ServerCreate):
    svc = _get_mcp_service()
    server = svc.add_server(
        name=body.name,
        command=body.command,
        args=body.args,
        env=body.env,
        description=body.description,
        enabled=body.enabled,
    )
    return {"server": server}


@router.put("/mcp/servers/{server_id}")
def update_server(server_id: str, body: ServerUpdate):
    svc = _get_mcp_service()
    server = svc.update_server(server_id, body.model_dump(exclude_none=True))
    return {"server": server}


@router.delete("/mcp/servers/{server_id}")
def delete_server(server_id: str):
    svc = _get_mcp_service()
    svc.delete_server(server_id)
    return {"deleted": server_id}


# ── Tool listing ────────────────────────────────────────────────────────

@router.get("/mcp/servers/{server_id}/tools")
async def list_server_tools(server_id: str):
    svc = _get_mcp_service()
    tools = await svc.list_tools(server_id)
    return {"tools": tools}


@router.get("/mcp/tools")
async def list_all_tools():
    svc = _get_mcp_service()
    tools = await svc.list_all_tools()
    return {"tools": tools}


# ── Tool invocation ─────────────────────────────────────────────────────

@router.post("/mcp/tools/call")
async def call_tool(body: ToolCall):
    svc = _get_mcp_service()
    result = await svc.call_tool(body.server_id, body.tool_name, body.arguments)
    return {"result": result}


# ── Preset templates ─────────────────────────────────────────────────────

PRESETS = [
    {
        "name": "GitHub MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
        "description": "GitHub tools: repos, issues, PRs, file access",
    },
    {
        "name": "Filesystem MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "env": {},
        "description": "Read/write local files in the specified directory",
    },
    {
        "name": "Brave Search MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        "description": "Web search via Brave Search API",
    },
    {
        "name": "SQLite MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/tmp/agent.db"],
        "env": {},
        "description": "Query and modify a local SQLite database",
    },
    {
        "name": "Fetch MCP",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "env": {},
        "description": "Fetch web pages and convert to markdown",
    },
]


@router.get("/mcp/presets")
def list_presets():
    return {"presets": PRESETS}
