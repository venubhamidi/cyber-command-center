"""A minimal MCP server used by test_mcp_client.py."""
import json

from mcp.server.mcpserver import MCPServer

server = MCPServer("echo", version="0")


@server.tool()
def echo(text: str) -> str:
    """Return the text as JSON."""
    return json.dumps({"echo": text})


if __name__ == "__main__":
    server.run()
