"""Asset data-quality rules, defined once (PRD Module 2, functional requirements 6 and 7).

The API summary endpoint and the MCP gap tool both use these predicates, so the dashboard
and the agents can never disagree about what counts as a gap.
"""
from __future__ import annotations

from typing import Any

NO_OWNER = "asset_owner IS NULL"
NO_CRITICALITY = "criticality = 'unknown'"
POTENTIALLY_INACTIVE = "lifecycle_state = 'potentially_inactive'"


REQUIRED_FIELDS = ("asset_owner", "business_unit", "business_service", "location")   # PRD Module 2: required


def asset_flags(asset: dict[str, Any]) -> list[str]:
    """Data-quality flags for one asset. The same rules as the SQL predicates above."""
    flags = []
    if not asset.get("asset_owner"):
        flags.append("no_owner")
    if asset.get("criticality") == "unknown":
        flags.append("no_criticality")
    if asset.get("lifecycle_state") == "potentially_inactive":
        flags.append("potentially_inactive")
    return flags


def missing_required_fields(asset: dict[str, Any]) -> list[str]:
    missing = [f for f in REQUIRED_FIELDS if not asset.get(f)]
    if asset.get("criticality") == "unknown":
        missing.append("criticality")
    return missing


def gap_counts(conn) -> dict[str, Any]:
    """Enterprise-wide counts, computed in SQL over the whole inventory (never over one page)."""
    return dict(conn.execute(
        f"""SELECT count(*)::int AS total_assets,
                   (count(*) FILTER (WHERE {NO_OWNER}))::int AS without_owner,
                   (count(*) FILTER (WHERE {NO_CRITICALITY}))::int AS without_criticality,
                   (count(*) FILTER (WHERE {POTENTIALLY_INACTIVE}))::int AS potentially_inactive,
                   max(last_seen_at) AS data_as_of
            FROM assets"""
    ).fetchone())


def gap_asset_ids(conn) -> dict[str, Any]:
    """The same gaps as lists of Enterprise Asset IDs, for agents."""

    def ids(predicate: str) -> list[str]:
        rows = conn.execute(f"SELECT enterprise_asset_id FROM assets WHERE {predicate} ORDER BY 1").fetchall()
        return [r["enterprise_asset_id"] for r in rows]

    return {
        "total_assets": conn.execute("SELECT count(*)::int AS n FROM assets").fetchone()["n"],
        "without_owner": ids(NO_OWNER),
        "without_criticality": ids(NO_CRITICALITY),
        "potentially_inactive": ids(POTENTIALLY_INACTIVE),
    }
