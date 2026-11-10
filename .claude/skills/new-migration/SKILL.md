---
name: new-migration
description: Add a database change as a new numbered .sql file in the application's migrations folder and apply it with python -m harness.migrate. Use for every schema change; never edit an applied migration.
argument-hint: <short slug>
---

# new-migration: append-only schema changes

Rule: migrations are append-only. One new numbered `.sql` file per change. An applied file is
never edited; the harness tracks each by checksum and refuses a changed one.

## Steps

1. Find the application package and the last migration:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   `ls $APP/migrations/` shows the numbering; read the highest-numbered file for the style
   (a comment naming the requirement, explicit types, `CHECK` or enum for closed value sets,
   `unknown` as the default for a value that may be missing, never a favourable default).
   Done when: you know the next number and the style.

2. Write the failing test first: a test in `tests/` that exercises the new column or table
   through a seam (an endpoint, a rule function, an MCP tool), with the expected value taken
   from the requirement, not from the migration.
   Done when: the test fails because the schema lacks the change.

3. Create `$APP/migrations/<NNN>_<slug>.sql` with the next number. Change nothing in any
   existing file. If a record of fact must go away, mark it (a status or a history row); do not
   `DROP` or `DELETE` it.
   Done when: the new file exists and `git diff --stat $APP/migrations/` shows only an addition.

4. Apply it: `python -m harness.migrate $APP`. Then run it again.
   Done when: the first run lists the new file and the second reports nothing to apply.

5. Make the tests see it: the test conftest applies migrations on start, so run
   `python -m pytest -q`. Update seed data if the change needs rows.
   Done when: the test from step 2 passes.

6. Run the checks: `python scripts/check_structure.py && ruff check . && python -m pytest -q`.
   Done when: all pass.

## Completion
The migration applies once and a second run applies nothing; no existing migration changed.
