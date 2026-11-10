"""PostgreSQL access and migrations.

Migrations are numbered *.sql files. Each file is applied exactly once and recorded in
schema_migrations with its checksum; changing a file after it has been applied is an error
(write a new file instead). Harness migrations run first, then the application's.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from harness.config import get_settings

HARNESS_MIGRATIONS = Path(__file__).resolve().parent / "migrations"


class MigrationError(RuntimeError):
    pass


@contextmanager
def get_conn(database_url: str | None = None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url or get_settings().database_url, row_factory=dict_row) as conn:
        yield conn


def conn_factory(database_url: str) -> Callable[[], Iterator[psycopg.Connection]]:
    """A zero-argument get_conn bound to one database (for AgentRunner and CLIs)."""
    return partial(get_conn, database_url)


def apply_migrations(*app_dirs: Path, database_url: str | None = None) -> list[str]:
    """Apply pending migrations. Returns the files applied in this call (empty if up to date)."""
    applied: list[str] = []
    with get_conn(database_url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7461001)")        # one migrator at a time
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                            source TEXT NOT NULL, filename TEXT NOT NULL, checksum TEXT NOT NULL,
                            applied_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (source, filename))""")
        done = {(r["source"], r["filename"]): r["checksum"]
                for r in conn.execute("SELECT source, filename, checksum FROM schema_migrations").fetchall()}
        for directory in (HARNESS_MIGRATIONS, *app_dirs):
            source = "harness" if directory == HARNESS_MIGRATIONS else "app"
            for path in sorted(directory.glob("*.sql")):
                sql = path.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                recorded = done.get((source, path.name))
                if recorded == checksum:
                    continue
                if recorded is not None:
                    raise MigrationError(f"{source}/{path.name} was changed after it was applied. "
                                         "Restore it and put the change in a new numbered file.")
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations (source, filename, checksum) VALUES (%s,%s,%s)",
                             (source, path.name, checksum))
                applied.append(f"{source}/{path.name}")
        conn.commit()
    return applied
