#!/usr/bin/env sh
set -euo pipefail

# Simple helper: create the symbols_v2 table (with NOT NULL project_id),
# attempt to copy data from old `symbols` table (if present), and add indexes.
#
# Usage:
#   export PGPASSWORD=your_db_password
#   SQL_DATABASE=... SQL_USER=... SQL_HOST=... SQL_PORT=... ./create_symbols_v2_table.sh
#
# NOTE: This script will FAIL if the source data contains NULL project_id values.
#       Back up your DB before running.

DB="${SQL_DATABASE:-tamga_local}"
USER="${SQL_USER:-tamga_user}"
HOST="${SQL_HOST:-localhost}"
PORT="${SQL_PORT:-5432}"

if [ -z "${PGPASSWORD:-}" ]; then
  echo "Please set PGPASSWORD and re-run. Example: export PGPASSWORD=your_pass"
  exit 1
fi

PSQL="psql -h $HOST -p $PORT -U $USER -d $DB -v ON_ERROR_STOP=1 --no-align --tuples-only -q"

# quick check: existing table?
existing=$($PSQL -c "SELECT to_regclass('public.symbols_v2');")
if [ "$existing" = "symbols_v2" ]; then
  echo "symbols_v2 already exists. Exiting."
  exit 0
fi

echo "Creating symbols_v2 (this will attempt to copy existing data from 'symbols' if present)..."

$PSQL <<'SQL'
BEGIN;
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the new table with NOT NULL constraint on project_id
CREATE TABLE symbols_v2 (
    id SERIAL PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    code TEXT NOT NULL,
    docstring TEXT,
    parent_name TEXT,
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- If old table exists, try to copy rows. This will fail if project_id is NULL in any row.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'symbols') THEN
    EXECUTE 'INSERT INTO symbols_v2 (project_id, name, symbol_type, file_path, start_line, end_line, code, docstring, parent_name, embedding, created_at) SELECT project_id, name, symbol_type, file_path, start_line, end_line, code, docstring, parent_name, embedding, created_at FROM symbols';
  END IF;
END$$;

-- Indexes (ivfflat for pgvector; may require tuning for large tables)
CREATE INDEX IF NOT EXISTS symbols_v2_embedding_idx ON symbols_v2 USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS symbols_v2_name_idx ON symbols_v2 (name);
CREATE INDEX IF NOT EXISTS symbols_v2_project_id_idx ON symbols_v2 (project_id);

-- Add uniqueness to avoid future duplicates (project+location)
CREATE UNIQUE INDEX IF NOT EXISTS symbols_v2_unique_idx ON symbols_v2 (project_id, file_path, start_line, end_line);

COMMIT;
SQL

echo "Checking for NULL project_id rows (should be 0):"
nulls=$($PSQL -c "SELECT COUNT(*) FROM symbols_v2 WHERE project_id IS NULL;" | tr -d '[:space:]')
if [ -n "$nulls" ] && [ "$nulls" -ne 0 ]; then
  echo "WARNING: $nulls rows have NULL project_id in symbols_v2. You should inspect and/or reindex those projects."
  exit 1
fi

echo "symbols_v2 created and indexed successfully (if copying succeeded)."
echo "Next step: reindex projects you want to populate into symbols_v2, e.g.:"
echo "  vox sync-v2 <project_id>   # do one project first (e.g. the frontend project you mentioned)"
echo "Verify data via psql queries, then optionally drop/rename the old table if everything looks good."
