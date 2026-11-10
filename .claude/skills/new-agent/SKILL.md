---
name: new-agent
description: Add an agent the harness way: agree the seams, write its evaluation cases first, then the agent using only self.call_tool() and self.llm() with a schema, and register its eval suite. Use for every new agent.
argument-hint: <agent name> <what it answers>
---

# new-agent: evaluation cases first, then the agent

Rules: agents get read-only tools; facts and flags are computed in code; the model only writes
words, returned as a validated pydantic schema; every agent has an evaluation suite that scores
1.0 on the mock model in CI.

## Steps

1. Find the application package and the example to imitate:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   `grep -l "(Agent)" $APP/agents/*.py` names the example agent; `$APP/evals/__init__.py` holds
   `EVAL_SUITES`; each suite's folder holds `cases.json`; `$APP/evals/fixtures.json` holds the
   records the suites run on. Read all three and `harness/README.md` "Writing an agent".
   Done when: you can say which tools, rules and schema the example uses.

2. Agree the seams with the owner before writing anything: the agent's `agent_id`, its input
   keys, the read-only tools it may call (`allowed_tools`), the rule functions that compute its
   facts, and the fields of its output schema. Facts the model would otherwise "recall" must come
   from a tool.
   Done when: the owner has agreed the list, and no tool on it writes anything.

3. Write the evaluation cases first: a new folder `$APP/evals/<suite>/cases.json` and fixture
   records in `fixtures.json`. Cover at least: a complete record, each flag the rules can raise,
   a missing record (`status` failed, `llm_calls` 0), an injection string in the data
   (`guardrail_events` contains `injection_suspected:<tool>`, stored data unchanged), and the
   expected `tool_calls` / `llm_calls` counts. Register the suite in `EVAL_SUITES` with a
   `DictToolClient` over the fixtures. Run `python -m harness.evals $APP` and watch it fail.
   Done when: the suite is registered and scores below 1.0 because the agent does not exist.

4. Write the agent in `$APP/agents/<name>.py` after the example: an `AgentSpec` with
   `agent_id`, `allowed_tools` and a version; `run()` that calls `self.call_tool()` for facts,
   the shared rule functions for flags, and `self.llm(system, user, data=<untrusted json>,
   schema=<Model>)` once; `self.ok()` with an explanation of what code computed and what the
   model wrote; `self.fail()` for a missing record. Never import a model SDK, an MCP client or
   the database in an agent.
   Done when: `python -m harness.evals $APP` scores 1.0 for the new suite.

5. Expose it: an endpoint guarded by `agents:run` (use `/new-endpoint`), and a test that runs
   it over the real MCP server and asserts stored data is unchanged, as the example test does.
   Done when: the endpoint test passes.

6. Run the checks: `python scripts/check_structure.py && ruff check . && python -m pytest -q`.
   Done when: all pass and the structure check reports no agent without a suite.

## Completion
`python -m harness.evals $APP` scores 1.0; no agent lacks a suite; the checks pass.
