---
name: adr
description: Decide whether a decision deserves an architecture decision record and, if so, write docs/adr/NNNN-<slug>.md in the agreed format; otherwise add a DECISIONS.md row. Use whenever a choice between workable alternatives has been made.
argument-hint: <decision in one sentence>
---

# adr: record a decision that will surprise someone later

The test and format are in `docs/adr/README.md`; the reasoning in `docs/working-practices.md` §2.

## Steps

1. Find the application package:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   Read `docs/adr/README.md` and list the existing records (`ls docs/adr/`).
   Done when: you know the next free number and whether a record on this topic already exists.

2. Apply the three-part test to the decision. Answer each part in one line:
   - Hard to reverse?
   - Would surprise a future reader?
   - A real choice between workable alternatives?
   Done when: all three are answered yes or no with a reason.

3. If any answer is no: say which, and instead add or update a row in `$APP/DECISIONS.md` with
   status `Decided`, the choice and who decided. Stop here.
   Done when: the row exists and your reply states why no record was written.

4. If all three are yes: write `docs/adr/NNNN-<slug>.md` (four-digit number, lower-case slug)
   with these sections in this order: title (as the `#` heading), **Status**, **Date**,
   **Context**, **Decision**, **Alternatives considered**, **Consequences**. Take the facts from
   the code and documents, not from memory; cite the file or section they come from.
   Done when: the file exists with all seven parts and `python scripts/check_structure.py` passes.

5. If the decision also has a `DECISIONS.md` row, set it to `Decided` and link the record from
   the row's "Current choice" column.
   Done when: the row links to the record, or there was no row.

## Completion
Either a numbered record exists with every section filled, or the reason for not writing one
was stated and a `DECISIONS.md` row holds the choice.
