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
   │  GET  /me                             caller's persona + permissions│
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

## Database design

One PostgreSQL database, two groups of tables. Harness tables come from `harness/migrations/`
and are the same in every application; domain tables come from `ccc/migrations/`, append-only,
one numbered file per change.

```
 DOMAIN (ccc/migrations)                              HARNESS (harness/migrations, read-only)

 assets                                               audit_log            every API call and
 ├ id                 BIGSERIAL PK                     ├ id, occurred_at    agent tool call,
 ├ enterprise_asset_id TEXT UNIQUE   ← the key         ├ principal, role    refused ones too;
 ├ hostname, ip_address INET, mac_address MACADDR      ├ action, resource   hash-chained
 ├ asset_type         ENUM (22 values: IT, cloud, OT)  ├ status_code
 ├ asset_owner, business_unit, business_service        ├ request_id, detail JSONB
 ├ criticality        ENUM critical…low, unknown       └ prev_hash, row_hash
 ├ location, environment ENUM (…, unknown)
 ├ operating_system                                   agent_definitions    one row per agent id
 ├ lifecycle_state    ENUM active, potentially_        agent_executions     one row per run:
 │                    inactive, retired, unknown        input/output JSONB, status, counts,
 ├ first_seen_at, last_seen_at                         guardrail_events, latency
 └ created_at, updated_at                             model_usage          one row per model call:
   idx: lower(hostname), ip_address, business_unit     tokens, cost_usd (NULL = unknown)
        │ 1                                            eval_runs, eval_results  score history
        │
        ├──< asset_sources   (asset_id, source_system) PK
        │     source_record_id, first_seen_at, last_seen_at
        │     one row per source system that reported the asset
        │
        └──< asset_history   id PK, asset_id FK
              changed_at, changed_by, field, old_value, new_value
              append-only; written by ingestion for every field change
```

Rules the schema encodes:
- **The enterprise asset ID is the one key.** Everything addresses an asset by it; the row id
  stays internal. Correlation on other identifiers waits for D-010 and will add an
  `asset_identifiers` table (D-019), not more columns.
- **Closed value sets are enums that include `unknown`**, and `unknown` is the default where a
  value may be missing. There is no favourable default anywhere.
- **Nothing is deleted.** A source that stops reporting an asset flips `lifecycle_state` to
  `potentially_inactive` and writes a history row; `retired` is set only by a person (D-012).
- **Facts and derived values are separate.** Flags, counts and completeness are computed from
  these columns by `ccc/assets.py` at read time and never stored. Model output lives only in
  `agent_executions.output` and never in a domain table.
- **Provenance travels with the record.** `asset_sources` says who reported an asset and when;
  every future finding carries source system, source record id, collected and updated times,
  data-quality and correlation status (PRD §7).
- **Identifiers are normalised before comparison** (lower-case MAC, canonical IP), or history
  fills with phantom changes.

Growth, one slice at a time, only when a feature reads the table (each needs its own design
pass before it is built):

| Module | Tables, in outline | Keyed by |
|---|---|---|
| 3 Vulnerabilities | `findings` (provenance fields, severity, cve, exploitability, status), `asset_findings` | finding by (source_system, source_record_id); link by asset id |
| 4 Patch compliance | `patch_status` per asset and source: applicable, non-applicable, unknown, offline, exempt, failed | asset id, source system |
| 5 Controls | `controls` (library), `framework_mappings`, `control_assessments` (status, effectiveness, assessor, dates), `evidence_records`, `asset_controls` | control id |
| 6 Risk | `risks`, `risk_findings` | risk id; model version on every row |
| Platform | `data_sources` (connector configuration), `ingestion_runs` | source system |

Sizing, from the assumptions below: assets in the tens of thousands, history in the low
millions per year, audit in the millions per year. All fit one instance with the existing
indexes; partition `asset_history` and `audit_log` by month only past roughly ten million rows.

## Executive dashboard (Module 1), approved 2026-11-10

The landing page: eight KPI tiles and the top five enterprise risks. Assets are real (Module 2).
Findings, patch status, control assessments, incidents and risks come from **mock connectors**
that load into real tables; when a real connector arrives only the connector changes. No model
call anywhere in this feature; every number is SQL plus versioned Python.

```
 seed files (ccc/mock/*.json)             ccc/sample_assets.csv
        |                                        |
        v                                        v
 connector plugins (kind "connector")        ingest_csv
  mock_tenable mock_sccm mock_grc                |
  mock_chronicle mock_risk    fetch() only       |
        |                                        |
        v                                        v
 ccc/ingest_sources.py  upsert, mark missing, never DELETE      deterministic code
        |
        v
 PostgreSQL (ccc/migrations/002_dashboard.sql)
   findings  patch_status  control_assessments  incidents  risks  risk_assets  kpi_snapshots
        |  SQL aggregates                          ^
        v                                          |  python -m ccc.snapshot   (daily, by ops cron)
 ccc/dashboard.py   KPI math, FORMULA_VERSION  ----+
        |
        v
 GET /api/v1/dashboard   require("dashboard:read")        audit, rate limit, auth: harness
 GET /api/v1/{findings|patch-status|controls|incidents}   each behind its module permission
        |
        v
 DashboardPage: 8 tiles + top-5 risks; the inventory becomes a tab (?view=assets)
```

Each KPI carries: value, previous value (latest earlier snapshot), trend (`up`, `down`, `flat`,
`no_history`), `data_as_of` (oldest collected_at among its sources), `source_systems`, and a
drill-down path. Rules written as code and tests (`ccc/dashboard.py`):

| KPI | Calculation | Sources |
|---|---|---|
| Critical Assets | assets with criticality `critical` and lifecycle `active` | assets |
| Vulnerability Exposure | open findings of severity critical or high, one per (cve, asset) | findings |
| Patch Compliance | compliant / applicable; applicable excludes `non_applicable`, `unknown`, `offline`, `exempt`; unknown is never compliant | patch_status |
| NIST Compliance | implemented 1.0, partially 0.5, else 0, over applicable controls; `not_assessed` and `evidence_pending` count 0 (weights provisional, D-008) | control_assessments |
| Open Incidents | incidents with status `open` | incidents |
| Remediation SLA | findings closed on or before due date / findings whose due date has passed or that closed; SLA days by severity 7/30/90/180 (D-038) | findings |
| Enterprise Risk Score | provisional v0 (D-039): mean of exposure, patch gap, NIST gap and incident pressure, 0..100 | the four above |
| Security Posture | 100 minus the risk score (D-039) | same |

Tables (append-only migration `002_dashboard.sql`), each with the PRD §7 provenance fields
`source_system`, `source_record_id`, `collected_at`, `updated_at`, and `data_quality_status`:

| Table | For | Key |
|---|---|---|
| `findings` | one vulnerability on one asset: severity, cvss, cve, exploitable, known_exploited, status, first/last seen, due_at, closed_at | (source_system, source_record_id) |
| `patch_status` | one asset per source: `compliant`, `missing`, `failed`, `unknown`, `offline`, `exempt`, `non_applicable`; missing_count | (asset_id, source_system) |
| `control_assessments` | control id and title, framework, status (six PRD states), effectiveness text (D-029), assessed_at, assessor | (source_system, source_record_id) |
| `incidents` | title, severity, status open/closed, opened_at, closed_at | (source_system, source_record_id) |
| `risks`, `risk_assets` | PRD Module 1 risk fields plus `model_version`; link rows to assets | risk id |
| `kpi_snapshots` | kpi, period_date, value, formula_version, source_systems, computed_at | (kpi, period_date) |

Guardrails: `dashboard:read` on the dashboard; each drill-down list keeps its module permission,
so a CIO sees the vulnerability count and not the list. Connectors only fetch; ingestion upserts
and never deletes, a record absent from its source is marked `data_quality_status = 'stale'`.
Rows loaded from mocks carry `source_system` starting with `mock_` and the tile says so. The
formula version is stored on every snapshot, so changing a weight never rewrites history.

Tests at the seams: hand-computed expected values for all eight KPIs over the seed; an all-unknown
fleet gives no patch compliance value (unknown, never 0 or 100); the same CVE on one asset from two scanners counts once;
no snapshot means `no_history`, never zero; the snapshot command is idempotent per day; the
permission matrix on `/dashboard`; top five ordered by rating then updated_at with all nine PRD
fields. No evals: nothing calls a model.

Tripwire: the dashboard is six aggregate queries per load. Past roughly a million findings, serve
the daily snapshot and recompute on ingest.

Not built: real connectors, Module 3 to 6 screens and filters, the risk engine (risks are seeded,
not derived), a scheduler, incident detail.

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
