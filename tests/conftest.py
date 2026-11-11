from pathlib import Path

import pytest

from ccc.config import MIGRATIONS_DIR, settings
from harness.db import apply_migrations, get_conn

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def schema():
    apply_migrations(MIGRATIONS_DIR, database_url=settings.database_url)


@pytest.fixture(autouse=True)
def clean_tables(schema):
    with get_conn(settings.database_url) as conn:
        conn.execute("TRUNCATE kpi_snapshots, risk_assets, risks, incidents, control_assessments, patch_status, findings, "
                     "asset_history, asset_sources, assets, audit_log, model_usage, agent_executions, "
                     "agent_definitions, eval_results, eval_runs RESTART IDENTITY CASCADE")
        conn.commit()
    yield


@pytest.fixture
def sample_csv() -> Path:
    return ROOT / "ccc" / "sample_assets.csv"
