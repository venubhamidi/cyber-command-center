from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from harness.db import get_conn


class Health(BaseModel):
    status: str
    database: str
    auth_provider: str
    llm_provider: str
    version: str
    harness_version: str


def health_router(version: str, harness_version: str) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/platform/health", response_model=Health)
    def health(request: Request) -> Health:
        """Unauthenticated liveness probe (containers and load balancers call it). Returns no secrets."""
        settings = request.app.state.settings
        try:
            with get_conn(settings.database_url) as conn:
                conn.execute("SELECT 1")
            db = "ok"
        except Exception as exc:  # noqa: BLE001
            db = f"error: {type(exc).__name__}"
        return Health(status="ok" if db == "ok" else "degraded", database=db,
                      auth_provider=settings.auth_provider, llm_provider=settings.llm_provider,
                      version=version, harness_version=harness_version)

    return router
