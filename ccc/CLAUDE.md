# Cyber Command Center — domain rules for Claude Code

Enterprise cybersecurity intelligence platform for CIO/CISO/CTO and audit. Requirements:
`docs/PRD.pdf` (v1.0). Open questions: `ccc/DECISIONS.md`. The repository-wide rules in the root
`CLAUDE.md` apply here as well; this file adds only what is specific to the Command Center.

## Not decided yet — do not guess
- Agent framework (LangGraph, Google ADK or none): D-001. Do not import either; use the harness contract.
- Approved model, and whether asset facts may go to a hosted model: D-014. Mock provider only.
- Risk-score and compliance weights: D-007, D-008. Do not invent formulas.
- Asset correlation keys: D-010. Match on `enterprise_asset_id` only.

## Layout
```
ccc/config.py        settings and the PRD §2 role table
ccc/migrations/      asset schema (all PRD asset types, including cloud and OT placeholders)
ccc/assets.py        data-quality rules, defined once, shared by the API, the MCP tools and the agent
ccc/ingest.py        CSV asset import
ccc/api/             routes and response models
ccc/agents/          Asset Summary Agent
ccc/mcp_servers/     MCP tool servers (the folder is not `mcp/`: that would shadow the SDK)
ccc/evals/           evaluation cases and fixtures for each agent
ccc/plugins/         connectors to source systems (Tenable, Defender, SCCM, ...) go here as plugins
ccc/sample_assets.csv  six invented assets for development and tests
tests/               tests;  frontend/: React dashboard
```

## Commands
```
python -m harness.migrate ccc
python -m ccc.ingest                      # loads ccc/sample_assets.csv
uvicorn ccc.main:app --reload                  # API on :8000
python -m ccc.agents.asset_agent EA-000003     # the agent, tools over real MCP
python -m harness.evals ccc                    # agent evaluations
```

## Domain rules (each has a test)
1. **Never auto-delete an asset.** Missing from a source ⇒ `lifecycle_state='potentially_inactive'`
   plus a history row. (`test_asset_missing_from_source_is_marked_not_deleted`)
2. **Blank criticality ⇒ `'unknown'`**, never a default like `low`. The same will apply to patch
   status: unknown is never compliant. (`test_blank_criticality_becomes_unknown_not_low`)
3. **Asset KPIs come from `/api/v1/assets/summary`**, using the rules in `ccc/assets.py`; the agent
   uses the same rules. (`test_summary_counts_whole_inventory_not_one_page`, `test_flags_are_computed_by_rules_and_match_the_api`)
4. **Normalize identifiers before comparing** (MAC lower-case, IP canonical) or history fills with
   phantom changes. (`test_ingest_is_idempotent`)
5. **Agents never write to `assets`** or any other record of fact. (`test_agent_does_not_write_to_assets`)
6. **IP, MAC and e-mail addresses never reach a model** (`redact_patterns` in `ccc/config.py`).
   (`test_ip_addresses_never_reach_the_model_but_are_intact_in_the_result`)
7. **Agent answers follow the PRD Module 7 format:** summary, supporting facts, business impact,
   recommended action, source references, last-updated time, data completeness. Facts, sources,
   time and completeness are filled by code. (`test_response_carries_sources_timestamp_and_completeness`)
8. **Read-only MVP (PRD §12).** No endpoint or agent changes an asset, a finding or a control;
   ticketing is switched off.

## How to add things
- Endpoint: `ccc/api/routes.py`, following `list_assets`; add the permission to `ROLE_PERMISSIONS`;
  tests for 401, 403, 200 and pagination.
- Agent: follow `ccc/agents/asset_agent.py`; add a suite to `ccc/evals/` (CI fails without one).
- MCP tool: add to `ccc/mcp_servers/*/server.py` and to its `TOOLS` dict; tools return JSON text.
- Source-system connector: a plugin in `ccc/plugins/`, selected by a setting.
- Schema change: a new numbered file in `ccc/migrations/`.
- Docstrings cite the PRD section a rule comes from.
