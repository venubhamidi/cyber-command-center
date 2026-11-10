#!/usr/bin/env bash
# Create the local development and test databases (PostgreSQL must be running; run as a user
# allowed to create roles, e.g.  sudo -u postgres scripts/dev_db.sh).
set -euo pipefail
psql -v ON_ERROR_STOP=1 <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN CREATE ROLE app LOGIN PASSWORD 'app'; END IF;
END $$;
SQL
for db in app app_test; do
  psql -tc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 || psql -c "CREATE DATABASE $db OWNER app"
done
echo "databases ready: app (development), app_test (tests)"
