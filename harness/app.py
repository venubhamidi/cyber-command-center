"""FastAPI application factory with the harness's cross-cutting behaviour wired in.

Per-application state (settings, role table, plugins) lives on `app.state`, never in module
globals, so several applications can run in one process without interfering.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request

from harness import plugins
from harness.audit import AuditMiddleware
from harness.config import HarnessSettings
from harness.health import health_router
from harness.plugins.ticketing import TicketingProvider, ticketing_for
from harness.ratelimit import RateLimitMiddleware

HARNESS_VERSION = (Path(__file__).resolve().parent / "VERSION").read_text().strip()


class UnsafeConfiguration(RuntimeError):
    pass


def create_app(
    *,
    title: str,
    version: str,
    settings: HarnessSettings,
    role_permissions: dict[str, set[str]],
    routers: Sequence[APIRouter],
    description: str = "",
) -> FastAPI:
    if settings.environment == "prod" and settings.auth_provider == "static":
        raise UnsafeConfiguration("Static development tokens are not allowed when APP_ENVIRONMENT=prod. "
                                  "Set APP_AUTH_PROVIDER=oidc (or another single sign-on plugin).")

    app = FastAPI(title=title, version=version, description=description)
    app.state.settings = settings
    app.state.role_permissions = role_permissions
    app.state.auth_provider = plugins.create("auth", settings.auth_provider, settings)
    app.state.ticketing = ticketing_for(settings)

    # Middleware added last runs first: audit wraps rate limiting, so refused calls are audited too.
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(AuditMiddleware, database_url=settings.database_url)
    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                           allow_methods=["GET", "POST"], allow_headers=["authorization", "content-type"])
    app.include_router(health_router(version, HARNESS_VERSION))
    for r in routers:
        app.include_router(r)
    return app


def db_url(request: Request) -> str:
    """Dependency: the database URL of the application handling this request."""
    return request.app.state.settings.database_url


def ticketing(request: Request) -> TicketingProvider:
    """Dependency: the configured ticketing plugin, or 503 if none is configured."""
    provider = request.app.state.ticketing
    if provider is None:
        raise HTTPException(503, "No ticketing provider is configured")
    return provider
