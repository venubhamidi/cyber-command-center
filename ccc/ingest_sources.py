"""Load the dashboard tables from connectors (PRD Modules 3 to 6 sources; mock today).

Deterministic Python only. Every record is upserted on (source_system, source_record_id); a record
the source no longer reports is marked data_quality_status = 'stale', never deleted (PRD §7 rule,
ARCHITECTURE.md "Executive dashboard"). A record for an asset the inventory lacks is skipped and
counted: the inventory is the one key (ccc/CONTEXT.md: enterprise asset ID), not the scanner.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ccc.config import settings
from ccc.plugins.mock_connectors import Feed
from harness import plugins
from harness.db import get_conn


@dataclass
class SourceIngestResult:
    source_system: str
    kind: str
    inserted: int
    updated: int
    skipped_unknown_asset: int
    marked_stale: int


def _asset_ids(conn) -> dict[str, int]:
    return {r["enterprise_asset_id"]: r["id"] for r in conn.execute("SELECT id, enterprise_asset_id FROM assets").fetchall()}


def _due_at(first_seen_at: str, severity: str) -> datetime | None:
    """Remediation due date: first sighting plus the SLA days for the severity (D-038). None when no SLA."""
    days = settings.sla_days.get(severity)
    if days is None:
        return None
    return datetime.fromisoformat(first_seen_at.replace("Z", "+00:00")) + timedelta(days=days)


# Columns written per kind, besides the provenance ones every table shares.
_COLUMNS = {
    "findings": ("asset_id", "cve", "title", "severity", "cvss", "exploitable", "known_exploited", "status",
                 "first_seen_at", "last_seen_at", "due_at", "closed_at"),
    "patch_status": ("asset_id", "state", "missing_count"),
    "control_assessments": ("framework", "control_id", "title", "status", "effectiveness", "assessor", "assessed_at"),
    "incidents": ("title", "severity", "status", "opened_at", "closed_at"),
    "risks": ("title", "business_unit", "business_service", "rating", "business_impact", "owner",
              "recommended_action", "model_version"),
}
_KEY = {"patch_status": ("asset_id", "source_system")}      # one row per asset per source


def _upsert(conn, kind: str, row: dict[str, Any]) -> bool:
    """Insert or update one record. Returns True when inserted."""
    cols = (*_COLUMNS[kind], "source_system", "source_record_id", "collected_at")
    key = _KEY.get(kind, ("source_system", "source_record_id"))
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key)
    r = conn.execute(
        f"INSERT INTO {kind} ({', '.join(cols)}) VALUES ({', '.join('%(' + c + ')s' for c in cols)}) "
        f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {sets}, updated_at = now(), data_quality_status = 'ok' "
        "RETURNING (xmax = 0) AS inserted",
        {c: row.get(c) for c in cols},
    ).fetchone()
    return bool(r["inserted"])


def ingest_feed(conn, feed: Feed) -> SourceIngestResult:
    inserted = updated = skipped = 0
    seen: list[str] = []

    if feed.kind == "kpi_snapshots":
        for rec in feed.records:
            conn.execute(
                "INSERT INTO kpi_snapshots (kpi, period_date, value, formula_version, source_systems) "
                "VALUES (%(kpi)s, %(period_date)s, %(value)s, %(formula_version)s, %(source_systems)s) "
                "ON CONFLICT (kpi, period_date) DO NOTHING", rec)
            inserted += 1
        return SourceIngestResult(feed.source_system, feed.kind, inserted, 0, 0, 0)

    assets = _asset_ids(conn)
    for rec in feed.records:
        row = {**rec, "source_system": feed.source_system, "collected_at": feed.collected_at}
        if "enterprise_asset_id" in rec:
            asset_id = assets.get(rec["enterprise_asset_id"])
            if asset_id is None:
                skipped += 1
                continue
            row["asset_id"] = asset_id
        if feed.kind == "findings":
            row["due_at"] = _due_at(rec["first_seen_at"], rec["severity"])
        seen.append(rec["source_record_id"])
        if _upsert(conn, feed.kind, row):
            inserted += 1
        else:
            updated += 1
        if feed.kind == "risks":
            risk_id = conn.execute("SELECT id FROM risks WHERE source_system = %s AND source_record_id = %s",
                                   (feed.source_system, rec["source_record_id"])).fetchone()["id"]
            for eaid in rec.get("assets", []):
                if eaid in assets:
                    conn.execute("INSERT INTO risk_assets (risk_id, asset_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                 (risk_id, assets[eaid]))

    stale = conn.execute(
        f"UPDATE {feed.kind} SET data_quality_status = 'stale', updated_at = now() "
        "WHERE source_system = %s AND data_quality_status <> 'stale' AND NOT (source_record_id = ANY(%s)) RETURNING 1",
        (feed.source_system, seen)).fetchall()
    return SourceIngestResult(feed.source_system, feed.kind, inserted, updated, skipped, len(stale))


def ingest_sources(names: list[str] | None = None, database_url: str | None = None) -> list[SourceIngestResult]:
    """Fetch every configured connector and load its feed. Each feed is one transaction."""
    results = []
    for name in names or settings.connectors:
        feed = plugins.create("connector", name, settings).fetch()
        with get_conn(database_url or settings.database_url) as conn:
            results.append(ingest_feed(conn, feed))
            conn.commit()
    return results


if __name__ == "__main__":
    for result in ingest_sources(sys.argv[1:] or None):
        print(result)
