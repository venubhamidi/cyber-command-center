"""CSV asset ingestion (stand-in for the enterprise asset database import until the real connector exists).

PRD Module 2, functional requirement 1: "Import the existing asset database."
PRD rule: an asset that disappears from a source is NOT deleted; it is marked potentially_inactive.

Deterministic Python only. No LLM involvement in ingestion (PRD §9 agent execution principles).
"""
from __future__ import annotations

import csv
import ipaddress
import sys
from dataclasses import dataclass
from pathlib import Path

from ccc.config import settings
from harness.db import get_conn

ASSET_COLUMNS = [
    "enterprise_asset_id", "hostname", "ip_address", "mac_address", "asset_type",
    "asset_owner", "business_unit", "business_service", "criticality", "location",
    "environment", "operating_system",
]


@dataclass
class IngestResult:
    source_system: str
    inserted: int
    updated: int
    marked_potentially_inactive: int


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


# Identifiers PostgreSQL normalizes on storage (MACADDR -> lowercase, INET -> canonical form).
# Normalize before comparing so history only records real changes.
NORMALIZERS = {
    "mac_address": lambda v: v.lower() if v else v,
    "ip_address": lambda v: str(ipaddress.ip_address(v)) if v else v,
}


def _normalize(values: dict[str, str | None]) -> dict[str, str | None]:
    return {k: (NORMALIZERS[k](v) if k in NORMALIZERS else v) for k, v in values.items()}


def ingest_csv(path: Path, source_system: str = "asset_db_csv", changed_by: str = "ingest:csv",
               database_url: str | None = None) -> IngestResult:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))

    missing = [c for c in ASSET_COLUMNS if c not in (rows[0].keys() if rows else ASSET_COLUMNS)]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    inserted = updated = 0
    seen_ids: list[str] = []

    with get_conn(database_url or settings.database_url) as conn:
        for row in rows:
            eid = _clean(row["enterprise_asset_id"])
            if not eid:
                raise ValueError("Row without enterprise_asset_id (PRD: required field)")
            seen_ids.append(eid)
            values = _normalize({c: _clean(row.get(c)) for c in ASSET_COLUMNS})
            values["criticality"] = values["criticality"] or "unknown"
            values["environment"] = values["environment"] or "unknown"

            existing = conn.execute(
                "SELECT * FROM assets WHERE enterprise_asset_id = %s", (eid,)
            ).fetchone()

            if existing is None:
                cur = conn.execute(
                    """
                    INSERT INTO assets (enterprise_asset_id, hostname, ip_address, mac_address, asset_type,
                        asset_owner, business_unit, business_service, criticality, location, environment,
                        operating_system, lifecycle_state)
                    VALUES (%(enterprise_asset_id)s, %(hostname)s, %(ip_address)s, %(mac_address)s, %(asset_type)s,
                        %(asset_owner)s, %(business_unit)s, %(business_service)s, %(criticality)s, %(location)s,
                        %(environment)s, %(operating_system)s, 'active')
                    RETURNING id
                    """,
                    values,
                )
                asset_id = cur.fetchone()["id"]
                inserted += 1
            else:
                asset_id = existing["id"]
                # Record field-level history (PRD req. 10) and update.
                for col in ASSET_COLUMNS:
                    old = existing[col]
                    old_s = str(old) if old is not None else None
                    if old_s != values[col]:
                        conn.execute(
                            "INSERT INTO asset_history (asset_id, changed_by, field, old_value, new_value) VALUES (%s,%s,%s,%s,%s)",
                            (asset_id, changed_by, col, old_s, values[col]),
                        )
                conn.execute(
                    """
                    UPDATE assets SET hostname=%(hostname)s, ip_address=%(ip_address)s, mac_address=%(mac_address)s,
                        asset_type=%(asset_type)s, asset_owner=%(asset_owner)s, business_unit=%(business_unit)s,
                        business_service=%(business_service)s, criticality=%(criticality)s, location=%(location)s,
                        environment=%(environment)s, operating_system=%(operating_system)s,
                        lifecycle_state='active', last_seen_at=now(), updated_at=now()
                    WHERE id=%(id)s
                    """,
                    {**values, "id": asset_id},
                )
                updated += 1

            conn.execute(
                """
                INSERT INTO asset_sources (asset_id, source_system, source_record_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (asset_id, source_system) DO UPDATE SET last_seen_at = now()
                """,
                (asset_id, source_system, eid),
            )

        # Potentially-inactive rule: assets previously reported by THIS source and absent now.
        cur = conn.execute(
            """
            WITH gone AS (
                SELECT a.id FROM assets a
                JOIN asset_sources s ON s.asset_id = a.id AND s.source_system = %s
                WHERE a.lifecycle_state = 'active' AND NOT (a.enterprise_asset_id = ANY(%s))
            )
            UPDATE assets SET lifecycle_state = 'potentially_inactive', updated_at = now()
            WHERE id IN (SELECT id FROM gone)
            RETURNING id
            """,
            (source_system, seen_ids),
        )
        gone_ids = [r["id"] for r in cur.fetchall()]
        for aid in gone_ids:
            conn.execute(
                "INSERT INTO asset_history (asset_id, changed_by, field, old_value, new_value) VALUES (%s,%s,'lifecycle_state','active','potentially_inactive')",
                (aid, changed_by),
            )
        conn.commit()

    return IngestResult(source_system, inserted, updated, len(gone_ids))


if __name__ == "__main__":
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "sample_assets.csv"
    print(ingest_csv(csv_path))
