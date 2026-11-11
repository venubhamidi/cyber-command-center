# Decision log

Questions the PRD leaves open or that building exposed. **Open** items need an accountable
owner's answer before the affected module is built. Nothing here is guessed in code.

## Decide first

These three block the most work and should be settled before any new module is started.

1. **D-014 — May asset facts leave the premises?** Decided 2026-11-10: a hosted model, with host
   names, owners and business units redacted as well, until the PRD §6 reviews are done. Next:
   add the three patterns to `redact_patterns` and choose the model id (D-006 follows).
2. **Real data.** Decided 2026-11-10: an anonymised export of the real asset database (same
   columns, scrambled names and addresses) is the next input; it also answers D-010 and D-005.
   Waiting on: a named provider and a date (not known on 2026-11-10; the PRD's Data Engineer role
   is the likely owner).
3. **D-010 / D-019 — Asset correlation keys.** Which identifiers match one asset across sources,
   in what order of trust. Waiting on the real data export (item 2); then the Data Engineer.

Interview of 2026-11-10 (`/grill`, two rounds): 22 rows decided, recorded in the log below. Still
Open and waiting on the real data export: D-005, D-007, D-008, D-009, D-010, D-019. Waiting on the
control and risk modules being designed: D-029, D-033, D-036.

## Log

| ID | Status | Raised by | Question / finding | Current choice in code | Owner |
|----|--------|-----------|--------------------|------------------------|-------|
| D-001 | Decided | PRD §5 | Agent orchestration: LangGraph, Google ADK, or no framework. | No framework; agents use the harness contract. The PoC comparing LangGraph, Google ADK and none runs only when an agent needs branching, cycles or resumable state; that need is the trigger. Decided by the owner, 2026-11-10. | Principal AI Architect |
| D-002 | Decided | Build | PRD Part 6 names the folder `mcp/`. In Python this shadows the `mcp` SDK package and breaks every import. | Folder is `mcp_servers/` ([ADR 0001](../docs/adr/0001-mcp-servers-folder-name.md)). | — |
| D-003 | Decided | PRD §2, §12 | Identity provider. | Microsoft Entra ID over OIDC (`APP_AUTH_PROVIDER=oidc`), one IdP group per persona mapped in `APP_OIDC_ROLE_MAP`. Still needed: the tenant's issuer, audience and group names; the browser login redirect is its own ticket. Decided by the owner, 2026-11-10. | Security Architect |
| D-004 | Decided | PRD §8 | Should `/platform/health` be unauthenticated? | Public; it is the liveness probe and returns no secrets (`test_health_is_public`). Decided by the owner, 2026-11-10. | Security Architect |
| D-005 | Open | Build | PRD requires IP and MAC "where applicable" but says nothing about normalization. Uppercase MACs produced phantom history rows. | Normalized in ingestion; the policy on canonical forms for correlation still needs a decision. | Data Engineer |
| D-006 | Decided | Module 8 | Cost per token: which price list, who maintains it, how are local-model costs computed? | A price table setting per provider and model from the provider's published list price, maintained by the Platform Admin; local models at an agreed internal rate per token; `cost_usd` stays NULL for any model not in the table (mock = 0). Decided by the owner, 2026-11-10. Implementation is a ticket. | Platform Admin |
| D-007 | Open | Module 1 | Enterprise Risk Score is a "weighted risk model" with no weights or formula. | Provisional v0 formula in code (D-039), labelled provisional on the tile; the CISO's weights replace it with a version bump. | CISO |
| D-008 | Open | Module 5 | NIST compliance is a "weighted applicable control assessment" with no weights defined. | Provisional weights in `ccc/dashboard.py`: implemented 1.0, partially 0.5, else 0, over applicable controls. | CISO / Internal Audit |
| D-009 | Open | Module 2 | Criticality source of truth: who assigns it, and can a source system override a manual value? | Blank ⇒ `unknown`; surfaced as a KPI. | Business Owners |
| D-010 | Open | Module 2 | Correlation keys for dedup across sources (hostname, MAC, serial, cloud resource ID?). PRD says "multiple identifiers" without ranking them. | Keys only on `enterprise_asset_id`. | Data Engineer |
| D-011 | Decided | PRD §5 | Event broker. | None until the first connector that pushes events; ingestion stays synchronous. Revisit when such a connector is scheduled. Decided by the owner, 2026-11-10. | Principal AI Architect |
| D-012 | Decided | Module 2 | When, and verified by whom, does `potentially_inactive` become `retired`? | Only a person with a new permission `assets:retire`, through an endpoint, in Phase 2 when the MVP stops being read-only (D-025). Never automatically. Decided by the owner, 2026-11-10. | Infrastructure Leadership |
| D-013 | Decided | Build | MCP Python SDK is at 2.x; `FastMCP` is gone, replaced by `MCPServer`. | Pin `mcp>=2,<3`. | — |
| D-014 | Decided | PRD §6 | Which models are approved, and may asset facts be sent to a hosted model at all? | A hosted model is allowed, with host names, owner names and business-unit names redacted in addition to IP, MAC and e-mail ([ADR 0004](../docs/adr/0004-network-identifiers-and-emails-redacted-before-any-model.md)), until the PRD §6 classification, privacy, contractual and security reviews are done. Decided by the owner, 2026-11-10. Which model id: still to be configured; no real model call has been made. | Security Architect / CISO |
| D-015 | Decided | Build | Generic/domain split. | Two repositories: `agent-harness` (template with the read-only `harness/`) and this one, created from it ([ADR 0002](../docs/adr/0002-built-from-the-agent-harness-template.md)). | — |
| D-016 | Decided | Build | Module-level settings made two apps in one process overwrite each other. | Per-app state on `app.state`. | — |
| D-017 | Decided | Build | How applications take the harness. | Copied from the `agent-harness` template; `harness/` is read-only here and checksum-verified in CI; upgrades by `scripts/update_harness.sh`. Revisit a versioned package when two or three real applications exist ([ADR 0002](../docs/adr/0002-built-from-the-agent-harness-template.md)). | Principal AI Architect |
| D-018 | Decided | PRD §7, §12 | PRD names the table `audit_events` and requires **tamper-evident** audit records. | Keep `audit_log` (a harness table), hash-chained. Phase 2 ticket: ship the latest chain hash to a separate store so a full rewrite is detectable. Decided by the owner, 2026-11-10. | Security Architect |
| D-019 | Open | PRD §7 | PRD lists an `asset_identifiers` table ("external identifiers and correlations"). | `asset_sources` holds one source record id per source. Reshape once real data settles D-010. | Data Engineer |
| D-020 | Decided | PRD §5 | UI library and charts. | Material UI and Apache ECharts, adopted before the asset detail screen is built. Decided by the owner, 2026-11-10. | UI/UX Designer |
| D-021 | Decided | Module 8 | "Never store sensitive prompts or outputs in cost telemetry by default." | `model_usage` holds no prompts. `agent_executions` input and output: kept 90 days, redacted with the same patterns as model input; both as settings. Decided by the owner, 2026-11-10. Implementation is a ticket (the redaction and retention settings do not exist yet). | Security Architect |
| D-022 | Decided | PRD §9, §12 | Agents need dedicated workload identities; MCP access must be authenticated and authorized. | Accepted for the on-premises MVP: tools are allow-listed per agent and every call is audited; stdio MCP runs in one process. Any networked MCP transport needs a workload identity first. Decided by the owner, 2026-11-10. | Security Architect |
| D-023 | Decided | Review | Dashboard KPIs were counted in the browser from the loaded page, so they would be wrong beyond one page. | `/api/v1/assets/summary` counts in SQL; one set of gap rules shared with the MCP tool (`ccc/assets.py`). | — |
| D-024 | Decided | Build | PRD Part 6 proposes a repository layout (`backend/`, `agents/`, `integrations/`, `mcp/`, `platform/`). | The template's layout is used instead: `harness/` plus the `ccc/` package. PRD `integrations/` connectors become plugins in `ccc/plugins/` ([ADR 0003](../docs/adr/0003-repository-layout-follows-the-template.md)). | — |
| D-025 | Decided | PRD §3, §12 | Remediation tickets: which system, and who may open tickets? | Jira, in Phase 2 with explicit approval; a Jira plugin in `ccc/plugins/` is scheduled then. Until then ticketing is switched off ([ADR 0005](../docs/adr/0005-read-only-mvp-ticketing-off.md)). `tickets:create` goes to the Security Operations persona only. Decided by the owner, 2026-11-10. | CISO |
| D-026 | Decided | Build | Agent limits: at most 8 model calls, 20 tool calls and 50,000 tokens per run, 3 attempts on transient failures. | Harness defaults kept; revisit when a multi-asset or chat agent exists. Decided by the owner, 2026-11-10. | Principal AI Architect |
| D-027 | Decided | Glossary | Is an *asset owner* a person, a team, or either? | Either. Stored as text; an owner type (person or team) is added when real data shows the mix. Decided by the owner, 2026-11-10. | Business Owners |
| D-028 | Decided | Glossary | One word for the agent's answer about an asset. | **brief**. Endpoint `/assets/{id}/brief`, dashboard, test and docs renamed (asset detail ticket 01). Decided by the owner, 2026-11-10. | Product Owner |
| D-029 | Open | Glossary | *Control effectiveness* values. The PRD requires a separate effectiveness status but names no states. | Not implemented. | CISO / Internal Audit |
| D-030 | Decided | Glossary | Are "asset criticality" and "business criticality" the same field as *criticality*? | Yes: one field, `criticality`, on the asset. Decided by the owner, 2026-11-10. | CISO |
| D-031 | Decided | Glossary | Which fields count for *data completeness*? | The code's five (`REQUIRED_FIELDS` in `ccc/assets.py`: owner, business unit, business service, location, known criticality). Findings, control status and risk rating are added when those tables exist. Decided by the owner, 2026-11-10. | Data Engineer |
| D-032 | Decided | Glossary | The same gap has two names (`no_*` flags, `without_*` counts). | `without_*` everywhere (asset detail ticket 02). Decided by the owner, 2026-11-10. | Product Owner |
| D-033 | Open | Glossary | Does *finding* cover vulnerability findings, control-assessment findings and the findings behind a risk, or does each get its own term? | Not implemented. | Security Architect |
| D-034 | Decided | Glossary | "Unknown asset" (PRD Module 2 req. 5) versus lifecycle state `unknown`. | **unregistered**: an asset a source reports that the inventory lacks. The lifecycle state keeps `unknown`. Unregistered assets are not yet detected. Decided by the owner, 2026-11-10. | Data Engineer |
| D-035 | Decided | Glossary | *Persona* or *role* for a user group? | Persona for the group (documents, screens); role for its key in code (`ROLE_PERMISSIONS`, the OIDC role map). Nothing renamed. Decided by the owner, 2026-11-10. | Product Owner |
| D-036 | Open | Glossary | *Risk rating* (asset field), *Enterprise Risk Score* (KPI) and *risk priority* (agent output): three words, how many things? | None implemented. | CISO |
| D-037 | Decided | Glossary | One word for an outside system that reports assets or findings. | **source system**; API field `source_systems` (asset detail ticket 02). Decided by the owner, 2026-11-10. | Data Engineer |
| D-038 | Decided | Module 1 | Remediation SLA needs days per severity; the PRD names none. | Settings `sla_days`: critical 7, high 30, medium 90, low 180. Decided by the owner, 2026-11-10 (dashboard design, item 2). | CISO |
| D-039 | Decided | Module 1 | Enterprise Risk Score and Security Posture have no formula (D-007). | Provisional v0 in `ccc/dashboard.py`, `FORMULA_VERSION` stored on every snapshot; posture = 100 - risk score; tile labelled provisional. Decided by the owner, 2026-11-10 (dashboard design, item 1). | CISO |
| D-040 | Decided | Module 1 | Drill-down for modules not yet built. | Critical Assets drills to the inventory filtered by criticality; other tiles land on a plain read-only list of the underlying records; filters arrive with each module. Decided by the owner, 2026-11-10 (item 3). | Product Owner |
| D-041 | Decided | Module 1 | Landing page. | The dashboard is the root; the inventory is a tab. Decided by the owner, 2026-11-10 (item 5). | Product Owner |
| D-042 | Open | Module 1 | The PRD §2 persona table gives the CISO no `patch:read` or `incidents:read`, so the dashboard shows the patch and incident counts but the CISO cannot open the records behind them. | Role table unchanged; the tile hides the drill-down link for a caller without the permission. | CISO |

## Known gaps against the PRD

Not decisions, just work not done yet. Listed so nobody assumes it exists.

- **Not proven:** a real model call (mock only); CI and the container images (first run happens on GitHub);
  single sign-on against your identity provider.
- **Security (§12):** ABAC, secrets manager integration (environment and mounted files only), encryption and
  data classification, tool input validation. Prompt-injection handling is a heuristic scan plus fencing;
  the real protection is that agents have read-only tools.
- **Chat (Module 7):** no `/api/v1/chat`. The asset agent's answer does follow the seven-part response format.
- **AI operations (Module 8):** `model_usage` has no use-case field; no success/failure/retry-rate views
  (the data is recorded in `agent_executions`). Agent evaluations exist for the one agent.
- **Data (§7):** 11 of the PRD's 22 tables exist in some form, plus the audit table under a different name.
  Findings, patch status, control assessments, incidents and risks hold mock data only.
- **Modules 3 to 6:** no screens or filters of their own; the dashboard's drill-down is a plain list.
  Risks are seeded by a mock, not derived by a risk engine. Control-to-ISO/TISAX mappings and evidence
  records do not exist.
- **Screens (§11):** dashboard, drill-down list, asset inventory, asset detail. No chat, no AI operations screen.
- **Integrations:** every connector is a mock (`ccc/plugins/mock_connectors.py`); no connector to Tenable,
  Defender, SCCM, Intune, Chronicle or Entra ID. A real one is a plugin in `ccc/plugins/` chosen by `APP_CONNECTORS`.
- **Scheduling:** `python -m ccc.snapshot` must be run daily by ops; nothing in the application schedules it.
- **Observability:** no OpenTelemetry, metrics or tracing.
