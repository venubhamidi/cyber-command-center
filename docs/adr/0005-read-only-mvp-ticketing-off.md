# The MVP is read-only and ticketing is switched off
**Status:** accepted
**Date:** 2026-11-10

## Context
PRD §12 requires a read-only MVP: no autonomous remediation, and the assistant may recommend but
may not disable accounts, modify firewall rules, patch, change configurations, delete assets,
close findings or alter control assessments. Jira ticket creation is scheduled for Phase 2 with
explicit approval (`DECISIONS.md` D-025). The harness ships a ticketing plugin kind with
`memory` and `servicenow` plugins and an endpoint pattern for opening tickets.

## Decision
No endpoint or agent in this repository changes an asset, a finding or a control. Agents have
only read-only MCP tools (template rule). `ticketing_provider = "none"` is the default in
`ccc/config.py`, so no ticket endpoint is wired and a call to one would be a 503. Turning
ticketing on is a decision with a named approver (D-025), a plugin choice, a permission in the
role table and an endpoint a person calls; it is not a configuration flip. Tests:
`test_agent_does_not_write_to_assets`, `test_review_endpoint_runs_the_agent_over_real_mcp_and_needs_permission`.

## Alternatives considered
- **Ship with the `memory` ticketing plugin on**, as the template example does. Harmless in
  development but leaves a write path that the PRD says must not exist yet.
- **Build the Jira plugin now, disabled.** Work ahead of a decision; the system and the approver
  are not chosen.

## Consequences
- The PRD's remediation and ticket features are Phase 2 work with their own decision records.
- Every new endpoint is `GET` until D-025 is decided; `/new-endpoint` reviews should refuse a
  writing route.
