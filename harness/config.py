"""Harness settings. An application subclasses HarnessSettings to add or override fields.

Every setting is read from the environment with the APP_ prefix (APP_DATABASE_URL, ...), so the
deploy files are identical for every application. Every field must be listed in
deploy/.env.example; scripts/check_structure.py enforces that.
"""
from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    # "prod" turns on production safety checks (for example: static dev tokens are refused).
    environment: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql://app:app@localhost:5432/app"

    # ---- plugins ----
    # Extra modules to import at startup; each registers its own plugins (see harness/plugins.py).
    plugin_modules: list[str] = []

    # ---- authentication (plugin kind "auth") ----
    auth_provider: str = "static"                      # static | oidc | <your plugin>
    api_tokens: dict[str, tuple[str, str]] = {}        # static provider: token -> (subject, role). Dev only.
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""                            # where the IdP publishes its signing keys
    oidc_jwks_json: str = ""                           # or the key set itself, for air-gapped sites and tests
    oidc_algorithms: list[str] = ["RS256"]
    oidc_subject_claim: str = "sub"
    oidc_roles_claim: str = "roles"
    oidc_role_map: dict[str, str] = {}                 # IdP group/role -> application role

    # ---- API protection ----
    rate_limit_per_minute: int = 120                   # per caller; 0 disables
    cors_origins: list[str] = []

    # ---- LLM (plugin kind "llm") ----
    llm_provider: str = "mock"                         # mock | anthropic | <your plugin>
    llm_model: str = ""                                # no default on purpose: the approved model is a decision
    llm_timeout_s: float = 60.0

    # ---- guardrails ----
    redact_patterns: list[str] = []                    # e.g. ["email","ipv4","mac"]; applied before text reaches a model

    # ---- secrets (plugin kind "secrets") ----
    secrets_provider: str = "env"                      # env | file | <your plugin>
    secrets_dir: str = "/run/secrets"                  # file provider: one file per secret

    # ---- ticketing (plugin kind "ticketing") ----
    ticketing_provider: str = "none"                   # none | memory | servicenow | <your plugin>
    servicenow_instance_url: str = ""                  # https://<instance>.service-now.com
    servicenow_user: str = ""                          # password comes from the secrets provider: SERVICENOW_PASSWORD
    servicenow_table: str = "incident"


_settings: HarnessSettings | None = None


def configure(settings: HarnessSettings) -> HarnessSettings:
    """Install process-wide settings for code that runs outside a web request (CLIs, MCP servers).
    Web requests never use this; they read request.app.state.settings."""
    global _settings
    _settings = settings
    return settings


def get_settings() -> HarnessSettings:
    if _settings is None:
        raise RuntimeError("harness.config.configure() has not been called")
    return _settings
