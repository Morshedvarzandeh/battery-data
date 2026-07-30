-- =====================================================================
-- battery-data : 090_timeseries.sql
--
-- Column names here are the Battery Data Format (BDF) machine names,
-- verbatim. BDF was published by the LF Energy Battery Data Alliance in
-- December 2025 and is the first credible cross-vendor time-series
-- standard, with a resolvable ontology IRI per column. Adopting its
-- names rather than inventing our own means every column in this table
-- gets an RDF predicate for free, and BDF files round-trip losslessly.
--
-- STORAGE STRATEGY
-- Raw cycling data is large and is usually queried as whole series, not
-- row-by-row. The default is therefore:
--   dataset      -> metadata + pointer to a Parquet/HDF5 object
--   timeseries_record -> optional in-database materialisation, partitioned
-- Both are supported. The original vendor file is ALWAYS archived with
-- its hash, because every normalisation step is a potential information
-- loss and the only defence is keeping the input.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE dataset_storage AS ENUM (
  'inline_table', 'parquet', 'hdf5', 'csv', 'bdf_csv', 'bdf_parquet',
  'vendor_native', 'external_url'
);

CREATE TABLE dataset (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,
  test_run_id       bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  test_segment_id   bigint REFERENCES test_segment(id) ON DELETE CASCADE,
  role              text NOT NULL DEFAULT 'raw',   -- raw|structured|summary|interpolated

  storage           dataset_storage NOT NULL,
  storage_uri       text,
  -- BDF filename convention: InstitutionCode__CellName__YYYYMMDD_XXX.csv
  file_name         text,
  media_type        text,
  byte_size         bigint,
  sha256            text,

  -- which BDF columns this dataset actually contains
  columns_present   text[] NOT NULL DEFAULT '{}',
  n_rows            bigint,
  sample_interval_s double precision,
  -- Sampling regime is per-step, not per-test: an HPPC run logs at
  -- 10-20 ms during pulses and far slower during rests. A single
  -- test-level sample rate is a lie for most interesting tests.
  sampling_note     text,

  t_start           timestamptz,
  t_end             timestamptz,

  -- the untouched vendor file, always kept
  original_file_uri text,
  original_sha256   text,
  original_format   text,

  provenance_id     bigint NOT NULL REFERENCES provenance(id),
  access_tier       access_tier NOT NULL DEFAULT 'public',
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON dataset (test_run_id);
CREATE INDEX ON dataset (sha256) WHERE sha256 IS NOT NULL;

-- ---------------------------------------------------------------------
-- STEP table. `step` is near-universal across cyclers and safe as a
-- first-class entity. `cycle` is NOT: it is vendor-defined, computed
-- differently by every tool, and frequently wrong. It is therefore
-- carried as two columns on the record - what the instrument said, and
-- what a named algorithm derived - rather than as a table.
-- ---------------------------------------------------------------------
CREATE TABLE timeseries_step (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  dataset_id         bigint NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
  step_count         int NOT NULL,          -- BDF: monotonic, never resets
  step_id            int,                   -- vendor step index
  step_type          text,                  -- 'CC_Chg'|'CC_DChg'|'Rest'|'CV_Chg'|'EIS'
  control_mode       control_mode,
  protocol_step_id   bigint REFERENCES protocol_step(id),
  start_test_time_s  double precision,
  end_test_time_s    double precision,
  duration_s         double precision,
  start_voltage_v    double precision,
  end_voltage_v      double precision,
  mean_current_a     double precision,
  charge_capacity_ah double precision,
  discharge_capacity_ah double precision,
  charge_energy_wh   double precision,
  discharge_energy_wh double precision,
  max_temperature_c  double precision,
  cycle_index_as_reported int,
  UNIQUE (dataset_id, step_count)
);
CREATE INDEX ON timeseries_step (dataset_id, step_type);

-- ---------------------------------------------------------------------
-- RECORD table, BDF-aligned, declaratively partitioned by dataset range.
-- Only populated when storage = 'inline_table'.
-- ---------------------------------------------------------------------
CREATE TABLE timeseries_record (
  dataset_id                  bigint NOT NULL,
  record_index                bigint NOT NULL,

  -- BDF required
  test_time_second            double precision NOT NULL,
  voltage_volt                double precision NOT NULL,
  current_ampere              double precision NOT NULL,

  -- BDF recommended
  unix_time_second            double precision,
  cycle_count                 int,
  step_count                  int,
  ambient_temperature_celsius double precision,

  -- BDF optional: cumulative and per-scope capacity/energy
  charging_capacity_ah        double precision,
  discharging_capacity_ah     double precision,
  net_capacity_ah             double precision,
  cumulative_capacity_ah      double precision,
  charging_energy_wh          double precision,
  discharging_energy_wh       double precision,
  net_energy_wh               double precision,
  cumulative_energy_wh        double precision,
  step_time_second            double precision,
  power_watt                  double precision,

  -- BDF optional: impedance columns (populated by cyclers with EIS opts)
  ac_internal_resistance_ohm  double precision,
  dc_internal_resistance_ohm  double precision,

  -- BDF optional: environment and multi-point temperature
  surface_temperature_celsius double precision,
  temperature_t1_celsius      double precision,
  temperature_t2_celsius      double precision,
  temperature_t3_celsius      double precision,
  temperature_t4_celsius      double precision,
  temperature_t5_celsius      double precision,
  ambient_pressure_pa         double precision,
  applied_pressure_pa         double precision,
  surface_pressure_pa         double precision,

  -- beyond BDF: three-electrode and mechanical instrumentation
  working_electrode_volt      double precision,   -- Ewe, cathode vs reference
  counter_electrode_volt      double precision,   -- Ece, anode vs reference
  displacement_um             double precision,
  force_newton                double precision,

  -- cycle bookkeeping, both flavours retained
  cycle_index_as_reported     int,
  cycle_index_derived         int,

  -- anything the vendor emitted that we have no column for. Never dropped.
  extra                       jsonb,

  PRIMARY KEY (dataset_id, record_index)
) PARTITION BY RANGE (dataset_id);

-- Partitions are created per dataset batch by tools/partition_manager.py.
-- A catch-all keeps small imports working out of the box.
CREATE TABLE timeseries_record_default PARTITION OF timeseries_record DEFAULT;

CREATE INDEX ON timeseries_record (dataset_id, test_time_second);
CREATE INDEX ON timeseries_record (dataset_id, cycle_count);

COMMENT ON TABLE timeseries_record IS
  'BDF-aligned raw records. Column names are Battery Data Format machine '
  'names so that each maps to an IRI under '
  'https://w3id.org/battery-data-alliance/ontology/battery-data-format#. '
  'Sign convention is governed by test_run.current_sign and is NOT assumed.';

-- ---------------------------------------------------------------------
-- Per-cycle summary. Kept as a real table rather than a view because
-- heterogeneous retention is normal: labs keep full raw for diagnostic
-- cycles and summary-only for the thousands of aging cycles between them.
-- ---------------------------------------------------------------------
CREATE TABLE cycle_summary (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  test_run_id           bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  test_segment_id       bigint REFERENCES test_segment(id) ON DELETE CASCADE,
  cycle_index           int NOT NULL,
  cycle_index_source    cycle_definition NOT NULL DEFAULT 'as_reported',
  cycle_type            text,             -- 'aging'|'rpt'|'hppc'|'reset'|'diagnostic'

  start_test_time_s     double precision,
  duration_s            double precision,
  charge_capacity_ah    double precision,
  discharge_capacity_ah double precision,
  charge_energy_wh      double precision,
  discharge_energy_wh   double precision,
  coulombic_efficiency  double precision,
  energy_efficiency     double precision,
  mean_discharge_voltage_v double precision,
  mean_charge_voltage_v double precision,
  v_max                 double precision,
  v_min                 double precision,
  dc_internal_resistance_ohm double precision,
  temperature_min_c     double precision,
  temperature_mean_c    double precision,
  temperature_max_c     double precision,
  throughput_ah         double precision,
  equivalent_full_cycles double precision,
  -- high-precision coulometry separates SEI growth from oxidation; these
  -- cannot be reconstructed from CE alone, so all three are stored.
  charge_endpoint_slippage_ah    double precision,
  discharge_endpoint_slippage_ah double precision,
  capacity_retention_pct double precision,
  UNIQUE (test_run_id, cycle_index, cycle_index_source)
);
CREATE INDEX ON cycle_summary (test_run_id, cycle_index);
CREATE INDEX ON cycle_summary (cycle_type);
