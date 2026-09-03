-- =====================================================================
-- battery-data : 120_models.sql
--
-- Model parameter sets, always linked back to the data they were fitted
-- from. A parameter set with no traceable fit provenance is a number
-- someone typed.
--
-- BPX (Faraday Institution) is the only real standard here and covers
-- physics models only - DFN/SPM/SPMe. For EQUIVALENT CIRCUIT MODELS
-- there is no standard whatsoever: practice is NREL thevenin structs,
-- impedance.py circuit strings, and MATLAB/Simscape blobs. Defining a
-- clean versioned ECM schema with explicit fit provenance is an
-- unoccupied, low-cost win, and that is what ecm_* below is.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE model_kind AS ENUM (
  'bpx_dfn', 'bpx_spme', 'bpx_spm', 'bpx_partial',
  'dfn_parameter_set',        -- a published physics parameter set in a non-BPX format (PyBaMM dict)
  'ecm_rint', 'ecm_1rc', 'ecm_2rc', 'ecm_nrc', 'ecm_hysteresis',
  'empirical_degradation', 'semi_empirical_degradation',
  'thermal_lumped', 'thermal_2d', 'data_driven', 'other'
);

CREATE TABLE model_parameterisation (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,
  name              text NOT NULL,
  kind              model_kind NOT NULL,
  product_revision_id bigint REFERENCES product_revision(id),
  product_unit_id   bigint REFERENCES product_unit(id),

  -- For BPX kinds this holds the BPX JSON document verbatim, so the row
  -- round-trips through `pip install bpx` and pybamm.ParameterValues
  -- .create_from_bpx() without translation.
  payload           jsonb NOT NULL,
  format_name       text,             -- 'BPX'|'pybamm_dict'|'thevenin'|'native'
  format_version    text,

  -- fit provenance: which data, which protocol, which tool, how good
  fitted_from_run_ids   bigint[],
  fitted_from_dataset_ids bigint[],
  fit_tool          text,
  fit_tool_version  text,
  fit_objective     text,
  fit_rmse          double precision,
  fit_rmse_unit     text,
  validation_run_id bigint REFERENCES test_run(id),
  validation_rmse   double precision,

  temperature_range_c numrange,
  soc_range_pct     numrange,
  valid_c_rate_max  double precision,

  provenance_id     bigint NOT NULL REFERENCES provenance(id),
  access_tier       access_tier NOT NULL DEFAULT 'public',
  created_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT model_one_subject CHECK (
    num_nonnulls(product_revision_id, product_unit_id) >= 1
  )
);
CREATE INDEX ON model_parameterisation (kind);
CREATE INDEX ON model_parameterisation (product_revision_id);
CREATE INDEX ON model_parameterisation USING gin (payload jsonb_path_ops);

-- ---------------------------------------------------------------------
-- ECM parameters as a lookup surface over (SOC, temperature).
-- Every real ECM is a table, not a set of scalars, and flattening it to
-- scalars is the reason published ECM parameters are rarely reusable.
-- ---------------------------------------------------------------------
CREATE TABLE ecm_parameter_point (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id       bigint NOT NULL REFERENCES model_parameterisation(id) ON DELETE CASCADE,
  soc_pct        double precision NOT NULL,
  temperature_c  double precision NOT NULL,
  direction      text,               -- 'charge'|'discharge'|'symmetric'
  ocv_v          double precision,
  r0_ohm         double precision,
  -- RC branches as parallel arrays: r_ohm[i] pairs with c_farad[i]
  r_branch_ohm   double precision[],
  c_branch_farad double precision[],
  tau_branch_s   double precision[],
  hysteresis_v   double precision,
  entropic_v_k   double precision,
  -- the pulse duration this R was extracted at, because R is duration
  -- dependent and merging 2 s and 18 s resistances is meaningless
  pulse_duration_s double precision,
  pulse_current_a  double precision,
  CONSTRAINT ecm_branches_aligned CHECK (
    r_branch_ohm IS NULL OR c_branch_farad IS NULL
    OR cardinality(r_branch_ohm) = cardinality(c_branch_farad)
  ),
  UNIQUE (model_id, soc_pct, temperature_c, direction, pulse_duration_s)
);
CREATE INDEX ON ecm_parameter_point (model_id, soc_pct, temperature_c);

-- ---------------------------------------------------------------------
-- Degradation model coefficients (Arrhenius, sqrt-t, cycle-count terms).
-- ---------------------------------------------------------------------
CREATE TABLE degradation_model_term (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id       bigint NOT NULL REFERENCES model_parameterisation(id) ON DELETE CASCADE,
  term_name      text NOT NULL,      -- 'calendar_sqrt_t'|'cycle_linear'|'arrhenius_ea'
  coefficient    double precision NOT NULL,
  unit           text,
  std_error      double precision,
  applies_to     text,               -- 'capacity_fade'|'resistance_growth'
  UNIQUE (model_id, term_name, applies_to)
);
