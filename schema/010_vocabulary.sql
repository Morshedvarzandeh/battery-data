-- =====================================================================
-- battery-data : 010_vocabulary.sql
-- Enumerations and the quantity/unit registry.
--
-- DESIGN NOTE
-- Every enum here exists because the field genuinely disagrees about the
-- value, and a database that assumes one convention silently destroys
-- the other. Where an enum encodes a convention (current sign, capacity
-- accumulation, cycle counting), it is NOT optional metadata: it is part
-- of the meaning of the numbers it governs.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Product taxonomy
-- ---------------------------------------------------------------------
CREATE TYPE product_kind AS ENUM (
  'cell',              -- the atomic electrochemical unit
  'module',            -- cells assembled, no independent BMS necessarily
  'pack',              -- modules + BMS, a fielded unit
  'system',            -- pack + PCS/inverter/thermal, e.g. BESS container
  'primary_cell',      -- non-rechargeable
  'component'          -- electrode, separator, electrolyte as a product
);

CREATE TYPE form_factor AS ENUM (
  'cylindrical', 'pouch', 'prismatic_hardcase', 'coin', 'button',
  'blade', 'rack', 'container', 'brick', 'other'
);

CREATE TYPE lifecycle_status AS ENUM (
  'announced', 'sampling', 'active', 'nrnd', 'last_time_buy',
  'obsolete', 'unknown'
);

-- ---------------------------------------------------------------------
-- The hardware around the cell. A pack is a cell plus the components that
-- let it be used safely, and they are products with datasheets like any
-- cell: a contactor's breaking capacity, a fuse's I2t, a converter's
-- efficiency surface. product.kind = 'component' says it is one of these;
-- component_kind says which.
-- ---------------------------------------------------------------------
CREATE TYPE component_kind AS ENUM (
  'dc_dc_converter', 'on_board_charger', 'inverter', 'pcs',
  'contactor', 'relay', 'fuse', 'pyro_fuse', 'circuit_breaker',
  'bms', 'battery_disconnect_unit', 'busbar', 'cell_contact_system',
  'current_sensor', 'voltage_sensor', 'temperature_sensor',
  'pre_charge_resistor', 'service_disconnect', 'isolation_monitor',
  'cooling_plate', 'chiller', 'heater', 'thermal_interface_material',
  'vent', 'enclosure', 'cell_holder', 'connector', 'cable', 'wire_harness',
  'electrode', 'separator', 'electrolyte', 'other'
);

-- Every chemistry a reference has to hold. The designation string stays
-- free text ("NMC811", "Li-SOCl2", "AGM 12V"); the family is the enum a
-- query filters on and the class an ontology export binds to.
CREATE TYPE chemistry_family AS ENUM (
  'lithium_ion', 'lithium_metal', 'lithium_primary',
  'sodium_ion', 'sodium_sulfur', 'sodium_nickel_chloride',
  'lead_acid',
  'nickel_metal_hydride', 'nickel_cadmium', 'nickel_zinc', 'nickel_iron',
  'zinc_air', 'zinc_carbon', 'alkaline', 'silver_oxide',
  'flow_vanadium', 'flow_zinc_bromine', 'flow_iron', 'flow_other',
  'solid_state', 'supercapacitor', 'other'
);

-- Lead-acid construction decides the charge voltages, the orientation, the
-- gassing and the cycle life more than the chemistry does.
CREATE TYPE lead_acid_construction AS ENUM (
  'flooded', 'agm', 'gel', 'tubular_plate', 'flat_plate', 'bipolar',
  'carbon_enhanced', 'other'
);

-- ---------------------------------------------------------------------
-- Provenance and evidence
-- ---------------------------------------------------------------------
CREATE TYPE source_kind AS ENUM (
  'datasheet',          -- manufacturer PDF
  'manufacturer_web',   -- vendor product page
  'standard',           -- IEC/ISO/SAE/UN/GB text
  'journal_article',
  'preprint',
  'conference_paper',
  'thesis',
  'patent',
  'dataset',            -- Zenodo / Figshare / BatteryArchive / data.matr.io
  'code_repository',
  'regulatory_filing',
  'distributor_listing',
  'teardown_report',
  'third_party_test',   -- independent lab characterisation
  'user_submission',
  'internal_measurement'
);

-- How a value got into the database. This is deliberately separate from
-- source_kind: a value can come from a journal article by being read off
-- a table (high confidence) or digitised off a figure (much lower).
CREATE TYPE evidence_class AS ENUM (
  'manufacturer_claim',    -- vendor asserts it; not independently verified
  'measured',              -- someone actually measured it, raw data exists
  'literature_reported',   -- reported in a paper, raw data not available
  'plot_digitised',        -- reverse-engineered from a figure
  'derived',               -- computed from other stored values
  'estimated',             -- model output / interpolation
  'inferred_by_agent'      -- LLM extraction not yet human-reviewed
);

CREATE TYPE extraction_method AS ENUM (
  'manual_entry',
  'table_parse',           -- structured table in a PDF/HTML
  'text_llm',              -- LLM read prose
  'vision_llm',            -- LLM read a rendered page image
  'plot_digitisation',
  'file_parse',            -- cycler file / supplementary CSV
  'api_import',
  'ocr'
);

-- Statistic qualifier. Datasheets use all of these for "capacity" and
-- they are NOT interchangeable (Panasonic NCR18650GA lists rated 3300,
-- minimum 3350 and typical 3450 mAh on one page).
CREATE TYPE statistic_kind AS ENUM (
  'rated', 'nominal', 'standard', 'minimum', 'typical', 'maximum',
  'initial', 'design', 'guaranteed', 'mean', 'median', 'measured',
  'absolute_max', 'absolute_min'
);

-- Access tier, per EU Regulation 2023/1542 Art. 77(2).
CREATE TYPE access_tier AS ENUM (
  'public', 'legitimate_interest', 'authority_only', 'restricted'
);

CREATE TYPE review_state AS ENUM (
  'draft', 'pending_review', 'needs_changes', 'accepted', 'rejected',
  'superseded', 'disputed'
);

-- ---------------------------------------------------------------------
-- Conditions
-- ---------------------------------------------------------------------
-- Where a temperature was actually measured. Ambient and cell-surface can
-- differ by >20 K under load; most datasheets never say which they mean.
CREATE TYPE temperature_reference AS ENUM (
  'ambient', 'chamber_setpoint', 'cell_surface', 'can', 'tab',
  'core', 'coolant_inlet', 'coolant_outlet', 'unspecified'
);

-- The unit a rate is expressed in. C-rate, absolute current, IEC It
-- notation and constant-POWER rating are not interconvertible without
-- extra information. EVE rates the LF280K in constant power ("0.5P").
CREATE TYPE rate_unit AS ENUM (
  'A', 'mA', 'C', 'It', 'W', 'P', 'W_per_kg', 'ohm', 'pct', 'unspecified'
);
-- 'pct' is a load point as a fraction of rating: a converter's efficiency
-- "at 50% load" is stated against its own rated output, not an ampere.

-- How SOC was established. Voltage-based SOC is unusable on LFP.
CREATE TYPE soc_method AS ENUM (
  'coulomb_counted', 'ocv_lookup', 'bms_reported', 'voltage_proxy',
  'time_from_full', 'unspecified'
);

-- Constant-force and constant-gap fixtures measure different physical
-- quantities. Sharing one "swelling" table between them is a modelling error.
CREATE TYPE mechanical_constraint AS ENUM (
  'unconstrained', 'constant_force', 'constant_gap', 'rigid_case',
  'stack_in_module', 'unspecified'
);

-- Where an efficiency / energy figure is measured. Tesla Powerwall 3
-- quotes 13.5 kWh AC; BYD quotes usable energy DC. Not comparable.
CREATE TYPE measurement_boundary AS ENUM (
  'electrode', 'cell', 'module', 'pack_dc', 'dc_bus', 'ac_terminal',
  'ac_including_auxiliaries', 'unspecified'
);

-- ---------------------------------------------------------------------
-- Test and protocol taxonomy
-- ---------------------------------------------------------------------
CREATE TYPE test_kind AS ENUM (
  'formation',
  'capacity',                -- static capacity / C-rate discharge
  'rate_capability',
  'rpt',                     -- reference performance test (bundle)
  'hppc',
  'eis',
  'drt',                     -- distribution of relaxation times (derived from EIS)
  'cycle_life',
  'calendar_aging',
  'ocv_pseudo',              -- pOCV, low-rate charge/discharge
  'ocv_incremental',         -- iOCV, pulse-and-rest
  'gitt',
  'pitt',
  'ica_dva',                 -- dQ/dV, dV/dQ
  'coulombic_efficiency',    -- high-precision coulometry
  'self_discharge',
  'leakage_current',
  'entropic_coefficient',
  'heat_capacity',
  'thermal_conductivity',
  'thermal_impedance',
  'isothermal_calorimetry',
  'arc',                     -- accelerating rate calorimetry
  'thermal_ramp',
  'thermal_propagation',
  'nail_penetration',
  'crush',
  'overcharge',
  'over_discharge',
  'external_short',
  'internal_short',
  'vent_gas_analysis',
  'drop', 'vibration', 'shock', 'altitude', 'thermal_shock',
  'immersion',
  'swelling',                -- thickness / force vs SOC
  'stack_pressure',
  'drive_cycle',
  'three_electrode',
  'post_mortem',
  'xrd', 'sem', 'eds', 'xps', 'icp', 'bet', 'nmr', 'gcms',
  'half_cell_reconstruction',
  'other'
);

-- The role a segment plays inside a longer campaign. Aging campaigns are
-- [aging, RPT, aging, RPT, ...] and no public schema captures that.
CREATE TYPE segment_role AS ENUM (
  'conditioning', 'formation', 'baseline_rpt', 'aging_cycling',
  'aging_storage', 'periodic_rpt', 'diagnostic', 'final_rpt',
  'teardown_prep', 'other'
);

CREATE TYPE control_mode AS ENUM (
  'rest', 'cc', 'cv', 'cccv', 'cp', 'cr', 'profile', 'eis_geis',
  'eis_peis', 'loop', 'temperature_hold', 'other'
);

-- ---------------------------------------------------------------------
-- Conventions. These are the load-bearing ones.
-- ---------------------------------------------------------------------
-- BDF / VDF / battdat / battery-data-standard default to charge-positive.
-- ionworksdata enforces discharge-positive. Same column name, opposite sign.
CREATE TYPE current_sign_convention AS ENUM (
  'charge_positive', 'discharge_positive', 'unsigned_with_mode_flag'
);

-- Arbin accumulates capacity within a step; Neware/fastnda give net per
-- step; Voltaiq resets per cycle; BDF carries all three separately.
CREATE TYPE capacity_accumulation AS ENUM (
  'per_step', 'per_cycle', 'cumulative_test', 'net_signed', 'unspecified'
);

-- No two cyclers agree on when a cycle increments. NewareNDA alone offers
-- three modes. Store what the instrument said AND how we recomputed it.
CREATE TYPE cycle_definition AS ENUM (
  'as_reported', 'on_charge_start', 'on_discharge_start',
  'on_charge_discharge_pair', 'schedule_loop', 'equivalent_full_cycle'
);

-- Which two samples defined ΔV in a pulse-resistance calculation.
-- Logging configuration alone has been shown to move a measured pulse
-- resistance from 36 mΩ to 28 mΩ on the same cell.
CREATE TYPE dcir_extraction AS ENUM (
  'last_pre_pulse_to_pulse_end',
  'ocv_to_pulse_end',
  'first_sample_after_step_to_pulse_end',
  'interpolated_at_nominal_duration',
  'instrument_reported',
  'unspecified'
);

CREATE TYPE eis_mode AS ENUM ('geis', 'peis', 'hybrid', 'unspecified');
CREATE TYPE amplitude_type AS ENUM ('rms', 'zero_to_peak', 'peak_to_peak', 'unspecified');

-- ASI = R × A, but "A" is variously total separator area, single-sided
-- cathode area, or double-sided coated area.
CREATE TYPE area_definition AS ENUM (
  'separator_total', 'cathode_single_sided', 'cathode_double_sided',
  'anode_single_sided', 'anode_double_sided', 'geometric_footprint',
  'unspecified'
);

CREATE TYPE eol_reference AS ENUM (
  'nameplate_capacity', 'measured_bol_capacity', 'nameplate_energy',
  'measured_bol_energy', 'initial_resistance', 'unspecified'
);

CREATE TYPE hazard_scale AS ENUM ('eucar', 'sae_j2464_hsl', 'gbt', 'proprietary', 'unspecified');

CREATE TYPE self_discharge_metric AS ENUM (
  'ocv_decay_mv_per_day',      -- "K-value" in CN manufacturing practice
  'leakage_current_ua',        -- direct potentiostatic measurement
  'capacity_retention_pct',    -- standards' stand-test method
  'permanent_loss_pct',        -- irrecoverable fraction
  'percent_per_month',
  'percent_per_year'
);

-- ---------------------------------------------------------------------
-- QUANTITY REGISTRY
-- The vocabulary spine. Every numeric value in the database points at a
-- row here, which carries the SI unit and the external IRIs so the graph
-- projection and the JSON-LD export are generated, not hand-maintained.
-- ---------------------------------------------------------------------
CREATE TABLE quantity (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code            text NOT NULL UNIQUE,      -- snake_case internal name
  label           text NOT NULL,
  si_unit         text NOT NULL,             -- canonical unit for value_si
  dimension       text,                      -- e.g. 'electric_charge'
  description     text,
  -- external vocabulary bindings (populated by tools/sync_vocabularies.py)
  emmo_iri        text,                      -- EMMO domain-battery / -electrochemistry
  bdf_name        text,                      -- Battery Data Format machine name
  bpx_key         text,                      -- BPX parameter key
  battery_pass_path text,                    -- io.BatteryPass.* aspect path
  qudt_quantity_kind text,                   -- http://qudt.org/vocab/quantitykind/...
  -- which condition dimensions MUST be present for this quantity to be
  -- interpretable. Enforced by validate_observation(); this is what stops
  -- a bare "internal_resistance = 15 mΩ" from ever entering the database.
  required_conditions text[] NOT NULL DEFAULT '{}',
  is_derived      boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN quantity.required_conditions IS
  'Condition columns that must be non-null on the linked condition_set. '
  'A quantity with an empty array is a true scalar attribute (e.g. mass); '
  'anything with entries is a measurement whose value is meaningless alone.';

-- Unit conversion registry: value_native (any unit) -> value_si.
CREATE TABLE unit (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  symbol      text NOT NULL UNIQUE,
  si_symbol   text NOT NULL,
  factor      double precision NOT NULL,   -- value_si = value*factor + offset
  offset_     double precision NOT NULL DEFAULT 0,
  dimension   text,
  qudt_iri    text                            -- http://qudt.org/vocab/unit/..., set by 175
);

INSERT INTO unit (symbol, si_symbol, factor, offset_, dimension) VALUES
  ('Ah','C',3600,0,'electric_charge'),        ('mAh','C',3.6,0,'electric_charge'),
  ('C','C',1,0,'electric_charge'),
  ('Wh','J',3600,0,'energy'),                 ('kWh','J',3.6e6,0,'energy'),
  ('mWh','J',3.6,0,'energy'),                 ('J','J',1,0,'energy'),
  ('Wh/kg','J/kg',3600,0,'specific_energy'),  ('Wh/L','J/m3',3.6e6,0,'energy_density'),
  ('V','V',1,0,'voltage'),                    ('mV','V',1e-3,0,'voltage'),
  ('A','A',1,0,'current'),                    ('mA','A',1e-3,0,'current'),
  ('uA','A',1e-6,0,'current'),
  ('ohm','ohm',1,0,'resistance'),             ('mohm','ohm',1e-3,0,'resistance'),
  ('Ω','ohm',1,0,'resistance'),               ('mΩ','ohm',1e-3,0,'resistance'),
  ('uohm','ohm',1e-6,0,'resistance'),
  ('degC','K',1,273.15,'temperature'),        ('°C','K',1,273.15,'temperature'),
  ('K','K',1,0,'temperature'),
  ('g','kg',1e-3,0,'mass'),                   ('kg','kg',1,0,'mass'),
  ('mm','m',1e-3,0,'length'),                 ('m','m',1,0,'length'),
  ('um','m',1e-6,0,'length'),
  ('cm2','m2',1e-4,0,'area'),                 ('m2','m2',1,0,'area'),
  ('cm3','m3',1e-6,0,'volume'),               ('L','m3',1e-3,0,'volume'),
  ('W','W',1,0,'power'),                      ('kW','W',1e3,0,'power'),
  ('N','N',1,0,'force'),                      ('kN','N',1e3,0,'force'),
  ('kgf','N',9.80665,0,'force'),
  ('Pa','Pa',1,0,'pressure'),                 ('kPa','Pa',1e3,0,'pressure'),
  ('MPa','Pa',1e6,0,'pressure'),              ('bar','Pa',1e5,0,'pressure'),
  ('Hz','Hz',1,0,'frequency'),                ('kHz','Hz',1e3,0,'frequency'),
  ('mHz','Hz',1e-3,0,'frequency'),
  ('s','s',1,0,'time'),                       ('h','s',3600,0,'time'),
  ('day','s',86400,0,'time'),                 ('year','s',31557600,0,'time'),
  ('pct','1',0.01,0,'dimensionless'),         ('%','1',0.01,0,'dimensionless'),
  ('1','1',1,0,'dimensionless'),
  -- Self-discharge is quoted per unit time, and quantity.self_discharge_rate
  -- says outright that %/month, mV/day and uA are not interconvertible. They
  -- get their own dimension so nothing joins a monthly rate to a bare fraction
  -- on the strength of both reducing to '1'.
  ('%/month','1/month',0.01,0,'fraction_per_month'),
  ('%/year','1/year',0.01,0,'fraction_per_year'),
  ('mV/day','V/day',1e-3,0,'voltage_per_day'),
  ('mV_per_K','V/K',1e-3,0,'entropic'),       ('V_per_K','V/K',1,0,'entropic'),
  ('W_per_mK','W/(m*K)',1,0,'thermal_conductivity'),
  ('J_per_kgK','J/(kg*K)',1,0,'specific_heat'),
  ('Wh_per_kg','J/kg',3600,0,'specific_energy'),
  ('Wh_per_L','J/m3',3.6e6,0,'energy_density'),
  ('W_per_kg','W/kg',1,0,'specific_power'),
  ('cycles','1',1,0,'dimensionless'),
  ('ohm_cm2','ohm*m2',1e-4,0,'area_specific_impedance'),
  ('deg','deg',1,0,'angle');

CREATE OR REPLACE FUNCTION bd.to_si(value double precision, unit_symbol text)
RETURNS double precision LANGUAGE sql STABLE AS $$
  SELECT value * u.factor + u.offset_ FROM bd.unit u WHERE u.symbol = unit_symbol
$$;
