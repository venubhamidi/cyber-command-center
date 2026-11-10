"""Ingestion rules from PRD Module 2."""
from pathlib import Path

from ccc.config import settings
from ccc.ingest import ingest_csv
from harness.db import get_conn


def test_ingest_inserts_all_rows(sample_csv: Path):
    r = ingest_csv(sample_csv)
    assert (r.inserted, r.updated, r.marked_potentially_inactive) == (6, 0, 0)


def test_ingest_is_idempotent(sample_csv: Path):
    ingest_csv(sample_csv)
    r = ingest_csv(sample_csv)
    assert (r.inserted, r.updated) == (0, 6)
    with get_conn(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"] == 6
        # No spurious history rows when nothing changed
        assert conn.execute("SELECT count(*) AS n FROM asset_history").fetchone()["n"] == 0


def test_asset_missing_from_source_is_marked_not_deleted(sample_csv: Path, tmp_path: Path):
    """PRD: 'An asset must not be automatically deleted because it disappears from one source.'"""
    ingest_csv(sample_csv)
    lines = sample_csv.read_text().splitlines()
    shorter = tmp_path / "second_run.csv"
    shorter.write_text("\n".join(line for line in lines if not line.startswith("EA-000004")) + "\n")

    r = ingest_csv(shorter)
    assert r.marked_potentially_inactive == 1
    with get_conn(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) AS n FROM assets").fetchone()["n"] == 6  # still 6
        row = conn.execute("SELECT lifecycle_state::text AS s FROM assets WHERE enterprise_asset_id='EA-000004'").fetchone()
        assert row["s"] == "potentially_inactive"
        hist = conn.execute("SELECT field, old_value, new_value FROM asset_history").fetchall()
        assert {"field": "lifecycle_state", "old_value": "active", "new_value": "potentially_inactive"} in [dict(h) for h in hist]


def test_reappearing_asset_becomes_active_again(sample_csv: Path, tmp_path: Path):
    ingest_csv(sample_csv)
    lines = sample_csv.read_text().splitlines()
    (tmp_path / "s.csv").write_text("\n".join(line for line in lines if not line.startswith("EA-000004")) + "\n")
    ingest_csv(tmp_path / "s.csv")
    ingest_csv(sample_csv)
    with get_conn(settings.database_url) as conn:
        row = conn.execute("SELECT lifecycle_state::text AS s FROM assets WHERE enterprise_asset_id='EA-000004'").fetchone()
        assert row["s"] == "active"


def test_field_change_is_recorded_in_history(sample_csv: Path, tmp_path: Path):
    ingest_csv(sample_csv)
    text = sample_csv.read_text().replace("hr-portal-web01,10.20.2.40,00:1A:2B:3C:4D:03,server,,", "hr-portal-web01,10.20.2.40,00:1A:2B:3C:4D:03,server,k.nguyen,")
    (tmp_path / "owner.csv").write_text(text)
    ingest_csv(tmp_path / "owner.csv")
    with get_conn(settings.database_url) as conn:
        h = conn.execute("SELECT field, old_value, new_value FROM asset_history").fetchall()
        assert [dict(x) for x in h] == [{"field": "asset_owner", "old_value": None, "new_value": "k.nguyen"}]


def test_blank_criticality_becomes_unknown_not_low(sample_csv: Path):
    """Unknown must never be silently treated as a known value (same principle as PRD Module 4)."""
    ingest_csv(sample_csv)
    with get_conn(settings.database_url) as conn:
        row = conn.execute("SELECT criticality::text AS c FROM assets WHERE enterprise_asset_id='EA-000006'").fetchone()
        assert row["c"] == "unknown"
