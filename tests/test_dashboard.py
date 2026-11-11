"""Executive dashboard (PRD Module 1): tables, mock connectors, KPI math, snapshots, endpoint."""
import pytest

from ccc.config import MIGRATIONS_DIR, settings
from ccc.ingest import ingest_csv
from ccc.ingest_sources import ingest_feed, ingest_sources
from ccc.plugins.mock_connectors import Feed
from harness.db import apply_migrations, get_conn


def test_dashboard_migration_is_repeatable():
    """Ticket 01: the dashboard tables exist and applying the migrations again is a no-op."""
    apply_migrations(MIGRATIONS_DIR, database_url=settings.database_url)
    with get_conn(settings.database_url) as conn:
        names = {r["table_name"] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'").fetchall()}
    assert {"findings", "patch_status", "control_assessments", "incidents", "risks", "risk_assets", "kpi_snapshots"} <= names


# --- Ticket 02: mock connectors and source ingestion -------------------------------------------


@pytest.fixture
def seeded(sample_csv):
    """The six sample assets plus every mock feed, as the demo loads them."""
    ingest_csv(sample_csv)
    return ingest_sources()


def _count(table: str, where: str = "TRUE") -> int:
    with get_conn(settings.database_url) as conn:
        return conn.execute(f"SELECT count(*)::int AS n FROM {table} WHERE {where}").fetchone()["n"]


def test_mock_connectors_load_every_dashboard_table_once(seeded):
    """Expected counts come from the files under ccc/mock/, not from the loader."""
    by_kind = {r.kind: r for r in seeded}
    assert by_kind["findings"].inserted == 15 and by_kind["findings"].skipped_unknown_asset == 0
    assert by_kind["patch_status"].inserted == 6
    assert by_kind["control_assessments"].inserted == 12
    assert by_kind["incidents"].inserted == 4
    assert by_kind["risks"].inserted == 6 and _count("risk_assets") == 8
    assert _count("kpi_snapshots", "period_date = '2026-11-09'") == 8
    # Due dates are computed by code from the SLA table (D-038): critical first seen 2026-10-20 is due 2026-10-27.
    with get_conn(settings.database_url) as conn:
        due = conn.execute("SELECT due_at FROM findings WHERE source_record_id = 'TEN-10001'").fetchone()["due_at"]
    assert due.date().isoformat() == "2026-10-27"

    again = {r.kind: r for r in ingest_sources()}
    assert again["findings"].inserted == 0 and again["findings"].updated == 15 and again["findings"].marked_stale == 0
    assert _count("findings") == 15 and _count("risk_assets") == 8


def test_a_record_the_source_stops_reporting_is_marked_stale_not_deleted(seeded):
    feed = Feed("mock_sccm", "patch_status", "2026-11-11T05:30:00Z",
                [{"source_record_id": "SCCM-1", "enterprise_asset_id": "EA-000001", "state": "missing", "missing_count": 1}])
    with get_conn(settings.database_url) as conn:
        r = ingest_feed(conn, feed)
        conn.commit()
    assert (r.inserted, r.updated, r.marked_stale) == (0, 1, 5)
    assert _count("patch_status") == 6
    assert _count("patch_status", "data_quality_status = 'stale'") == 5
    assert _count("patch_status", "state = 'missing' AND data_quality_status = 'ok'") == 1


def test_a_record_for_an_unregistered_asset_is_skipped_and_the_rest_loads(seeded):
    feed = Feed("mock_tenable", "findings", "2026-11-11T03:00:00Z", [
        {"source_record_id": "TEN-20001", "enterprise_asset_id": "EA-999999", "title": "on an unregistered asset",
         "severity": "high", "status": "open", "first_seen_at": "2026-11-11T03:00:00Z", "last_seen_at": "2026-11-11T03:00:00Z"},
        {"source_record_id": "TEN-20002", "enterprise_asset_id": "EA-000004", "title": "new on a known asset",
         "severity": "low", "status": "open", "first_seen_at": "2026-11-11T03:00:00Z", "last_seen_at": "2026-11-11T03:00:00Z"},
    ])
    with get_conn(settings.database_url) as conn:
        r = ingest_feed(conn, feed)
        conn.commit()
    assert (r.inserted, r.skipped_unknown_asset, r.marked_stale) == (1, 1, 15)
    assert _count("findings") == 16
