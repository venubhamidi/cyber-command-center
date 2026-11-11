"""Executive dashboard (PRD Module 1): tables, mock connectors, KPI math, snapshots, endpoint."""
from datetime import UTC, date, datetime

import pytest

from ccc.config import MIGRATIONS_DIR, settings
from ccc.dashboard import compute_kpis
from ccc.ingest import ingest_csv
from ccc.ingest_sources import ingest_feed, ingest_sources
from ccc.plugins.mock_connectors import Feed
from ccc.snapshot import previous_values, trend, write_snapshots
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


# --- Ticket 03: KPI math --------------------------------------------------------------------------

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _kpis(now=NOW):
    with get_conn(settings.database_url) as conn:
        return compute_kpis(conn, now=now)


def test_every_kpi_matches_the_hand_count_over_the_mock_data(seeded):
    """Expected values were counted by hand from ccc/mock/*.json and ccc/sample_assets.csv (see the
    comments), with "now" fixed at 2026-11-10 12:00 UTC."""
    k = _kpis()
    assert k["critical_assets"].value == 3                 # EA-000001, EA-000002, EA-000005: critical and active
    assert k["vulnerability_exposure"].value == 7          # open critical/high, one per (cve, asset): EA1 x3, EA2, EA3, EA5, EA6
    assert k["patch_compliance"].value == 33.3             # compliant 1 / applicable 3 (compliant, missing, failed)
    assert k["nist_compliance"].value == 59.1              # (5 x 1.0 + 3 x 0.5) / 11 applicable (PE-3 not applicable)
    assert k["open_incidents"].value == 2                  # INC-2041, INC-2039
    assert k["remediation_sla"].value == 42.9              # within 3 / eligible 7 (4 closed + 3 open past due)
    assert k["enterprise_risk_score"].value == 56.9        # mean(70, 66.7, 40.9, 50)
    assert k["security_posture"].value == 43.1             # 100 - 56.9
    assert k["patch_compliance"].source_systems == ["mock_sccm"]
    assert k["patch_compliance"].data_as_of.isoformat() == "2026-11-10T05:30:00+00:00"
    assert k["critical_assets"].source_systems == ["asset_db_csv"]
    assert all(v.formula_version == "v0" for v in k.values())


def test_sla_counts_a_finding_as_eligible_only_once_its_due_date_has_passed(seeded):
    """With now at 2026-10-28 only TEN-10001 (due 10-27) is overdue among the open findings, so
    eligible = 4 closed + 1 overdue and within = 3 of the closed ones."""
    k = _kpis(now=datetime(2026, 10, 28, 12, 0, tzinfo=UTC))
    assert k["remediation_sla"].value == 60.0


def test_unknown_patch_status_is_never_compliant(sample_csv):
    ingest_csv(sample_csv)
    feed = Feed("mock_sccm", "patch_status", "2026-11-10T05:30:00Z", [
        {"source_record_id": f"SCCM-{n}", "enterprise_asset_id": f"EA-00000{n}", "state": state, "missing_count": 0}
        for n, state in enumerate(("unknown", "unknown", "offline", "exempt", "non_applicable", "unknown"), start=1)])
    with get_conn(settings.database_url) as conn:
        ingest_feed(conn, feed)
        conn.commit()
    k = _kpis()
    assert k["patch_compliance"].value is None             # no applicable system: unknown, not 100 and not 0
    assert k["enterprise_risk_score"].value is None        # nothing else loaded either: no favourable default


def test_the_same_cve_on_one_asset_from_two_scanners_counts_once(seeded):
    feed = Feed("mock_defender", "findings", "2026-11-10T07:00:00Z", [
        {"source_record_id": "DEF-1", "enterprise_asset_id": "EA-000001", "cve": "CVE-2024-3094", "title": "xz backdoor",
         "severity": "critical", "status": "open", "first_seen_at": "2026-10-21T03:00:00Z", "last_seen_at": "2026-11-10T03:00:00Z"},
        {"source_record_id": "DEF-2", "enterprise_asset_id": "EA-000004", "cve": "CVE-2024-3094", "title": "xz backdoor",
         "severity": "critical", "status": "open", "first_seen_at": "2026-11-09T03:00:00Z", "last_seen_at": "2026-11-10T03:00:00Z"},
    ])
    with get_conn(settings.database_url) as conn:
        ingest_feed(conn, feed)
        conn.commit()
    k = _kpis()
    assert k["vulnerability_exposure"].value == 8          # DEF-1 duplicates TEN-10001; DEF-2 is new on EA-000004
    assert k["vulnerability_exposure"].source_systems == ["mock_defender", "mock_tenable"]


def test_stale_rows_are_left_out_of_every_count(seeded):
    with get_conn(settings.database_url) as conn:
        ingest_feed(conn, Feed("mock_chronicle", "incidents", "2026-11-11T06:10:00Z", []))   # the source now reports nothing
        conn.commit()
    k = _kpis()
    assert k["open_incidents"].value is None and k["open_incidents"].source_systems == []   # unknown, not zero


# --- Ticket 04: snapshots and trend ---------------------------------------------------------------

def test_previous_value_and_trend_come_from_the_latest_earlier_snapshot(seeded):
    """The mock history holds 2026-11-09 values; today's are computed. patch 33.3 = 33.3 flat,
    exposure 7 < 9 down, risk 56.9 < 61.2 down, posture 43.1 > 38.8 up."""
    with get_conn(settings.database_url) as conn:
        assert write_snapshots(conn, date(2026, 11, 10), now=NOW) == 8
        assert write_snapshots(conn, date(2026, 11, 10), now=NOW) == 8          # same day again: replaced, not duplicated
        conn.commit()
        prev = previous_values(conn, date(2026, 11, 10))
        k = compute_kpis(conn, now=NOW)
    assert _count("kpi_snapshots") == 16
    assert prev["vulnerability_exposure"] == (9.0, date(2026, 11, 9))
    assert trend(k["patch_compliance"].value, prev["patch_compliance"][0]) == "flat"
    assert trend(k["vulnerability_exposure"].value, prev["vulnerability_exposure"][0]) == "down"
    assert trend(k["enterprise_risk_score"].value, prev["enterprise_risk_score"][0]) == "down"
    assert trend(k["security_posture"].value, prev["security_posture"][0]) == "up"


def test_no_snapshot_means_no_history_not_zero(sample_csv):
    ingest_csv(sample_csv)
    with get_conn(settings.database_url) as conn:
        assert previous_values(conn, date(2026, 11, 10)) == {}
        assert write_snapshots(conn, date(2026, 11, 10), now=NOW) == 1           # only critical_assets has a value
    assert trend(3.0, None) == "no_history"
