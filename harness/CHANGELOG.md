# Harness changelog

## 1.0.0
First released version.

- **Plugins:** registry in `harness/plugins/`; kinds `auth`, `llm`, `secrets`, `ticketing`;
  applications add their own through `APP_PLUGIN_MODULES`.
- **Login:** `static` (development tokens, refused in production) and `oidc` (single sign-on: signature,
  issuer, audience and expiry checked on every request; roles mapped from a claim).
- **API protection:** per-caller rate limiting; every call audited; audit log is hash-chained
  (tamper-evident) with `verify_audit_chain`.
- **Integrations:** ServiceNow ticketing (Table API), in-memory ticketing, secrets from environment or files.
- **Agents:** tool allow-list; budgets for tool calls, model calls and tokens; retries with backoff on
  transient failures; timeouts; structured output validated against a schema with a corrective retry;
  redaction before text reaches a model; untrusted data fenced; injection scan of tool results;
  usage, retries, tool calls and guardrail events recorded by the runner.
- **Evaluations:** case files, `python -m harness.evals`, results stored per run with provider and model.
- **Database:** migrations applied once and tracked by checksum; editing an applied file is an error.
- **Deployment:** settings from `APP_*` environment variables; health endpoint reports harness version.

Not yet proven or not included: a call to a real model; a live ServiceNow instance; a live identity
provider; the browser login redirect for single sign-on; authenticated MCP transport; rate limiting
shared across replicas; metrics and tracing.
