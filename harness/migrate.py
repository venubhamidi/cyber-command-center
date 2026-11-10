"""Run database migrations for an application:  python -m harness.migrate <app_package>

The package must expose `config.settings` and `config.MIGRATIONS_DIR`. The container start
command runs this before the API starts.
"""
from __future__ import annotations

import importlib
import sys

from harness.db import apply_migrations


def main(app_package: str) -> None:
    config = importlib.import_module(f"{app_package}.config")
    applied = apply_migrations(config.MIGRATIONS_DIR, database_url=config.settings.database_url)
    print(f"migrations applied: {applied or 'none (already up to date)'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m harness.migrate <app_package>")
    main(sys.argv[1])
