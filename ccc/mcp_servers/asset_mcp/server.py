"""Asset MCP server (PRD Part 6 asset-mcp): read-only asset tools for agents.

The server, not the model, talks to PostgreSQL (PRD §6: no direct connection from a public LLM
to the enterprise database).

Run over stdio:  python -m ccc.mcp_servers.asset_mcp.server
Tools return a JSON document as text. `TOOLS` exposes the same functions for in-process tests.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer  # MCP SDK 2.x (FastMCP was renamed)

from ccc.assets import gap_asset_ids
from ccc.config import settings
from harness.db import get_conn

server = MCPServer("asset-mcp", version="0.2.0")


def _get_asset(enterprise_asset_id: str) -> dict[str, Any] | None:
    with get_conn(settings.database_url) as conn:
        row = conn.execute(
            """SELECT a.enterprise_asset_id, a.hostname, host(a.ip_address) AS ip_address, a.asset_type::text,
                      a.asset_owner, a.business_unit, a.business_service, a.criticality::text, a.location,
                      a.environment::text, a.operating_system, a.lifecycle_state::text, a.last_seen_at::text,
                      COALESCE(array_agg(s.source_system ORDER BY s.source_system)
                               FILTER (WHERE s.source_system IS NOT NULL), '{}') AS sources
               FROM assets a LEFT JOIN asset_sources s ON s.asset_id = a.id
               WHERE a.enterprise_asset_id = %s GROUP BY a.id""",
            (enterprise_asset_id,)).fetchone()
    return dict(row) if row else None


def _list_asset_gaps() -> dict[str, Any]:
    """PRD Module 2 req. 6 and 7: assets without owner or criticality, and potentially-inactive assets."""
    with get_conn(settings.database_url) as conn:
        return gap_asset_ids(conn)


@server.tool()
def get_asset(enterprise_asset_id: str) -> str:
    """Return one asset by Enterprise Asset ID, as JSON (null if there is none). Read-only."""
    return json.dumps(_get_asset(enterprise_asset_id))


@server.tool()
def list_asset_gaps() -> str:
    """Return assets missing owner or criticality, and potentially-inactive assets. Read-only."""
    return json.dumps(_list_asset_gaps())


TOOLS = {"get_asset": _get_asset, "list_asset_gaps": _list_asset_gaps}

if __name__ == "__main__":
    server.run()
