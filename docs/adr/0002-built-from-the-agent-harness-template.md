# Built from the agent-harness template; `harness/` is read-only here
**Status:** accepted
**Date:** 2026-11-10

## Context
The Command Center needs login, permissions, audit, rate limiting, migrations, an agent contract
with guardrails, evaluations, plugins and container deployment. None of that is specific to
cybersecurity, and the next application will need the same. Building it inside this repository
would make it the only copy (`DECISIONS.md` D-015, D-017).

## Decision
The generic foundation lives in a separate template repository, `agent-harness`. This repository
was created from it. `harness/` is a byte-for-byte copy of the template's, checked by
`scripts/harness_lock.py` in CI, and is never edited here. Everything specific to the Command
Center is in `ccc/`, `frontend/` and `tests/`. Upgrades arrive through
`scripts/update_harness.sh`, which replaces `harness/` with a released version and reruns the
checks. The template's own record of this choice is
https://github.com/venubhamidi/agent-harness/blob/main/docs/adr/0001-harness-by-template-copy.md.

## Alternatives considered
- **One repository with a `platform/` folder** (PRD Part 6). Simplest at first; the second
  application copies and diverges, or imports across repositories.
- **A versioned `harness` Python package.** The right end state; deferred until two or three real
  applications justify release tooling (D-017).
- **A git submodule.** Awkward review and stale pins.

## Consequences
- Anything the Command Center needs that the harness lacks is built in `ccc/` (a plugin, a
  helper, a subclass) or proposed to the template; it is never patched into `harness/`.
- `scripts/check_structure.py`, `scripts/harness_lock.py` and `scripts/rename_app.py` are
  template-owned and overwritten on upgrade.
