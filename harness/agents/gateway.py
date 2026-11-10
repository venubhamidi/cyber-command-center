"""Provider-independent LLM gateway. Providers are plugins of kind "llm".

Rules enforced here, not in agents:
  * every call returns the provider's own token usage (never an estimate, except the mock)
  * cost is recorded only when a confirmed price exists for the model; otherwise NULL
  * the gateway receives text and returns text; it has no database access
  * provider failures worth retrying are raised as TransientLLMError; the agent contract
    applies the retry policy (provider SDK retries are turned off so there is one policy)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from harness import plugins
from harness.agents.reliability import TransientError


class TransientLLMError(TransientError):
    pass


class LLMUsage(BaseModel):
    provider: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cost_usd: float | None = None
    latency_ms: int = 0


class LLMResult(BaseModel):
    text: str
    usage: LLMUsage


class LLMGateway(ABC):
    provider: str = "unknown"
    model_id: str = ""

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 512,
                 response_schema: dict[str, Any] | None = None) -> LLMResult:
        """response_schema: a JSON Schema the reply must satisfy (the caller validates it)."""


def _schema_instruction(schema: dict[str, Any]) -> str:
    return ("\n\nReply with only one JSON object that satisfies this JSON Schema, with no other text:\n"
            + json.dumps(schema))


def _mock_instance(schema: dict[str, Any], text: str, root: dict[str, Any] | None = None) -> Any:
    """Smallest value that satisfies a JSON Schema: lets the mock stand in for structured replies."""
    root = root or schema
    if "$ref" in schema:
        return _mock_instance(root["$defs"][schema["$ref"].split("/")[-1]], text, root)
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        options = [s for s in schema["anyOf"] if s.get("type") != "null"]
        return _mock_instance(options[0], text, root) if options else None
    kind = schema.get("type")
    if kind == "object":
        return {k: _mock_instance(v, text, root) for k, v in schema.get("properties", {}).items()
                if k in schema.get("required", [])}
    return {"string": text, "integer": 0, "number": 0, "boolean": False, "array": []}.get(kind)


class MockGateway(LLMGateway):
    """Deterministic and offline, for tests and for running without a model. Echoes its input;
    token counts are word counts (an estimate, acceptable only because this is not a real model)."""

    provider, model_id = "mock", "mock-v1"

    def complete(self, system: str, user: str, max_tokens: int = 512,
                 response_schema: dict[str, Any] | None = None) -> LLMResult:
        started = time.perf_counter()
        digest = hashlib.sha256(user.encode()).hexdigest()[:8]
        text = f"[mock {digest}] " + user.strip().replace("\n", " ")[:400]
        if response_schema is not None:
            text = json.dumps(_mock_instance(response_schema, text))
        return LLMResult(text=text, usage=LLMUsage(
            provider=self.provider, model_id=self.model_id, input_tokens=len((system + user).split()),
            output_tokens=len(text.split()), cost_usd=0.0, latency_ms=int((time.perf_counter() - started) * 1000)))


class AnthropicGateway(LLMGateway):
    """Requires ANTHROPIC_API_KEY and an explicit model id. The price table is empty until prices
    are confirmed from the provider's current price list, so cost_usd is NULL."""

    provider = "anthropic"
    PRICE_PER_MTOK: dict[str, tuple[float, float]] = {}

    def __init__(self, model_id: str, timeout_s: float = 60.0):
        import anthropic

        if not model_id:
            raise RuntimeError("No model configured: set APP_LLM_MODEL to an approved model id")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=0, timeout=timeout_s)
        self.model_id = model_id

    def complete(self, system: str, user: str, max_tokens: int = 512,
                 response_schema: dict[str, Any] | None = None) -> LLMResult:
        a = self._anthropic
        if response_schema is not None:
            system = system + _schema_instruction(response_schema)
        started = time.perf_counter()
        try:
            msg = self.client.messages.create(model=self.model_id, max_tokens=max_tokens, system=system,
                                              messages=[{"role": "user", "content": user}])
        except (a.APIConnectionError, a.RateLimitError, a.InternalServerError) as exc:
            raise TransientLLMError(f"{type(exc).__name__}") from exc     # timeouts are APIConnectionError
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        price = self.PRICE_PER_MTOK.get(self.model_id)
        cost = None
        if price:
            cost = msg.usage.input_tokens / 1e6 * price[0] + msg.usage.output_tokens / 1e6 * price[1]
        return LLMResult(text=text, usage=LLMUsage(
            provider=self.provider, model_id=self.model_id, input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            cache_read_tokens=getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
            cost_usd=cost, latency_ms=int((time.perf_counter() - started) * 1000)))


@plugins.register("llm", "mock")
def _mock(settings) -> MockGateway:
    return MockGateway()


@plugins.register("llm", "anthropic")
def _anthropic(settings) -> AnthropicGateway:
    return AnthropicGateway(settings.llm_model, settings.llm_timeout_s)


def build_gateway(settings) -> LLMGateway:
    return plugins.create("llm", settings.llm_provider, settings)
