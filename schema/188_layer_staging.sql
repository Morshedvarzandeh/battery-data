-- =====================================================================
-- battery-data : 188_layer_staging.sql
--
-- NAMES BEFORE FACTS. The world's cell, cathode and anode makers and
-- their factories are recalled here as candidates: a name, a country,
-- a role or a site kind, and the page to verify it against. No source,
-- no page, no quote, so nothing here may ever be accepted as it stands.
-- tools/verify_layer_candidates.py fetches the named page, finds the
-- name and writes a contribution with a real locator; only that file,
-- through tools/load_layers.py, reaches bd.*.
-- =====================================================================

SET search_path = bd_stage, bd, public;

CREATE TABLE bd_stage.layer_candidate (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id         bigint NOT NULL REFERENCES bd_stage.ingest_job(id) ON DELETE CASCADE,
  candidate_set  text NOT NULL,                   -- 'cell-makers', 'gigafactories'
  entity         text NOT NULL CHECK (entity IN ('company', 'site')),
  uid            text NOT NULL UNIQUE,
  name           text NOT NULL,
  country        text,
  kind           bd.site_kind,                    -- sites only
  roles          text[] NOT NULL DEFAULT '{}',    -- companies only
  operator_uid   text,                            -- sites only
  verify_at      text NOT NULL,
  confidence     text NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
  recalled_on    date NOT NULL,
  payload        jsonb NOT NULL,
  state          bd_stage.candidate_state NOT NULL DEFAULT 'queued',
  reviewed_by    bigint REFERENCES bd.contributor(id),
  reviewed_at    timestamptz,
  review_note    text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT candidate_carries_no_provenance CHECK (
    NOT (payload ? 'quote' OR payload ? 'page' OR payload ? 'locator' OR payload ? 'source')
  )
);
CREATE INDEX ON bd_stage.layer_candidate (candidate_set, entity);
CREATE INDEX ON bd_stage.layer_candidate (state);
CREATE INDEX ON bd_stage.layer_candidate (country);

-- The queue as the API serves it: one row per name, with the stage the
-- role or the site kind puts it on, and nothing that could be mistaken
-- for a verified fact.
CREATE VIEW bd_stage.v_layer_candidate AS
SELECT c.uid, c.entity, c.candidate_set, c.name, c.country,
       c.payload->>'region'   AS region,
       c.payload->>'locality' AS locality,
       c.kind::text           AS kind,
       CASE WHEN c.kind IS NOT NULL THEN ARRAY[bd.site_stage(c.kind)]
            ELSE bd.role_stages(c.roles) END               AS stages,
       c.roles, c.operator_uid,
       (SELECT array_agg(x) FROM jsonb_array_elements_text(COALESCE(c.payload->'makes', '[]')) x)       AS makes,
       (SELECT array_agg(x) FROM jsonb_array_elements_text(COALESCE(c.payload->'chemistries', '[]')) x) AS chemistries,
       c.payload->>'status'   AS status_recalled,
       c.payload->>'website'  AS website,
       c.verify_at, c.confidence, c.recalled_on, c.state::text AS state, c.review_note,
       EXISTS (SELECT 1 FROM bd.organization o WHERE o.uid = c.uid)
         OR EXISTS (SELECT 1 FROM bd.site s WHERE s.uid = c.uid)          AS in_library,
       c.id AS candidate_id
  FROM bd_stage.layer_candidate c;

COMMENT ON TABLE bd_stage.layer_candidate IS
  'Recalled names of companies and sites awaiting verification against a document. '
  'The CHECK refuses a payload that carries a quote, a page, a locator or a source: '
  'provenance is added by verification, never typed into a candidate.';
