-- =====================================================================
-- battery-data : 100_spectral_thermal.sql
--
-- EIS is not a time series and must not be stored as one. It is a set of
-- complex impedance points indexed by frequency, taken at one state.
-- Everything downstream of it (equivalent-circuit fits, DRT) is an
-- interpretation with its own parameters, and an R_ct without its
-- circuit string is uninterpretable.
--
-- The thermal tables exist because thermal conductivity is a TENSOR
-- (through-plane and in-plane differ by ~50x on the same pouch cell) and
-- specific heat is SOC-dependent. A scalar "k" column is a
-- data-destroying schema choice.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- EIS
-- ---------------------------------------------------------------------
CREATE TABLE eis_spectrum (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                text NOT NULL UNIQUE,
  test_run_id        bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  test_segment_id    bigint REFERENCES test_segment(id) ON DELETE CASCADE,

  mode               eis_mode NOT NULL,
  amplitude_value    double precision,
  amplitude_unit     text,                -- mV for PEIS, mA for GEIS
  amplitude_kind     amplitude_type NOT NULL DEFAULT 'unspecified',
  f_max_hz           double precision,
  f_min_hz           double precision,
  points_per_decade  double precision,
  sweep_direction    text,                -- 'high_to_low'|'low_to_high'
  dc_bias_v          double precision,
  dc_bias_a          double precision,

  condition_set_id   bigint REFERENCES condition_set(id),

  -- connection quality dominates the high-frequency end
  sensing            text,                -- '4_wire_kelvin' strongly recommended
  cable_description  text,
  ir_compensation    boolean,

  -- Kramers-Kronig / Lin-KK validation is a quality gate, not a nicety
  kk_validated       boolean,
  kk_method          text,
  kk_max_residual    double precision,
  drift_flag         boolean,

  n_points           int,
  provenance_id      bigint NOT NULL REFERENCES provenance(id),
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON eis_spectrum (test_run_id);

CREATE TABLE eis_point (
  spectrum_id   bigint NOT NULL REFERENCES eis_spectrum(id) ON DELETE CASCADE,
  point_index   int NOT NULL,
  frequency_hz  double precision NOT NULL,
  z_real_ohm    double precision NOT NULL,
  z_imag_ohm    double precision NOT NULL,   -- sign convention: as measured, Im(Z)
  z_mag_ohm     double precision,
  z_phase_deg   double precision,
  ewe_v         double precision,
  current_a     double precision,
  temperature_c double precision,
  test_time_s   double precision,
  quality_nsd   double precision,
  PRIMARY KEY (spectrum_id, point_index)
);
CREATE INDEX ON eis_point (spectrum_id, frequency_hz);

-- Equivalent-circuit fit. The circuit string IS the schema for `params`.
CREATE TABLE eis_fit (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  spectrum_id    bigint NOT NULL REFERENCES eis_spectrum(id) ON DELETE CASCADE,
  circuit_string text NOT NULL,          -- 'L0-R0-p(R1,CPE1)-p(R2,CPE2)-Ws1'
  params         jsonb NOT NULL,         -- {"R0":0.0152,"R1":0.0071,...}
  param_errors   jsonb,
  chi_squared    double precision,
  fit_tool       text,                   -- 'impedance.py'|'ZView'|'EC-Lab'
  fit_tool_version text,
  weighting      text,
  provenance_id  bigint NOT NULL REFERENCES provenance(id),
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Distribution of relaxation times. Reproducible only with the full
-- regularisation recipe, so the recipe is mandatory alongside the result.
CREATE TABLE drt_result (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  spectrum_id       bigint NOT NULL REFERENCES eis_spectrum(id) ON DELETE CASCADE,
  tau_s             double precision[] NOT NULL,
  gamma             double precision[] NOT NULL,
  regularisation    text NOT NULL,       -- 'tikhonov_ridge'|'lasso'
  lambda_value      double precision NOT NULL,
  lambda_selection  text NOT NULL,       -- 'l_curve'|'gcv'|'re_im_cv'|'manual'
  discretisation    text,                -- 'piecewise_linear'|'rbf'
  rbf_type          text,
  rbf_shape_factor  double precision,
  re_im_weighting   double precision,
  bayesian_ci       boolean NOT NULL DEFAULT false,
  tool              text,                -- 'pyDRTtools'
  tool_version      text,
  provenance_id     bigint NOT NULL REFERENCES provenance(id),
  CONSTRAINT drt_same_length CHECK (cardinality(tau_s) = cardinality(gamma))
);

-- Peak assignment is interpretation, not data. Kept separate so that a
-- disputed assignment never contaminates the underlying spectrum.
CREATE TABLE drt_peak (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  drt_id        bigint NOT NULL REFERENCES drt_result(id) ON DELETE CASCADE,
  label         text NOT NULL,           -- 'P1','P2'
  tau_s         double precision,
  area          double precision,
  assigned_process text,                 -- 'SEI'|'charge_transfer_anode'|...
  confidence    numeric(4,3),
  provenance_id bigint NOT NULL REFERENCES provenance(id)
);

-- ---------------------------------------------------------------------
-- THERMAL
-- ---------------------------------------------------------------------
CREATE TABLE thermal_property (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id   bigint REFERENCES product_revision(id) ON DELETE CASCADE,
  product_unit_id       bigint REFERENCES product_unit(id) ON DELETE CASCADE,
  test_run_id           bigint REFERENCES test_run(id) ON DELETE CASCADE,

  -- anisotropy is the point of this table
  k_through_plane_w_mk  double precision,
  k_in_plane_x_w_mk     double precision,
  k_in_plane_y_w_mk     double precision,
  k_uncertainty_w_mk    double precision,

  specific_heat_j_kgk   double precision,
  heat_capacity_j_k     double precision,   -- total, cell as built
  mass_basis            text,               -- 'cell_with_tabs'|'jellyroll_only'|'with_casing'

  -- entropic coefficient: sign convention and units both vary in the wild
  entropic_coeff_v_k    double precision,
  entropic_method       text,               -- 'potentiometric'|'calorimetric'|'frequency_domain'
  entropic_sign_convention text,
  entropic_fit_r2       double precision,

  heat_transfer_coeff_w_m2k double precision,
  thermal_resistance_k_w    double precision,

  condition_set_id      bigint REFERENCES condition_set(id),
  method_note           text,
  boundary_conditions   jsonb,             -- required to reproduce inverse fits
  provenance_id         bigint NOT NULL REFERENCES provenance(id),
  CONSTRAINT thermal_one_subject CHECK (
    num_nonnulls(product_revision_id, product_unit_id, test_run_id) = 1
  )
);

-- ---------------------------------------------------------------------
-- ARC / thermal runaway
-- ---------------------------------------------------------------------
CREATE TABLE arc_result (
  id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  test_run_id            bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  heat_step_c            double precision,      -- typically 5
  wait_time_s            double precision,
  detection_threshold_c_min double precision,   -- 0.02 typical
  t_start_c              double precision,
  t_end_c                double precision,
  -- Without the thermal-inertia factor and holder mass, ARC results are
  -- not comparable between labs. Routinely omitted in the literature.
  phi_factor             double precision,
  holder_mass_g          double precision,
  thermocouple_location  text,

  t_onset_c              double precision,      -- T1, self-heating onset
  t_trigger_c            double precision,      -- T2, runaway trigger
  t_max_c                double precision,      -- T3, peak
  max_self_heating_rate_c_min double precision,
  peak_pressure_pa       double precision,
  mass_loss_g            double precision,
  gas_volume_mmol        double precision,
  provenance_id          bigint NOT NULL REFERENCES provenance(id)
);

CREATE TABLE calorimetry_result (
  id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  test_run_id          bigint NOT NULL REFERENCES test_run(id) ON DELETE CASCADE,
  instrument_id        bigint REFERENCES instrument(id),
  condition_set_id     bigint REFERENCES condition_set(id),
  heat_rate_w          double precision,
  total_heat_j         double precision,
  irreversible_heat_j  double precision,
  reversible_heat_j    double precision,
  derived_resistance_ohm double precision,      -- Q_irrev / I^2
  derived_entropic_v_k double precision,        -- Q_rev / (I*T)
  heat_flux_accuracy_w double precision,
  bath_stability_c     double precision,
  calibration_drift_pct double precision,
  provenance_id        bigint NOT NULL REFERENCES provenance(id)
);
