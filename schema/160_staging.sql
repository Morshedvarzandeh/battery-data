-- =====================================================================
-- battery-data : 160_staging.sql
--
-- The ingestion staging area and human review queue.
--
-- Nothing an agent extracts lands in bd.* directly. It lands here, gets
-- validated mechanically, and is promoted only after review. That is not
-- bureaucracy: LLM extraction from datasheets and papers has a failure
-- mode where the output is fluent, plausible, and wrong, and the only
-- defence that scales is making every extracted value cheap to check
-- against a quoted snippet and a page number.
--
-- The review queue is also prioritised, because reviewer attention is
-- the scarce resource. High-impact and low-confidence items surface
-- first; a value that contradicts an existing one surfaces immediately.
-- =====================================================================

SET search_path = bd_stage, bd, public;

CREATE TYPE bd_stage.candidate_state AS ENUM (
  'new', 'validating', 'valid', 'invalid', 'queued',
  'accepted', 'rejected', 'merged', 'duplicate'
);

-- ---------------------------------------------------------------------
-- One row per unit of work an agent picked up.
-- ---------------------------------------------------------------------
CREATE TABLE bd_stage.ingest_job (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,
  agent_run_id   bigint REFERENCES bd.agent_run(id),
  input_kind     text NOT NULL,     -- 'datasheet_pdf'|'paper'|'dataset_archive'|'cycler_file'|'contrib_yaml'
  input_uri      text,
  input_sha256   text,
  source_id      bigint REFERENCES bd.source(id),
  state          text NOT NULL DEFAULT 'new',
  error          text,
  stats          jsonb NOT NULL DEFAULT '{}',
  started_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz
);
CREATE INDEX ON bd_stage.ingest_job (state);
CREATE UNIQUE INDEX ON bd_stage.ingest_job (input_sha256)
  WHERE input_sha256 IS NOT NULL;   -- never process the same bytes twice

-- ---------------------------------------------------------------------
-- Candidate records: the agent's proposed rows, before promotion.
-- Stored as jsonb rather than shadow tables so the extractor can evolve
-- without a migration, and so a rejected candidate stays inspectable.
-- ---------------------------------------------------------------------
CREATE TABLE bd_stage.candidate (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id         bigint NOT NULL REFERENCES bd_stage.ingest_job(id) ON DELETE CASCADE,
  target_table   text NOT NULL,     -- 'observation'|'curve'|'product'|'test_run'|...
  payload        jsonb NOT NULL,
  -- what the agent thinks it found, denormalised for triage
  product_hint   text,
  quantity_code  text,
  value_native   double precision,
  unit_native    text,
  condition_json jsonb,

  -- the evidence, mandatory. A candidate with no quote and no locator is
  -- rejected mechanically before a human ever sees it.
  page           int,
  section        text,
  quote          text,
  bbox           numeric[],

  confidence     numeric(4,3),
  state          bd_stage.candidate_state NOT NULL DEFAULT 'new',
  validation     jsonb NOT NULL DEFAULT '{}',   -- {errors:[], warnings:[]}
  -- set when this candidate disagrees with something already accepted
  conflicts_with bigint[],
  promoted_id    bigint,                        -- id in the target bd.* table
  reviewed_by    bigint REFERENCES bd.contributor(id),
  reviewed_at    timestamptz,
  review_note    text,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON bd_stage.candidate (job_id);
CREATE INDEX ON bd_stage.candidate (state);
CREATE INDEX ON bd_stage.candidate (quantity_code);
CREATE INDEX ON bd_stage.candidate USING gin (payload jsonb_path_ops);

-- ---------------------------------------------------------------------
-- Mechanical validation. Runs before any human sees the row.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd_stage.validate_candidate(p_id bigint)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
  c        bd_stage.candidate%ROWTYPE;
  q        bd.quantity%ROWTYPE;
  errs     text[] := '{}';
  warns    text[] := '{}';
  k        text;
  si       double precision;
BEGIN
  SELECT * INTO c FROM bd_stage.candidate WHERE id = p_id;
  IF NOT FOUND THEN RETURN jsonb_build_object('errors', ARRAY['no such candidate']); END IF;

  -- 1. evidence is not optional
  IF c.quote IS NULL AND c.page IS NULL AND c.section IS NULL THEN
    errs := errs || 'no locator: needs at least one of quote, page, section';
  END IF;

  -- 2. the quantity must exist
  IF c.quantity_code IS NOT NULL THEN
    SELECT * INTO q FROM bd.quantity WHERE code = c.quantity_code;
    IF NOT FOUND THEN
      errs := errs || format('unknown quantity "%s"', c.quantity_code);
    ELSE
      -- 3. required conditions must be present
      FOREACH k IN ARRAY q.required_conditions LOOP
        IF c.condition_json IS NULL OR c.condition_json->>k IS NULL THEN
          errs := errs || format('missing required condition "%s" for %s', k, q.code);
        END IF;
      END LOOP;

      -- 4. the unit must be convertible to the quantity's SI unit
      IF c.unit_native IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM bd.unit u WHERE u.symbol = c.unit_native) THEN
          errs := errs || format('unknown unit "%s"', c.unit_native);
        ELSE
          si := bd.to_si(c.value_native, c.unit_native);
          -- 5. physical plausibility. Catches unit-scale errors, which are
          -- the single most common LLM extraction failure (mAh read as Ah).
          IF q.code = 'capacity' AND (si < 3.6 OR si > 3600000) THEN
            warns := warns || format('capacity %s %s = %s C looks out of range',
                                     c.value_native, c.unit_native, si);
          END IF;
          IF q.code IN ('internal_resistance_ac','internal_resistance_dc')
             AND (si <= 0 OR si > 100) THEN
            warns := warns || 'resistance outside 0-100 ohm';
          END IF;
          IF q.code = 'nominal_voltage' AND (si < 0.5 OR si > 1500) THEN
            warns := warns || 'nominal voltage outside 0.5-1500 V';
          END IF;
        END IF;
      END IF;
    END IF;
  END IF;

  -- 6. confidence floor
  IF c.confidence IS NOT NULL AND c.confidence < 0.5 THEN
    warns := warns || 'low extraction confidence';
  END IF;

  UPDATE bd_stage.candidate
     SET validation = jsonb_build_object('errors', errs, 'warnings', warns),
         state = CASE WHEN cardinality(errs) > 0 THEN 'invalid'::bd_stage.candidate_state
                      ELSE 'valid'::bd_stage.candidate_state END
   WHERE id = p_id;

  RETURN jsonb_build_object('errors', errs, 'warnings', warns);
END$$;

-- ---------------------------------------------------------------------
-- Prioritised review queue. Reviewer attention is the bottleneck, so
-- order by expected value of the review, not by arrival time.
-- ---------------------------------------------------------------------
CREATE VIEW bd_stage.review_queue AS
SELECT c.id,
       c.job_id,
       j.input_kind,
       c.product_hint,
       c.quantity_code,
       c.value_native,
       c.unit_native,
       c.condition_json,
       c.page, c.section, c.quote,
       c.confidence,
       c.validation,
       cardinality(COALESCE(c.conflicts_with,'{}')) AS n_conflicts,
       -- priority: conflicts first, then warnings, then low confidence,
       -- then quantities we have little coverage of
       (CASE WHEN cardinality(COALESCE(c.conflicts_with,'{}')) > 0 THEN 100 ELSE 0 END
      + CASE WHEN jsonb_array_length(COALESCE(c.validation->'warnings','[]'::jsonb)) > 0
             THEN 40 ELSE 0 END
      + CASE WHEN c.confidence < 0.75 THEN 30 ELSE 0 END
      + CASE WHEN NOT EXISTS (
               SELECT 1 FROM bd.observation o
                 JOIN bd.quantity qq ON qq.id=o.quantity_id
                WHERE qq.code = c.quantity_code) THEN 20 ELSE 0 END
       ) AS priority
  FROM bd_stage.candidate c
  JOIN bd_stage.ingest_job j ON j.id = c.job_id
 WHERE c.state IN ('valid','queued')
 ORDER BY priority DESC, c.confidence ASC NULLS FIRST, c.id;

-- ---------------------------------------------------------------------
-- Conflict detection against already-accepted data. Run after validation.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd_stage.detect_conflicts(p_id bigint)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
  c      bd_stage.candidate%ROWTYPE;
  hits   bigint[];
  si     double precision;
BEGIN
  SELECT * INTO c FROM bd_stage.candidate WHERE id = p_id;
  IF c.quantity_code IS NULL OR c.value_native IS NULL THEN RETURN 0; END IF;
  si := bd.to_si(c.value_native, c.unit_native);

  SELECT array_agg(o.id) INTO hits
    FROM bd.observation o
    JOIN bd.quantity q ON q.id = o.quantity_id AND q.code = c.quantity_code
    JOIN bd.product_revision pr ON pr.id = o.product_revision_id
    JOIN bd.product p ON p.id = pr.product_id
   WHERE p.uid = c.product_hint
     AND o.value_si IS NOT NULL
     AND abs(o.value_si - si) / NULLIF(GREATEST(abs(o.value_si), abs(si)),0) > 0.02;

  UPDATE bd_stage.candidate SET conflicts_with = hits WHERE id = p_id;
  RETURN cardinality(COALESCE(hits,'{}'));
END$$;

-- ---------------------------------------------------------------------
-- Reviewer decisions, kept as an append-only log so that extraction
-- quality is measurable per agent version.
-- ---------------------------------------------------------------------
CREATE TABLE bd_stage.review_action (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  candidate_id  bigint NOT NULL REFERENCES bd_stage.candidate(id) ON DELETE CASCADE,
  reviewer_id   bigint REFERENCES bd.contributor(id),
  action        text NOT NULL,        -- 'accept'|'reject'|'correct'|'defer'
  corrected     jsonb,                -- the reviewer's edited payload
  reason        text,
  acted_at      timestamptz NOT NULL DEFAULT now()
);

-- Agent accuracy scoreboard. If a prompt revision makes extraction worse,
-- this is where it shows up.
CREATE VIEW bd_stage.agent_accuracy AS
SELECT ar.agent_name,
       ar.agent_version,
       ar.model_id,
       count(*)                                                    AS n_reviewed,
       count(*) FILTER (WHERE ra.action = 'accept')                AS n_accepted,
       count(*) FILTER (WHERE ra.action = 'correct')               AS n_corrected,
       count(*) FILTER (WHERE ra.action = 'reject')                AS n_rejected,
       round(100.0 * count(*) FILTER (WHERE ra.action='accept')
             / NULLIF(count(*),0), 1)                              AS accept_pct,
       avg(c.confidence) FILTER (WHERE ra.action='accept')         AS mean_conf_accepted,
       avg(c.confidence) FILTER (WHERE ra.action='reject')         AS mean_conf_rejected
  FROM bd_stage.review_action ra
  JOIN bd_stage.candidate c ON c.id = ra.candidate_id
  JOIN bd_stage.ingest_job j ON j.id = c.job_id
  JOIN bd.agent_run ar ON ar.id = j.agent_run_id
 GROUP BY ar.agent_name, ar.agent_version, ar.model_id;

COMMENT ON VIEW bd_stage.agent_accuracy IS
  'Calibration check. If mean_conf_rejected is close to mean_conf_accepted, '
  'the extractor confidence signal is not informative and the review '
  'prioritisation is running blind.';
