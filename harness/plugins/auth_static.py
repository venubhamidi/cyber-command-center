"""Auth plugin "static": fixed bearer tokens from settings. Development and tests only.

create_app() refuses to start with this provider when APP_ENVIRONMENT=prod.
"""
from __future__ import annotations

from harness.plugins import register
from harness.security import Identity


class StaticTokenAuth:
    def __init__(self, tokens: dict[str, tuple[str, str]]):
        self.tokens = tokens

    def authenticate(self, token: str) -> Identity | None:
        entry = self.tokens.get(token)
        return Identity(subject=entry[0], roles=(entry[1],)) if entry else None


@register("auth", "static")
def build(settings) -> StaticTokenAuth:
    return StaticTokenAuth(settings.api_tokens)
