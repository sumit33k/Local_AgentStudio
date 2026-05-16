"""MCP service: configuration management and tool calling via MCP SDK."""
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException


class McpService:
    def __init__(self, configs_path: Path):
        self.configs_path = configs_path

    # ── Config persistence ──────────────────────────────────────────────

    def load(self) -> Dict:
        if not self.configs_path.exists():
            return {"servers": []}
        try:
            return json.loads(self.configs_path.read_text())
        except Exception:
            return {"servers": []}

    def save(self, data: Dict) -> None:
        tmp = self.configs_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.configs_path)

    # ── Server CRUD ─────────────────────────────────────────────────────

    def list_servers(self) -> List[Dict]:
        return self.load().get("servers", [])

    def get_server(self, server_id: str) -> Dict:
        for s in self.list_servers():
            if s.get("id") == server_id:
                return s
        raise HTTPException(404, f"MCP server not found: {server_id}")

    def add_server(self, name: str, command: str, args: List[str],
                   env: Dict[str, str], description: str = "", enabled: bool = True) -> Dict:
        data = self.load()
        new_server = {
            "id": f"mcp_{uuid.uuid4().hex[:8]}",
            "name": name,
            "command": command,
            "args": args,
            "env": env,
            "enabled": enabled,
            "description": description,
        }
        data["servers"].append(new_server)
        self.save(data)
        return new_server

    def update_server(self, server_id: str, updates: Dict) -> Dict:
        data = self.load()
        for server in data["servers"]:
            if server.get("id") == server_id:
                for k, v in updates.items():
                    if k != "id":
                        server[k] = v
                self.save(data)
                return server
        raise HTTPException(404, f"MCP server not found: {server_id}")

    def delete_server(self, server_id: str) -> None:
        data = self.load()
        data["servers"] = [s for s in data["servers"] if s.get("id") != server_id]
        self.save(data)

    # ── Tool operations (ephemeral connections) ─────────────────────────

    def _resolve_env(self, env: Dict[str, str]) -> Dict[str, str]:
        resolved = {}
        for k, v in env.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                var_name = v[2:-1]
                resolved[k] = os.environ.get(var_name, "")
            else:
                resolved[k] = v
        return resolved

    async def list_tools(self, server_id: str) -> List[Dict]:
        server = self.get_server(server_id)
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise HTTPException(500, "Install 'mcp': pip install mcp")

        params = StdioServerParameters(
            command=server["command"],
            args=server.get("args", []),
            env={**os.environ, **self._resolve_env(server.get("env", {}))},
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "inputSchema": t.inputSchema if hasattr(t, "inputSchema") else {},
                            "server_id": server_id,
                            "server_name": server.get("name", server_id),
                        }
                        for t in result.tools
                    ]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, f"Failed to connect to MCP server '{server.get('name')}': {exc}")

    async def list_all_tools(self) -> List[Dict]:
        all_tools: List[Dict] = []
        for server in self.list_servers():
            if not server.get("enabled", True):
                continue
            try:
                tools = await self.list_tools(server["id"])
                all_tools.extend(tools)
            except Exception:
                pass
        return all_tools

    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        server = self.get_server(server_id)
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise HTTPException(500, "Install 'mcp': pip install mcp")

        params = StdioServerParameters(
            command=server["command"],
            args=server.get("args", []),
            env={**os.environ, **self._resolve_env(server.get("env", {}))},
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    # result.content is a list of content blocks
                    parts = []
                    for block in (result.content or []):
                        if hasattr(block, "text"):
                            parts.append(block.text)
                        else:
                            parts.append(str(block))
                    return "\n".join(parts)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, f"Tool call failed: {exc}")

    # ── Convert tools to LLM tool-call format ───────────────────────────

    @staticmethod
    def tools_to_anthropic_format(tools: List[Dict]) -> List[Dict]:
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]

    @staticmethod
    def tools_to_openai_format(tools: List[Dict]) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    @staticmethod
    def tools_to_ollama_context(tools: List[Dict]) -> str:
        if not tools:
            return ""
        lines = ["Available tools (call by responding with JSON {\"tool\": \"name\", \"args\": {...}}):"]
        for t in tools:
            lines.append(f"- {t['name']}: {t.get('description', 'no description')}")
        return "\n".join(lines)
