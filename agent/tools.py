"""The agent's side of MCP: a small client that calls the tool server.

The agent's steps are synchronous (LangGraph nodes), and the MCP client is async, so each
call runs its own short event loop. The server is connected in-process, which skips the
cost of a subprocess while still going through the MCP protocol.
"""

import json
from typing import Any

import anyio
from mcp import Client
from mcp.server.mcpserver import MCPServer


class ToolError(RuntimeError):
    """A tool reported a failure, e.g. a path outside the repository or Docker not running."""


class ToolClient:
    def __init__(self, server: MCPServer) -> None:
        self._server = server

    def call(self, name: str, **arguments: Any) -> Any:
        return anyio.run(self._call, name, arguments)

    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        async with Client(self._server) as client:
            result = await client.call_tool(name, arguments)
        text = "".join(getattr(block, "text", "") for block in result.content)
        if result.is_error:
            raise ToolError(text)
        # Lists and numbers come back wrapped as {"result": ...}; dicts only as JSON text.
        if result.structured_content is not None:
            return result.structured_content.get("result", result.structured_content)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def list_tools(self) -> list[str]:
        return anyio.run(self._list_tools)

    async def _list_tools(self) -> list[str]:
        async with Client(self._server) as client:
            return [tool.name for tool in (await client.list_tools()).tools]
