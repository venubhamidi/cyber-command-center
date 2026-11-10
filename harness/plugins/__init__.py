"""Plugin registry: how the harness and applications plug in integrations.

A plugin is a factory registered under a (kind, name) pair. Settings choose which name to use for
each kind, so swapping an integration is a configuration change, not a code change:

    APP_AUTH_PROVIDER=oidc   APP_TICKETING_PROVIDER=servicenow   APP_LLM_PROVIDER=anthropic

Kinds the harness defines (built-ins live in this folder; the LLM ones in harness/agents/gateway.py):

    auth        who is calling            static, oidc
    llm         model provider            mock, anthropic
    secrets     where secrets come from   env, file
    ticketing   ticket systems            memory, servicenow

Writing your own (in your application, never in harness/):

    # <your app>/plugins/jira.py
    from harness.plugins import register

    @register("ticketing", "jira")
    def build(settings):          # receives the application's settings object
        return JiraTicketing(...)  # must implement the kind's interface

    then set APP_PLUGIN_MODULES='["myapp.plugins.jira"]' and APP_TICKETING_PROVIDER=jira.

An application may also invent new kinds (for example "scanner" with tenable/defender plugins).
The registry holds code (factories) only; it never holds per-application state.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable
from typing import Any

Factory = Callable[[Any], Any]

_registry: dict[tuple[str, str], Factory] = {}

BUILTIN_MODULES = (
    "harness.plugins.auth_static",
    "harness.plugins.auth_oidc",
    "harness.plugins.secrets",
    "harness.plugins.ticketing",
    "harness.plugins.ticketing_servicenow",
    "harness.agents.gateway",
)


class PluginNotFound(LookupError):
    pass


def register(kind: str, name: str) -> Callable[[Factory], Factory]:
    def decorator(factory: Factory) -> Factory:
        _registry[(kind, name)] = factory
        return factory

    return decorator


def available(kind: str) -> list[str]:
    return sorted(name for (k, name) in _registry if k == kind)


def load(modules: Iterable[str] = ()) -> None:
    """Import the built-in plugin modules plus any the application lists."""
    for module in (*BUILTIN_MODULES, *modules):
        importlib.import_module(module)


def create(kind: str, name: str, settings: Any) -> Any:
    load(getattr(settings, "plugin_modules", ()))
    factory = _registry.get((kind, name))
    if factory is None:
        raise PluginNotFound(f"No '{kind}' plugin named '{name}'. Available: {available(kind) or 'none'}")
    return factory(settings)
