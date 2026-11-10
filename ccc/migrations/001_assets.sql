-- Cyber Command Center: asset domain schema (walking skeleton). Harness tables live in harness/migrations.
-- Source: PRD v1.0 §4 Module 2 (asset fields), §7 (tables), §9 (agent contract), Module 8 (usage)
-- Rule: schema is deliberately broader than the skeleton's features. Asset types for
-- cloud, identity and OT exist from day one even with zero rows (PRD §3 "Important").


-- ---------- Enumerations ----------
-- PRD Module 2 asset categories: IT, Cloud, OT (placeholders maintained manually at first)
DO $$ BEGIN
  CREATE TYPE asset_type AS ENUM (
    -- IT
    'endpoint','server','application','database','network_device','cloud_resource','saas','identity',
    -- Cloud
    'gcp_project','compute_instance','storage','kubernetes_cluster','container','service_account',
    -- OT placeholders
    'plc','hmi','scada','industrial_pc','robotics','mes','production_network','iiot'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE asset_criticality AS ENUM ('critical','high','medium','low','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE asset_environment AS ENUM ('production','staging','development','test','dr','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- PRD Module 2: "An asset must not be automatically deleted because it disappears from one
-- source. It should instead be marked as potentially inactive until verified."
DO $$ BEGIN
  CREATE TYPE asset_lifecycle AS ENUM ('active','potentially_inactive','retired','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------- Assets ----------
CREATE TABLE assets (
  id                  BIGSERIAL PRIMARY KEY,
  enterprise_asset_id TEXT NOT NULL UNIQUE,              -- PRD: required
  hostname            TEXT,                              -- where applicable
  ip_address          INET,                              -- where applicable
  mac_address         MACADDR,                           -- where applicable
  asset_type          asset_type NOT NULL,
  asset_owner         TEXT,                              -- NULL = "asset without owner" (PRD func. req. 6)
  business_unit       TEXT,
  business_service    TEXT,
  criticality         asset_criticality NOT NULL DEFAULT 'unknown',  -- 'unknown' = "asset without criticality" (req. 7)
  location            TEXT,
  environment         asset_environment NOT NULL DEFAULT 'unknown',
  operating_system    TEXT,
  lifecycle_state     asset_lifecycle NOT NULL DEFAULT 'active',
  first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_assets_hostname ON assets (lower(hostname));
CREATE INDEX idx_assets_ip ON assets (ip_address);
CREATE INDEX idx_assets_bu ON assets (business_unit);

-- Which source systems have reported this asset, and when. Supports correlation (req. 3),
-- duplicate detection (req. 4) and the potentially-inactive rule.
CREATE TABLE asset_sources (
  asset_id       BIGINT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  source_system  TEXT NOT NULL,        -- e.g. 'asset_db_csv', 'sccm', 'intune', 'defender', 'gcp'
  source_record_id TEXT NOT NULL,
  first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (asset_id, source_system)
);

-- PRD req. 10: maintain asset history (append-only)
CREATE TABLE asset_history (
  id          BIGSERIAL PRIMARY KEY,
  asset_id    BIGINT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  changed_by  TEXT NOT NULL,           -- user id, service identity or agent id
  field       TEXT NOT NULL,
  old_value   TEXT,
  new_value   TEXT
);

