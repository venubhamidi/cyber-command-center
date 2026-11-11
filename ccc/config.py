"""Cyber Command Center settings and role table (PRD §2 personas)."""
from __future__ import annotations

from pathlib import Path

from harness.config import HarnessSettings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class Settings(HarnessSettings):
    # Development tokens. Ignored with single sign-on; refused when APP_ENVIRONMENT=prod.
    api_tokens: dict[str, tuple[str, str]] = {
        "dev-ciso-token": ("ciso@example.com", "ciso"),
        "dev-auditor-token": ("audit@example.com", "internal_audit"),
        "dev-admin-token": ("admin@example.com", "platform_admin"),
        "dev-bizowner-token": ("owner@example.com", "business_owner"),
    }
    # Network identifiers and e-mail addresses never reach a model, whichever model is chosen.
    # Whether host names and owner names may is still open: DECISIONS.md D-014.
    redact_patterns: list[str] = ["ipv4", "mac", "email"]
    # Read-only MVP (PRD §12): the platform opens no tickets until Phase 2.
    ticketing_provider: str = "none"
    # Source connectors for the dashboard tables (ARCHITECTURE.md, executive dashboard). Mocks until
    # the real integrations exist; a real one replaces a mock here, nothing else changes.
    plugin_modules: list[str] = ["ccc.plugins.mock_connectors"]
    connectors: list[str] = ["mock_tenable", "mock_sccm", "mock_grc", "mock_chronicle", "mock_risk", "mock_history"]
    # Remediation SLA, days from first sighting, by severity (D-038).
    sla_days: dict[str, int] = {"critical": 7, "high": 30, "medium": 90, "low": 180}


settings = Settings()

# PRD §2 personas -> permissions.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "cio": {"dashboard:read", "assets:read", "risks:read", "ai_usage:read", "agents:run"},
    "ciso": {"dashboard:read", "assets:read", "vulns:read", "controls:read", "risks:read", "ai_usage:read", "agents:run"},
    "cto": {"dashboard:read", "assets:read", "vulns:read", "risks:read", "agents:run"},
    "security_ops": {"assets:read", "vulns:read", "incidents:read", "agents:run"},
    "infrastructure": {"assets:read", "patch:read"},
    "application_owner": {"assets:read", "vulns:read", "controls:read"},
    "business_owner": {"risks:read"},
    "internal_audit": {"controls:read", "assets:read", "audit:read"},
    "platform_admin": {"*"},
}
