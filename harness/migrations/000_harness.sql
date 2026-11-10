-- Harness tables: domain-neutral. Every application built on the harness gets these.

-- Every API call and every agent tool call, including denied ones. Rows are hash-chained:
-- each row's hash covers its content and the previous row's hash, so editing or deleting a
-- row in the middle is detectable (harness.audit.verify_audit_chain).
CREATE TABLE audit_log (
  id           BIGSERIAL PRIMARY KEY,
  occurred_at  TIMESTAMPTZ NOT NULL,
  principal    TEXT NOT NULL,
  role         TEXT,
  action       TEXT NOT NULL,
  resource     TEXT,
  status_code  INT,
  request_id   TEXT,
  detail       JSONB,
  prev_hash    TEXT,
  row_hash     TEXT NOT NULL
);

CREATE TABLE agent_definitions (
  agent_id     TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  version      TEXT NOT NULL,
  description  TEXT,
  enabled      BOOLEAN NOT NULL DEFAULT true,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_executions (
  execution_id  UUID PRIMARY KEY,
  agent_id      TEXT NOT NULL REFERENCES agent_definitions(agent_id),
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  status        TEXT NOT NULL CHECK (status IN ('running','succeeded','failed')),
  requested_by  TEXT NOT NULL,
  input         JSONB,
  output        JSONB,
  error         TEXT,
  tool_calls    INT NOT NULL DEFAULT 0,
  llm_calls     INT NOT NULL DEFAULT 0,
  retries       INT NOT NULL DEFAULT 0,
  guardrail_events JSONB NOT NULL DEFAULT '[]',
  latency_ms    INT
);

-- Token and cost accounting per model call. cost_usd NULL = price unknown, never guessed.
-- Holds no prompt or response text.
CREATE TABLE model_usage (
  id             BIGSERIAL PRIMARY KEY,
  execution_id   UUID REFERENCES agent_executions(execution_id) ON DELETE SET NULL,
  agent_id       TEXT REFERENCES agent_definitions(agent_id),
  provider       TEXT NOT NULL,
  model_id       TEXT NOT NULL,
  input_tokens   INT NOT NULL,
  output_tokens  INT NOT NULL,
  cache_read_tokens INT NOT NULL DEFAULT 0,
  cost_usd       NUMERIC(12,6),
  latency_ms     INT,
  recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent evaluation history, so models, prompts and versions can be compared over time.
CREATE TABLE eval_runs (
  run_id        UUID PRIMARY KEY,
  agent_id      TEXT NOT NULL,
  agent_version TEXT NOT NULL,
  provider      TEXT NOT NULL,
  model_id      TEXT NOT NULL,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  total         INT NOT NULL,
  passed        INT NOT NULL,
  score         NUMERIC(5,4) NOT NULL,
  total_tokens  INT NOT NULL DEFAULT 0
);

CREATE TABLE eval_results (
  run_id      UUID NOT NULL REFERENCES eval_runs(run_id) ON DELETE CASCADE,
  case_id     TEXT NOT NULL,
  passed      BOOLEAN NOT NULL,
  failures    JSONB NOT NULL DEFAULT '[]',
  latency_ms  INT,
  PRIMARY KEY (run_id, case_id)
);
