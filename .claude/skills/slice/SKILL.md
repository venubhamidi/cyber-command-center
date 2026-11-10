---
name: slice
description: Turn a plan into vertical-slice tickets, get the breakdown approved, then create them as GitHub issues or as files under .scratch/<feature>/issues/. Use when a feature is agreed and needs cutting into work that fits one session each.
argument-hint: <feature or plan>
---

# slice: thin, complete, demonstrable tickets

The rules are `docs/working-practices.md` §3; the ticket shape is
`.github/ISSUE_TEMPLATE/slice.md`.

## Steps

1. Find the application package and read its context:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   Read `$APP/CLAUDE.md`, `$APP/DECISIONS.md` and both `CONTEXT.md` files.
   Done when: you can name every `Open` decision the plan touches.

2. If the plan depends on an `Open` decision, stop and run `/grill` on it first. Only settled
   decisions may be assumed in a ticket.
   Done when: no ticket will rest on a guess.

3. Cut the plan into slices. Each slice: a complete path through every layer it needs (schema,
   rule, tool, endpoint, screen, as applicable), demonstrable alone, small enough for one fresh
   session. Preparatory refactoring is its own slice and comes first. Name each slice in
   glossary terms.
   Done when: every slice can be shown working on its own.

4. For each slice write the three sections from the template: **What to build** (observable
   behaviour, no file paths or code), **Blocked by** (slice numbers or decision IDs, or "nothing"),
   **Acceptance criteria** (a checklist a reviewer can tick; name the seam each check observes).
   Done when: each ticket has all three sections and no implementation detail.

5. Show the numbered breakdown with its dependency order and ask the owner to approve or
   change it. Wait.
   Done when: the owner has approved the breakdown.

6. Create the tickets. If `gh auth status` succeeds, create one issue per slice with the label
   `ready-for-agent` and the blockers in the body. Otherwise write
   `.scratch/<feature>/issues/NN-<slug>.md`, one file per slice, same content.
   Done when: every approved slice exists as an issue or a file, and the blocker references
   point at real ticket numbers.

## Completion
Every ticket has the three template sections and its blockers; the owner approved the breakdown;
the tickets exist as issues or files. No code was written.
