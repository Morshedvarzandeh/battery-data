-- =====================================================================
-- battery-data : 000_extensions.sql
-- Extensions, schemas, and shared helper functions.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- gen_random_uuid, digest()
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- fuzzy manufacturer/model matching

-- Optional: Apache AGE for the in-database graph projection.
-- If AGE is unavailable, 900_graph_projection.sql falls back to
-- materialised node/edge views + an export to Neo4j / GraphML.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS age;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'Apache AGE not available - graph layer will use view fallback.';
END$$;

CREATE SCHEMA IF NOT EXISTS bd;        -- core relational model
CREATE SCHEMA IF NOT EXISTS bd_stage;  -- ingestion staging / review queue
CREATE SCHEMA IF NOT EXISTS bd_graph;  -- derived graph projection

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Canonical JSON hashing. Used to content-address condition_set rows and
-- source documents so that identical conditions dedupe automatically
-- instead of proliferating near-duplicate rows.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd.canonical_json(j jsonb)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  -- jsonb already normalises key order and whitespace; nulls are stripped
  -- so that an explicit NULL and an absent key hash identically.
  SELECT jsonb_strip_nulls(COALESCE(j, '{}'::jsonb))::text
$$;

CREATE OR REPLACE FUNCTION bd.json_hash(j jsonb)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT encode(digest(bd.canonical_json(j), 'sha256'), 'hex')
$$;

-- ---------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd.touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END$$;
