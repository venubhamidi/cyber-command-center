# Decision log

Questions the PRD leaves open or that building exposed. **Open** items need an accountable
owner's answer before the affected module is built. Nothing here is guessed in code.

## Decide first

These three block the most work and should be settled before any new module is started.

1. **D-014 — May asset facts leave the premises?** Whether hostnames, IPs and owners may be sent
   to a hosted model decides between a hosted and a local model for every agent and the chat
   assistant. The PRD says the data platform stays on-premises and hosted inference needs
   classification, privacy, contractual and security review first.
2. **Real data.** Everything so far runs on six invented assets. An export of the real asset
   database (anonymized if needed) is the next input the project needs; it also answers D-010.
3. **D-010 / D-019 — Asset correlation keys.** Which identifiers match one asset across sources,
   in what order of trust.

## Log

| ID | Status | Raised by | Question / finding | Current choice in code | Owner |
|----|--------|-----------|--------------------|------------------------|-------|
| D-001 | Open | PRD §5 | Agent orchestration: LangGraph, Google ADK, or **no framework** (the harness agent contract alone). The PRD asks for a proof of concept and warns against letting a framework dictate the architecture. | Neither imported. The proof of concept should compare all three on the same agent and evaluation set. | Principal AI Architect |
| D-002 | Decided | Build | PRD Part 6 names the folder `mcp/`. In Python this shadows the `mcp` SDK package and breaks every import. | Folder is `mcp_servers/`. | — |
| D-003 | Open | PRD §2, §12 | Identity provider. PRD requires enterprise SSO / OIDC with RBAC + ABAC but names no IdP. | The harness validates OIDC tokens (`APP_AUTH_PROVIDER=oidc`) and refuses development tokens in production. Still needed from you: which IdP, its issuer and audience, and which IdP groups map to which role. The browser login redirect is not built. | Security Architect |
| D-004 | Open | PRD §8 | Should `/platform/health` be unauthenticated (liveness probe) or require auth? | Public, returns no secrets. | Security Architect |
| D-005 | Open | Build | PRD requires IP and MAC "where applicable" but says nothing about normalization. Uppercase MACs produced phantom history rows. | Normalized in ingestion; the policy on canonical forms for correlation still needs a decision. | Data Engineer |
| D-006 | Open | Module 8 | Cost per token: which price list, who maintains it, how are local-model costs computed? | `cost_usd` is NULL unless a confirmed price table exists; mock = 0. | Platform Admin |
| D-007 | Open | Module 1 | Enterprise Risk Score is a "weighted risk model" with no weights or formula. | Not implemented. | CISO |
| D-008 | Open | Module 5 | NIST compliance is a "weighted applicable control assessment" with no weights defined. | Not implemented. | CISO / Internal Audit |
| D-009 | Open | Module 2 | Criticality source of truth: who assigns it, and can a source system override a manual value? | Blank ⇒ `unknown`; surfaced as a KPI. | Business Owners |
| D-010 | Open | Module 2 | Correlation keys for dedup across sources (hostname, MAC, serial, cloud resource ID?). PRD says "multiple identifiers" without ranking them. | Keys only on `enterprise_asset_id`. | Data Engineer |
| D-011 | Open | PRD §5 | Event broker: "Kafka-compatible" but no product named. | None used; ingestion is synchronous. | Principal AI Architect |
| D-012 | Open | Module 2 | When, and verified by whom, does `potentially_inactive` become `retired`? | Never auto-transitions. | Infrastructure Leadership |
| D-013 | Decided | Build | MCP Python SDK is at 2.x; `FastMCP` is gone, replaced by `MCPServer`. | Pin `mcp>=2,<3`. | — |
| D-014 | Open | PRD §6 | Which models are approved, and may asset facts be sent to a hosted model at all? | Mock provider only; no model id is configured. IP addresses, MAC addresses and e-mail addresses are replaced with placeholders before any model sees them. Host names, owners and business-unit names are **not** redacted; decide whether they may be sent. No real model call has been made. | Security Architect / CISO |
| D-015 | Decided | Build | Generic/domain split. | Two repositories: `agent-harness` (template with the read-only `harness/`) and this one, created from it. | — |
| D-016 | Decided | Build | Module-level settings made two apps in one process overwrite each other. | Per-app state on `app.state`. | — |
| D-017 | Decided | Build | How applications take the harness. | Copied from the `agent-harness` template; `harness/` is read-only here and checksum-verified in CI; upgrades by `scripts/update_harness.sh`. Revisit a versioned package when two or three real applications exist. | Principal AI Architect |
| D-018 | Open | PRD §7, §12 | PRD names the table `audit_events` and requires **tamper-evident** audit records. | Table is `audit_log`. Records are hash-chained, so edits and deletions inside the log are detectable. Not yet covered: someone who can rewrite the whole table; that needs the latest hash shipped to a separate system. | Security Architect |
| D-019 | Open | PRD §7 | PRD lists an `asset_identifiers` table ("external identifiers and correlations"). | `asset_sources` holds one source record id per source. Reshape once real data settles D-010. | Data Engineer |
| D-020 | Open | PRD §5 | PRD proposes Material UI and Apache ECharts ("proposed, not mandatory"). | Hand-written CSS, no chart library. Decide before the dashboard grows. | UI/UX Designer |
| D-021 | Open | Module 8 | "Never store sensitive prompts or outputs in cost telemetry by default." | `model_usage` holds no prompts. `agent_executions` stores full input and output; retention and redaction policy needed. | Security Architect |
| D-022 | Open | PRD §9, §12 | Agents need dedicated workload identities; MCP access must be authenticated and authorized. | Tools are allow-listed per agent and every call is audited. The agent id is still only a label and the MCP stdio transport has no authentication. | Security Architect |
| D-023 | Decided | Review | Dashboard KPIs were counted in the browser from the loaded page, so they would be wrong beyond one page. | `/api/v1/assets/summary` counts in SQL; one set of gap rules shared with the MCP tool (`ccc/assets.py`). | — |
| D-024 | Decided | Build | PRD Part 6 proposes a repository layout (`backend/`, `agents/`, `integrations/`, `mcp/`, `platform/`). | The template's layout is used instead: `harness/` plus the `ccc/` package. PRD `integrations/` connectors become plugins in `ccc/plugins/`. | — |
| D-025 | Open | PRD §3, §12 | Remediation tickets: the PRD schedules Jira in Phase 2 with explicit approval. The harness ships a ServiceNow plugin and no Jira plugin. Which system, and who may open tickets? | Ticketing is switched off (`APP_TICKETING_PROVIDER=none`). Agents can never open tickets; only a permitted person through an endpoint. | CISO |
| D-026 | Open | Build | Agent limits: at most 8 model calls, 20 tool calls and 50,000 tokens per run, 3 attempts on transient failures. Are these right for the Command Center's agents? | Harness defaults. | Principal AI Architect |

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
- **Data (§7):** 4 of the PRD's 22 tables exist in some form, plus the audit table under a different name.
- **Screens (§11):** asset inventory with an assistant brief per asset. No asset detail screen yet.
- **Integrations:** no connector to Tenable, Defender, SCCM, Intune, Chronicle or Entra ID. Each will be a
  plugin in `ccc/plugins/`.
- **Observability:** no OpenTelemetry, metrics or tracing.
