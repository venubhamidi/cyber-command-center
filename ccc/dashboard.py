"""Executive dashboard KPIs (PRD Module 1), computed in SQL and Python. No model anywhere.

Every rule here is the one the PRD states, or a provisional one recorded in DECISIONS.md:
patch compliance excludes unknown, offline, exempt and non-applicable (Module 4); exposure counts
one finding per CVE per asset (Module 3 "deduplicated"); NIST weights are provisional (D-008);
the risk score and posture are provisional v0 (D-039); SLA days come from settings (D-038).
Stale rows (a source stopped reporting them) are left out of every count, and a KPI whose source
has reported nothing is None (unknown), never zero.

`FORMULA_VERSION` is stored on every snapshot so a change of weights never rewrites history.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

FORMULA_VERSION = "v0"

Unit = Literal["count", "percent", "score"]

# What a KPI tile needs to know besides its number: its unit, which way is good, and where it drills down.
KPIS: dict[str, tuple[Unit, Literal["up", "down"], str]] = {
    "enterprise_risk_score": ("score", "down", "/?view=risks"),
    "security_posture": ("score", "up", "/?view=risks"),
    "patch_compliance": ("percent", "up", "/?view=patch-status"),
    "vulnerability_exposure": ("count", "down", "/?view=findings"),
    "nist_compliance": ("percent", "up", "/?view=controls"),
    "critical_assets": ("count", "up", "/?view=assets&criticality=critical"),
    "open_incidents": ("count", "down", "/?view=incidents"),
    "remediation_sla": ("percent", "up", "/?view=findings"),
}

NIST_WEIGHTS = {"implemented": 1.0, "partially_implemented": 0.5}   # every other state counts 0 (D-008)


@dataclass
class KpiValue:
    kpi: str
    value: float | None               # None = cannot be computed from the data (never a favourable default)
    unit: Unit
    data_as_of: datetime | None
    source_systems: list[str]
    formula_version: str = FORMULA_VERSION


def _pct(num: float, den: float) -> float | None:
    return None if not den else round(100.0 * num / den, 1)


def _one(conn, sql: str, params: tuple = ()) -> dict:
    return dict(conn.execute(sql, params).fetchone())


def _sources(conn, table: str) -> list[str]:
    rows = conn.execute(f"SELECT DISTINCT source_system FROM {table} WHERE data_quality_status = 'ok' ORDER BY 1").fetchall()
    return [r["source_system"] for r in rows]


def compute_kpis(conn, now: datetime | None = None) -> dict[str, KpiValue]:
    """All eight KPIs over the whole database. `now` is a parameter so tests are stable."""
    now = now or datetime.now(UTC)

    a = _one(conn, "SELECT (count(*) FILTER (WHERE criticality = 'critical' AND lifecycle_state = 'active'))::int AS n, "
                   "max(last_seen_at) AS as_of FROM assets")
    asset_sources = [r["source_system"] for r in conn.execute("SELECT DISTINCT source_system FROM asset_sources ORDER BY 1").fetchall()]

    f = _one(conn, """
        SELECT (SELECT count(*) FROM (SELECT DISTINCT asset_id, COALESCE(cve, 'finding:' || id::text) FROM findings
                 WHERE status = 'open' AND severity IN ('critical','high') AND data_quality_status = 'ok') d)::int AS exposure,
               (count(*) FILTER (WHERE status = 'closed' AND due_at IS NOT NULL AND closed_at <= due_at))::int AS within_sla,
               (count(*) FILTER (WHERE due_at IS NOT NULL AND (status = 'closed' OR due_at < %s)))::int AS sla_eligible,
               min(collected_at) AS as_of
        FROM findings WHERE data_quality_status = 'ok'""", (now,))

    p = _one(conn, """
        SELECT (count(*) FILTER (WHERE state = 'compliant'))::int AS compliant,
               (count(*) FILTER (WHERE state IN ('compliant','missing','failed')))::int AS applicable,
               min(collected_at) AS as_of
        FROM patch_status WHERE data_quality_status = 'ok'""")

    c = _one(conn, """
        SELECT COALESCE(sum(CASE status WHEN 'implemented' THEN %s WHEN 'partially_implemented' THEN %s ELSE 0 END), 0) AS score,
               (count(*) FILTER (WHERE status <> 'not_applicable'))::int AS applicable,
               min(collected_at) AS as_of
        FROM control_assessments WHERE data_quality_status = 'ok'""",
        (NIST_WEIGHTS["implemented"], NIST_WEIGHTS["partially_implemented"]))

    i = _one(conn, "SELECT (count(*) FILTER (WHERE status = 'open'))::int AS n, min(collected_at) AS as_of "
                   "FROM incidents WHERE data_quality_status = 'ok'")

    patch = _pct(p["compliant"], p["applicable"])
    nist = _pct(float(c["score"]), c["applicable"])
    sla = _pct(f["within_sla"], f["sla_eligible"])

    # Provisional v0 (D-039): the mean of four pressures on a 0..100 scale. Components the data cannot
    # give are left out of the mean rather than assumed zero.
    components = [
        min(100.0, 10.0 * f["exposure"]) if f["as_of"] else None,     # ten critical/high findings = full pressure
        None if patch is None else 100.0 - patch,
        None if nist is None else 100.0 - nist,
        min(100.0, 25.0 * i["n"]) if i["as_of"] else None,             # four open incidents = full pressure
    ]
    present = [x for x in components if x is not None]
    risk = round(sum(present) / len(present), 1) if present else None
    posture = None if risk is None else round(100.0 - risk, 1)
    risk_sources = sorted(set(_sources(conn, "findings") + _sources(conn, "patch_status")
                              + _sources(conn, "control_assessments") + _sources(conn, "incidents")))
    risk_as_of = min((x for x in (f["as_of"], p["as_of"], c["as_of"], i["as_of"]) if x), default=None)

    values = {
        "enterprise_risk_score": (risk, risk_as_of, risk_sources),
        "security_posture": (posture, risk_as_of, risk_sources),
        "patch_compliance": (patch, p["as_of"], _sources(conn, "patch_status")),
        "vulnerability_exposure": (float(f["exposure"]) if f["as_of"] else None, f["as_of"], _sources(conn, "findings")),
        "nist_compliance": (nist, c["as_of"], _sources(conn, "control_assessments")),
        "critical_assets": (float(a["n"]), a["as_of"], asset_sources),
        "open_incidents": (float(i["n"]) if i["as_of"] else None, i["as_of"], _sources(conn, "incidents")),
        "remediation_sla": (sla, f["as_of"], _sources(conn, "findings")),
    }
    return {k: KpiValue(k, v, KPIS[k][0], as_of, src) for k, (v, as_of, src) in values.items()}
