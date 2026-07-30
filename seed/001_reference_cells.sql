-- =====================================================================
-- battery-data : seed/001_reference_cells.sql
--
-- Four cells chosen because each one breaks a naive schema in a
-- different way. If the model holds for these, it holds generally.
--
--   Samsung INR21700-50E  two capacities on one page (0.2C vs 1C)
--   LG INR21700-M50LT     AC and DC resistance 53% apart; no Ah rating,
--                         only Wh; temperature-banded current limits
--   EVE LF280K            rated in constant POWER; clamp force required
--                         for the cycle-life figure; two contradictory
--                         end-of-life definitions on one datasheet
--   Energizer E91         no capacity field exists at all, only service
--                         hours against load, schedule and cutoff
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Organisations
-- ---------------------------------------------------------------------
INSERT INTO organization (uid, name, country, roles) VALUES
  ('org/samsung-sdi','Samsung SDI','KR','{manufacturer}'),
  ('org/lg-energy-solution','LG Energy Solution','KR','{manufacturer}'),
  ('org/eve-energy','EVE Energy','CN','{manufacturer}'),
  ('org/energizer','Energizer Holdings','US','{manufacturer}'),
  ('org/molicel','E-One Moli Energy','TW','{manufacturer}');

INSERT INTO organization_alias (org_id, alias, kind)
SELECT id,'Molicel','trade_name' FROM organization WHERE uid='org/molicel';

-- ---------------------------------------------------------------------
-- Contributor + agent identity for this seed load
-- ---------------------------------------------------------------------
INSERT INTO contributor (uid, display_name, is_bot)
VALUES ('user/seed','battery-data seed loader', true);

-- ---------------------------------------------------------------------
-- Sources. Note is_final = false on the LG sheet: the document itself
-- says "This document is NOT the final version".
-- ---------------------------------------------------------------------
INSERT INTO source (uid, kind, title, publisher_org_id, url, document_number,
                    revision, document_date, is_final, scope_note, license,
                    redistributable, retrieved_at)
SELECT 'src/samsung-50e-v1.0','datasheet',
       'Samsung INR21700-50E Specification',
       (SELECT id FROM organization WHERE uid='org/samsung-sdi'),
       'https://batteryservice.bg/wp-content/uploads/2018/12/INR21700-50E.pdf',
       NULL,'V1.0','2018-07-11', true,
       'Customer-scoped issue observed on some copies (WPG China Inc)',
       'proprietary', false, now();

INSERT INTO source (uid, kind, title, publisher_org_id, url, document_number,
                    revision, document_date, is_final, scope_note, license,
                    redistributable, retrieved_at)
SELECT 'src/lg-m50lt-rev0','datasheet',
       'LG INR21700-M50LT Cell Specification',
       (SELECT id FROM organization WHERE uid='org/lg-energy-solution'),
       'https://www.dnkpower.com/wp-content/uploads/2022/07/LG-INR21700_M50LT_-CELL-SPECIFICATION.pdf',
       '2020-LSD-MBD-b00082','0','2020-08-27', false,
       'Document is stamped: this is NOT the final version',
       'proprietary', false, now();

INSERT INTO source (uid, kind, title, publisher_org_id, url,
                    revision, document_date, is_final, license,
                    redistributable, retrieved_at)
SELECT 'src/eve-lf280k-revb','datasheet',
       'EVE LF280K 280Ah Product Specification',
       (SELECT id FROM organization WHERE uid='org/eve-energy'),
       'https://www.battery-germany.de/wp-content/uploads/2022/02/LF280K-280Ah-Product-Specification-Version-B-2023.pdf',
       'B','2023-02-01', true, 'proprietary', false, now();

INSERT INTO source (uid, kind, title, publisher_org_id, url,
                    document_date, is_final, license, redistributable, retrieved_at)
SELECT 'src/energizer-e91','datasheet',
       'Energizer E91 Alkaline AA Product Datasheet',
       (SELECT id FROM organization WHERE uid='org/energizer'),
       'https://data.energizer.com/pdfs/e91.pdf',
       '2018-01-01', true, 'proprietary', false, now();

-- ---------------------------------------------------------------------
-- Source locations (page/table level)
-- ---------------------------------------------------------------------
INSERT INTO source_location (source_id, page, section, locator_kind, quote)
SELECT id, 3, 'Table 2 - Specification', 'table',
       'Standard Discharge Capacity 4900 mAh (0.2C, 2.5V cut-off); '
       'Rated Discharge Capacity 4753 mAh (1.0C, 2.5V cut-off)'
  FROM source WHERE uid='src/samsung-50e-v1.0';

INSERT INTO source_location (source_id, page, section, locator_kind, quote)
SELECT id, 4, 'Table 3 - Electrical Characteristics', 'table',
       'AC Internal Impedance (1kHz) 15 +/- 6 mOhm; '
       'DC Internal Resistance 23 +/- 6 mOhm (50% SOC, 0.5C, 10s, 25degC)'
  FROM source WHERE uid='src/lg-m50lt-rev0';

INSERT INTO source_location (source_id, page, section, locator_kind, quote)
SELECT id, 2, 'Table 1 - Cell Performance', 'table',
       'Nominal capacity >= 280 Ah (0.5P, 448 W constant power, 25 degC, '
       '3.65 V to 2.5 V); Cycle life 6000 cycles to 80% energy retention '
       'under 300 kgf +/- 20 kgf clamping force'
  FROM source WHERE uid='src/eve-lf280k-revb';

INSERT INTO source_location (source_id, page, section, locator_kind, quote)
SELECT id, 1, 'Constant Current Service Hours', 'table',
       'Service hours to 0.8 V cutoff at 21 degC, continuous discharge'
  FROM source WHERE uid='src/energizer-e91';

-- ---------------------------------------------------------------------
-- Provenance rows: manufacturer claims, table-parsed, human-accepted
-- ---------------------------------------------------------------------
INSERT INTO provenance (source_location_id, evidence, extraction, confidence,
                        review, contributor_id, reviewed_by, reviewed_at)
SELECT sl.id, 'manufacturer_claim', 'table_parse', 0.99, 'accepted',
       c.id, c.id, now()
  FROM source_location sl, contributor c
 WHERE c.uid='user/seed';

-- ---------------------------------------------------------------------
-- Products and revisions
-- ---------------------------------------------------------------------
INSERT INTO product (uid, kind, manufacturer_id, model_number, form_factor,
                     form_factor_code, iec_designation, is_rechargeable, lifecycle)
VALUES
 ('cell/samsung-sdi/inr21700-50e','cell',
   (SELECT id FROM organization WHERE uid='org/samsung-sdi'),
   'INR21700-50E','cylindrical','21700','INR21700', true,'active'),
 ('cell/lg-energy-solution/inr21700-m50lt','cell',
   (SELECT id FROM organization WHERE uid='org/lg-energy-solution'),
   'INR21700-M50LT','cylindrical','21700','INR21700', true,'active'),
 ('cell/eve-energy/lf280k','cell',
   (SELECT id FROM organization WHERE uid='org/eve-energy'),
   'LF280K','prismatic_hardcase','173x72x207', NULL, true,'active'),
 ('primary_cell/energizer/e91','primary_cell',
   (SELECT id FROM organization WHERE uid='org/energizer'),
   'E91','cylindrical','AA','LR6', false,'active');

INSERT INTO product_alias (product_id, alias, kind)
SELECT id,'15A','oem_code' FROM product WHERE uid='primary_cell/energizer/e91';

INSERT INTO product_revision (uid, product_id, source_id, revision_label,
                              effective_date, is_preliminary, review)
SELECT 'rev/samsung-50e/v1.0', p.id, s.id, 'V1.0', '2018-07-11', false, 'accepted'
  FROM product p, source s
 WHERE p.uid='cell/samsung-sdi/inr21700-50e' AND s.uid='src/samsung-50e-v1.0';

INSERT INTO product_revision (uid, product_id, source_id, revision_label,
                              effective_date, is_preliminary, review)
SELECT 'rev/lg-m50lt/rev0', p.id, s.id, 'rev0', '2020-08-27', true, 'accepted'
  FROM product p, source s
 WHERE p.uid='cell/lg-energy-solution/inr21700-m50lt' AND s.uid='src/lg-m50lt-rev0';

INSERT INTO product_revision (uid, product_id, source_id, revision_label,
                              effective_date, is_preliminary, review)
SELECT 'rev/eve-lf280k/revB', p.id, s.id, 'B', '2023-02-01', false, 'accepted'
  FROM product p, source s
 WHERE p.uid='cell/eve-energy/lf280k' AND s.uid='src/eve-lf280k-revb';

INSERT INTO product_revision (uid, product_id, source_id, revision_label, review)
SELECT 'rev/energizer-e91/2018', p.id, s.id, '2018', 'accepted'
  FROM product p, source s
 WHERE p.uid='primary_cell/energizer/e91' AND s.uid='src/energizer-e91';

-- ---------------------------------------------------------------------
-- Chemistry
-- ---------------------------------------------------------------------
INSERT INTO product_chemistry (product_revision_id, designation, cathode_text,
                               anode_text, provenance_id)
SELECT pr.id,'NCA','Ni-based (high Ni)','Graphite',
       (SELECT pv.id FROM provenance pv JOIN source_location sl ON sl.id=pv.source_location_id
         JOIN source s ON s.id=sl.source_id WHERE s.uid='src/samsung-50e-v1.0' LIMIT 1)
  FROM product_revision pr WHERE pr.uid='rev/samsung-50e/v1.0';

INSERT INTO product_chemistry (product_revision_id, designation, cathode_text,
                               anode_text, provenance_id)
SELECT pr.id,'NMC811','Li(NiMnCo)O2','Graphite + Si',
       (SELECT pv.id FROM provenance pv JOIN source_location sl ON sl.id=pv.source_location_id
         JOIN source s ON s.id=sl.source_id WHERE s.uid='src/lg-m50lt-rev0' LIMIT 1)
  FROM product_revision pr WHERE pr.uid='rev/lg-m50lt/rev0';

INSERT INTO product_chemistry (product_revision_id, designation, cathode_text,
                               anode_text, provenance_id)
SELECT pr.id,'LFP','LiFePO4','Graphite',
       (SELECT pv.id FROM provenance pv JOIN source_location sl ON sl.id=pv.source_location_id
         JOIN source s ON s.id=sl.source_id WHERE s.uid='src/eve-lf280k-revb' LIMIT 1)
  FROM product_revision pr WHERE pr.uid='rev/eve-lf280k/revB';

INSERT INTO product_chemistry (product_revision_id, designation, system_string,
                               provenance_id)
SELECT pr.id,'Zn/MnO2','Zinc-Manganese Dioxide (Zn/MnO2)',
       (SELECT pv.id FROM provenance pv JOIN source_location sl ON sl.id=pv.source_location_id
         JOIN source s ON s.id=sl.source_id WHERE s.uid='src/energizer-e91' LIMIT 1)
  FROM product_revision pr WHERE pr.uid='rev/energizer-e91/2018';

-- =====================================================================
-- OBSERVATIONS
-- =====================================================================
-- Helper: resolve (product_revision uid, source uid) -> ids
CREATE OR REPLACE FUNCTION pg_temp.obs(
  p_rev text, p_src text, p_quantity text, p_stat statistic_kind,
  p_value double precision, p_unit text, p_cond jsonb,
  p_tol_plus double precision DEFAULT NULL,
  p_tol_minus double precision DEFAULT NULL,
  p_lower_bound boolean DEFAULT false
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_id bigint;
BEGIN
  INSERT INTO bd.observation
    (product_revision_id, quantity_id, statistic, value_native, unit_native,
     tol_plus, tol_minus, is_lower_bound, condition_set_id, provenance_id)
  SELECT pr.id, q.id, p_stat, p_value, p_unit, p_tol_plus, p_tol_minus,
         p_lower_bound,
         CASE WHEN p_cond IS NULL THEN NULL ELSE bd.intern_conditions(p_cond) END,
         pv.id
    FROM bd.product_revision pr,
         bd.quantity q,
         bd.provenance pv
    JOIN bd.source_location sl ON sl.id = pv.source_location_id
    JOIN bd.source s ON s.id = sl.source_id
   WHERE pr.uid = p_rev AND q.code = p_quantity AND s.uid = p_src
   LIMIT 1
  RETURNING id INTO v_id;
  RETURN v_id;
END$$;

-- ---- Samsung INR21700-50E -------------------------------------------
-- The two capacities. Same page. Different rate. Both true.
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0','capacity',
  'standard', 4900,'mAh',
  '{"temperature_c":25,"temperature_reference":"ambient","rate_value":0.2,
    "rate_unit":"C","rate_reference_capacity_ah":4.9,"voltage_lower_v":2.5,
    "voltage_upper_v":4.2,"direction":"discharge",
    "verbatim":"Standard Discharge Capacity, 0.2C to 2.5V"}'::jsonb);

SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0','capacity',
  'rated', 4753,'mAh',
  '{"temperature_c":25,"temperature_reference":"ambient","rate_value":1.0,
    "rate_unit":"C","rate_reference_capacity_ah":4.9,"voltage_lower_v":2.5,
    "voltage_upper_v":4.2,"direction":"discharge",
    "verbatim":"Rated Discharge Capacity, 1.0C to 2.5V"}'::jsonb);

SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'nominal_voltage','nominal', 3.6,'V', NULL);
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'mass','maximum', 69,'g', NULL);
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'charge_cutoff_voltage','nominal', 4.2,'V', NULL);
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'max_continuous_discharge_current','maximum', 9800,'mA',
  '{"temperature_c":25,"temperature_reference":"cell_surface","direction":"discharge"}'::jsonb);
-- "max non-continuous 14700 mA" - the datasheet gives NO duration. We
-- record that absence explicitly rather than inventing one.
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'max_pulse_discharge_current','maximum', 14700,'mA',
  '{"temperature_c":25,"direction":"discharge",
    "unstated":["pulse_duration_s"],
    "extra":{"note":"Samsung states a 14700 mA non-continuous rating and never gives a duration. Recorded as declared-unstated, not as NULL."},
    "verbatim":"Max. non-continuous discharge current 14700 mA"}'::jsonb);
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'cycle_life','minimum', 500,'cycles',
  '{"temperature_c":23,"dod_pct":100,"rate_value":0.5,"rate_unit":"C",
    "rate_reference_capacity_ah":4.9,
    "extra":{"eol_criterion_pct":80,"eol_reference":"nameplate_capacity"}}'::jsonb);
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'operating_temperature_min','absolute_min', -20,'degC',
  '{"temperature_reference":"cell_surface","direction":"discharge"}'::jsonb);
SELECT pg_temp.obs('rev/samsung-50e/v1.0','src/samsung-50e-v1.0',
  'operating_temperature_max','absolute_max', 60,'degC',
  '{"temperature_reference":"cell_surface","direction":"discharge"}'::jsonb);

-- ---- LG INR21700-M50LT ----------------------------------------------
-- LG publishes NO Ah rating. Only Wh. Recorded as such: no invented Ah.
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0','energy',
  'nominal', 18.2,'Wh',
  '{"temperature_c":25,"rate_value":0.2,"rate_unit":"C",
    "rate_reference_capacity_ah":4.8,"rate_reference_source":"declared_1c_4800mA",
    "voltage_lower_v":2.5,"direction":"discharge"}'::jsonb);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0','energy',
  'minimum', 17.6,'Wh',
  '{"temperature_c":25,"rate_value":0.2,"rate_unit":"C",
    "rate_reference_capacity_ah":4.8,"rate_reference_source":"declared_1c_4800mA",
    "voltage_lower_v":2.5,"direction":"discharge"}'::jsonb);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'nominal_voltage','nominal', 3.69,'V', NULL);

-- The two resistances. 15 vs 23 mOhm. Same cell. Both correct.
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'internal_resistance_ac','typical', 15,'mohm',
  '{"frequency_hz":1000,"soc_pct":50,"soc_method":"unspecified",
    "temperature_c":25,"temperature_reference":"ambient"}'::jsonb, 6, 6);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'internal_resistance_dc','typical', 23,'mohm',
  '{"pulse_duration_s":10,"pulse_current_a":2.4,"soc_pct":50,
    "soc_method":"coulomb_counted","temperature_c":25,
    "temperature_reference":"ambient","direction":"discharge",
    "rate_value":0.5,"rate_unit":"C","rate_reference_capacity_ah":4.8}'::jsonb, 6, 6);

-- Temperature-banded current limits: three rows, not one scalar.
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'max_continuous_discharge_current','maximum', 2.4,'A',
  '{"temperature_c":-5,"temperature_reference":"ambient","direction":"discharge",
    "extra":{"band_min_c":-20,"band_max_c":10}}'::jsonb);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'max_continuous_discharge_current','maximum', 14.4,'A',
  '{"temperature_c":17,"temperature_reference":"ambient","direction":"discharge",
    "extra":{"band_min_c":10,"band_max_c":25}}'::jsonb);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'max_continuous_discharge_current','maximum', 7.2,'A',
  '{"temperature_c":40,"temperature_reference":"ambient","direction":"discharge",
    "extra":{"band_min_c":25,"band_max_c":55}}'::jsonb);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'mass','typical', 68.2,'g', NULL, 1.0, 1.0);
SELECT pg_temp.obs('rev/lg-m50lt/rev0','src/lg-m50lt-rev0',
  'cycle_life','minimum', 1000,'cycles',
  '{"temperature_c":25,"dod_pct":100,"rate_value":0.5,"rate_unit":"C",
    "rate_reference_capacity_ah":4.8,
    "extra":{"eol_criterion_pct":80,"eol_reference":"measured_bol_energy",
             "note":"LG defines EOL on ENERGY not capacity"}}'::jsonb);

-- ---- EVE LF280K ------------------------------------------------------
-- Rated in constant POWER. rate_unit = 'P', not 'C'.
SELECT pg_temp.obs('rev/eve-lf280k/revB','src/eve-lf280k-revb','capacity',
  'nominal', 280,'Ah',
  '{"temperature_c":25,"temperature_reference":"ambient","rate_value":0.5,
    "rate_unit":"P","voltage_upper_v":3.65,"voltage_lower_v":2.5,
    "direction":"discharge","constraint_mode":"constant_force",
    "clamp_force_n":2942,
    "verbatim":"0.5P (448 W constant power), 3.65 V to 2.5 V, 25 degC"}'::jsonb,
  NULL, NULL, true);
SELECT pg_temp.obs('rev/eve-lf280k/revB','src/eve-lf280k-revb',
  'nominal_voltage','nominal', 3.2,'V', NULL);
SELECT pg_temp.obs('rev/eve-lf280k/revB','src/eve-lf280k-revb',
  'internal_resistance_ac','maximum', 0.25,'mohm',
  '{"frequency_hz":1000,"soc_pct":40,"temperature_c":25}'::jsonb);
-- Cycle life. Requires clamp force or it is not reproducible.
SELECT pg_temp.obs('rev/eve-lf280k/revB','src/eve-lf280k-revb',
  'cycle_life','minimum', 6000,'cycles',
  '{"temperature_c":25,"dod_pct":100,"rate_value":0.5,"rate_unit":"P",
    "constraint_mode":"constant_force","clamp_force_n":2942,
    "extra":{"clamp_force_kgf":300,"clamp_tolerance_kgf":20,
             "eol_criterion_pct":80,"eol_reference":"measured_bol_energy"}}'::jsonb);
-- The SECOND, contradictory end-of-life definition on the same datasheet.
SELECT pg_temp.obs('rev/eve-lf280k/revB','src/eve-lf280k-revb',
  'capacity_retention','minimum', 0.60,'1',
  '{"cycle_index":6000,"temperature_c":25,"rate_value":0.5,"rate_unit":"P",
    "extra":{"definition":"product_end_of_life",
             "note":"same datasheet also defines product EOL as IR > 150% of initial OR capacity < 60% of nominal, which contradicts the 80% figure used for the 6000-cycle claim"}}'::jsonb);
SELECT pg_temp.obs('rev/eve-lf280k/revB','src/eve-lf280k-revb',
  'round_trip_efficiency','minimum', 0.935,'1',
  '{"boundary":"cell","rate_value":0.5,"rate_unit":"P","temperature_c":25}'::jsonb);

-- ---- Energizer E91 ---------------------------------------------------
-- No capacity field exists. Service hours only.
SELECT pg_temp.obs('rev/energizer-e91/2018','src/energizer-e91',
  'service_life_hours','typical', 40.6,'h',
  '{"load_value":25,"load_unit":"mA","duty_schedule":"continuous",
    "cutoff_voltage_v":0.8,"temperature_c":21}'::jsonb);
SELECT pg_temp.obs('rev/energizer-e91/2018','src/energizer-e91',
  'service_life_hours','typical', 6.4,'h',
  '{"load_value":250,"load_unit":"mA","duty_schedule":"continuous",
    "cutoff_voltage_v":0.8,"temperature_c":21}'::jsonb);
SELECT pg_temp.obs('rev/energizer-e91/2018','src/energizer-e91',
  'nominal_voltage','nominal', 1.5,'V', NULL);
SELECT pg_temp.obs('rev/energizer-e91/2018','src/energizer-e91',
  'mass','typical', 23.0,'g', NULL);
SELECT pg_temp.obs('rev/energizer-e91/2018','src/energizer-e91',
  'internal_resistance_ac','typical', 225,'mohm',
  '{"frequency_hz":1000,"soc_pct":100,"temperature_c":21,
    "extra":{"stated_range_mohm":[150,300],"note":"datasheet gives a range"}}'::jsonb);

-- ---------------------------------------------------------------------
-- A rate-capability curve, which no scalar column can hold.
-- ---------------------------------------------------------------------
INSERT INTO curve (uid, product_revision_id, curve_kind, x_quantity_id,
                   y_quantity_id, x_unit, y_unit, x_values, y_values,
                   condition_set_id, provenance_id)
SELECT 'curve/lg-m50lt/rate-capability',
       pr.id, 'rate_capability',
       (SELECT id FROM quantity WHERE code='current'),
       (SELECT id FROM quantity WHERE code='capacity'),
       'A','Ah',
       ARRAY[0.96, 4.8, 9.6, 14.4],
       ARRAY[4.85, 4.80, 4.72, 4.60],
       bd.intern_conditions('{"temperature_c":25,"voltage_lower_v":2.5,
                              "direction":"discharge"}'::jsonb),
       pv.id
  FROM product_revision pr, provenance pv
  JOIN source_location sl ON sl.id=pv.source_location_id
  JOIN source s ON s.id=sl.source_id
 WHERE pr.uid='rev/lg-m50lt/rev0' AND s.uid='src/lg-m50lt-rev0' LIMIT 1;
