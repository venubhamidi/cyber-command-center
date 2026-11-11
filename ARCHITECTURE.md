# Architecture: Cyber Command Center

The validated design. Approved by the owner on 2026-11-10 for the asset detail feature; later
features extend this file rather than re-deriving it. Rules live in `CLAUDE.md` and `ccc/CLAUDE.md`;
decisions in `ccc/DECISIONS.md` and `docs/adr/`; terms in `CONTEXT.md` and `ccc/CONTEXT.md`.
The PRD (`docs/PRD.pdf`) is the requirements input, not this design.

## Components and data flow

```
                 browser (CIO / CISO / Audit persona)
                 React + Material UI + ECharts       displays only; computes nothing
                         │  bearer token (Entra ID OIDC in prod, dev tokens locally)
                         ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │ FastAPI  (harness/app.py)                                          │
   │  AuditMiddleware ─► RateLimit ─► require("assets:read"|"agents:run")│
   │                                                                    │
   │  GET  /assets                         inventory (Page[Asset])      │
   │  GET  /assets/summary                 KPIs, counted in SQL         │
   │  GET  /assets/{eaid}          ──┐     profile + flags + completeness│
   │  GET  /assets/{eaid}/history  ──┤     + source systems              │
   │  POST /assets/{eaid}/brief    ──┼─┐   runs the agent, changes nothing│
   └─────────────────────────────────┼─┼───────────────────────────────┘
                 ccc/assets.py rules ◄┘ │   asset_flags(), missing_required_fields(),
                 (one place, SQL + py)  │   gap_counts()  ← also used by MCP + agent
                         │              │
                         ▼              ▼
   ┌──────────────┐   ┌──────────────────────────────────────────────┐
   │ PostgreSQL   │   │ AgentRunner (harness/agents/contract.py)     │
   │ assets       │   │  Asset Summary Agent                         │
   │ asset_sources│◄──│   call_tool("get_asset")  ─► asset-mcp (stdio)│──► SELECT only
   │ asset_history│   │   rules → flags, completeness   (code)        │
   │ audit_log    │◄──│   llm(system, user, data=asset, schema=Brief) │
   │ model_usage  │◄──│      ├ redact ipv4/mac/email (+host/owner/BU) │
   │ agent_exec.  │◄──│      ├ fence + injection scan on data         │
   │ eval_runs    │   │      ├ budget 8 llm / 20 tools / 50k tokens   │
   └──────────────┘   │      └ validate schema, retry once            │
                      │   ok(output, explanation)  → advisory          │
                      └──────────────┬───────────────────────────────┘
                                     ▼
                      model gateway plugin: mock (tests, CI) | anthropic (D-014, id not set)

   ingestion (ccc/ingest.py, CSV today; plugins per source later) ──► assets, asset_sources,
   asset_history. Deterministic. Never deletes; marks potentially_inactive.
```

Outside systems, all behind plugins chosen by a setting: Entra ID (auth), the model provider
(llm), the secrets store, and later Tenable, Defender, SCCM and Intune (source systems). Nothing
in `ccc/` calls one directly.

One user action, "open EA-000003 and ask for a brief":
1. The browser calls the detail endpoint. An audit row is written (who, what, allowed or refused),
   the permission is checked, one SQL query reads the asset with its sources, the rules compute
   flags and completeness in Python. The response is the record plus the derived fields.
2. The browser renders it. Unknown stays "unknown".
3. The user presses Brief. The agent runs inside the request: one MCP tool call (audited), the
   rules again on the tool result, one model call with the asset JSON as fenced data and
   redaction applied, a validated `AssetBrief` back, a usage row and an execution row written.
   The response carries the seven parts (PRD Module 7). Stored asset data is unchanged.

## Stack

| Layer | Choice | Deviation from the global defaults |
|---|---|---|
| Frontend | React + Vite, Material UI, Apache ECharts | None. MUI and ECharts per D-020. |
| API | Python, FastAPI, explicit SQL through psycopg | None. |
| Agents | Harness agent contract; no framework | **Yes.** The contract gives allow-list, budgets, retries, guardrails and audit; a framework is deferred until a flow needs a graph (D-001). |
| Database | PostgreSQL, on premises | **Yes.** PRD §6 keeps the data platform on premises; not the shared Railway instance. |
| Queue, cache | None | **Yes.** Briefs are synchronous; a jobs table comes before Redis if ever needed. |
| Vector store | None | No retrieval yet. |
| Secrets | Environment or mounted files, via the secrets plugin | None. |

## Data model

Existing, written by ingestion: `assets` (one row per enterprise asset ID), `asset_sources` (one
row per asset per source system, first and last seen), `asset_history` (append-only field
changes). Harness tables: `audit_log` (hash-chained), `model_usage`, `agent_executions`,
`agent_definitions`, `eval_runs`, `eval_results`.

The asset detail feature adds no table. It changes the API shape: detail keyed by enterprise
asset ID; `flags` and `data_completeness` on the detail; `source_systems` with first and last
seen; a paginated history list. Renames from the interview land first: `without_*` for every gap
(D-032), `source_systems` (D-037), `brief` (D-028).

Later modules add, one slice at a time and only when a feature reads them: findings, patch
status, controls and assessments, risks. Each carries the PRD §7 provenance fields (source
system, source record id, collected at, updated at, data-quality status, correlation status).

## Guardrails, by layer

- **Entry:** every `/api/*` call audited including refusals; rate limited; a permission on every
  endpoint; bounded page size; development tokens refused in production.
- **Agent:** tools allow-listed per agent and all read-only; redaction before the model (ipv4,
  mac, email; host name, owner and business unit to be added per D-014); tool results fenced as
  untrusted data and scanned for instruction-like text, recorded as guardrail events; output
  validated against a pydantic schema with one retry; budgets on calls and tokens; every output
  marked advisory.
- **Data:** no DELETE of a record of fact; lifecycle changes write history; a missing value is
  unknown, never a favourable default; identifiers normalised before comparison.
- **Model:** cannot reach the database; receives only what code hands it; its words never update
  a record; usage recorded from provider metadata, cost NULL unless a price table exists (D-006).

## Tests and evaluations

One failing test first per ticket, at a seam, with expected values from `ccc/sample_assets.csv`
or the requirement, never from the code under test. Tests are named in glossary terms.

- Endpoint seams: 401, 403, 200, 404, pagination and bounded limit for every list.
- Rule seam: detail flags equal `asset_flags()`; agent flags equal endpoint flags; summary counts
  the whole table.
- Ingestion seam: a second CSV under another source name adds a source entry; a field change
  appears in history; a missing asset becomes potentially inactive and comes back when seen again.
- Agent seam: a brief changes nothing in `assets`; redacted values are absent from what the model
  saw and present in the result; the audit chain verifies; a missing asset fails cleanly.
- Browser: `npm run build` and the CI frontend job; the browser computes no number.

Evaluations run on the mock model and CI requires a score of 1.0: the asset-summary suite covers
each flag, completeness on a complete and an incomplete asset, a missing asset, injection in the
data, and the expected tool-call and model-call counts. Prose quality is judged only once a real
model exists, with a small golden set of briefs and a rubric.

## Assumptions and tripwires

| | Assumed |
|---|---|
| Users, peak concurrent | 50 named executives and auditors, 10 concurrent |
| Requests per day | 2,000 API calls, 50 briefs |
| Largest object | asset export CSV, 50 MB, 100k rows |
| Data growth, retention | history 50k rows/month; agent executions 90 days (D-021); audit kept |
| Latency p95 | API 300 ms; brief 10 s, shown as in progress |
| Availability | business hours; a failure shows the last data with its "as of" time |
| Cost ceiling | on-prem infrastructure owned; model under 100 USD/month at 50 briefs/day |
| Sensitive data | host names, IPs, owners; visible by persona; never to a model unredacted |

Where these break a choice: one PostgreSQL instance holds to roughly a million assets and ten
million history rows before partitioning matters. Synchronous briefs hold to a few per minute;
beyond that, a jobs table and a status endpoint, not Redis. Per-process rate limiting is fine for
one API container; two containers need a shared counter. Stdio MCP is fine in one process; a
networked MCP transport needs a workload identity first (D-022).

## Not built, and deferred

Not in the asset detail feature: security posture (findings, patch status, controls), risk,
evidence, chat, executive KPIs beyond the asset ones, any source connector. Each is its own
`/slice` after this one, in the PRD §14 order: findings, patch status, controls.

Decided for this feature without asking (cheap to reverse): history page size 50, newest first;
briefs are not cached; the detail screen is the first Material UI screen and the inventory
migrates later.
