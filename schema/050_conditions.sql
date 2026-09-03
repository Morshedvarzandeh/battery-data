-- =====================================================================
-- battery-data : 050_conditions.sql
--
-- THE LOAD-BEARING TABLE.
--
-- Roughly 40% of what a datasheet calls a "specification" is not an
-- attribute of the product. It is the result of a measurement under
-- conditions that the datasheet may or may not disclose. Storing those
-- as plain columns destroys the conditions and makes rows silently
-- non-comparable.
--
-- Worked examples that a `capacity_mah REAL` column cannot represent:
--   Samsung INR21700-50E : 4900 mAh AND 4753 mAh, same page
--                          (0.2C "standard" vs 1C "rated")
--   Panasonic NCR18650GA : rated 3300 < minimum 3350 < typical 3450
--                          (rated at 20 C, the others at 25 C)
--   Molicel P45B         : the -30 C figure uses a 2.0 V cutoff while
--                          every other figure uses 2.5 V
--   LG M50LT             : AC 1 kHz = 15 mohm, DC 10 s = 23 mohm.
--                          Same cell. 53% apart. Both "internal resistance".
--   EVE LF280K           : rated in constant POWER (0.5P), not current
--   Energizer E91        : no capacity field exists at all, only
--                          service-hours vs load/schedule/cutoff
--
-- condition_set is content-addressed: identical conditions collapse to
-- one row automatically, which is what makes "find every cell measured
-- under comparable conditions" a join rather than a research project.
-- =====================================================================

SET search_path = bd, public;

CREATE TABLE condition_set (
  id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- ---- thermal ----------------------------------------------------
  temperature_c            double precision,
  temperature_tolerance_c  double precision,
  temperature_reference    temperature_reference NOT NULL DEFAULT 'unspecified',
  soak_time_s              double precision,        -- equilibration before measuring

  -- ---- rate -------------------------------------------------------
  -- rate_unit distinguishes 0.5C from 0.5 A from 0.5P. They are not the
  -- same quantity and cannot be converted without the reference below.
  rate_value               double precision,
  rate_unit                rate_unit NOT NULL DEFAULT 'unspecified',
  -- "1C" is self-referential. LG calls 1C = 4800 mA, Samsung 4900 mA, and
  -- measured C1 routinely differs from nameplate by >10%. Any C-rate is
  -- meaningless without saying which capacity it was taken as a fraction of.
  rate_reference_capacity_ah double precision,
  rate_reference_source    text,                    -- 'nameplate'|'measured_c1'|'measured_c25'|'declared'
  direction                text,                    -- 'charge'|'discharge'|'rest'|'symmetric'

  -- ---- circuit (contactors, fuses, converters) ---------------------
  -- A DC interrupt rating is a function of the circuit it was tested in:
  -- the voltage and the L/R time constant. A contactor that breaks 2000 A
  -- at 450 V with L/R = 1 ms is a different claim from the same figure at
  -- a longer time constant, and datasheets state both. Efficiency and
  -- output ratings of a converter likewise carry the input voltage here.
  circuit_voltage_v        double precision,
  time_constant_ms         double precision,

  -- ---- voltage window --------------------------------------------
  voltage_upper_v          double precision,
  voltage_lower_v          double precision,
  cv_cutoff_current_a      double precision,        -- CC-CV taper termination
  cv_cutoff_current_c      double precision,

  -- ---- state ------------------------------------------------------
  soc_pct                  double precision CHECK (soc_pct BETWEEN -5 AND 105),
  soc_method               soc_method NOT NULL DEFAULT 'unspecified',
  dod_pct                  double precision,
  soc_window_min_pct       double precision,
  soc_window_max_pct       double precision,

  -- ---- pulse (HPPC / DCIR) ---------------------------------------
  -- Resistance is current-dependent and duration-dependent. USABC uses
  -- 10 s, ISO 12405-4 uses 0.1/2/10/18 s, SAE J1798 uses 30 s. An R
  -- without its pulse duration and current is not a number, it is a rumour.
  pulse_duration_s         double precision,
  pulse_current_a          double precision,
  pulse_direction          text,                    -- 'discharge'|'regen'|'charge'
  rest_before_pulse_s      double precision,

  -- ---- AC / spectral ---------------------------------------------
  frequency_hz             double precision,
  amplitude_value          double precision,
  amplitude_unit           text,                    -- 'mV' (PEIS) or 'mA' (GEIS)
  amplitude_kind           amplitude_type NOT NULL DEFAULT 'unspecified',

  -- ---- relaxation -------------------------------------------------
  -- 15 min, 1 h, 3 h and 60 h all appear in the literature for "rest
  -- before EIS". It determines the low-frequency tail entirely.
  rest_before_s            double precision,
  relaxation_criterion     text,                    -- 'fixed_time'|'dvdt<5mV/h'|...

  -- ---- mechanical -------------------------------------------------
  constraint_mode          mechanical_constraint NOT NULL DEFAULT 'unspecified',
  clamp_force_n            double precision,
  clamp_pressure_kpa       double precision,
  plate_area_cm2           double precision,
  fixture_stiffness_n_per_mm double precision,

  -- ---- environment ------------------------------------------------
  humidity_pct             double precision,
  pressure_pa              double precision,
  altitude_m               double precision,
  atmosphere               text,                    -- 'air'|'argon'|'nitrogen'

  -- ---- duration / ageing state ------------------------------------
  duration_s               double precision,        -- storage or stand time
  cycle_index              int,                     -- age at which measured
  equivalent_full_cycles   double precision,
  throughput_ah            double precision,
  calendar_age_days        double precision,

  -- ---- boundary ---------------------------------------------------
  -- Whether an efficiency or energy is quoted at the cell, the DC bus,
  -- or the AC terminals, and whether auxiliary loads are inside the
  -- boundary. CATL's HVAC draws up to 36.7 kW on a 2 MW system; including
  -- or excluding it moves round-trip efficiency by points.
  boundary                 measurement_boundary NOT NULL DEFAULT 'unspecified',
  auxiliaries_included     boolean,

  -- ---- load schedule (primary cells) ------------------------------
  -- Alkaline datasheets have no capacity, only service hours vs a load
  -- and a duty schedule ("2 min/hr") and a cutoff voltage.
  load_value               double precision,
  load_unit                text,                    -- 'mA'|'ohm'|'mW'
  duty_schedule            text,                    -- 'continuous'|'2min/hr'|'1h/day'
  cutoff_voltage_v         double precision,

  -- ---- area normalisation -----------------------------------------
  area_cm2                 double precision,
  area_kind                area_definition NOT NULL DEFAULT 'unspecified',

  -- ---- declared absence -------------------------------------------
  -- Names condition columns that the SOURCE ITSELF does not state.
  --
  -- This is the difference between "we failed to record the pulse
  -- duration" and "Samsung published a 14700 mA pulse rating and never
  -- said how long the pulse is". The second is a fact about the
  -- datasheet and is worth knowing; silently leaving the column NULL
  -- would make the two indistinguishable.
  --
  -- Listing a column here satisfies the required-conditions check, and
  -- marks every observation using this condition_set as incomplete so
  -- that v_incomplete_observation can report it.
  unstated                 text[] NOT NULL DEFAULT '{}',

  -- ---- escape hatch ------------------------------------------------
  -- Deliberately present. A schema that cannot represent an unforeseen
  -- condition will have that condition silently dropped at ingest.
  extra                    jsonb NOT NULL DEFAULT '{}',

  -- free-text as written in the source, always retained
  verbatim                 text,

  -- content address for dedup
  fingerprint              text NOT NULL,
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT condition_set_fingerprint_uq UNIQUE (fingerprint),
  CONSTRAINT soc_window_ordered CHECK (
    soc_window_min_pct IS NULL OR soc_window_max_pct IS NULL
    OR soc_window_min_pct <= soc_window_max_pct
  ),
  CONSTRAINT voltage_window_ordered CHECK (
    voltage_upper_v IS NULL OR voltage_lower_v IS NULL
    OR voltage_lower_v <= voltage_upper_v
  ),
  -- A C-rate without its reference capacity is uninterpretable. Refuse it.
  CONSTRAINT c_rate_needs_reference CHECK (
    rate_unit <> 'C' OR rate_reference_capacity_ah IS NOT NULL
                     OR rate_reference_source IS NOT NULL
  )
);

CREATE INDEX ON condition_set (temperature_c);
CREATE INDEX ON condition_set (rate_value, rate_unit);
CREATE INDEX ON condition_set (soc_pct);
CREATE INDEX ON condition_set (pulse_duration_s) WHERE pulse_duration_s IS NOT NULL;
CREATE INDEX ON condition_set USING gin (extra jsonb_path_ops);

-- ---------------------------------------------------------------------
-- Fingerprint = hash of every semantic column. Computed in a trigger so
-- that no client can forget to set it.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd.condition_fingerprint(c bd.condition_set)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT bd.json_hash(
    to_jsonb(c) - 'id' - 'fingerprint' - 'created_at' - 'verbatim'
  )
$$;

CREATE OR REPLACE FUNCTION bd.set_condition_fingerprint()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.fingerprint := bd.condition_fingerprint(NEW);
  RETURN NEW;
END$$;

CREATE TRIGGER condition_set_fp
  BEFORE INSERT OR UPDATE ON condition_set
  FOR EACH ROW EXECUTE FUNCTION bd.set_condition_fingerprint();

-- ---------------------------------------------------------------------
-- Upsert helper. Callers pass a jsonb of condition columns and get back
-- the id of the canonical row, creating it only if new.
-- ---------------------------------------------------------------------
-- Column defaults that jsonb_populate_record would otherwise turn into
-- NULLs. Applying them here also makes the fingerprint stable whether or
-- not the caller passed the defaults explicitly.
CREATE OR REPLACE FUNCTION bd.condition_defaults()
RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
  SELECT jsonb_build_object(
    'temperature_reference', 'unspecified',
    'rate_unit',             'unspecified',
    'soc_method',            'unspecified',
    'constraint_mode',       'unspecified',
    'boundary',              'unspecified',
    'area_kind',             'unspecified',
    'amplitude_kind',        'unspecified',
    'unstated',              '[]'::jsonb,
    'extra',                 '{}'::jsonb
  )
$$;

CREATE OR REPLACE FUNCTION bd.intern_conditions(payload jsonb)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
  v_norm jsonb;
  v_row  bd.condition_set%ROWTYPE;
  v_fp   text;
  v_id   bigint;
  v_cols text;
BEGIN
  v_norm := bd.condition_defaults() || COALESCE(payload, '{}'::jsonb);

  v_row := jsonb_populate_record(NULL::bd.condition_set, v_norm);
  v_fp  := bd.condition_fingerprint(v_row);

  SELECT id INTO v_id FROM bd.condition_set WHERE fingerprint = v_fp;
  IF v_id IS NOT NULL THEN
    RETURN v_id;                                 -- already interned
  END IF;

  -- Explicit column list, excluding the generated identity and the
  -- trigger-maintained fingerprint.
  SELECT string_agg(quote_ident(attname), ', ' ORDER BY attnum)
    INTO v_cols
    FROM pg_attribute
   WHERE attrelid = 'bd.condition_set'::regclass
     AND attnum > 0 AND NOT attisdropped
     AND attname NOT IN ('id', 'fingerprint', 'created_at');

  EXECUTE format(
    'INSERT INTO bd.condition_set (%1$s) '
    'SELECT %1$s FROM jsonb_populate_record(NULL::bd.condition_set, $1) '
    'ON CONFLICT (fingerprint) DO NOTHING RETURNING id',
    v_cols
  ) INTO v_id USING v_norm;

  IF v_id IS NULL THEN                            -- lost a concurrent race
    SELECT id INTO v_id FROM bd.condition_set WHERE fingerprint = v_fp;
  END IF;
  RETURN v_id;
END$$;

COMMENT ON FUNCTION bd.intern_conditions(jsonb) IS
  'Content-addressed upsert. bd.intern_conditions(''{"temperature_c":25,'
  '"rate_value":0.2,"rate_unit":"C","rate_reference_capacity_ah":4.9}'') '
  'returns the canonical condition_set id.';
