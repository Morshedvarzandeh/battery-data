-- =====================================================================
-- battery-data : 060_observation.sql
--
-- One table for every scalar fact in the database, whatever its subject
-- and whatever its origin. A manufacturer's claimed 1C capacity and a
-- lab's measured 1C capacity are the same shape of statement; they
-- differ in their evidence_class and their subject, not their structure.
--
-- That uniformity is what makes the killer query possible:
--   "every 21700 with >= 5 Ah at <= 1C and >= 15 A continuous"
-- becomes a join over one table instead of a union over forty.
--
-- Subject polymorphism is done with mutually exclusive nullable FKs
-- rather than a (type, id) pair, so referential integrity survives.
-- =====================================================================

SET search_path = bd, public;

CREATE TABLE observation (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- ---- subject: exactly one -------------------------------------
  product_revision_id bigint REFERENCES product_revision(id) ON DELETE CASCADE,
  product_unit_id     bigint REFERENCES product_unit(id)     ON DELETE CASCADE,
  test_run_id         bigint,   -- FK added in 080 (circular dependency)
  test_segment_id     bigint,   -- FK added in 080
  material_id         bigint REFERENCES material(id)         ON DELETE CASCADE,
  sample_id           bigint,   -- FK added in 110 (post-mortem coupons)

  -- ---- what ------------------------------------------------------
  quantity_id    bigint NOT NULL REFERENCES quantity(id),
  statistic      statistic_kind NOT NULL DEFAULT 'nominal',

  -- ---- value -----------------------------------------------------
  -- value_native is what the source literally said, in the source's own
  -- unit. value_si is the machine-comparable form. Both are kept: the
  -- native value is the auditable one, the SI value is the queryable one.
  value_native   double precision,
  unit_native    text NOT NULL,
  value_si       double precision,
  -- asymmetric tolerances are common ("+0.00 / -0.55 mm")
  tol_plus       double precision,
  tol_minus      double precision,
  value_min      double precision,     -- when the source states a range
  value_max      double precision,
  is_lower_bound boolean NOT NULL DEFAULT false,   -- ">= 280 Ah"
  is_upper_bound boolean NOT NULL DEFAULT false,   -- "<= 8 mohm"
  value_text     text,                 -- when genuinely non-numeric
  n_samples      int,
  std_dev        double precision,

  -- ---- under what conditions -------------------------------------
  condition_set_id bigint REFERENCES condition_set(id),

  -- ---- where it came from ----------------------------------------
  provenance_id  bigint NOT NULL REFERENCES provenance(id),

  -- ---- access control (EU passport tiering) ----------------------
  access_tier    access_tier NOT NULL DEFAULT 'public',

  created_at     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT observation_one_subject CHECK (
    num_nonnulls(product_revision_id, product_unit_id, test_run_id,
                 test_segment_id, material_id, sample_id) = 1
  ),
  CONSTRAINT observation_has_value CHECK (
    value_native IS NOT NULL OR value_text IS NOT NULL
    OR value_min IS NOT NULL OR value_max IS NOT NULL
  ),
  CONSTRAINT observation_bounds_exclusive CHECK (
    NOT (is_lower_bound AND is_upper_bound)
  )
);

CREATE INDEX ON observation (quantity_id, value_si);
CREATE INDEX ON observation (product_revision_id, quantity_id);
CREATE INDEX ON observation (test_run_id, quantity_id);
CREATE INDEX ON observation (condition_set_id);
CREATE INDEX ON observation (provenance_id);

-- ---------------------------------------------------------------------
-- SI normalisation and required-condition enforcement.
--
-- This trigger is the reason a bare "internal resistance = 15 mohm" can
-- never enter the database. quantity.required_conditions names the
-- condition columns without which the quantity is uninterpretable, and
-- the insert fails if they are absent.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd.validate_observation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_required text[];
  v_code     text;
  v_cond     jsonb;
  v_missing  text[] := '{}';
  k          text;
BEGIN
  SELECT required_conditions, code INTO v_required, v_code
    FROM bd.quantity WHERE id = NEW.quantity_id;

  -- normalise to SI where we know the unit
  IF NEW.value_native IS NOT NULL AND NEW.value_si IS NULL THEN
    NEW.value_si := bd.to_si(NEW.value_native, NEW.unit_native);
  END IF;

  IF v_required IS NULL OR cardinality(v_required) = 0 THEN
    RETURN NEW;
  END IF;

  IF NEW.condition_set_id IS NULL THEN
    RAISE EXCEPTION
      'quantity "%" requires conditions % but no condition_set was supplied',
      v_code, v_required
      USING HINT = 'Call bd.intern_conditions(jsonb) and pass the returned id.';
  END IF;

  SELECT to_jsonb(c) INTO v_cond FROM bd.condition_set c WHERE c.id = NEW.condition_set_id;

  FOREACH k IN ARRAY v_required LOOP
    -- A condition the source itself never states is declared, not missing.
    CONTINUE WHEN v_cond->'unstated' ? k;

    IF v_cond->>k IS NULL
       OR (k = 'temperature_reference' AND v_cond->>k = 'unspecified')
       OR (k = 'rate_unit'             AND v_cond->>k = 'unspecified')
       OR (k = 'soc_method'            AND v_cond->>k = 'unspecified')
       OR (k = 'boundary'              AND v_cond->>k = 'unspecified')
       OR (k = 'area_kind'             AND v_cond->>k = 'unspecified')
    THEN
      v_missing := v_missing || k;
    END IF;
  END LOOP;

  IF cardinality(v_missing) > 0 THEN
    RAISE EXCEPTION
      'quantity "%" is uninterpretable without condition(s): %',
      v_code, array_to_string(v_missing, ', ')
      USING HINT = 'Supply the condition, or - if the SOURCE genuinely does '
                   'not state it - list the column name in '
                   'condition_set.unstated. That records the omission as a '
                   'fact about the document instead of hiding it as a NULL.';
  END IF;

  RETURN NEW;
END$$;

CREATE TRIGGER observation_validate
  BEFORE INSERT OR UPDATE ON observation
  FOR EACH ROW EXECUTE FUNCTION bd.validate_observation();

-- ---------------------------------------------------------------------
-- CURVES. A great deal of the most valuable data is not scalar:
-- rate-capability tables, temperature derating maps, OCV-SOC curves,
-- dQ/dV traces, discharge curves, warranty retention curves, alkaline
-- service-hours tables, ARC temperature ramps, DRT spectra.
--
-- Stored as parallel float arrays: compact, exactly reproducible, and
-- directly loadable into numpy/pandas without a join per point.
-- ---------------------------------------------------------------------
CREATE TABLE curve (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,

  -- subject: exactly one, same discipline as observation
  product_revision_id bigint REFERENCES product_revision(id) ON DELETE CASCADE,
  product_unit_id     bigint REFERENCES product_unit(id)     ON DELETE CASCADE,
  test_run_id         bigint,
  test_segment_id     bigint,
  material_id         bigint REFERENCES material(id),

  curve_kind     text NOT NULL,     -- 'ocv_soc'|'rate_capability'|'dqdv'|'derating_map'|'service_hours'|...
  x_quantity_id  bigint NOT NULL REFERENCES quantity(id),
  y_quantity_id  bigint NOT NULL REFERENCES quantity(id),
  z_quantity_id  bigint REFERENCES quantity(id),   -- for 2-D maps
  x_unit         text NOT NULL,
  y_unit         text NOT NULL,
  z_unit         text,
  x_values       double precision[] NOT NULL,
  y_values       double precision[] NOT NULL,
  z_values       double precision[],
  n_points       int GENERATED ALWAYS AS (cardinality(x_values)) STORED,

  condition_set_id bigint REFERENCES condition_set(id),
  -- when the curve is a derivative or otherwise processed, the recipe is
  -- part of the data. A dQ/dV trace without its smoothing parameters is
  -- not reproducible and its peak positions are not comparable.
  processing     jsonb NOT NULL DEFAULT '{}',
  provenance_id  bigint NOT NULL REFERENCES provenance(id),
  access_tier    access_tier NOT NULL DEFAULT 'public',
  created_at     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT curve_one_subject CHECK (
    num_nonnulls(product_revision_id, product_unit_id, test_run_id,
                 test_segment_id, material_id) = 1
  ),
  CONSTRAINT curve_xy_same_length CHECK (
    cardinality(x_values) = cardinality(y_values)
  ),
  CONSTRAINT curve_z_same_length CHECK (
    z_values IS NULL OR cardinality(z_values) = cardinality(x_values)
  )
);
CREATE INDEX ON curve (curve_kind);
CREATE INDEX ON curve (product_revision_id);
CREATE INDEX ON curve (test_run_id);

COMMENT ON COLUMN curve.processing IS
  'For derived curves: {"smoothing":"savgol","window":21,"polyorder":3,'
  '"smoothed_before_differentiation":true,"voltage_bin_mv":2,'
  '"peak_position_convention":"onset"}. The best-practice literature is '
  'emphatic that smoothing AFTER differentiation displaces peaks and is '
  'routinely misread as degradation, so the order is recorded explicitly.';
