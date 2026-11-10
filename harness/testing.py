"""Helpers for tests (the harness's own and applications')."""
from __future__ import annotations

import os
from typing import Any

from harness.agents.contract import ToolClient
from harness.agents.gateway import LLMGateway, LLMResult, LLMUsage

DEFAULT_TEST_DATABASE_URL = "postgresql://app:app@localhost:5432/app_test"


def test_database_url() -> str:
    """Tests run against APP_TEST_DATABASE_URL, never the development database: they empty tables."""
    return os.environ.get("APP_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


test_database_url.__test__ = False   # not a test, despite the name


class ScriptedGateway(LLMGateway):
    """A gateway that replies with the given items in order. An Exception item is raised."""

    provider, model_id = "scripted", "scripted-v1"

    def __init__(self, replies: list[str | Exception], tokens_per_call: tuple[int, int] = (10, 5)):
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        self.tokens = tokens_per_call

    def complete(self, system: str, user: str, max_tokens: int = 512, response_schema=None) -> LLMResult:
        self.calls.append({"system": system, "user": user, "response_schema": response_schema})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LLMResult(text=reply, usage=LLMUsage(provider=self.provider, model_id=self.model_id,
                                                    input_tokens=self.tokens[0], output_tokens=self.tokens[1]))


class DictToolClient(ToolClient):
    """In-process tools for unit tests: a dict of name -> function."""

    def __init__(self, registry: dict[str, Any]):
        self.registry = registry

    def call(self, name: str, **kwargs: Any) -> Any:
        return self.registry[name](**kwargs)
