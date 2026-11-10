"""ToolClient that reaches tools over real MCP (stdio transport).

Each call starts the MCP server as a subprocess, performs the MCP handshake, calls one tool
and shuts the server down. Simple and correct; slow (a process per call), and stdio carries no
authentication. A long-lived authenticated HTTP transport replaces this when deployments need it.

Convention: tools return a JSON document as text; the client parses it.
A call that exceeds timeout_s, or cannot reach the server, is a TransientToolError (retried by
the agent contract). A tool that reports an error is a ToolCallError (not retried).
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from harness.agents.contract import ToolClient, TransientToolError


class ToolCallError(RuntimeError):
    pass


class McpStdioToolClient(ToolClient):
    def __init__(self, command: str, args: list[str], cwd: str | None = None, env: dict[str, str] | None = None,
                 timeout_s: float = 30.0):
        # The MCP SDK passes only a minimal environment to the server by default; the server
        # needs the application's settings (database URL etc.), so inherit ours unless told otherwise.
        self.params = StdioServerParameters(command=command, args=args, cwd=cwd,
                                            env=env if env is not None else dict(os.environ))
        self.timeout_s = timeout_s

    def call(self, name: str, **kwargs: Any) -> Any:
        try:
            return asyncio.run(asyncio.wait_for(self._call(name, kwargs), self.timeout_s))
        except TimeoutError as exc:
            raise TransientToolError(f"MCP tool '{name}' timed out after {self.timeout_s}s") from exc
        except (ConnectionError, BrokenPipeError, EOFError) as exc:
            raise TransientToolError(f"MCP tool '{name}': connection lost") from exc

    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        async with stdio_client(self.params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
        text = "".join(getattr(block, "text", "") for block in result.content)
        if getattr(result, "is_error", False) or getattr(result, "isError", False):
            raise ToolCallError(f"MCP tool '{name}' failed: {text}")
        return json.loads(text)
