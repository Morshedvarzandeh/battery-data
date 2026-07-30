-- =====================================================================
-- battery-data : 110_abuse_postmortem.sql
--
-- Abuse tests produce an EVENT SEQUENCE plus a hazard rating, not a
-- scalar. The hazard scales themselves disagree (EUCAR 0-7 and SAE J2464
-- HSL 0-7 are similar but not identical, and some labs use proprietary
-- scales), so the scale name and version travel with every level.
--
-- Post-mortem data orphaned from the parent cell's cycling history is
-- nearly worthless, so the link to product_unit is mandatory and the
-- disassembly conditions - SOC at teardown, glovebox atmosphere, washing
-- protocol, coupon location - are first-class columns. Washing protocol
-- in particular is the least standardised step in the field and it
-- materially changes XPS/SEM/ICP results.
-- =====================================================================

SET search_path = bd, public;

CREATE TABLE abuse_result (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  test_run_id         bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,

  -- hazard rating, always with its scale
  hazard_scale        hazard_scale NOT NULL DEFAULT 'unspecified',
  hazard_scale_version text,
  hazard_level        int,
  outcome             text,          -- 'no_event'|'leakage'|'venting'|'smoke'|'fire'|'rupture'|'explosion'

  -- geometry / mechanics of the insult
  impactor_shape      text,
  impactor_diameter_mm double precision,
  impactor_radius_mm  double precision,
  crush_speed_mm_min  double precision,
  peak_force_n        double precision,
  displacement_at_peak_mm double precision,
  nail_diameter_mm    double precision,
  nail_material       text,
  penetration_speed_mm_s double precision,
  penetration_depth_mm double precision,
  penetration_location text,

  short_resistance_ohm double precision,
  overcharge_target_soc_pct double precision,
  compliance_voltage_v double precision,
  heating_rate_c_min  double precision,

  -- observed response
  t_max_c             double precision,
  time_to_runaway_s   double precision,
  mass_before_g       double precision,
  mass_after_g        double precision,
  mass_loss_pct       double precision,
  cells_propagated    int,
  propagation_duration_s double precision,

  video_uri           text,
  observations        text,
  provenance_id       bigint NOT NULL REFERENCES provenance(id)
);
CREATE INDEX ON abuse_result (test_run_id);

-- Timeline of discrete events during an abuse test.
CREATE TABLE abuse_event (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  abuse_result_id bigint NOT NULL REFERENCES abuse_result(id) ON DELETE CASCADE,
  t_s            double precision NOT NULL,
  event_type     text NOT NULL,     -- 'cid_trip'|'vent'|'first_smoke'|'ignition'|'peak_temp'|'rupture'
  temperature_c  double precision,
  voltage_v      double precision,
  pressure_pa    double precision,
  note           text
);

-- Vent gas. Normalise volume to STP and per Ah, because absolute litres
-- at an unstated chamber pressure are not comparable (published 18650
-- figures vary with collection pressure).
CREATE TABLE vent_gas_analysis (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  abuse_result_id     bigint NOT NULL REFERENCES abuse_result(id) ON DELETE CASCADE,
  chamber_volume_l    double precision,
  chamber_atmosphere  text,
  chamber_pressure_pa double precision,
  total_volume_l      double precision,
  total_volume_l_stp  double precision,
  volume_per_ah_l     double precision,
  total_moles         double precision,
  instruments         text[],        -- ['GC-TCD','GC-FID','NDIR','paramagnetic']
  lfl_pct             double precision,
  ufl_pct             double precision,
  provenance_id       bigint NOT NULL REFERENCES provenance(id)
);

CREATE TABLE vent_gas_species (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  analysis_id    bigint NOT NULL REFERENCES vent_gas_analysis(id) ON DELETE CASCADE,
  species        text NOT NULL,      -- 'H2','CO','CO2','CH4','C2H4','HF','POF3'
  vol_pct        double precision,
  moles          double precision,
  mass_g         double precision,
  detection_limit double precision,
  UNIQUE (analysis_id, species)
);

-- ---------------------------------------------------------------------
-- POST-MORTEM
-- ---------------------------------------------------------------------
CREATE TABLE teardown (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                 text NOT NULL UNIQUE,
  product_unit_id     bigint NOT NULL REFERENCES product_unit(id),
  -- the cycling history this teardown is the endpoint of
  parent_test_run_id  bigint REFERENCES test_run(id),

  disassembly_date    date,
  soc_at_disassembly_pct double precision,
  voltage_at_disassembly_v double precision,
  discharge_method    text,          -- 'cycler_to_cutoff'|'salt_water'|'resistor'
  glovebox_o2_ppm     double precision,
  glovebox_h2o_ppm    double precision,
  layer_count         int,
  jellyroll_length_mm double precision,
  electrode_width_mm  double precision,
  coated_area_cm2     double precision,
  area_kind           area_definition NOT NULL DEFAULT 'unspecified',
  lab_org_id          bigint REFERENCES organization(id),
  provenance_id       bigint NOT NULL REFERENCES provenance(id)
);

-- Degradation is spatially heterogeneous, so coupon position is data.
CREATE TABLE sample (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,
  teardown_id    bigint NOT NULL REFERENCES teardown(id) ON DELETE CASCADE,
  sample_kind    text NOT NULL,     -- 'cathode_coupon'|'anode_coupon'|'separator'|'electrolyte'
  layer_index    int,
  position_x_mm  double precision,
  position_y_mm  double precision,
  position_note  text,              -- 'inner_winding'|'edge'|'under_tab'
  punch_diameter_mm double precision,
  area_cm2       double precision,
  mass_mg        double precision,
  coating_thickness_um double precision,
  loading_mg_cm2 double precision,
  -- washing protocol: the least standardised and most consequential step
  wash_solvent   text,              -- 'DMC'|'DEC'|'EMC'|'none'
  wash_rinses    int,
  wash_duration_s double precision,
  dry_temperature_c double precision,
  dry_vacuum_pa  double precision,
  dry_duration_s double precision,
  provenance_id  bigint NOT NULL REFERENCES provenance(id)
);
CREATE INDEX ON sample (teardown_id);

-- close the deferred FK from 060
ALTER TABLE observation
  ADD CONSTRAINT observation_sample_fk
    FOREIGN KEY (sample_id) REFERENCES sample(id) ON DELETE CASCADE;

-- Reconstructed half/full cells built from harvested electrodes.
CREATE TABLE reconstructed_cell (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,
  sample_id         bigint NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
  configuration     text NOT NULL,   -- 'half_cell_vs_li'|'symmetric_anode'|'symmetric_cathode'|'full_cell'
  counter_electrode text,
  counter_thickness_um double precision,
  separator         text,
  electrolyte       text,
  electrolyte_volume_ul double precision,
  assembly_pressure_kpa double precision,
  rest_before_first_cycle_s double precision,
  cell_format       text,            -- 'CR2032'|'EL-CELL_PAT'|'pouch'
  provenance_id     bigint NOT NULL REFERENCES provenance(id)
);

-- Characterisation results keyed to a sample. The structured payload is
-- technique-specific; spectra and diffractograms go in `curve`.
CREATE TABLE characterisation (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sample_id      bigint NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
  technique      test_kind NOT NULL,       -- xrd|sem|eds|xps|icp|bet|nmr|gcms
  instrument_id  bigint REFERENCES instrument(id),
  conditions     jsonb NOT NULL DEFAULT '{}',   -- kV, WD, magnification, source, step size
  results        jsonb NOT NULL DEFAULT '{}',   -- lattice params, at%, phase fractions
  provenance_id  bigint NOT NULL REFERENCES provenance(id)
);
CREATE INDEX ON characterisation (sample_id, technique);

-- ---------------------------------------------------------------------
-- Degradation mode attribution (LLI / LAM), the output of DVA-ICA or
-- half-cell reconstruction. Interpretation, kept separate from the
-- measurement it is derived from.
-- ---------------------------------------------------------------------
CREATE TABLE degradation_mode (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  test_segment_id   bigint REFERENCES test_segment(id) ON DELETE CASCADE,
  teardown_id       bigint REFERENCES teardown(id) ON DELETE CASCADE,
  lli_pct           double precision,       -- loss of lithium inventory
  lam_pe_pct        double precision,       -- loss of active material, positive
  lam_ne_pct        double precision,       -- loss of active material, negative
  lam_pe_delithiated_pct double precision,
  lam_ne_delithiated_pct double precision,
  resistance_growth_pct double precision,
  method            text NOT NULL,          -- 'dva_peak_tracking'|'half_cell_fit'|'ica'
  method_version    text,
  fit_quality       double precision,
  provenance_id     bigint NOT NULL REFERENCES provenance(id),
  CONSTRAINT degradation_one_subject CHECK (
    num_nonnulls(test_segment_id, teardown_id) = 1
  )
);
