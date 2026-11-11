"""The Asset Summary Agent (PRD §9, Modules 5, 7 and 8)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ccc.agents.asset_agent import AssetSummaryAgent, summarize_asset
from ccc.config import settings
from ccc.evals import EVAL_SUITES
from ccc.ingest import ingest_csv
from ccc.main import app
from ccc.mcp_servers.asset_mcp.server import TOOLS
from harness.agents.contract import AgentRequest, AgentRunner
from harness.agents.guardrails import Redactor
from harness.audit import verify_audit_chain
from harness.db import conn_factory, get_conn
from harness.evals import run_suite
from harness.testing import DictToolClient, ScriptedGateway

CISO = {"Authorization": "Bearer dev-ciso-token"}
AUDITOR = {"Authorization": "Bearer dev-auditor-token"}
BRIEF = '{"executive_summary": "S [IPV4_1]", "business_impact": "I", "recommended_action": "A"}'


@pytest.fixture(autouse=True)
def assets(sample_csv: Path):
    ingest_csv(sample_csv)


def in_process(asset_id: str):
    return summarize_asset(asset_id, requested_by="test", tools=DictToolClient(TOOLS))


def test_flags_are_computed_by_rules_and_match_the_api():
    resp = in_process("EA-000003")
    assert resp.status == "succeeded" and resp.confidence == "advisory"
    assert resp.output["data_quality_flags"] == ["no_owner"]
    assert resp.output["data_completeness"] == {"complete": False, "missing_fields": ["asset_owner"]}
    assert in_process("EA-000006").output["data_quality_flags"] == ["no_criticality"]
    summary = TestClient(app).get("/api/v1/assets/summary", headers=CISO).json()
    assert (summary["without_owner"], summary["without_criticality"]) == (1, 1)


def test_response_carries_sources_timestamp_and_completeness():
    """PRD Module 7 mandatory response format."""
    out = in_process("EA-000001").output
    assert set(out) == {"executive_summary", "supporting_facts", "business_impact", "recommended_action",
                        "source_references", "last_updated", "data_completeness", "data_quality_flags"}
    assert out["source_references"] == ["asset_db_csv"] and out["last_updated"]
    assert out["data_completeness"] == {"complete": True, "missing_fields": []}


def test_ip_addresses_never_reach_the_model_but_are_intact_in_the_result():
    gateway = ScriptedGateway([BRIEF])
    agent = AssetSummaryAgent(gateway, DictToolClient(TOOLS), redactor=Redactor(settings.redact_patterns))
    resp = AgentRunner(conn_factory(settings.database_url)).execute(
        agent, AgentRequest(requested_by="test", input={"enterprise_asset_id": "EA-000001"}))
    assert "10.20.1.15" not in gateway.calls[0]["user"] and "[IPV4_1]" in gateway.calls[0]["user"]
    assert resp.output["executive_summary"] == "S 10.20.1.15"            # restored for the reader
    assert resp.output["supporting_facts"]["ip_address"] == "10.20.1.15"
    assert "redacted:1" in resp.guardrail_events


def test_execution_usage_and_tool_calls_are_recorded():
    resp = in_process("EA-000001")
    with get_conn(settings.database_url) as conn:
        ex = conn.execute("SELECT status, tool_calls, llm_calls, requested_by FROM agent_executions "
                          "WHERE execution_id=%s", (resp.execution_id,)).fetchone()
        usage = conn.execute("SELECT provider, input_tokens FROM model_usage WHERE execution_id=%s",
                             (resp.execution_id,)).fetchall()
        audit = conn.execute("SELECT principal, action FROM audit_log WHERE role='agent'").fetchall()
        assert verify_audit_chain(conn) == (True, None)
    assert (ex["status"], ex["tool_calls"], ex["llm_calls"], ex["requested_by"]) == ("succeeded", 1, 1, "test")
    assert len(usage) == 1 and usage[0]["provider"] == "mock" and usage[0]["input_tokens"] > 0
    assert [(a["principal"], a["action"]) for a in audit] == [("asset-summary-agent", "TOOL get_asset")]


def test_unknown_asset_fails_cleanly():
    resp = in_process("EA-DOES-NOT-EXIST")
    assert resp.status == "failed" and resp.error == "asset_not_found" and resp.llm_calls == 0


def test_agent_does_not_write_to_assets():
    """PRD Module 5: agents recommend, never decide. No stored value may change."""
    with get_conn(settings.database_url) as conn:
        before = conn.execute("SELECT * FROM assets ORDER BY id").fetchall()
    in_process("EA-000003")
    with get_conn(settings.database_url) as conn:
        assert conn.execute("SELECT * FROM assets ORDER BY id").fetchall() == before


def test_brief_endpoint_runs_the_agent_over_real_mcp_and_needs_permission():
    c = TestClient(app)
    assert c.post("/api/v1/assets/EA-000003/brief").status_code == 401
    assert c.post("/api/v1/assets/EA-000003/brief", headers=AUDITOR).status_code == 403     # auditors read, not run
    r = c.post("/api/v1/assets/EA-000003/brief", headers=CISO)
    assert r.status_code == 200
    assert c.post("/api/v1/assets/EA-000003/review", headers=CISO).status_code == 404        # the old word is gone (D-028)
    body = r.json()
    assert body["status"] == "succeeded" and body["output"]["data_quality_flags"] == ["no_owner"]
    assert body["output"]["supporting_facts"]["hostname"] == "hr-portal-web01"
    assert (body["tool_calls"], body["llm_calls"]) == (1, 1)


def test_agent_evals_pass():
    for name, suite in EVAL_SUITES.items():
        run = run_suite(suite, conn_factory(settings.database_url))
        assert run.score == 1.0, (name, run.failures)
