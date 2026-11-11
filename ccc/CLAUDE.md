# Cyber Command Center — domain rules for Claude Code

Enterprise cybersecurity intelligence platform for CIO, CISO, CTO and Internal Audit. Requirements:
`docs/PRD.pdf` (v1.0); cite the PRD section in a docstring when a rule comes from it. The PRD is
the requirements input, not the design: understand the need behind each item and build it the
harness way; where the PRD's wording pulls against a harness rule, the harness wins and the
difference is a `DECISIONS.md` row or an ADR. The root `CLAUDE.md` applies here as well; this
file adds only what is specific to the Command Center.
Terms, glossary: `ccc/CONTEXT.md`. Open questions: `ccc/DECISIONS.md` ("Decide first" comes first).
Decision records: `docs/adr/`. Design, data flow, guardrails, test seams: `ARCHITECTURE.md`;
read it before a feature and extend it after one.

## Key decisions already made
No agent framework (D-001), on-premises PostgreSQL (PRD §6), no queue or cache, no retrieval:
see the stack table in `ARCHITECTURE.md`. Folder `mcp_servers/` (ADR 0001); read-only MVP (ADR 0005).

## Not decided yet — do not guess
- Agent framework (LangGraph, Google ADK or none): D-001. Import neither; use the harness contract.
- Approved model, and whether asset facts may go to a hosted model: D-014. Mock provider only.
- Risk-score and compliance weights: D-007, D-008. Do not invent formulas.
- Asset correlation keys: D-010. Match on `enterprise_asset_id` only.
- Wording conflicts D-027 to D-037: use the glossary's current definition; rename nothing until decided.

## Domain rules (each names its test)
1. **Never auto-delete an asset.** Missing from a source ⇒ `lifecycle_state='potentially_inactive'`
   plus a history row. (`test_asset_missing_from_source_is_marked_not_deleted`)
2. **Store blank criticality as `'unknown'`**, never as a default like `low`. The same will apply to
   patch status: unknown is never compliant. (`test_blank_criticality_becomes_unknown_not_low`)
3. **Take asset KPIs from `/api/v1/assets/summary`**, computed by the rules in `ccc/assets.py`; the
   agent uses the same rules. (`test_summary_counts_whole_inventory_not_one_page`,
   `test_flags_are_computed_by_rules_and_match_the_api`)
4. **Normalize identifiers before comparing** (MAC lower-case, IP canonical), or history fills with
   phantom changes. (`test_ingest_is_idempotent`)
5. **Agents never write to `assets`** or any other record of fact. (`test_agent_does_not_write_to_assets`)
6. **IP, MAC and e-mail addresses never reach a model** (`redact_patterns` in `ccc/config.py`, ADR 0004).
   (`test_ip_addresses_never_reach_the_model_but_are_intact_in_the_result`)
7. **Shape every agent answer as the PRD Module 7 format:** summary, supporting facts, business
   impact, recommended action, source references, last-updated time, data completeness. Code fills
   facts, sources, time and completeness; the model writes only summary, impact and action.
   (`test_response_carries_sources_timestamp_and_completeness`)
8. **Read-only MVP (PRD §12, ADR 0005).** No endpoint or agent changes an asset, a finding or a
   control; ticketing is switched off. Every new endpoint is `GET` until D-025 is decided.

## Traps
- The folder is `mcp_servers/`, never `mcp/`: that name shadows the MCP SDK (ADR 0001).
- Keep source facts and model output apart (PRD §7): `supporting_facts` is the record as stored.
- Source-system connectors (Tenable, Defender, SCCM, Intune, Chronicle, Entra ID) are plugins in
  `ccc/plugins/` chosen by a setting; none exists yet. `ccc/sample_assets.csv` holds six invented
  assets, and the tests and evals assume exactly those.
