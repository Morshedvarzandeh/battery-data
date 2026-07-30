-- =====================================================================
-- battery-data : 080_test_execution.sql
--
-- THE FLOW.
--
--   campaign          a study, with an objective and a publication
--     -> test_run     one cell on one channel under one protocol
--          -> segment [aging, RPT, aging, RPT, ...]
--               -> dataset      raw time series (BDF-aligned)
--               -> eis_spectrum spectral, not time series
--               -> observation  derived scalars
--               -> curve        derived traces
--
-- The segment layer is the piece missing from every existing schema.
-- Essentially all aging data is structured as alternating aging blocks
-- and reference performance tests, and the constant confusion in the
-- literature about "is this the RPT capacity or the cycling capacity"
-- exists precisely because no schema distinguishes them.
--
-- The conventions block on test_run is not metadata. Current sign,
-- capacity accumulation and cycle counting disagree across vendors, and
-- the same column name carries the opposite meaning in two widely used
-- open formats. Recording the convention is what makes the numbers mean
-- anything at all.
-- =====================================================================

SET search_path = bd, public;

CREATE TABLE campaign (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,
  title          text NOT NULL,
  objective      test_kind,                -- primary purpose
  description    text,
  lab_org_id     bigint REFERENCES organization(id),
  source_id      bigint REFERENCES source(id),   -- the publication / dataset
  doi            text,
  started_on     date,
  ended_on       date,
  embargo_until  date,
  license        text,
  access_tier    access_tier NOT NULL DEFAULT 'public',
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- TEST_RUN
-- ---------------------------------------------------------------------
CREATE TABLE test_run (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,
  campaign_id       bigint REFERENCES campaign(id) ON DELETE SET NULL,
  product_unit_id   bigint NOT NULL REFERENCES product_unit(id),
  protocol_id       bigint REFERENCES protocol(id),
  test_kind         test_kind NOT NULL,

  instrument_id     bigint REFERENCES instrument(id),
  channel_id        bigint REFERENCES instrument_channel(id),
  chamber_id        bigint REFERENCES instrument(id),

  started_at        timestamptz,
  ended_at          timestamptz,
  operator_id       bigint REFERENCES contributor(id),

  -- achieved conditions, as distinct from the protocol's intent
  condition_set_id  bigint REFERENCES condition_set(id),

  -- =================================================================
  -- CONVENTIONS. Load-bearing. See docs/02-conventions.md.
  -- =================================================================
  current_sign      current_sign_convention NOT NULL DEFAULT 'charge_positive',
  capacity_accum    capacity_accumulation   NOT NULL DEFAULT 'unspecified',
  cycle_definition  cycle_definition        NOT NULL DEFAULT 'as_reported',
  cycle_algorithm_version text,
  -- The capacity that "1C" was taken to mean during this run. Nameplate
  -- and measured C1 routinely differ by more than 10%.
  c_rate_reference_capacity_ah double precision,
  c_rate_reference_source      text,
  dcir_extraction   dcir_extraction NOT NULL DEFAULT 'unspecified',
  soc_definition    soc_method NOT NULL DEFAULT 'unspecified',
  constraint_mode   mechanical_constraint NOT NULL DEFAULT 'unspecified',
  clamp_force_n     double precision,

  -- ingest provenance of the raw files
  source_format     text,             -- 'arbin_res'|'maccor_txt'|'neware_ndax'|'biologic_mpr'|'bdf_csv'
  source_encoding   text,
  parser_name       text,
  parser_version    text,

  quality_flags     text[] NOT NULL DEFAULT '{}',
  notes             text,
  provenance_id     bigint NOT NULL REFERENCES provenance(id),
  access_tier       access_tier NOT NULL DEFAULT 'public',
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON test_run (product_unit_id);
CREATE INDEX ON test_run (test_kind);
CREATE INDEX ON test_run (campaign_id);
CREATE INDEX ON test_run (protocol_id);

-- bind the sensors actually used on this run to their aux channel names
CREATE TABLE test_run_sensor (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  test_run_id    bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  sensor_id      bigint NOT NULL REFERENCES sensor(id),
  -- the raw column this sensor produced, e.g. 'Aux_Temperature_1',
  -- 'LogTemp001', 'temperature_t3_celsius'
  channel_column text NOT NULL,
  UNIQUE (test_run_id, channel_column)
);

-- ---------------------------------------------------------------------
-- SEGMENT: the RPT interleaving layer.
-- ---------------------------------------------------------------------
CREATE TABLE test_segment (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid              text NOT NULL UNIQUE,
  test_run_id      bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  sequence_index   int NOT NULL,
  role             segment_role NOT NULL,
  test_kind        test_kind,          -- what this segment actually is
  protocol_id      bigint REFERENCES protocol(id),

  started_at       timestamptz,
  ended_at         timestamptz,
  start_cycle      int,
  end_cycle        int,
  start_test_time_s double precision,
  end_test_time_s   double precision,

  condition_set_id bigint REFERENCES condition_set(id),

  -- ageing state at the START of this segment. Storing it here is what
  -- lets you plot capacity vs equivalent full cycles without recomputing
  -- from raw every time, and what distinguishes calendar time at the
  -- storage condition from total elapsed time (they differ by the
  -- checkups, and most datasets conflate them).
  cumulative_cycles          int,
  cumulative_throughput_ah   double precision,
  cumulative_equivalent_full_cycles double precision,
  calendar_days_at_condition double precision,
  total_elapsed_days         double precision,

  notes            text,
  UNIQUE (test_run_id, sequence_index)
);
CREATE INDEX ON test_segment (test_run_id, role);

-- resolve the circular FKs deferred from 060
ALTER TABLE observation
  ADD CONSTRAINT observation_test_run_fk
    FOREIGN KEY (test_run_id) REFERENCES test_run(id) ON DELETE CASCADE,
  ADD CONSTRAINT observation_test_segment_fk
    FOREIGN KEY (test_segment_id) REFERENCES test_segment(id) ON DELETE CASCADE;

ALTER TABLE curve
  ADD CONSTRAINT curve_test_run_fk
    FOREIGN KEY (test_run_id) REFERENCES test_run(id) ON DELETE CASCADE,
  ADD CONSTRAINT curve_test_segment_fk
    FOREIGN KEY (test_segment_id) REFERENCES test_segment(id) ON DELETE CASCADE;
