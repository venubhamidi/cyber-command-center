from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ccc.agents.asset_agent import summarize_asset
from ccc.api.schemas import (
    Asset,
    AssetDetail,
    AssetSummary,
    ControlAssessment,
    Dashboard,
    DataCompleteness,
    Finding,
    HistoryEntry,
    Incident,
    Kpi,
    Me,
    PatchStatus,
    Risk,
    SourceSystemRecord,
    TopRisk,
    UsageRow,
)
from ccc.assets import asset_flags, gap_counts, missing_required_fields
from ccc.dashboard import KPIS, compute_kpis
from ccc.snapshot import previous_values, trend
from harness.agents.contract import AgentResponse
from harness.app import db_url
from harness.db import get_conn
from harness.pagination import Page
from harness.security import Principal, get_principal, require

router = APIRouter(prefix="/api/v1")


@router.get("/me", response_model=Me)
def me(p: Principal = Depends(get_principal)) -> Me:
    """Who is calling and what they may do, so the screen shows only the actions this persona has."""
    return Me(subject=p.subject, roles=sorted(p.roles), permissions=sorted(p.permissions))


TOP_RISKS_SQL = """
SELECT r.title, r.business_unit, r.business_service, r.rating::text, r.business_impact, r.owner,
       r.recommended_action, r.updated_at AS last_updated, r.source_system, r.model_version,
       COALESCE(array_agg(a.enterprise_asset_id ORDER BY a.enterprise_asset_id) FILTER (WHERE a.id IS NOT NULL), '{}') AS affected_assets
FROM risks r LEFT JOIN risk_assets ra ON ra.risk_id = r.id LEFT JOIN assets a ON a.id = ra.asset_id
WHERE r.data_quality_status = 'ok'
GROUP BY r.id ORDER BY r.rating, r.updated_at DESC LIMIT 5
"""


@router.get("/dashboard", response_model=Dashboard)
def dashboard(_: Principal = Depends(require("dashboard:read")), db: str = Depends(db_url)) -> Dashboard:
    """PRD Module 1: eight KPIs and the top five risks. Every number is computed here, never in the browser."""
    now = datetime.now(UTC)
    with get_conn(db) as conn:
        kpis = compute_kpis(conn, now=now)
        previous = previous_values(conn, now.date())
        risks = conn.execute(TOP_RISKS_SQL).fetchall()
    tiles = []
    for name, (unit, good, drilldown) in KPIS.items():
        k, prev = kpis[name], previous.get(name)
        tiles.append(Kpi(kpi=name, value=k.value, unit=unit, previous_value=prev[0] if prev else None,
                         previous_period=prev[1] if prev else None, trend=trend(k.value, prev[0] if prev else None),
                         good_direction=good, data_as_of=k.data_as_of, source_systems=k.source_systems,
                         drilldown=drilldown, formula_version=k.formula_version,
                         mock=any(s.startswith("mock_") for s in k.source_systems)))
    return Dashboard(generated_at=now, kpis=tiles, top_risks=[TopRisk(**r) for r in risks])


# Drill-down lists (D-040): plain, read-only, newest first, each behind its module's permission.
# Filters arrive with each module's own slice.
PROVENANCE = "source_system, source_record_id, collected_at, updated_at, data_quality_status::text AS data_quality_status"
LISTS: dict[str, tuple[str, str, type, str]] = {
    "findings": ("vulns:read", f"""SELECT a.enterprise_asset_id, f.cve, f.title, f.severity::text, f.cvss::float, f.exploitable,
        f.known_exploited, f.status::text, f.first_seen_at, f.last_seen_at, f.due_at, f.closed_at, f.{PROVENANCE.replace(', ', ', f.')}
        FROM findings f JOIN assets a ON a.id = f.asset_id ORDER BY f.severity, f.last_seen_at DESC, f.id""", Finding, "findings"),
    "patch-status": ("patch:read", f"""SELECT a.enterprise_asset_id, p.state::text, p.missing_count, p.{PROVENANCE.replace(', ', ', p.')}
        FROM patch_status p JOIN assets a ON a.id = p.asset_id ORDER BY a.enterprise_asset_id, p.source_system""", PatchStatus, "patch_status"),
    "controls": ("controls:read", f"""SELECT framework, control_id, title, status::text, effectiveness, assessor, assessed_at, {PROVENANCE}
        FROM control_assessments ORDER BY framework, control_id""", ControlAssessment, "control_assessments"),
    "incidents": ("incidents:read", f"""SELECT title, severity::text, status::text, opened_at, closed_at, {PROVENANCE}
        FROM incidents ORDER BY status, opened_at DESC""", Incident, "incidents"),
    "risks": ("risks:read", f"""SELECT r.title, r.business_unit, r.business_service, r.rating::text, r.business_impact, r.owner,
        r.recommended_action, r.updated_at AS last_updated, r.model_version, r.{PROVENANCE.replace(', ', ', r.')},
        COALESCE(array_agg(a.enterprise_asset_id ORDER BY a.enterprise_asset_id) FILTER (WHERE a.id IS NOT NULL), '{{}}') AS affected_assets
        FROM risks r LEFT JOIN risk_assets ra ON ra.risk_id = r.id LEFT JOIN assets a ON a.id = ra.asset_id
        GROUP BY r.id ORDER BY r.rating, r.updated_at DESC""", Risk, "risks"),
}


def _list_route(name: str, permission: str, sql: str, model: type, table: str):
    def route(_: Principal = Depends(require(permission)), db: str = Depends(db_url),
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> Page[model]:
        with get_conn(db) as conn:
            total = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            rows = conn.execute(f"{sql} LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        return Page(items=[model(**r) for r in rows], total=total, limit=limit, offset=offset)

    route.__name__ = f"list_{name.replace('-', '_')}"
    route.__doc__ = f"Drill-down from the dashboard (D-040): every {table} record with its provenance, no filters yet."
    router.add_api_route(f"/{name}", route, methods=["GET"], response_model=Page[model])


for _name, (_perm, _sql, _model, _table) in LISTS.items():
    _list_route(_name, _perm, _sql, _model, _table)


ASSET_SELECT = """
SELECT a.id, a.enterprise_asset_id, a.hostname, host(a.ip_address) AS ip_address,
       a.mac_address::text AS mac_address, a.asset_type::text, a.asset_owner, a.business_unit,
       a.business_service, a.criticality::text, a.location, a.environment::text, a.operating_system,
       a.lifecycle_state::text, a.last_seen_at,
       COALESCE(array_agg(s.source_system ORDER BY s.source_system) FILTER (WHERE s.source_system IS NOT NULL), '{}') AS source_systems
FROM assets a LEFT JOIN asset_sources s ON s.asset_id = a.id
"""


def _asset(row: dict) -> Asset:
    """One asset with its derived fields, computed by the shared rules (the agent uses the same)."""
    missing = missing_required_fields(row)
    return Asset(**row, flags=asset_flags(row), data_completeness=DataCompleteness(complete=not missing, missing_fields=missing))


@router.get("/assets", response_model=Page[Asset])
def list_assets(
    _: Principal = Depends(require("assets:read")),
    db: str = Depends(db_url),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    business_unit: str | None = None,
    criticality: str | None = None,
    asset_type: str | None = None,
    lifecycle_state: str | None = None,
) -> Page[Asset]:
    """PRD §8 /api/v1/assets: asset inventory with pagination and filtering."""
    where, params = [], {}
    for col, val in (("business_unit", business_unit), ("criticality", criticality),
                     ("asset_type", asset_type), ("lifecycle_state", lifecycle_state)):
        if val is not None:
            where.append(f"a.{col}::text = %({col})s")
            params[col] = val
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with get_conn(db) as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM assets a {where_sql}", params).fetchone()["n"]
        rows = conn.execute(
            f"{ASSET_SELECT} {where_sql} GROUP BY a.id ORDER BY a.id LIMIT %(limit)s OFFSET %(offset)s",
            {**params, "limit": limit, "offset": offset},
        ).fetchall()
    return Page(items=[_asset(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/assets/summary", response_model=AssetSummary)
def asset_summary(_: Principal = Depends(require("assets:read")), db: str = Depends(db_url)) -> AssetSummary:
    """Asset KPIs for the dashboard. Counted by the backend, never by the browser."""
    with get_conn(db) as conn:
        return AssetSummary(**gap_counts(conn))


@router.get("/assets/{enterprise_asset_id}", response_model=AssetDetail)
def get_asset(enterprise_asset_id: str, _: Principal = Depends(require("assets:read")),
              db: str = Depends(db_url)) -> AssetDetail:
    """PRD §8 asset details, addressed by the enterprise asset ID (the one key; see ccc/CONTEXT.md)."""
    with get_conn(db) as conn:
        row = conn.execute(f"{ASSET_SELECT} WHERE a.enterprise_asset_id = %s GROUP BY a.id",
                           (enterprise_asset_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Asset not found")
        sources = conn.execute(
            "SELECT source_system, source_record_id, first_seen_at, last_seen_at FROM asset_sources "
            "WHERE asset_id = %s ORDER BY source_system", (row["id"],)).fetchall()
    asset = _asset(row)
    return AssetDetail(**asset.model_dump(exclude={"source_systems"}),
                       source_systems=[SourceSystemRecord(**s) for s in sources])


@router.get("/assets/{enterprise_asset_id}/history", response_model=Page[HistoryEntry])
def asset_history(enterprise_asset_id: str, _: Principal = Depends(require("assets:read")), db: str = Depends(db_url),
                  limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> Page[HistoryEntry]:
    """What changed on an asset, newest first (PRD §11 history; written by ingestion, never edited)."""
    with get_conn(db) as conn:
        asset = conn.execute("SELECT id FROM assets WHERE enterprise_asset_id = %s", (enterprise_asset_id,)).fetchone()
        if asset is None:
            raise HTTPException(404, "Asset not found")
        total = conn.execute("SELECT count(*) AS n FROM asset_history WHERE asset_id = %s", (asset["id"],)).fetchone()["n"]
        rows = conn.execute(
            "SELECT changed_at, changed_by, field, old_value, new_value FROM asset_history WHERE asset_id = %(id)s "
            "ORDER BY changed_at DESC, id DESC LIMIT %(limit)s OFFSET %(offset)s",
            {"id": asset["id"], "limit": limit, "offset": offset}).fetchall()
    return Page(items=[HistoryEntry(**r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/assets/{enterprise_asset_id}/brief", response_model=AgentResponse)
def brief_asset(enterprise_asset_id: str, p: Principal = Depends(require("agents:run"))) -> AgentResponse:
    """A brief on one asset from the Asset Summary Agent (PRD Module 7). Advisory: nothing is changed (PRD §12)."""
    return summarize_asset(enterprise_asset_id, requested_by=p.subject)


@router.get("/ai/usage", response_model=list[UsageRow])
def ai_usage(_: Principal = Depends(require("ai_usage:read")), db: str = Depends(db_url)) -> list[UsageRow]:
    """PRD Module 8 / §8 /api/v1/ai/usage: tokens and cost by agent and model."""
    with get_conn(db) as conn:
        rows = conn.execute(
            """
            SELECT agent_id, provider, model_id, count(DISTINCT execution_id) AS executions,
                   sum(input_tokens)::int AS input_tokens, sum(output_tokens)::int AS output_tokens,
                   sum(input_tokens + output_tokens)::int AS total_tokens,
                   CASE WHEN bool_and(cost_usd IS NOT NULL) THEN sum(cost_usd)::float ELSE NULL END AS cost_usd
            FROM model_usage GROUP BY agent_id, provider, model_id ORDER BY total_tokens DESC
            """
        ).fetchall()
    return [UsageRow(**r) for r in rows]
