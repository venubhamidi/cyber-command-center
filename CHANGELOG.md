# Changelog: the template

What each release of the template repository adds. The harness has its own log in
`harness/CHANGELOG.md` and its own version in `harness/VERSION`; a template release does not
always change the harness.

## Template 1.1.0 (2026-11-10), harness 1.0.0

A working development process, enforced rather than described:

- `docs/working-practices.md`: settling decisions, shared language, vertical slices, test-first
  at the seams, module design, writing for agents.
- Process skills in `.claude/skills/`: `grill`, `glossary`, `adr`, `slice`, `handoff`.
- Building-block skills: `new-endpoint`, `new-agent`, `new-mcp-tool`, `new-plugin`,
  `new-migration`; each imitates the application's own example and ends by running the checks.
- Glossaries: root `CONTEXT.md` (foundation terms) and `<app_package>/CONTEXT.md` (domain terms).
- Decision records in `docs/adr/`, with the three-part test in its `README.md` and four records
  for the template's own foundation decisions.
- `.github/ISSUE_TEMPLATE/slice.md` and `.github/pull_request_template.md`.
- `scripts/check_structure.py` fails when any of the above is missing, a skill has no
  description, a glossary term has no definition or is defined twice, or a `DECISIONS.md` row has
  a status other than `Open` or `Decided`. `tests/test_structure.py` covers each rule.
- `scripts/rename_app.py` renames a bare `` `app/` `` in documents; `tests/test_rename.py` proves
  a renamed copy still passes.
- Both `CLAUDE.md` files pruned to rules, reasons and traps; the "How we work" section in `README.md`.

## Template 1.0.0, harness 1.0.0

First release: `harness/`, the example application, deployment files, scripts and CI.
