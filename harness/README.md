# harness/ — the foundation every application is built on

Nothing in this folder knows about any particular application. Application repositories treat it
as read-only: `scripts/harness_lock.py --check` fails CI if a file here was changed. The version is
in `VERSION`; what each version added is in `CHANGELOG.md`.

## What an application gets without writing it

| Area | What the harness does | Where |
|---|---|---|
| Login | Development tokens or single sign-on (OIDC), chosen by a setting | `plugins/auth_*.py`, `security.py` |
| Permissions | `Depends(require("things:read"))` on every endpoint, from the application's role table | `security.py` |
| Audit | Every API call and agent tool call recorded, including refused ones; tamper-evident chain | `audit.py` |
| Rate limiting | Requests per caller per minute; 429 when exceeded | `ratelimit.py` |
| Production safety | Refuses development tokens when `APP_ENVIRONMENT=prod` | `app.py` |
| Database | Connections; migrations applied once, tracked by checksum | `db.py`, `migrate.py` |
| Agents | Allow-listed tools, budgets, retries, timeouts, validated output, usage accounting | `agents/contract.py` |
| Guardrails | Redaction before a model sees text; untrusted data fenced and scanned | `agents/guardrails.py` |
| Models | Provider chosen by a setting; usage always recorded; cost never guessed | `agents/gateway.py` |
| Tools | Agents reach tools over MCP | `agents/mcp_client.py` |
| Evaluations | Score agents against case files; history stored | `evals.py` |
| Integrations | ServiceNow ticketing; secrets from environment or files; your own plugins | `plugins/` |
| Deployment | One settings scheme (`APP_*`), health endpoint, migration command | `config.py`, `health.py` |

## Plugins
A plugin is a factory registered under a kind and a name; a setting picks the name.

| Kind | Built in | Setting |
|---|---|---|
| `auth` | `static`, `oidc` | `APP_AUTH_PROVIDER` |
| `llm` | `mock`, `anthropic` | `APP_LLM_PROVIDER` |
| `secrets` | `env`, `file` | `APP_SECRETS_PROVIDER` |
| `ticketing` | `memory`, `servicenow` | `APP_TICKETING_PROVIDER` |

To add one (a Jira connector, a vault, another model provider, a scanner), write it in your
application's `plugins/` folder and list the module in `APP_PLUGIN_MODULES`. The pattern is shown
at the top of `plugins/__init__.py`; `tests/sample_plugin.py` is a complete small example.

## Writing an agent
```python
class Review(BaseModel):
    summary: str

class MyAgent(Agent):
    spec = AgentSpec(agent_id="my-agent", name="My Agent", version="0.1.0", description="...",
                     allowed_tools=["get_thing"])

    def run(self, request):
        thing = self.call_tool("get_thing", key=request.input["key"])     # allow-listed, audited, retried
        if thing is None:
            return self.fail(request, "not_found")
        flags = my_rules(thing)                                           # facts are computed in code
        review = self.llm(SYSTEM, "Review this.", data=json.dumps(thing), schema=Review)   # validated
        return self.ok(request, {"flags": flags, "summary": review.summary}, "how this was produced")
```
Build it with `build_agent(MyAgent, settings, tools)` and run it with `AgentRunner`. Limits are set
on the spec: `budget=Budget(...)`, `retry=RetryPolicy(...)`, `block_on_injection=True`.

## Known limits
- No real model has been called; the Anthropic provider is tested against a stand-in client.
- ServiceNow and OIDC are tested against simulated servers and locally generated keys, not live systems.
- Single sign-on validates tokens; the browser login redirect is not included.
- The MCP client starts a server process per call, and stdio carries no authentication.
- Rate-limit counters are per process. Timeouts are enforced for model and MCP calls, not for in-process tools.
- The injection scan is a heuristic. The real protection is that agents have read-only tools.
- The audit chain detects edits and deletions inside the log, not a full rewrite by a database owner.
