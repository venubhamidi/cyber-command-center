"""Agent evaluation: run an agent against a set of cases and score it.

    python -m harness.evals <app_package> [--min-score 1.0]

The application package exposes `evals.EVAL_SUITES` (a dict of name -> EvalSuite) and
`config.settings`. Each case is a JSON file (or a JSON list of cases) in the suite's folder:

    {"id": "ownerless-item",
     "input": {"item_id": "IT-2"},
     "checks": [{"path": "status", "equals": "succeeded"},
                {"path": "output.flags", "equals": ["no_owner"]},
                {"path": "output.summary", "op": "not_contains", "value": "guaranteed"}]}

`path` is a dotted path into the agent's response. Operators: equals (default), contains,
not_contains, in, exists. Every run is stored in eval_runs / eval_results with the provider and
model used, so versions, prompts and models can be compared over time. The command exits
non-zero when a suite scores below --min-score, so CI can block a regression.

With the mock model, evals check the deterministic half of an agent (flags, tool use,
failure handling). Judging the quality of model prose needs a real model.
"""
from __future__ import annotations

import importlib
import json
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from harness.agents.contract import Agent, AgentRequest, AgentRunner


class Check(BaseModel):
    path: str
    op: Literal["equals", "contains", "not_contains", "in", "exists"] = "equals"
    value: Any = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        """Allow {"path": "status", "equals": "succeeded"} as well as {"op": ..., "value": ...}."""
        if isinstance(data, dict) and "op" not in data:
            for op in ("equals", "contains", "not_contains", "in", "exists"):
                if op in data:
                    return {"path": data["path"], "op": op, "value": data[op]}
        return data


class EvalCase(BaseModel):
    id: str
    input: dict[str, Any]
    checks: list[Check]
    description: str = ""


@dataclass
class EvalSuite:
    agent_factory: Callable[[], Agent]
    cases_dir: Path


@dataclass
class EvalRunResult:
    run_id: uuid.UUID
    agent_id: str
    total: int
    passed: int
    failures: dict[str, list[str]] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_cases(cases_dir: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(Path(cases_dir).glob("*.json")):
        doc = json.loads(path.read_text())
        cases.extend(EvalCase(**c) for c in (doc if isinstance(doc, list) else [doc]))
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate eval case ids in {cases_dir}")
    return cases


def _lookup(doc: Any, path: str) -> tuple[bool, Any]:
    for part in path.split("."):
        if isinstance(doc, dict) and part in doc:
            doc = doc[part]
        elif isinstance(doc, list) and part.isdigit() and int(part) < len(doc):
            doc = doc[int(part)]
        else:
            return False, None
    return True, doc


def check_case(case: EvalCase, response: dict[str, Any]) -> list[str]:
    """Return the list of failed checks, described in words (empty list = passed)."""
    failures: list[str] = []
    for c in case.checks:
        found, actual = _lookup(response, c.path)
        if c.op == "exists":
            ok = found == (c.value is not False)
        elif not found:
            ok = False
        elif c.op == "equals":
            ok = actual == c.value
        elif c.op == "contains":
            ok = c.value in actual if isinstance(actual, (str, list, dict)) else False
        elif c.op == "not_contains":
            ok = c.value not in actual if isinstance(actual, (str, list, dict)) else True
        else:  # in
            ok = actual in c.value
        if not ok:
            failures.append(f"{c.path} {c.op} {c.value!r}: got {actual!r}" if found else f"{c.path}: missing")
    return failures


def run_suite(suite: EvalSuite, conn_factory) -> EvalRunResult:
    cases = load_cases(suite.cases_dir)
    if not cases:
        raise ValueError(f"no eval cases in {suite.cases_dir}")
    runner = AgentRunner(conn_factory)
    agent = suite.agent_factory()
    run = EvalRunResult(run_id=uuid.uuid4(), agent_id=agent.spec.agent_id, total=len(cases), passed=0)
    rows, tokens = [], 0
    for case in cases:
        response = runner.execute(agent, AgentRequest(requested_by="eval", input=case.input))
        failures = check_case(case, response.model_dump(mode="json"))
        tokens += sum(u.input_tokens + u.output_tokens for u in response.usage)
        if failures:
            run.failures[case.id] = failures
        else:
            run.passed += 1
        rows.append((run.run_id, case.id, not failures, json.dumps(failures), response.latency_ms))
    with conn_factory() as conn:
        conn.execute(
            """INSERT INTO eval_runs (run_id, agent_id, agent_version, provider, model_id, total, passed, score,
               total_tokens) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run.run_id, run.agent_id, agent.spec.version, agent.gateway.provider, agent.gateway.model_id,
             run.total, run.passed, round(run.score, 4), tokens))
        for row in rows:
            conn.execute("INSERT INTO eval_results (run_id, case_id, passed, failures, latency_ms) "
                         "VALUES (%s,%s,%s,%s,%s)", row)
        conn.commit()
    return run


def main(argv: list[str]) -> int:
    from harness.config import configure
    from harness.db import conn_factory

    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print("usage: python -m harness.evals <app_package> [--min-score 1.0]")
        return 2
    min_score = float(argv[argv.index("--min-score") + 1]) if "--min-score" in argv else 1.0
    settings = configure(importlib.import_module(f"{args[0]}.config").settings)
    suites: dict[str, EvalSuite] = importlib.import_module(f"{args[0]}.evals").EVAL_SUITES
    worst = 1.0
    for name, suite in suites.items():
        run = run_suite(suite, conn_factory(settings.database_url))
        worst = min(worst, run.score)
        print(f"{name}: {run.passed}/{run.total} passed (score {run.score:.2f}) "
              f"[{settings.llm_provider}] run {run.run_id}")
        for case_id, failures in run.failures.items():
            for f in failures:
                print(f"  FAIL {case_id}: {f}")
    if worst < min_score:
        print(f"below minimum score {min_score}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
