-- =====================================================================
-- battery-data : 170_crosswalk.sql
--
-- Bindings from this schema's quantities to the four external
-- vocabularies that describe overlapping parts of the battery landscape
-- and which nobody has connected:
--
--   BDF          LF Energy Battery Data Alliance, Dec 2025 (time series)
--   EMMO/BattINFO  vocabulary IRIs for cells, tests, models
--   BPX          Faraday Institution (physics model parameters)
--   BatteryPass  DIN DKE SPEC 99100 / EU Reg 2023/1542 (passport fields)
--
-- Held as data rather than prose so the published crosswalk is generated
-- (tools/export_crosswalk.py) and cannot drift from the schema.
--
-- HONESTY NOTE ON IRIs
-- EMMO class IRIs are opaque UUIDs (BatteryCell =
-- battery_68ed592a_7924_45d0_a108_94d6275d57f0). Only IRIs that have
-- been verified against the published TTL are set below. The rest are
-- deliberately left NULL for tools/sync_vocabularies.py to fill by
-- parsing battery.ttl and electrochemistry.ttl at build time. Hand-copying
-- UUIDs from documentation is how crosswalks silently become wrong.
-- =====================================================================

SET search_path = bd, public;

CREATE TABLE vocabulary (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code          text NOT NULL UNIQUE,
  name          text NOT NULL,
  namespace     text,
  version       text,
  url           text,
  license       text,
  notes         text
);

INSERT INTO vocabulary (code, name, namespace, version, url, license, notes) VALUES
 ('bdf','Battery Data Format',
  'https://w3id.org/battery-data-alliance/ontology/battery-data-format#',
  '1.2.0','https://github.com/battery-data-alliance/battery-data-format',
  'Apache-2.0',
  'Published Dec 2025 by the LF Energy Battery Data Alliance. Adopted verbatim '
  'for bd.timeseries_record column names. A parallel METADATA format has been '
  'announced but does not yet exist - that is the layer bd.product_revision, '
  'bd.condition_set and bd.protocol occupy.'),
 ('emmo_battery','EMMO domain-battery',
  'https://w3id.org/emmo/domain/battery#','0.20.0',
  'https://github.com/emmo-repo/domain-battery','CC-BY-4.0',
  'Annotated "unstable". Class IRIs are opaque UUIDs; human labels live in '
  'skos:prefLabel. Adoption outside EU projects is thin. Treat as the '
  'vocabulary of record, not a working data format.'),
 ('emmo_electrochemistry','EMMO domain-electrochemistry',
  'https://w3id.org/emmo/domain/electrochemistry#','0.34.0',
  'https://github.com/emmo-repo/domain-electrochemistry','CC-BY-4.0',
  'Carries the quantities and materials terms (~3000).'),
 ('bpx','Battery Parameter eXchange',NULL,'0.4',
  'https://github.com/FaradayInstitution/BPX','Apache-2.0',
  'Physics models only - DFN/SPM/SPMe. No ECM schema and no published roadmap '
  'for one; bd.ecm_parameter_point fills that gap.'),
 ('battery_pass','Battery Passport Data Model',
  'https://github.com/batterypass/BatteryPassDataModel','1.2.0',
  'https://github.com/batterypass/BatteryPassDataModel','MIT',
  'Aligned to DIN DKE SPEC 99100:2025-02. Mandatory under EU Reg 2023/1542 '
  'Art. 77 + Annex XIII from 18 Feb 2027.'),
 ('optimade','OPTIMADE','https://optimade.org/','1.3.0',
  'https://www.optimade.org/','CC-BY-4.0',
  'API conventions worth copying; entry types are crystal-structure-shaped '
  'and should not be extended to cells. Federate materials by ID.');

-- ---------------------------------------------------------------------
-- Term-level mappings. `relation` records mapping FIDELITY, which is the
-- part a naive crosswalk omits and the part that matters: an "exact"
-- mapping can be relied on for round-tripping, a "narrower" one cannot.
-- ---------------------------------------------------------------------
CREATE TYPE mapping_relation AS ENUM (
  'exact',        -- same quantity, same definition, round-trips losslessly
  'close',        -- same quantity, minor definitional differences
  'broader',      -- the external term is more general than ours
  'narrower',     -- the external term is more specific than ours
  'related',      -- associated but not substitutable
  'no_equivalent' -- explicitly recorded absence: THEY have no term for this
);

CREATE TABLE quantity_mapping (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  quantity_id   bigint NOT NULL REFERENCES quantity(id) ON DELETE CASCADE,
  vocabulary_id bigint NOT NULL REFERENCES vocabulary(id),
  external_term text,                    -- NULL when relation = no_equivalent
  external_iri  text,
  external_unit text,
  relation      mapping_relation NOT NULL,
  note          text,
  verified      boolean NOT NULL DEFAULT false,
  verified_against text,                 -- the file/spec version checked
  UNIQUE (quantity_id, vocabulary_id, external_term)
);
CREATE INDEX ON quantity_mapping (vocabulary_id, relation);

-- Helper so the inserts below stay readable.
CREATE OR REPLACE FUNCTION bd.map_quantity(
  p_quantity text, p_vocab text, p_term text, p_unit text,
  p_relation mapping_relation, p_note text DEFAULT NULL,
  p_verified boolean DEFAULT false, p_against text DEFAULT NULL
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_q bigint; v_v bigint;
BEGIN
  SELECT id INTO v_q FROM bd.quantity   WHERE code = p_quantity;
  SELECT id INTO v_v FROM bd.vocabulary WHERE code = p_vocab;
  IF v_q IS NULL THEN RAISE EXCEPTION 'unknown quantity %', p_quantity; END IF;
  IF v_v IS NULL THEN RAISE EXCEPTION 'unknown vocabulary %', p_vocab; END IF;
  INSERT INTO bd.quantity_mapping
    (quantity_id, vocabulary_id, external_term, external_unit, relation,
     note, verified, verified_against)
  VALUES (v_q, v_v, p_term, p_unit, p_relation, p_note, p_verified, p_against)
  ON CONFLICT DO NOTHING;
END$$;

-- =====================================================================
-- BDF  (verified against the published column list)
-- =====================================================================
SELECT bd.map_quantity('time','bdf','test_time_second','s','exact',
  'BDF required column.', true, 'BDF 1.2.0');
SELECT bd.map_quantity('voltage','bdf','voltage_volt','V','exact',
  'BDF required column.', true, 'BDF 1.2.0');
SELECT bd.map_quantity('current','bdf','current_ampere','A','close',
  'BDF documents positive = charge. This schema does NOT inherit that as an '
  'assumption: test_run.current_sign records the convention per run, because '
  'ionworksdata uses the opposite sign under the same column name.',
  true, 'BDF 1.2.0');
SELECT bd.map_quantity('cycle_number','bdf','cycle_count','1','close',
  'BDF carries a single cycle count. This schema stores cycle_index_as_reported '
  'AND cycle_index_derived, because no two cyclers agree on when a cycle '
  'increments.', true, 'BDF 1.2.0');
SELECT bd.map_quantity('temperature','bdf','ambient_temperature_celsius','degC','narrower',
  'BDF separates ambient / surface / t1..t5. This schema additionally binds each '
  'to a sensor entity with a mount location, which BDF has no concept of.',
  true, 'BDF 1.2.0');
SELECT bd.map_quantity('power','bdf','power_watt','W','exact', NULL, true, 'BDF 1.2.0');
SELECT bd.map_quantity('frequency','bdf','frequency_hertz','Hz','exact', NULL, true, 'BDF 1.2.0');
SELECT bd.map_quantity('impedance_real','bdf','real_impedance_ohm','ohm','exact', NULL, true, 'BDF 1.2.0');
SELECT bd.map_quantity('impedance_imag','bdf','imaginary_impedance_ohm','ohm','exact', NULL, true, 'BDF 1.2.0');
SELECT bd.map_quantity('internal_resistance_ac','bdf','ac_internal_resistance_ohm','ohm','broader',
  'BDF has a single AC resistance column with no frequency, SOC or temperature. '
  'Those are required conditions here, so a BDF value alone cannot be promoted '
  'to an observation without them.', true, 'BDF 1.2.0');
SELECT bd.map_quantity('internal_resistance_dc','bdf','dc_internal_resistance_ohm','ohm','broader',
  'Same issue, worse: DC resistance without a pulse duration is uninterpretable, '
  'and 2 s / 10 s / 18 s / 30 s are all in standard use.', true, 'BDF 1.2.0');
SELECT bd.map_quantity('pressure','bdf','applied_pressure_pa','Pa','narrower',
  'BDF separates ambient / applied / surface pressure.', true, 'BDF 1.2.0');

-- Explicit absences: things BDF has no column for. Recording these is the
-- point of the crosswalk, not an omission from it.
SELECT bd.map_quantity('capacity','bdf',NULL,NULL,'no_equivalent',
  'BDF carries cumulative charge/discharge capacity per record. It has no '
  'concept of a rated capacity under stated conditions - that is metadata, '
  'and the metadata format does not exist yet.', true, 'BDF 1.2.0');
SELECT bd.map_quantity('cycle_life','bdf',NULL,NULL,'no_equivalent',
  'Out of scope for a time-series format.', true, 'BDF 1.2.0');

-- =====================================================================
-- BPX  (verified against the published JSON Schema key names)
-- =====================================================================
SELECT bd.map_quantity('capacity','bpx','Nominal cell capacity [A.h]','A.h','close',
  'BPX nominal capacity carries no rate or temperature; this schema requires them.',
  true, 'BPX 0.4');
SELECT bd.map_quantity('charge_cutoff_voltage','bpx','Upper voltage cut-off [V]','V','exact',
  NULL, true, 'BPX 0.4');
SELECT bd.map_quantity('discharge_cutoff_voltage','bpx','Lower voltage cut-off [V]','V','exact',
  NULL, true, 'BPX 0.4');
SELECT bd.map_quantity('electrode_area','bpx','Electrode area [m2]','m2','close',
  'BPX does not state which area definition; this schema requires area_kind.',
  true, 'BPX 0.4');
SELECT bd.map_quantity('specific_heat_capacity','bpx',
  'Specific heat capacity [J.K-1.kg-1]','J.K-1.kg-1','close',
  'BPX stores a single scalar. Measured specific heat is SOC-dependent (~6% '
  'between 50% and 100% SOC), so this schema requires soc_pct.', true, 'BPX 0.4');
SELECT bd.map_quantity('entropic_coefficient','bpx',
  'Entropic change coefficient [V.K-1]','V.K-1','close',
  'BPX places this per-particle; sign convention is not stated.', true, 'BPX 0.4');
SELECT bd.map_quantity('open_circuit_voltage','bpx','OCP [V]','V','related',
  'BPX OCP is per-electrode (with separate lithiation/delithiation branches and '
  'a hysteresis decay constant); this quantity is full-cell OCV.', true, 'BPX 0.4');
SELECT bd.map_quantity('diffusion_coefficient','bpx','Diffusivity [m2.s-1]','m2.s-1','close',
  NULL, true, 'BPX 0.4');
SELECT bd.map_quantity('internal_resistance_dc','bpx',NULL,NULL,'no_equivalent',
  'BPX is explicitly physics-model-only and has NO equivalent-circuit schema. '
  'There is no ECM standard anywhere in the field. bd.ecm_parameter_point is '
  'this project''s proposal: R0 and RC branches as a lookup surface over '
  '(SOC, temperature, direction, pulse duration) with mandatory fit provenance.',
  true, 'BPX 0.4');

-- =====================================================================
-- EU Battery Passport  (Annex XIII / DIN DKE SPEC 99100 aspect paths)
-- =====================================================================
SELECT bd.map_quantity('capacity','battery_pass',
  'io.BatteryPass.Performance#ratedCapacity','Ah','close',
  'Annex XIII rated capacity. Legally required from 18 Feb 2027.', true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('energy','battery_pass',
  'io.BatteryPass.Performance#ratedEnergy','Wh','close', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('usable_energy','battery_pass',
  'io.BatteryPass.Performance#usableBatteryEnergy','Wh','close', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('nominal_voltage','battery_pass',
  'io.BatteryPass.Performance#nominalVoltage','V','exact', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('round_trip_efficiency','battery_pass',
  'io.BatteryPass.Performance#roundTripEnergyEfficiency','1','close',
  'The Regulation specifies round-trip efficiency at 50% SOC but does not fix '
  'the measurement boundary; condition_set.boundary and auxiliaries_included '
  'capture what the Regulation leaves open.', true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('internal_resistance_dc','battery_pass',
  'io.BatteryPass.Performance#internalResistance','ohm','broader',
  'The Regulation requires "internal resistance (ohms)" with NO method '
  'specified. Expect incomparable values across manufacturers unless the '
  'method is captured separately - which is what this schema does.',
  true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('state_of_health','battery_pass',
  'io.BatteryPass.Performance#stateOfHealth','1','broader',
  'Capacity-based, resistance-based and blended SOH are different numbers.',
  true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('cycle_life','battery_pass',
  'io.BatteryPass.Performance#expectedLifetimeCycles','1','close', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('self_discharge_rate','battery_pass',
  'io.BatteryPass.Performance#selfDischargingRate','1','broader',
  'Four incommensurable metrics are all called self-discharge; the Regulation '
  'does not say which.', true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('carbon_footprint_per_kwh','battery_pass',
  'io.BatteryPass.CarbonFootprint#carbonFootprintTotal','kg CO2e/kWh','exact',
  NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('recycled_content_cobalt','battery_pass',
  'io.BatteryPass.MaterialComposition#recycledContentCobalt','1','exact', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('recycled_content_lithium','battery_pass',
  'io.BatteryPass.MaterialComposition#recycledContentLithium','1','exact', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('recycled_content_nickel','battery_pass',
  'io.BatteryPass.MaterialComposition#recycledContentNickel','1','exact', NULL, true, 'BatteryPass 1.2.0');
SELECT bd.map_quantity('mass','battery_pass',
  'io.BatteryPass.GeneralProductInformation#batteryWeight','kg','close',
  'Mass basis (with or without wrap, terminals, coolant) is unstated in the '
  'Regulation and varies between manufacturers.', true, 'BatteryPass 1.2.0');

-- =====================================================================
-- EMMO. Only labels are recorded here; IRIs are resolved at build time by
-- tools/sync_vocabularies.py against the published TTL, because the IRIs
-- are opaque UUIDs and hand-copying them is how crosswalks rot.
-- =====================================================================
SELECT bd.map_quantity('capacity','emmo_electrochemistry','Capacity',NULL,'broader',
  'IRI resolved at build time from electrochemistry.ttl.', false, NULL);
SELECT bd.map_quantity('open_circuit_voltage','emmo_electrochemistry',
  'OpenCircuitVoltage',NULL,'close', NULL, false, NULL);
SELECT bd.map_quantity('state_of_charge','emmo_battery','StateOfCharge',NULL,'exact',
  NULL, false, NULL);
SELECT bd.map_quantity('cycle_life','emmo_battery','ServiceLife',NULL,'related',
  NULL, false, NULL);

-- ---------------------------------------------------------------------
-- Publishable view
-- ---------------------------------------------------------------------
CREATE VIEW v_crosswalk AS
SELECT q.code            AS quantity,
       q.label,
       q.si_unit,
       q.required_conditions,
       v.code            AS vocabulary,
       v.version         AS vocabulary_version,
       m.external_term,
       COALESCE(m.external_iri,
                CASE WHEN v.namespace IS NOT NULL AND m.external_term IS NOT NULL
                     THEN v.namespace || m.external_term END) AS external_iri,
       m.external_unit,
       m.relation,
       m.verified,
       m.verified_against,
       m.note
  FROM quantity_mapping m
  JOIN quantity q   ON q.id = m.quantity_id
  JOIN vocabulary v ON v.id = m.vocabulary_id;

COMMENT ON VIEW v_crosswalk IS
  'The published crosswalk. Note that relation = no_equivalent rows are '
  'deliberate content: recording that BPX has no ECM schema, or that BDF has '
  'no rated-capacity concept, is more useful than omitting the row.';
