---
name: new-endpoint
description: Add an API endpoint the harness way, test first: 401, 403, 200 and pagination tests, then the route with require() and db_url, then the permission in the role table. Use for every new route.
argument-hint: <method> <path> <permission>
---

# new-endpoint: a route with its tests, permission and audit

Rules: every endpoint declares `Depends(require("<thing>:<action>"))` and `db: str = Depends(db_url)`;
a list endpoint returns `Page[T]` with a bounded `limit`. Audit is automatic.

## Steps

1. Find the application package and the example to imitate:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   `grep -rl "APIRouter(" $APP --include=*.py` names the route module(s);
   `grep -l "status_code == 401" tests/*.py` names the test file whose shape to copy;
   `ROLE_PERMISSIONS` is in `$APP/config.py`.
   Done when: you have read one existing route and its test.

2. Name the permission in glossary terms (`$APP/CONTEXT.md`), as `<thing>:<action>`.
   Done when: the permission string is chosen and not already used for something else.

3. Write the failing tests first, in the test file from step 1, using the token headers its
   conftest defines: no token gives 401; a role without the permission gives 403; a role with it
   gives 200 and the expected body; for a list, `limit`/`offset` are honoured, `total` counts the
   whole table, and `limit=0` gives 422. Take expected values from the seed data, not from the
   code you are about to write. Run `python -m pytest -q` and watch them fail.
   Done when: the new tests fail and the old ones still pass.

4. Write the route next to the example: permission dependency, `db_url`, explicit SQL through
   `get_conn(db)`, a pydantic response model, `Page[T]` for lists. Counts and flags come from the
   rule functions, never from the browser or the model.
   Done when: the route is registered on the router the application's `main.py` includes.

5. Add the permission to every role that should have it in `ROLE_PERMISSIONS`. Roles are a
   domain decision: if unsure which, ask; do not add it to all.
   Done when: the 403 test still fails for the role without it.

6. Run the checks: `python scripts/check_structure.py && ruff check . && python -m pytest -q`.
   Done when: all pass.

## Completion
The 401, 403, 200 and (for lists) pagination tests pass; the structure check passes.
