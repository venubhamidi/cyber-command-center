---
name: new-mcp-tool
description: Add a read-only MCP tool that returns JSON text, register it on the server and in its TOOLS dict, and test it through an agent or the MCP client. Use whenever an agent needs a new fact from the database.
argument-hint: <tool name> <what it returns>
---

# new-mcp-tool: one read-only fact source for agents

Rules: the MCP server, not the model, queries PostgreSQL; tools are read-only and return a JSON
document as text; the same function is exposed in `TOOLS` for in-process tests.

## Steps

1. Find the application package and the server to extend:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   `ls $APP/mcp_servers/*/server.py` lists the servers; read the one the tool belongs to and
   note its `TOOLS` dict and how its existing tool is written.
   Done when: you know which server, and have read one existing tool on it.

2. Write the failing test first. Either an evaluation case for an agent that uses the tool
   (`$APP/evals/<suite>/cases.json`, with a fixture record), or a test that starts the server
   over stdio through `McpStdioToolClient` and calls the tool, as the harness's own MCP tests do
   (`harness/tests/test_evals_ticketing_mcp.py`). Take the expected value from the seed data.
   Done when: the test fails because the tool does not exist.

3. Write a private function `_<tool>(...)` that opens `get_conn(settings.database_url)`, runs
   explicit `SELECT` SQL (no writes), and returns a plain dict or list, or `None` when nothing
   matches. Apply the shared rule functions here when the tool reports flags or gaps, so the
   API and the agent can never disagree.
   Done when: the function returns JSON-serialisable data.

4. Register it: a `@server.tool()` wrapper with the same name and a one-line docstring ending in
   "Read-only." that returns `json.dumps(_<tool>(...))`; add `"<tool>": _<tool>` to `TOOLS`.
   Done when: the wrapper and the dict entry both exist.

5. Give the agents that need it the name in their `allowed_tools`. Nothing else may call it.
   Done when: the test from step 2 passes.

6. Run the checks: `python scripts/check_structure.py && ruff check . && python -m pytest -q`.
   Done when: all pass.

## Completion
The tool is callable over MCP in a test, is listed in `TOOLS`, and performs no write.
