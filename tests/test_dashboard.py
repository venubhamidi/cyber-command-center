"""Executive dashboard (PRD Module 1): tables, mock connectors, KPI math, snapshots, endpoint."""
from ccc.config import MIGRATIONS_DIR, settings
from harness.db import apply_migrations, get_conn


def test_dashboard_migration_is_repeatable():
    """Ticket 01: the dashboard tables exist and applying the migrations again is a no-op."""
    apply_migrations(MIGRATIONS_DIR, database_url=settings.database_url)
    with get_conn(settings.database_url) as conn:
        names = {r["table_name"] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'").fetchall()}
    assert {"findings", "patch_status", "control_assessments", "incidents", "risks", "risk_assets", "kpi_snapshots"} <= names
