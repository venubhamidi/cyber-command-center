"""API cross-cutting rules from PRD §8: authorization, pagination, filtering, validation, audit logging."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ccc.config import settings
from ccc.ingest import ingest_csv
from ccc.main import app
from harness.db import get_conn

CISO = {"Authorization": "Bearer dev-ciso-token"}
BIZ = {"Authorization": "Bearer dev-bizowner-token"}


@pytest.fixture
def client(sample_csv: Path):
    ingest_csv(sample_csv)
    return TestClient(app)


def test_missing_token_is_401(client):
    assert client.get("/api/v1/assets").status_code == 401


def test_invalid_token_is_401(client):
    assert client.get("/api/v1/assets", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_role_without_permission_is_403(client):
    r = client.get("/api/v1/assets", headers=BIZ)
    assert r.status_code == 403


def test_list_assets_paginates(client):
    r = client.get("/api/v1/assets?limit=2&offset=2", headers=CISO)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 6 and body["limit"] == 2 and body["offset"] == 2
    assert [a["enterprise_asset_id"] for a in body["items"]] == ["EA-000003", "EA-000004"]


def test_list_assets_filters(client):
    r = client.get("/api/v1/assets?criticality=critical", headers=CISO)
    assert {a["enterprise_asset_id"] for a in r.json()["items"]} == {"EA-000001", "EA-000002", "EA-000005"}


def test_validation_rejects_bad_limit(client):
    assert client.get("/api/v1/assets?limit=0", headers=CISO).status_code == 422
    assert client.get("/api/v1/assets?limit=9999", headers=CISO).status_code == 422


def test_asset_is_addressed_by_enterprise_asset_id(client):
    assert client.get("/api/v1/assets/EA-000001").status_code == 401
    assert client.get("/api/v1/assets/EA-000001", headers=BIZ).status_code == 403
    a = client.get("/api/v1/assets/EA-000001", headers=CISO).json()
    assert a["enterprise_asset_id"] == "EA-000001" and a["hostname"] == "fin-erp-db01"
    assert client.get("/api/v1/assets/1", headers=CISO).status_code == 404        # the row id is not an address


def test_asset_detail_carries_flags_and_completeness_from_the_rules(client):
    """Expected values come from ccc/sample_assets.csv: EA-000003 has no owner, EA-000006 no criticality."""
    a = client.get("/api/v1/assets/EA-000003", headers=CISO).json()
    assert a["flags"] == ["without_owner"]
    assert a["data_completeness"] == {"complete": False, "missing_fields": ["asset_owner"]}
    b = client.get("/api/v1/assets/EA-000006", headers=CISO).json()
    assert b["flags"] == ["without_criticality"] and "criticality" in b["data_completeness"]["missing_fields"]
    c = client.get("/api/v1/assets/EA-000001", headers=CISO).json()
    assert c["flags"] == [] and c["data_completeness"] == {"complete": True, "missing_fields": []}


def test_asset_carries_freshness_and_source_systems(client):
    a = client.get("/api/v1/assets/EA-000001", headers=CISO).json()
    assert a["last_seen_at"] and a["source_systems"] == ["asset_db_csv"]


def test_unknown_asset_is_404(client):
    assert client.get("/api/v1/assets/EA-999999", headers=CISO).status_code == 404


def test_every_api_call_is_audited_including_denied(client):
    client.get("/api/v1/assets")                       # 401
    client.get("/api/v1/assets", headers=BIZ)          # 403
    client.get("/api/v1/assets?limit=1", headers=CISO) # 200
    with get_conn(settings.database_url) as conn:
        rows = conn.execute("SELECT principal, role, status_code FROM audit_log WHERE action='GET /api/v1/assets' ORDER BY id").fetchall()
    assert [(r["principal"], r["role"], r["status_code"]) for r in rows] == [
        ("anonymous", None, 401), ("owner@example.com", "business_owner", 403), ("ciso@example.com", "ciso", 200),
    ]


def test_health_is_public(client):
    r = client.get("/api/v1/platform/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_summary_counts_whole_inventory_not_one_page(client):
    """KPIs come from SQL over all assets; a browser that loaded one page must still see true counts."""
    r = client.get("/api/v1/assets/summary", headers=CISO)
    assert r.status_code == 200
    body = r.json()
    assert (body["total_assets"], body["without_owner"], body["without_criticality"],
            body["potentially_inactive"]) == (6, 1, 1, 0)
    assert body["data_as_of"]
    # The ownerless asset (EA-000003) is not on this page, yet the summary still counts it.
    page = client.get("/api/v1/assets?limit=2", headers=CISO).json()
    assert all(a["asset_owner"] for a in page["items"])


def test_summary_requires_permission(client):
    assert client.get("/api/v1/assets/summary").status_code == 401
    assert client.get("/api/v1/assets/summary", headers=BIZ).status_code == 403
