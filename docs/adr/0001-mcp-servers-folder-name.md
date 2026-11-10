# The MCP server folder is `mcp_servers/`, not the PRD's `mcp/`
**Status:** accepted
**Date:** 2026-11-10

## Context
PRD Part 6 proposes a folder named `mcp/` for the MCP servers (`asset-mcp`, `vulnerability-mcp`,
...). The servers are written with the Python MCP SDK, whose top-level package is also named
`mcp`. A package folder named `mcp/` inside the application shadows the SDK on the import path,
so `from mcp.server.mcpserver import MCPServer` resolves to the application's own folder and
every server fails to import. This was found while building the first server (`DECISIONS.md`
D-002).

## Decision
MCP servers live in `ccc/mcp_servers/<name>_mcp/server.py`. Each server is run as a module,
`python -m ccc.mcp_servers.asset_mcp.server`, and exposes its tool functions in a `TOOLS` dict
for in-process tests.

## Alternatives considered
- **Keep `mcp/` and rename the SDK import.** Not possible; the SDK's package name is fixed.
- **Keep `mcp/` as a non-package folder outside the import path.** Breaks `python -m` and the
  test imports, and still invites the shadowing the moment someone adds an `__init__.py`.
- **A different name such as `tools/`.** Would collide with the glossary's meaning of *tool*
  (one function an agent may call); `mcp_servers` says what the folder holds.

## Consequences
- Every reference to the PRD's `mcp/` path reads `mcp_servers/` here; the PRD's logical structure
  is otherwise unaffected.
- The `/new-mcp-tool` skill finds servers with `ls <app>/mcp_servers/*/server.py`.
