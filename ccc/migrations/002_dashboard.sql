-- 002: Executive dashboard (PRD Module 1) sources. ARCHITECTURE.md "Executive dashboard".
-- Findings, patch status, control assessments, incidents and risks are loaded by connectors
-- (mock today). Every table carries the PRD §7 provenance fields. Nothing here is ever deleted;
-- a record missing from its source is marked data_quality_status = 'stale'.

DO $$ BEGIN
  CREATE TYPE finding_severity AS ENUM ('critical','high','medium','low','info');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TYPE finding_status AS ENUM ('open','closed','risk_accepted','false_positive');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  -- PRD Module 4: unknown, offline, exempt and non-applicable are distinct and never compliant.
  CREATE TYPE patch_state AS ENUM ('compliant','missing','failed','unknown','offline','exempt','non_applicable');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  -- PRD Module 5: the six control states.
  CREATE TYPE control_status AS ENUM ('implemented','partially_implemented','not_implemented',
                                      'not_applicable','not_assessed','evidence_pending');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TYPE incident_status AS ENUM ('open','closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TYPE data_quality AS ENUM ('ok','stale','incomplete');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE findings (
  id                  BIGSERIAL PRIMARY KEY,
  asset_id            BIGINT NOT NULL REFERENCES assets(id),
  source_system       TEXT NOT NULL,
  source_record_id    TEXT NOT NULL,
  cve                 TEXT,
  title               TEXT NOT NULL,
  severity            finding_severity NOT NULL,
  cvss                NUMERIC(3,1),
  exploitable         BOOLEAN,                       -- NULL = unknown
  known_exploited     BOOLEAN,                       -- NULL = unknown
  status              finding_status NOT NULL DEFAULT 'open',
  first_seen_at       TIMESTAMPTZ NOT NULL,
  last_seen_at        TIMESTAMPTZ NOT NULL,
  due_at              TIMESTAMPTZ,                   -- first_seen_at + SLA days (D-038), set by code
  closed_at           TIMESTAMPTZ,
  collected_at        TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  data_quality_status data_quality NOT NULL DEFAULT 'ok',
  UNIQUE (source_system, source_record_id)
);
CREATE INDEX idx_findings_asset ON findings (asset_id);
CREATE INDEX idx_findings_status_sev ON findings (status, severity);

CREATE TABLE patch_status (
  asset_id            BIGINT NOT NULL REFERENCES assets(id),
  source_system       TEXT NOT NULL,
  source_record_id    TEXT NOT NULL,
  state               patch_state NOT NULL,
  missing_count       INT NOT NULL DEFAULT 0,
  collected_at        TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  data_quality_status data_quality NOT NULL DEFAULT 'ok',
  PRIMARY KEY (asset_id, source_system)
);

CREATE TABLE control_assessments (
  id                  BIGSERIAL PRIMARY KEY,
  source_system       TEXT NOT NULL,
  source_record_id    TEXT NOT NULL,
  framework           TEXT NOT NULL,                 -- 'NIST SP 800-53 r5'
  control_id          TEXT NOT NULL,                 -- 'AC-2'
  title               TEXT NOT NULL,
  status              control_status NOT NULL,
  effectiveness       TEXT,                          -- states not yet decided (D-029); text until then
  assessor            TEXT,
  assessed_at         TIMESTAMPTZ,
  collected_at        TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  data_quality_status data_quality NOT NULL DEFAULT 'ok',
  UNIQUE (source_system, source_record_id)
);

CREATE TABLE incidents (
  id                  BIGSERIAL PRIMARY KEY,
  source_system       TEXT NOT NULL,
  source_record_id    TEXT NOT NULL,
  title               TEXT NOT NULL,
  severity            finding_severity NOT NULL,
  status              incident_status NOT NULL,
  opened_at           TIMESTAMPTZ NOT NULL,
  closed_at           TIMESTAMPTZ,
  collected_at        TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  data_quality_status data_quality NOT NULL DEFAULT 'ok',
  UNIQUE (source_system, source_record_id)
);

CREATE TABLE risks (
  id                  BIGSERIAL PRIMARY KEY,
  source_system       TEXT NOT NULL,
  source_record_id    TEXT NOT NULL,
  title               TEXT NOT NULL,
  business_unit       TEXT,
  business_service    TEXT,
  rating              asset_criticality NOT NULL,     -- critical/high/medium/low/unknown, one scale (D-030)
  business_impact     TEXT NOT NULL,
  owner               TEXT,
  recommended_action  TEXT NOT NULL,
  model_version       TEXT NOT NULL,                  -- PRD Module 6: explainable and version-controlled
  collected_at        TIMESTAMPTZ NOT NULL,
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  data_quality_status data_quality NOT NULL DEFAULT 'ok',
  UNIQUE (source_system, source_record_id)
);

CREATE TABLE risk_assets (
  risk_id   BIGINT NOT NULL REFERENCES risks(id),
  asset_id  BIGINT NOT NULL REFERENCES assets(id),
  PRIMARY KEY (risk_id, asset_id)
);

CREATE TABLE kpi_snapshots (
  kpi              TEXT NOT NULL,
  period_date      DATE NOT NULL,
  value            NUMERIC NOT NULL,
  formula_version  TEXT NOT NULL,
  source_systems   TEXT[] NOT NULL,
  computed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (kpi, period_date)
);
