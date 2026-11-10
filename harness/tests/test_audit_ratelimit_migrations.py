import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harness.audit import append_audit, verify_audit_chain
from harness.db import MigrationError, apply_migrations, get_conn
from harness.ratelimit import RateLimitMiddleware
from harness.tests.conftest import OUTSIDER, READER


# ---- audit ----
def test_every_api_call_is_audited_including_denied(make_app, database_url):
    c = TestClient(make_app())
    c.get("/api/v1/things")
    c.get("/api/v1/things", headers=OUTSIDER)
    c.get("/api/v1/things?limit=1", headers=READER)
    with get_conn(database_url) as conn:
        rows = conn.execute("SELECT principal, role, status_code FROM audit_log ORDER BY id").fetchall()
        assert [(r["principal"], r["role"], r["status_code"]) for r in rows] == [
            ("anonymous", None, 401), ("outsider@example.com", "outsider", 403), ("reader@example.com", "reader", 200)]
        assert verify_audit_chain(conn) == (True, None)


def test_audit_chain_detects_an_edited_row_and_a_deleted_row(database_url):
    with get_conn(database_url) as conn:
        for i in range(4):
            append_audit(conn, principal=f"user{i}", role="reader", action="GET /x", status_code=200,
                         detail={"n": i, "nested": {"b": 1, "a": 2}})
        conn.commit()
        assert verify_audit_chain(conn) == (True, None)

        conn.execute("UPDATE audit_log SET principal='someone-else' WHERE id=2")
        assert verify_audit_chain(conn) == (False, 2)
        conn.rollback()

        conn.execute("DELETE FROM audit_log WHERE id=3")
        assert verify_audit_chain(conn) == (False, 4)
        conn.rollback()


# ---- rate limiting ----
def test_rate_limit_refuses_with_429_and_audits_it(make_app, database_url):
    c = TestClient(make_app(rate_limit_per_minute=3))
    codes = [c.get("/api/v1/things", headers=READER).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    refused = c.get("/api/v1/things", headers=READER)
    assert int(refused.headers["Retry-After"]) >= 1
    assert c.get("/api/v1/things", headers=OUTSIDER).status_code == 403      # another caller has its own budget
    for _ in range(10):
        assert c.get("/api/v1/platform/health").status_code == 200           # probes are exempt
    with get_conn(database_url) as conn:
        n = conn.execute("SELECT count(*) AS n FROM audit_log WHERE status_code=429").fetchone()["n"]
    assert n == 3


def test_rate_limit_window_resets():
    now = [0.0]
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit_per_minute=1, clock=lambda: now[0])

    @app.get("/api/ping")
    def ping():
        return {}

    c = TestClient(app)
    assert [c.get("/api/ping").status_code, c.get("/api/ping").status_code] == [200, 429]
    now[0] = 61.0
    assert c.get("/api/ping").status_code == 200


# ---- migrations ----
def test_migrations_apply_once_and_refuse_edited_files(database_url, tmp_path):
    first = tmp_path / "900_tmp.sql"
    first.write_text("CREATE TABLE zz_migration_test (id INT);")
    try:
        assert apply_migrations(tmp_path, database_url=database_url) == ["app/900_tmp.sql"]
        assert apply_migrations(tmp_path, database_url=database_url) == []          # not re-applied
        (tmp_path / "901_tmp.sql").write_text("ALTER TABLE zz_migration_test ADD COLUMN note TEXT;")
        assert apply_migrations(tmp_path, database_url=database_url) == ["app/901_tmp.sql"]
        first.write_text("CREATE TABLE zz_migration_test (id BIGINT);")             # history rewritten
        with pytest.raises(MigrationError, match="changed after it was applied"):
            apply_migrations(tmp_path, database_url=database_url)
    finally:
        with get_conn(database_url) as conn:
            conn.execute("DROP TABLE IF EXISTS zz_migration_test")
            conn.execute("DELETE FROM schema_migrations WHERE filename LIKE '90%_tmp.sql'")
            conn.commit()
