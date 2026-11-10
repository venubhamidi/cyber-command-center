"""Secrets plugins. Integrations ask for a secret by name; where it lives is configuration.

    env    environment variables (default)
    file   one file per secret in APP_SECRETS_DIR (how Docker and Kubernetes mount secrets)

A vault plugin (HashiCorp Vault, CyberArk, a cloud secret manager) implements the same
one-method interface and is registered by the application.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from harness.plugins import create, register


class SecretsProvider(Protocol):
    def get(self, name: str) -> str | None: ...


class EnvSecrets:
    def get(self, name: str) -> str | None:
        return os.environ.get(name) or None


class FileSecrets:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def get(self, name: str) -> str | None:
        if "/" in name or "\\" in name or name.startswith("."):
            return None                      # a secret name is never a path
        path = self.directory / name
        return path.read_text().strip() or None if path.is_file() else None


@register("secrets", "env")
def _env(settings) -> EnvSecrets:
    return EnvSecrets()


@register("secrets", "file")
def _file(settings) -> FileSecrets:
    return FileSecrets(settings.secrets_dir)


def secrets_for(settings) -> SecretsProvider:
    return create("secrets", settings.secrets_provider, settings)
