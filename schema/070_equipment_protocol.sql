-- =====================================================================
-- battery-data : 070_equipment_protocol.sql
--
-- Two things that every public dataset loses:
--
-- 1. THE PROTOCOL FILE. The Battery Data Genome names protocol
--    translation as the field's top unsolved problem. Cycler schedules
--    (.sdx, Maccor procedures, Neware step XML, BioLogic .mps) are
--    universally discarded at publication. Here the verbatim blob is
--    stored alongside a parsed step table and a hash.
--
-- 2. SENSOR IDENTITY. "Aux_Temperature_1", "LogTemp001" and "EVTemp"
--    are free text carrying no location semantics. A thermocouple on the
--    tab and one on the can centre read differently by tens of kelvin.
--    Here a sensor is a first-class entity that aux columns bind to.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Instruments and channels
-- ---------------------------------------------------------------------
CREATE TABLE instrument (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,
  kind           text NOT NULL,        -- cycler|potentiostat|calorimeter|arc|chamber|lvdt|ir_camera|gc
  manufacturer   text,
  model          text,
  serial_number  text,
  firmware       text,
  software       text,
  owner_org_id   bigint REFERENCES organization(id),
  notes          text
);

CREATE TABLE instrument_channel (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  instrument_id       bigint NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
  channel_label       text NOT NULL,
  -- Accuracy is quoted as a percentage of RANGE, so the configured range
  -- determines the actual resolution. Without it, an accuracy claim is
  -- not usable and high-precision coulometry is not assessable.
  current_range_a     double precision,
  voltage_range_v     double precision,
  current_accuracy_pct_fs double precision,
  voltage_accuracy_pct_fs double precision,
  current_resolution_a    double precision,
  voltage_resolution_v    double precision,
  timebase_stability_ppm  double precision,
  sensing             text,             -- '2_wire'|'4_wire_kelvin'
  fixture_resistance_ohm  double precision,
  last_calibration    date,
  UNIQUE (instrument_id, channel_label)
);

-- ---------------------------------------------------------------------
-- Sensors. The largest silent information loss in published data.
-- ---------------------------------------------------------------------
CREATE TABLE sensor (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid             text NOT NULL UNIQUE,
  sensor_type     text NOT NULL,        -- thermocouple_k|thermocouple_t|rtd|lvdt|load_cell|strain_gauge|pressure|ir_camera
  quantity_id     bigint REFERENCES quantity(id),
  unit            text,
  -- WHERE on the object. This is the field whose absence makes a
  -- temperature trace uninterpretable.
  mount_location  text,                 -- 'can_surface_mid'|'positive_tab'|'chamber_air'|'coolant_inlet'
  mount_detail    text,
  accuracy        double precision,
  resolution      double precision,
  last_calibration date,
  instrument_id   bigint REFERENCES instrument(id),
  notes           text
);

-- ---------------------------------------------------------------------
-- PROTOCOL: first-class, versioned, hashable.
--
-- There is currently no identifier scheme anywhere in the field for
-- "IEC 62660-1:2018 clause 7.2 capacity test at 23 C, 1 It". This table
-- creates one, and gives it a stable uid other projects can cite.
-- ---------------------------------------------------------------------
CREATE TABLE protocol (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,     -- 'proto/iec-62660-1-2018/7.2/23c-1it'
  name              text NOT NULL,
  test_kind         test_kind NOT NULL,
  standard_id       bigint REFERENCES standard(id),
  standard_clause   text,                     -- '7.2', 'Annex C'
  application_class text,                     -- 'BEV'|'HEV'|'PHEV'|'ESS'|'portable'
  version           text NOT NULL DEFAULT '1',
  description       text,

  -- The nominal conditions the protocol prescribes. Actual achieved
  -- conditions live on the test_run; these are the intent.
  nominal_condition_set_id bigint REFERENCES condition_set(id),

  -- structured, kind-specific parameters (pulse ladders, SOC grids,
  -- frequency lists, storage matrices)
  parameters        jsonb NOT NULL DEFAULT '{}',

  -- the vendor schedule, verbatim. Never discarded.
  schedule_format   text,                     -- 'arbin_sdx'|'maccor_procedure'|'neware_xml'|'biologic_mps'
  schedule_blob     bytea,
  schedule_text     text,
  schedule_sha256   text,

  -- how RPTs interleave into an aging campaign
  rpt_interval_cycles int,
  rpt_interval_days   double precision,
  rpt_interval_throughput_ah double precision,
  rpt_protocol_id     bigint REFERENCES protocol(id),

  -- end-of-life definition, which is a protocol property and not a
  -- property of the cell. "80%" of nameplate and of measured BOL, at
  -- different rates and temperatures, are four different numbers.
  eol_criterion_pct   double precision,
  eol_reference       eol_reference NOT NULL DEFAULT 'unspecified',
  eol_measurement_rate_c double precision,
  eol_measurement_temp_c double precision,

  provenance_id     bigint REFERENCES provenance(id),
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON protocol (test_kind);
CREATE INDEX ON protocol (standard_id);
CREATE INDEX ON protocol USING gin (parameters jsonb_path_ops);

COMMENT ON COLUMN protocol.parameters IS
$$Kind-specific structure. Examples:
  hppc: {"pulse_durations_s":[0.1,2,10,18],"soc_grid_pct":[80,65,50,35,20],
         "discharge_relative_current":1.0,"regen_relative_current":0.75,
         "rest_between_s":3600,"currents_c":[0.2,1,5]}
  eis:  {"mode":"geis","f_max_hz":10000,"f_min_hz":0.01,"points_per_decade":6,
         "amplitude":5,"amplitude_unit":"mV","amplitude_kind":"rms",
         "soc_grid_pct":[0,20,40,60,80,100],"sweep":"high_to_low"}
  calendar_aging: {"soc_matrix_pct":[30,50,70,100],"temps_c":[25,45,60],
         "checkup_interval_days":30,"soc_maintained":false}
  drive_cycle: {"profile_asset_uid":"profile/wltp-class3-v2","control":"power",
         "scaling":"battery_size_factor","bsf":40}$$;

-- ---------------------------------------------------------------------
-- Parsed schedule steps. Derived from schedule_blob but queryable.
-- ---------------------------------------------------------------------
CREATE TABLE protocol_step (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  protocol_id    bigint NOT NULL REFERENCES protocol(id) ON DELETE CASCADE,
  step_number    int NOT NULL,
  label          text,
  mode           control_mode NOT NULL,
  setpoint_value double precision,
  setpoint_unit  text,
  -- termination is a list of OR-ed limits in every cycler's state machine
  limits         jsonb NOT NULL DEFAULT '[]',   -- [{"quantity":"voltage","op":">=","value":4.2,"unit":"V"}]
  goto_step      int,
  repeat_count   int,
  -- Logging configuration is not incidental. Documented case: logging
  -- config alone moved a measured pulse resistance from 36 to 28 mohm.
  log_interval_s double precision,
  log_delta_v    double precision,
  log_delta_i    double precision,
  log_delta_t    double precision,
  notes          text,
  UNIQUE (protocol_id, step_number)
);

-- ---------------------------------------------------------------------
-- Drive-cycle / duty-cycle profiles as versioned assets.
-- "WLTP" as a bare string is not reproducible: two labs' WLTP cell
-- current profiles differ by more than the aging signal they are
-- being used to measure.
-- ---------------------------------------------------------------------
CREATE TABLE duty_profile (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,      -- 'profile/usabc-dst-v1'
  name           text NOT NULL,
  version        text NOT NULL DEFAULT '1',
  standard_id    bigint REFERENCES standard(id),
  control_kind   text NOT NULL,             -- 'power'|'current'|'resistance'
  time_s         double precision[] NOT NULL,
  setpoint       double precision[] NOT NULL,
  setpoint_unit  text NOT NULL,
  repetition_s   double precision,
  scaling_note   text,                      -- how it was scaled to the DUT
  battery_size_factor double precision,
  vehicle_model  jsonb,
  sha256         text,
  provenance_id  bigint NOT NULL REFERENCES provenance(id),
  CONSTRAINT duty_profile_same_length CHECK (
    cardinality(time_s) = cardinality(setpoint)
  )
);
