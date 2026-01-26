-- AI/vox-brain-v2/create_symbols_v2_table.sql
-- Migration: create symbols_v2 table for VOX Brain v2
-- NOTE: This script creates a fresh table (symbols_v2) with NOT NULL project_id
-- and a UNIQUE index to prevent duplicate symbol entries for the same location.
--
-- IMPORTANT:
-- 1) BACKUP your DB before running this:
--    PGPASSWORD=$SQL_PASSWORD pg_dump -Fc -h $SQL_HOST -U $SQL_USER -d $SQL_DATABASE -f /tmp/tamga_local_pre_migration.dump
-- 2) Ensure your embedding model dimension matches the vector column dimension below.
--    If your embeddings are D-dimensional, set `embedding vector(D)` accordingly.
--    (The project historically used 768; if you use a 384-dim model, change `vector(768)` -> `vector(384)`.)
--
-- Usage:
--    PGPASSWORD=... psql -h $SQL_HOST -U $SQL_USER -d $SQL_DATABASE -f create_symbols_v2_table.sql

BEGIN;

-- Ensure extension exists
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the fresh v2 table
CREATE TABLE IF NOT EXISTS symbols_v2 (
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

-- Vector index for efficient nearest-neighbour (pgvector / ivfflat)
-- Note: ivfflat requires additional tuning (lists parameter) for large tables.
CREATE INDEX IF NOT EXISTS symbols_v2_embedding_idx
    ON symbols_v2 USING ivfflat (embedding vector_cosine_ops);

-- Useful secondary indexes
CREATE INDEX IF NOT EXISTS symbols_v2_name_idx ON symbols_v2 (name);
CREATE INDEX IF NOT EXISTS symbols_v2_project_id_idx ON symbols_v2 (project_id);

-- Prevent duplicate symbol entries for the same project/file/location
CREATE UNIQUE INDEX IF NOT EXISTS symbols_v2_unique_idx
    ON symbols_v2 (project_id, file_path, start_line, end_line);

COMMIT;

-- Quick verification examples (run after migration / indexing):
-- 1) Confirm the table exists and has the right columns:
--    PGPASSWORD=... psql -h $SQL_HOST -U $SQL_USER -d $SQL_DATABASE -c "\d+ symbols_v2"
--
-- 2) After a test reindex of one project:
--    PGPASSWORD=... psql -h ... -U ... -d ... -c "SELECT project_id, COUNT(*) FROM symbols_v2 GROUP BY project_id ORDER BY COUNT DESC;"
--
-- 3) Sample row check:
--    PGPASSWORD=... psql -h ... -U ... -d ... -c "SELECT * FROM symbols_v2 WHERE project_id = '<your-id>' LIMIT 5;"
