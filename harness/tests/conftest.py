"""Fixtures for the harness's own tests. They build throwaway applications with create_app(),
so they do not depend on whichever application lives in this repository."""
import pytest
from fastapi import APIRouter, Depends

from harness.app import create_app, db_url, ticketing
from harness.config import HarnessSettings
from harness.db import apply_migrations, get_conn
from harness.pagination import Page
from harness.plugins.ticketing import Ticket, TicketingProvider, TicketRequest
from harness.security import Principal, require
from harness.testing import test_database_url

HARNESS_TABLES = "audit_log, model_usage, agent_executions, agent_definitions, eval_results, eval_runs"
READER = {"Authorization": "Bearer reader-token"}
OUTSIDER = {"Authorization": "Bearer outsider-token"}
ROLES = {"reader": {"things:read", "tickets:create"}, "outsider": set(), "admin": {"*"}}


@pytest.fixture(scope="session")
def database_url() -> str:
    url = test_database_url()
    apply_migrations(database_url=url)
    return url


@pytest.fixture(autouse=True)
def clean_harness_tables(database_url):
    with get_conn(database_url) as conn:
        conn.execute(f"TRUNCATE {HARNESS_TABLES} RESTART IDENTITY CASCADE")
        conn.commit()
    yield


@pytest.fixture
def conn_factory(database_url):
    from harness.db import conn_factory as factory

    return factory(database_url)


def base_settings(database_url: str, **overrides) -> HarnessSettings:
    # Every value is explicit so the harness tests do not depend on the environment they run in.
    values = dict(environment="test", database_url=database_url, rate_limit_per_minute=0,
                  auth_provider="static", llm_provider="mock", llm_model="", ticketing_provider="none",
                  secrets_provider="env", redact_patterns=[], plugin_modules=[],
                  api_tokens={"reader-token": ("reader@example.com", "reader"),
                              "outsider-token": ("outsider@example.com", "outsider")})
    values.update(overrides)
    return HarnessSettings(**values)


def things_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/things", response_model=Page[int])
    def things(p: Principal = Depends(require("things:read")), db: str = Depends(db_url)) -> Page[int]:
        return Page(items=[1, 2, 3], total=3, limit=50, offset=0)

    @router.get("/whoami")
    def whoami(p: Principal = Depends(require("things:read"))) -> dict:
        return {"subject": p.subject, "roles": list(p.roles)}

    @router.post("/tickets", response_model=Ticket)
    def open_ticket(p: Principal = Depends(require("tickets:create")),
                    provider: TicketingProvider = Depends(ticketing)) -> Ticket:
        return provider.create(TicketRequest(title="t", description="d", requested_by=p.subject))

    return router


@pytest.fixture
def make_app(database_url):
    def _make(**overrides):
        return create_app(title="test", version="0", settings=base_settings(database_url, **overrides),
                          role_permissions=ROLES, routers=[things_router()])

    return _make
