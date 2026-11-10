# The repository layout follows the template, not PRD Part 6
**Status:** accepted
**Date:** 2026-11-10

## Context
PRD Part 6 proposes a layout with `backend/`, `agents/`, `integrations/`, `mcp/`, `data/`,
`platform/`, `tests/` and `docs/` at the top level, and says "we should validate repository
boundaries and deployment ownership before implementation". The template that this repository
is built from (ADR 0002) fixes a different shape: one application package next to a read-only
`harness/` (`DECISIONS.md` D-024).

## Decision
The template's layout is used. The PRD's folders map as follows:

| PRD Part 6 | Here |
|---|---|
| `backend/api/`, `*-service/`, `ingestion/` | `ccc/api/`, `ccc/assets.py`, `ccc/ingest.py` |
| `agents/` | `ccc/agents/` |
| `integrations/` | plugins in `ccc/plugins/`, chosen by a setting |
| `mcp/` | `ccc/mcp_servers/` (ADR 0001) |
| `data/migrations/`, `schemas/` | `ccc/migrations/`, pydantic models in `ccc/api/schemas.py` |
| `platform/docker/`, `security/` | `deploy/`, and `harness/` for security |
| `tests/unit/`, `integration/`, `agent-evaluation/` | `tests/`, `ccc/evals/` |
| `docs/` | `docs/` |

## Alternatives considered
- **The PRD layout as written.** Would duplicate the harness's concerns under `platform/` and
  `backend/authentication/`, and the PRD itself marks the structure as proposed.
- **A hybrid** with PRD top-level folders wrapping the package. Two conventions to explain.

## Consequences
- `python scripts/check_structure.py` enforces the template shape; the PRD's folder names are a
  reading aid, not a contract.
- New connectors are plugins, not an `integrations/` tree; the `/new-plugin` skill applies.
