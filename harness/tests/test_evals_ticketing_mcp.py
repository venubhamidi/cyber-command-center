import json
import sys
from pathlib import Path

import httpx
import pytest

from harness.agents.contract import Agent, AgentSpec, TransientToolError
from harness.agents.gateway import MockGateway
from harness.agents.mcp_client import McpStdioToolClient
from harness.db import get_conn
from harness.evals import Check, EvalCase, EvalSuite, check_case, load_cases, run_suite
from harness.plugins.ticketing import MemoryTicketing, TicketingError, TicketRequest
from harness.plugins.ticketing_servicenow import ServiceNowTicketing
from harness.testing import DictToolClient

REPO_ROOT = str(Path(__file__).resolve().parents[2])


# ---- evals ----
class Flagger(Agent):
    spec = AgentSpec(agent_id="flagger", name="Flagger", version="1.2.0", description="", allowed_tools=["get"])

    def run(self, request):
        record = self.call_tool("get", key=request.input["key"])
        if record is None:
            return self.fail(request, "not_found")
        flags = [] if record["owner"] else ["no_owner"]
        return self.ok(request, {"flags": flags, "summary": self.llm("s", "Summarize.", data=json.dumps(record))}, "x")


RECORDS = {"A": {"owner": "kim"}, "B": {"owner": None}}


def test_check_operators():
    response = {"status": "succeeded", "output": {"flags": ["no_owner"], "summary": "All good", "items": [{"n": 1}]}}
    case = EvalCase(id="c", input={}, checks=[
        Check(path="status", value="succeeded"), Check(path="output.flags", op="contains", value="no_owner"),
        Check(path="output.summary", op="not_contains", value="guaranteed"), Check(path="output.items.0.n", value=1),
        Check(path="status", op="in", value=["succeeded", "failed"]), Check(path="output.flags", op="exists"),
        Check(path="output.nope", op="exists", value=False)])
    assert check_case(case, response) == []
    bad = EvalCase(id="c", input={}, checks=[{"path": "status", "equals": "failed"}, {"path": "output.missing", "equals": 1}])
    assert check_case(bad, response) == ["status equals 'failed': got 'succeeded'", "output.missing: missing"]


def test_run_suite_scores_and_stores_results(conn_factory, database_url, tmp_path):
    (tmp_path / "cases.json").write_text(json.dumps([
        {"id": "owned", "input": {"key": "A"}, "checks": [{"path": "output.flags", "equals": []}]},
        {"id": "ownerless", "input": {"key": "B"}, "checks": [{"path": "output.flags", "equals": ["no_owner"]}]},
        {"id": "missing", "input": {"key": "Z"}, "checks": [{"path": "status", "equals": "failed"},
                                                             {"path": "error", "equals": "not_found"}]},
        {"id": "wrong-expectation", "input": {"key": "A"}, "checks": [{"path": "output.flags", "equals": ["no_owner"]}]},
    ]))
    suite = EvalSuite(lambda: Flagger(MockGateway(), DictToolClient({"get": lambda key: RECORDS.get(key)})), tmp_path)
    run = run_suite(suite, conn_factory)
    assert (run.total, run.passed, run.score) == (4, 3, 0.75)
    assert list(run.failures) == ["wrong-expectation"]
    with get_conn(database_url) as conn:
        stored = conn.execute("SELECT agent_id, agent_version, provider, model_id, total, passed, score::float AS score, "
                              "total_tokens FROM eval_runs").fetchone()
        results = conn.execute("SELECT case_id, passed FROM eval_results ORDER BY case_id").fetchall()
    assert (stored["agent_id"], stored["agent_version"], stored["provider"], stored["model_id"]) == (
        "flagger", "1.2.0", "mock", "mock-v1")
    assert (stored["total"], stored["passed"], stored["score"]) == (4, 3, 0.75) and stored["total_tokens"] > 0
    assert {r["case_id"]: r["passed"] for r in results} == {"owned": True, "ownerless": True, "missing": True,
                                                           "wrong-expectation": False}


def test_duplicate_case_ids_are_rejected(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"id": "x", "input": {}, "checks": []}))
    (tmp_path / "b.json").write_text(json.dumps({"id": "x", "input": {}, "checks": []}))
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(tmp_path)


# ---- ticketing ----
def test_memory_ticketing():
    t = MemoryTicketing()
    ticket = t.create(TicketRequest(title="Fix", description="d", requested_by="kim"))
    assert ticket.number == "TKT0000001" and t.get(ticket.id) == ticket and t.get("nope") is None


def servicenow(handler) -> ServiceNowTicketing:
    return ServiceNowTicketing("https://acme.service-now.com", "svc_app", "pw", transport=httpx.MockTransport(handler))


def test_servicenow_create_and_read_use_the_table_api():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.method] = request
        if request.method == "POST":
            return httpx.Response(201, json={"result": {"sys_id": "abc123", "number": "INC0010001", "state": "1"}})
        if request.url.path.endswith("/abc123"):
            return httpx.Response(200, json={"result": {"sys_id": "abc123", "number": "INC0010001", "state": "2"}})
        return httpx.Response(404, json={"error": {"message": "No Record found"}})

    sn = servicenow(handler)
    ticket = sn.create(TicketRequest(title="Patch fin-erp-db01", description="3 critical findings", severity="critical",
                                     requested_by="ciso@example.com", external_ref="EA-000001"))
    post = seen["POST"]
    assert post.url == "https://acme.service-now.com/api/now/table/incident"
    assert post.headers["authorization"].startswith("Basic ") and post.headers["accept"] == "application/json"
    body = json.loads(post.content)
    assert (body["short_description"], body["urgency"], body["impact"], body["correlation_id"]) == (
        "Patch fin-erp-db01", "1", "1", "EA-000001")
    assert (ticket.id, ticket.number, ticket.status) == ("abc123", "INC0010001", "1")
    assert ticket.url == "https://acme.service-now.com/nav_to.do?uri=incident.do?sys_id=abc123"
    assert sn.get("abc123").status == "2"
    assert sn.get("missing") is None


def test_servicenow_failures_are_reported_without_leaking_details():
    sn = servicenow(lambda request: httpx.Response(500, text="stack trace with internal hostnames"))
    with pytest.raises(TicketingError) as err:
        sn.create(TicketRequest(title="t", description="d", requested_by="kim"))
    assert "internal hostnames" not in str(err.value)

    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(TicketingError):
        servicenow(down).get("abc")


def test_servicenow_requires_https_and_credentials():
    with pytest.raises(ValueError):
        ServiceNowTicketing("http://acme.service-now.com", "u", "p")
    with pytest.raises(ValueError):
        ServiceNowTicketing("https://acme.service-now.com", "u", "")


# ---- MCP client ----
def test_mcp_client_calls_a_real_server_over_stdio():
    client = McpStdioToolClient(sys.executable, ["-m", "harness.tests.echo_mcp_server"], cwd=REPO_ROOT)
    assert client.call("echo", text="hello") == {"echo": "hello"}


def test_mcp_client_timeout_is_a_retryable_error():
    hung = McpStdioToolClient(sys.executable, ["-c", "import time; time.sleep(30)"], timeout_s=1.0)
    with pytest.raises(TransientToolError, match="timed out"):
        hung.call("echo", text="x")
