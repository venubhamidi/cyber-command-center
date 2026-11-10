"""Standard agent contract. Every agent built on the harness follows it.

An agent:
  * declares an AgentSpec: identity, the tools it may call, its budget and retry policy
  * reaches tools only through self.call_tool() and models only through self.llm()
  * is executed by AgentRunner, which records the execution, token usage, tool calls
    (audited, including refused ones), retries and guardrail events
  * computes every number and flag in Python; the model only interprets and phrases
  * may RECOMMEND, never DECIDE: outputs are advisory and agents have no write tools

What self.call_tool() and self.llm() do for every agent, so no agent has to:
  allow-list check · budget limits (tool calls, model calls, tokens) · retries with backoff on
  transient failures · redaction before text reaches a model · untrusted data wrapped and
  scanned for injection · model output validated against a schema, with a corrective retry
"""
from __future__ import annotations

import json
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field, ValidationError

from harness.agents.gateway import LLMGateway, LLMUsage, build_gateway
from harness.agents.guardrails import DATA_RULE, Redactor, suspected_injection, wrap_data
from harness.agents.reliability import RetryPolicy, TransientError, call_with_retry
from harness.audit import append_audit

M = TypeVar("M", bound=BaseModel)


class TransientToolError(TransientError):
    """Raised by a ToolClient for failures worth retrying (timeout, connection lost)."""


class ToolDenied(PermissionError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class InjectionBlocked(RuntimeError):
    pass


class OutputValidationError(RuntimeError):
    pass


class Budget(BaseModel):
    """Hard limits for one run. Exceeding any of them fails the run."""

    max_llm_calls: int = 8
    max_tool_calls: int = 20
    max_total_tokens: int = 50_000


class AgentSpec(BaseModel):
    agent_id: str
    name: str
    version: str
    description: str
    allowed_tools: list[str]                 # anything else is refused and audited
    budget: Budget = Field(default_factory=Budget)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    max_validation_retries: int = 1          # extra model calls allowed to fix an invalid structured reply
    block_on_injection: bool = False         # True: a suspicious tool result stops the run


class AgentRequest(BaseModel):
    requested_by: str                        # principal or calling agent
    input: dict[str, Any]
    execution_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class AgentResponse(BaseModel):
    execution_id: uuid.UUID
    agent_id: str
    status: str                              # succeeded | failed
    output: dict[str, Any]
    explanation: str                         # human-readable account of how the output was produced
    confidence: str = "advisory"             # outputs are recommendations, not decisions
    error: str | None = None
    # The fields below are filled in by AgentRunner from what actually happened, never by the agent.
    tool_calls: int = 0
    llm_calls: int = 0
    retries: int = 0
    usage: list[LLMUsage] = Field(default_factory=list)
    guardrail_events: list[str] = Field(default_factory=list)
    latency_ms: int = 0


class ToolClient(ABC):
    """How an agent reaches its tools. harness.agents.mcp_client.McpStdioToolClient speaks real
    MCP; applications may use an in-process client in unit tests."""

    @abstractmethod
    def call(self, name: str, **kwargs: Any) -> Any: ...


def _extract_json(text: str) -> str:
    """Models often wrap JSON in a code fence or a sentence; take the outermost object."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


class Agent(ABC):
    spec: AgentSpec

    def __init__(self, gateway: LLMGateway, tools: ToolClient, *, redactor: Redactor | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.gateway = gateway
        self.tools = tools
        self.redactor = redactor
        self._sleep = sleep
        self._reset()

    def _reset(self) -> None:
        self.tool_log: list[dict[str, Any]] = []
        self.usage_log: list[LLMUsage] = []
        self.guardrail_events: list[str] = []
        self.retry_count = 0
        self.llm_call_count = 0

    @abstractmethod
    def run(self, request: AgentRequest) -> AgentResponse: ...

    # ---- helpers for building the response ----
    def ok(self, request: AgentRequest, output: dict[str, Any], explanation: str) -> AgentResponse:
        return AgentResponse(execution_id=request.execution_id, agent_id=self.spec.agent_id,
                             status="succeeded", output=output, explanation=explanation)

    def fail(self, request: AgentRequest, error: str, explanation: str = "") -> AgentResponse:
        return AgentResponse(execution_id=request.execution_id, agent_id=self.spec.agent_id,
                             status="failed", output={}, explanation=explanation, error=error)

    def _on_retry(self, attempt: int, exc: Exception) -> None:
        self.retry_count += 1

    # ---- tools ----
    def call_tool(self, name: str, **kwargs: Any) -> Any:
        entry: dict[str, Any] = {"tool": name, "args": kwargs, "outcome": "denied", "attempts": 0}
        self.tool_log.append(entry)
        if name not in self.spec.allowed_tools:
            raise ToolDenied(f"Agent {self.spec.agent_id} is not allowed to call tool '{name}'")
        if len(self.tool_log) > self.spec.budget.max_tool_calls:
            entry["outcome"] = "budget_exceeded"
            raise BudgetExceeded(f"more than {self.spec.budget.max_tool_calls} tool calls")
        entry["outcome"] = "error"

        def attempt() -> Any:
            entry["attempts"] += 1
            return self.tools.call(name, **kwargs)

        result = call_with_retry(attempt, self.spec.retry, sleep=self._sleep, on_retry=self._on_retry)
        entry["outcome"] = "ok"
        if suspected_injection(json.dumps(result, default=str)):
            entry["injection_suspected"] = True
            self.guardrail_events.append(f"injection_suspected:{name}")
            if self.spec.block_on_injection:
                entry["outcome"] = "blocked"
                raise InjectionBlocked(f"result of tool '{name}' looks like a prompt injection")
        return result

    # ---- model ----
    def llm(self, system: str, instruction: str, *, data: str | None = None, schema: type[M] | None = None,
            max_tokens: int = 512) -> str | M:
        """Ask the model. `instruction` is yours; `data` is untrusted material (tool results, file
        text) and is fenced off. With `schema`, returns a validated instance of that model."""
        user = instruction
        if data is not None:
            user += "\n\n" + wrap_data(data)
            system = system + "\n\n" + DATA_RULE
        mapping: dict[str, str] = {}
        if self.redactor is not None:
            user, mapping = self.redactor.redact(user)
            if mapping:
                self.guardrail_events.append(f"redacted:{len(mapping)}")
        schema_json = schema.model_json_schema() if schema is not None else None

        feedback = ""
        last_error = ""
        for _ in range(self.spec.max_validation_retries + 1):
            if self.llm_call_count >= self.spec.budget.max_llm_calls:
                raise BudgetExceeded(f"more than {self.spec.budget.max_llm_calls} model calls")
            self.llm_call_count += 1
            prompt = user + feedback
            result = call_with_retry(lambda p=prompt: self.gateway.complete(system, p, max_tokens, schema_json),
                                     self.spec.retry, sleep=self._sleep, on_retry=self._on_retry)
            self.usage_log.append(result.usage)
            spent = sum(u.input_tokens + u.output_tokens for u in self.usage_log)
            if spent > self.spec.budget.max_total_tokens:
                raise BudgetExceeded(f"{spent} tokens used, limit {self.spec.budget.max_total_tokens}")
            text = Redactor.restore(result.text, mapping)
            if schema is None:
                return text
            try:
                return schema.model_validate_json(_extract_json(text))
            except (ValidationError, ValueError) as exc:
                last_error = str(exc).splitlines()[0]
                self.guardrail_events.append("output_validation_retry")
                feedback = (f"\n\nYour previous reply was not valid ({last_error}). "
                            "Reply with only the JSON object.")
        self.guardrail_events[-1] = "output_validation_failed"
        raise OutputValidationError(f"model reply did not match {schema.__name__}: {last_error}")


def build_agent(agent_cls: type[Agent], settings, tools: ToolClient, **kwargs: Any) -> Agent:
    """Construct an agent the standard way: gateway and redaction come from settings."""
    redactor = Redactor(settings.redact_patterns) if settings.redact_patterns else None
    return agent_cls(build_gateway(settings), tools, redactor=redactor, **kwargs)


class AgentRunner:
    """Executes an agent and persists execution, usage, tool-call audit and guardrail records."""

    def __init__(self, conn_factory):
        self.conn_factory = conn_factory

    def ensure_registered(self, spec: AgentSpec) -> None:
        with self.conn_factory() as conn:
            conn.execute(
                """INSERT INTO agent_definitions (agent_id, name, version, description)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (agent_id) DO UPDATE SET version=EXCLUDED.version""",
                (spec.agent_id, spec.name, spec.version, spec.description))
            conn.commit()

    def execute(self, agent: Agent, request: AgentRequest) -> AgentResponse:
        self.ensure_registered(agent.spec)
        started = time.perf_counter()
        with self.conn_factory() as conn:
            conn.execute(
                """INSERT INTO agent_executions (execution_id, agent_id, status, requested_by, input)
                   VALUES (%s,%s,'running',%s,%s)""",
                (request.execution_id, agent.spec.agent_id, request.requested_by,
                 json.dumps(request.input, default=str)))
            conn.commit()

        agent._reset()
        try:
            response = agent.run(request)
            if not isinstance(response, AgentResponse):
                raise TypeError("agent.run() must return an AgentResponse")
        except Exception as exc:  # noqa: BLE001  (a failing agent is recorded, never raised to the caller)
            response = agent.fail(request, f"{type(exc).__name__}: {exc}")

        response.latency_ms = int((time.perf_counter() - started) * 1000)
        response.tool_calls = len(agent.tool_log)
        response.llm_calls = agent.llm_call_count
        response.retries = agent.retry_count
        response.usage = list(agent.usage_log)
        response.guardrail_events = list(agent.guardrail_events)

        with self.conn_factory() as conn:
            conn.execute(
                """UPDATE agent_executions SET status=%s, finished_at=%s, output=%s, error=%s, tool_calls=%s,
                   llm_calls=%s, retries=%s, guardrail_events=%s, latency_ms=%s WHERE execution_id=%s""",
                (response.status, datetime.now(UTC), json.dumps(response.output, default=str), response.error,
                 response.tool_calls, response.llm_calls, response.retries,
                 json.dumps(response.guardrail_events), response.latency_ms, request.execution_id))
            # Tool access is audited like API access. Arguments are recorded (they identify what
            # was accessed); tool results are not.
            for call in agent.tool_log:
                append_audit(conn, principal=agent.spec.agent_id, role="agent", action=f"TOOL {call['tool']}",
                             resource=call["tool"], request_id=str(request.execution_id),
                             detail={"args": call["args"], "outcome": call["outcome"],
                                     "attempts": call["attempts"], "requested_by": request.requested_by,
                                     **({"injection_suspected": True} if call.get("injection_suspected") else {})})
            for u in response.usage:
                conn.execute(
                    """INSERT INTO model_usage (execution_id, agent_id, provider, model_id, input_tokens,
                       output_tokens, cache_read_tokens, cost_usd, latency_ms) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (request.execution_id, agent.spec.agent_id, u.provider, u.model_id, u.input_tokens,
                     u.output_tokens, u.cache_read_tokens, u.cost_usd, u.latency_ms))
            conn.commit()
        return response
