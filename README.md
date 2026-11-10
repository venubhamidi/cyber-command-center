# Cyber Command Center

Enterprise cybersecurity intelligence platform (requirements: `docs/PRD.pdf`). Built on the
[agent-harness](https://github.com/venubhamidi/agent-harness) template: `harness/` is the shared foundation and is read-only here; everything
specific to the Command Center is in `ccc/`, `frontend/` and `tests/`.

```
CSV ──ingest──▶ PostgreSQL ──▶ FastAPI (login · roles · rate limit · audit) ──▶ React dashboard
                    ▲
                    └── asset-mcp (MCP) ◀── Asset Summary Agent ──▶ model gateway ──▶ usage records
```

What exists today: asset inventory from a sample CSV, 6 endpoints, one agent with 8 evaluation
cases, 2 MCP tools, one dashboard screen, 81 tests. What does not: see "Known gaps" in
`ccc/DECISIONS.md`, which also lists the decisions needed before more is built.

## Run it locally
Needs Python 3.12+, Node 22 and PostgreSQL 16.
```bash
sudo -u postgres scripts/dev_db.sh        # creates databases app and app_test
pip install -r requirements-dev.txt
python -m harness.migrate ccc
python -m ccc.ingest                      # loads ccc/sample_assets.csv
uvicorn ccc.main:app --reload             # API on http://localhost:8000/docs
cd frontend && npm install && npm run dev # dashboard on http://localhost:5173
```
Development tokens: `dev-ciso-token`, `dev-auditor-token`, `dev-admin-token`, `dev-bizowner-token`.

## Run it in containers
```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.yml up --build    # then open http://localhost:8080
docker compose -f deploy/docker-compose.yml exec api python -m ccc.ingest
```

## Check it
```bash
python scripts/check_structure.py   # harness contract
ruff check .
python -m pytest -q                 # uses the app_test database and empties its tables
python -m harness.evals ccc
```

## Run the agent
```bash
python -m ccc.agents.asset_agent EA-000003     # mock model, offline, tools over MCP
```
A real model needs an approved model id (`ccc/DECISIONS.md` D-014):
`APP_LLM_PROVIDER=anthropic APP_LLM_MODEL=<approved id> ANTHROPIC_API_KEY=...`

## Working on it
Read `CLAUDE.md` (rules for every application), `ccc/CLAUDE.md` (Command Center rules) and
`ccc/DECISIONS.md` (open questions) first. Do not edit `harness/`; upgrades come from the template
with
`scripts/update_harness.sh https://github.com/venubhamidi/agent-harness.git <tag>`.
