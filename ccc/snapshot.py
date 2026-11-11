"""Record today's KPI values (PRD Module 1: previous-period value and trend).

`python -m ccc.snapshot [YYYY-MM-DD]` writes one row per KPI for the day into `kpi_snapshots`,
replacing that day's row if it exists (idempotent). Ops runs it once a day; there is no scheduler
in the application (ARCHITECTURE.md). A KPI with no value today writes no row.
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from typing import Literal

from ccc.config import settings
from ccc.dashboard import compute_kpis
from harness.db import get_conn

Trend = Literal["up", "down", "flat", "no_history"]


def write_snapshots(conn, period_date: date | None = None, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    period_date = period_date or now.date()
    written = 0
    for k in compute_kpis(conn, now=now).values():
        if k.value is None:
            continue
        conn.execute(
            "INSERT INTO kpi_snapshots (kpi, period_date, value, formula_version, source_systems, computed_at) "
            "VALUES (%s, %s, %s, %s, %s, now()) ON CONFLICT (kpi, period_date) DO UPDATE SET value = EXCLUDED.value, "
            "formula_version = EXCLUDED.formula_version, source_systems = EXCLUDED.source_systems, computed_at = now()",
            (k.kpi, period_date, k.value, k.formula_version, k.source_systems))
        written += 1
    return written


def previous_values(conn, before: date) -> dict[str, tuple[float, date]]:
    """For each KPI, the latest snapshot strictly before `before`: the previous period."""
    rows = conn.execute(
        "SELECT DISTINCT ON (kpi) kpi, value::float AS value, period_date FROM kpi_snapshots "
        "WHERE period_date < %s ORDER BY kpi, period_date DESC", (before,)).fetchall()
    return {r["kpi"]: (r["value"], r["period_date"]) for r in rows}


def trend(current: float | None, previous: float | None) -> Trend:
    if current is None or previous is None:
        return "no_history"
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "flat"


if __name__ == "__main__":
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    with get_conn(settings.database_url) as conn:
        n = write_snapshots(conn, day)
        conn.commit()
    print(f"wrote {n} snapshots for {day or date.today()}")
