-- =====================================================================
-- battery-data : 140_views.sql
--
-- The query layer. The normalised model is deliberately strict, which
-- makes it verbose to query directly; these views are the ergonomic
-- surface that engineering-selection, the public API and the graph
-- projection all build on.
--
-- Nothing here invents data. Every view carries provenance through, so a
-- result row can always be traced back to a page of a document.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Latest accepted revision per product. Datasheets get revised and
-- customer/region-scoped variants coexist, so "the spec" is a choice,
-- and this view makes that choice explicit and overridable.
-- ---------------------------------------------------------------------
CREATE VIEW v_current_revision AS
SELECT DISTINCT ON (pr.product_id)
       pr.id                AS product_revision_id,
       pr.product_id,
       pr.uid               AS revision_uid,
       pr.revision_label,
       pr.effective_date,
       pr.region_scope,
       pr.customer_scope,
       pr.is_preliminary,
       s.uid                AS source_uid,
       s.document_date
  FROM product_revision pr
  JOIN source s ON s.id = pr.source_id
 WHERE pr.review <> 'rejected'
 ORDER BY pr.product_id,
          pr.is_preliminary ASC,                       -- prefer final over tentative
          COALESCE(pr.effective_date, s.document_date) DESC NULLS LAST,
          pr.id DESC;

-- ---------------------------------------------------------------------
-- Flattened observation view. One row per stated fact, with its
-- conditions spelled out. This is the workhorse.
-- ---------------------------------------------------------------------
CREATE VIEW v_observation AS
SELECT o.id                        AS observation_id,
       p.uid                       AS product_uid,
       p.model_number,
       org.name                    AS manufacturer,
       p.kind                      AS product_kind,
       p.form_factor,
       p.form_factor_code,
       pr.id                       AS product_revision_id,
       pr.revision_label,
       q.code                      AS quantity,
       q.label                     AS quantity_label,
       o.statistic,
       o.value_native,
       o.unit_native,
       o.value_si,
       q.si_unit,
       o.tol_plus, o.tol_minus,
       o.value_min, o.value_max,
       o.is_lower_bound, o.is_upper_bound,
       o.value_text,
       -- conditions, inlined for readability
       c.temperature_c,
       c.temperature_reference,
       c.rate_value, c.rate_unit, c.rate_reference_capacity_ah,
       c.direction,
       c.voltage_upper_v, c.voltage_lower_v,
       c.soc_pct, c.soc_method,
       c.dod_pct,
       c.pulse_duration_s, c.pulse_current_a,
       c.frequency_hz,
       c.cycle_index,
       c.duration_s,
       c.boundary,
       c.constraint_mode, c.clamp_force_n,
       c.verbatim                  AS condition_verbatim,
       -- provenance, always carried
       pv.evidence,
       pv.extraction,
       pv.confidence,
       pv.review,
       src.uid                     AS source_uid,
       src.title                   AS source_title,
       src.url                     AS source_url,
       src.doi,
       src.revision                AS source_revision,
       sl.page, sl.section, sl.quote,
       o.access_tier
  FROM observation o
  JOIN quantity q          ON q.id = o.quantity_id
  JOIN provenance pv       ON pv.id = o.provenance_id
  JOIN source_location sl  ON sl.id = pv.source_location_id
  JOIN source src          ON src.id = sl.source_id
  LEFT JOIN condition_set c   ON c.id = o.condition_set_id
  LEFT JOIN product_revision pr ON pr.id = o.product_revision_id
  LEFT JOIN product p         ON p.id = pr.product_id
  LEFT JOIN organization org  ON org.id = p.manufacturer_id;

-- ---------------------------------------------------------------------
-- ENGINEERING SELECTION.
--
-- One row per cell revision with the specs an engineer filters on. Note
-- what this view does NOT do: it does not collapse the multiple
-- capacities a datasheet states into one number. It exposes the best
-- capacity at or below 0.2C (the "standard" figure) and separately the
-- capacity nearest 1C (the "rated" figure), because those are different
-- questions and vendors answer them with different numbers.
-- ---------------------------------------------------------------------
CREATE VIEW v_cell_selection AS
WITH cells AS (
  SELECT cr.product_revision_id, cr.product_id, cr.revision_label
    FROM v_current_revision cr
    JOIN product p ON p.id = cr.product_id
   WHERE p.kind = 'cell'
),
cap_low AS (   -- capacity at low rate: the "standard"/"typical" figure
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si/3600.0 AS capacity_ah,
         c.rate_value, c.rate_unit, c.temperature_c, o.statistic
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='capacity'
    JOIN condition_set c ON c.id=o.condition_set_id
   WHERE c.rate_unit='C' AND c.rate_value <= 0.3
   ORDER BY o.product_revision_id, c.rate_value ASC, o.value_si DESC
),
cap_1c AS (    -- capacity nearest 1C: the "rated" figure
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si/3600.0 AS capacity_ah,
         c.rate_value, c.temperature_c, o.statistic
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='capacity'
    JOIN condition_set c ON c.id=o.condition_set_id
   WHERE c.rate_unit='C'
   ORDER BY o.product_revision_id, abs(c.rate_value - 1.0) ASC
),
disch AS (     -- max continuous discharge current, room temperature band
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS max_cont_discharge_a,
         c.temperature_c
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='max_continuous_discharge_current'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id,
            abs(COALESCE(c.temperature_c,25) - 25) ASC, o.value_si DESC
),
mass AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS mass_kg, o.statistic
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='mass'
   ORDER BY o.product_revision_id,
            (o.statistic='typical') DESC, o.id
),
tmin AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si-273.15 AS discharge_temp_min_c
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='operating_temperature_min'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   WHERE COALESCE(c.direction,'discharge')='discharge'
   ORDER BY o.product_revision_id, o.value_si ASC
),
chg AS (      -- max continuous charge current, room temperature band
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS max_cont_charge_a
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='max_continuous_charge_current'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id,
            abs(COALESCE(c.temperature_c,25) - 25) ASC, o.value_si DESC
),
stdchg AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS standard_charge_a
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='standard_charge_current'
   ORDER BY o.product_revision_id, o.id
),
-- Resistance travels with its method. The row nearest 50% SOC and 25 C leads;
-- the pulse duration or frequency comes with it because without them the
-- number is a rumour (docs/02-conventions.md section 7 and 8).
dcir AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si*1000 AS dcir_mohm,
         c.pulse_duration_s AS dcir_pulse_s, c.soc_pct AS dcir_soc_pct,
         c.temperature_c AS dcir_temp_c
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='internal_resistance_dc'
    JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id,
            abs(COALESCE(c.soc_pct,50) - 50) ASC,
            abs(COALESCE(c.temperature_c,25) - 25) ASC, o.id
),
acir AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si*1000 AS acir_mohm,
         c.frequency_hz AS acir_frequency_hz, c.soc_pct AS acir_soc_pct,
         c.temperature_c AS acir_temp_c
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='internal_resistance_ac'
    JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id,
            abs(COALESCE(c.soc_pct,50) - 50) ASC,
            abs(COALESCE(c.temperature_c,25) - 25) ASC, o.id
),
-- Cycle life is a function, not a number: lead with the claim that states
-- the most of its conditions and carry those conditions alongside.
life AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS cycle_life_cycles,
         c.dod_pct AS cycle_life_dod_pct, c.rate_value AS cycle_life_rate_value,
         c.rate_unit::text AS cycle_life_rate_unit, c.temperature_c AS cycle_life_temp_c
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='cycle_life'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id,
            ((c.temperature_c IS NOT NULL)::int + (c.dod_pct IS NOT NULL)::int
             + (c.rate_value IS NOT NULL)::int) DESC, o.value_si DESC
),
tmax AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si-273.15 AS discharge_temp_max_c
    FROM observation o
    JOIN quantity q ON q.id=o.quantity_id AND q.code='operating_temperature_max'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   WHERE COALESCE(c.direction,'discharge')='discharge'
   ORDER BY o.product_revision_id, o.value_si DESC
),
vchg AS (
  SELECT DISTINCT ON (o.product_revision_id) o.product_revision_id, o.value_si AS charge_cutoff_v
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='charge_cutoff_voltage'
   ORDER BY o.product_revision_id, o.id
),
vdis AS (
  SELECT DISTINCT ON (o.product_revision_id) o.product_revision_id, o.value_si AS discharge_cutoff_v
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='discharge_cutoff_voltage'
   ORDER BY o.product_revision_id, o.id
),
chem AS (
  SELECT product_revision_id, designation, cathode_text, anode_text
    FROM product_chemistry
)
SELECT p.uid                     AS product_uid,
       org.name                  AS manufacturer,
       p.model_number,
       p.form_factor,
       p.form_factor_code,
       chem.designation          AS chemistry,
       chem.cathode_text, chem.anode_text,
       cl.capacity_ah            AS capacity_low_rate_ah,
       cl.rate_value             AS capacity_low_rate_c,
       cl.statistic              AS capacity_low_rate_statistic,
       c1.capacity_ah            AS capacity_1c_ah,
       c1.rate_value             AS capacity_1c_actual_rate,
       d.max_cont_discharge_a,
       -- derived, and flagged as such by name
       CASE WHEN m.mass_kg > 0 AND cl.capacity_ah IS NOT NULL
            THEN (cl.capacity_ah * nv.value_si) / m.mass_kg
       END                       AS specific_energy_wh_per_kg_derived,
       m.mass_kg,
       nv.value_si               AS nominal_voltage_v,
       t.discharge_temp_min_c,
       tx.discharge_temp_max_c,
       g.max_cont_charge_a,
       sc.standard_charge_a,
       vc.charge_cutoff_v,
       vd.discharge_cutoff_v,
       r.dcir_mohm, r.dcir_pulse_s, r.dcir_soc_pct, r.dcir_temp_c,
       a.acir_mohm, a.acir_frequency_hz, a.acir_soc_pct, a.acir_temp_c,
       l.cycle_life_cycles, l.cycle_life_dod_pct, l.cycle_life_rate_value,
       l.cycle_life_rate_unit, l.cycle_life_temp_c,
       cr.revision_label,
       cr.product_revision_id
  FROM cells cr
  JOIN product p       ON p.id  = cr.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  LEFT JOIN cap_low cl ON cl.product_revision_id = cr.product_revision_id
  LEFT JOIN cap_1c  c1 ON c1.product_revision_id = cr.product_revision_id
  LEFT JOIN disch   d  ON d.product_revision_id  = cr.product_revision_id
  LEFT JOIN mass    m  ON m.product_revision_id  = cr.product_revision_id
  LEFT JOIN tmin    t  ON t.product_revision_id  = cr.product_revision_id
  LEFT JOIN tmax    tx ON tx.product_revision_id = cr.product_revision_id
  LEFT JOIN chg     g  ON g.product_revision_id  = cr.product_revision_id
  LEFT JOIN stdchg  sc ON sc.product_revision_id = cr.product_revision_id
  LEFT JOIN vchg    vc ON vc.product_revision_id = cr.product_revision_id
  LEFT JOIN vdis    vd ON vd.product_revision_id = cr.product_revision_id
  LEFT JOIN dcir    r  ON r.product_revision_id  = cr.product_revision_id
  LEFT JOIN acir    a  ON a.product_revision_id  = cr.product_revision_id
  LEFT JOIN life    l  ON l.product_revision_id  = cr.product_revision_id
  LEFT JOIN chem       ON chem.product_revision_id = cr.product_revision_id
  LEFT JOIN LATERAL (
        SELECT o.value_si FROM observation o
          JOIN quantity q ON q.id=o.quantity_id AND q.code='nominal_voltage'
         WHERE o.product_revision_id = cr.product_revision_id LIMIT 1
  ) nv ON true;

COMMENT ON VIEW v_cell_selection IS
  'Engineering selection surface. Deliberately exposes both the low-rate '
  'and the ~1C capacity rather than collapsing them: on the Samsung '
  'INR21700-50E those are 4900 mAh and 4753 mAh and picking one silently '
  'is how comparison tables become wrong.';

-- ---------------------------------------------------------------------
-- COMPONENT SELECTION. The hardware around the cell, selected on the
-- figures its datasheet is read for. Every figure keeps the condition it
-- was stated at: a breaking capacity is nothing without its circuit
-- voltage and time constant, a rated current without its ambient.
-- ---------------------------------------------------------------------
CREATE VIEW v_component_selection AS
WITH comps AS (
  SELECT cr.product_revision_id, cr.product_id, cr.revision_label
    FROM v_current_revision cr
    JOIN product p ON p.id = cr.product_id
   WHERE p.kind = 'component'
),
one AS (   -- first stated value of a conditionless quantity
  SELECT DISTINCT ON (o.product_revision_id, q.code)
         o.product_revision_id, q.code, o.value_si
    FROM observation o JOIN quantity q ON q.id = o.quantity_id
   WHERE q.code IN ('rated_voltage','coil_voltage','coil_power','i2t_prearcing',
                    'mechanical_endurance','input_voltage_min','input_voltage_max',
                    'output_voltage_min','output_voltage_max','switching_frequency',
                    'mass','short_circuit_current')
   ORDER BY o.product_revision_id, q.code, o.id
),
rated AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS rated_current_a, c.temperature_c AS rated_current_temp_c
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='rated_current'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id, abs(COALESCE(c.temperature_c,25) - 25) ASC, o.value_si DESC
),
breaking AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS breaking_capacity_a,
         c.circuit_voltage_v AS breaking_circuit_v, c.time_constant_ms AS breaking_time_constant_ms
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='breaking_capacity'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id, o.value_si DESC
),
contact AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si*1000 AS contact_resistance_mohm,
         c.rate_value AS contact_test_current_a
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='contact_resistance'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id, o.id
),
eff AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS efficiency,
         c.circuit_voltage_v AS efficiency_input_v, c.rate_value AS efficiency_load_value,
         c.rate_unit::text AS efficiency_load_unit
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='conversion_efficiency'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id, o.value_si DESC
),
iout AS (
  SELECT DISTINCT ON (o.product_revision_id)
         o.product_revision_id, o.value_si AS output_current_a, c.temperature_c AS output_current_temp_c
    FROM observation o JOIN quantity q ON q.id=o.quantity_id AND q.code='output_current'
    LEFT JOIN condition_set c ON c.id=o.condition_set_id
   ORDER BY o.product_revision_id, abs(COALESCE(c.temperature_c,25) - 25) ASC, o.value_si DESC
)
SELECT p.uid                          AS product_uid,
       org.name                       AS manufacturer,
       p.model_number,
       p.component_kind::text         AS component_kind,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='rated_voltage')     AS rated_voltage_v,
       r.rated_current_a, r.rated_current_temp_c,
       b.breaking_capacity_a, b.breaking_circuit_v, b.breaking_time_constant_ms,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='i2t_prearcing')     AS i2t_prearcing_a2s,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='coil_voltage')      AS coil_voltage_v,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='coil_power')        AS coil_power_w,
       ct.contact_resistance_mohm, ct.contact_test_current_a,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='mechanical_endurance') AS mechanical_endurance,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='input_voltage_min') AS input_voltage_min_v,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='input_voltage_max') AS input_voltage_max_v,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='output_voltage_min') AS output_voltage_min_v,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='output_voltage_max') AS output_voltage_max_v,
       io.output_current_a, io.output_current_temp_c,
       e.efficiency, e.efficiency_input_v, e.efficiency_load_value, e.efficiency_load_unit,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='switching_frequency') AS switching_frequency_hz,
       (SELECT value_si FROM one WHERE one.product_revision_id=cr.product_revision_id AND code='mass')              AS mass_kg,
       cr.revision_label,
       cr.product_revision_id
  FROM comps cr
  JOIN product p        ON p.id = cr.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  LEFT JOIN rated    r  ON r.product_revision_id  = cr.product_revision_id
  LEFT JOIN breaking b  ON b.product_revision_id  = cr.product_revision_id
  LEFT JOIN contact  ct ON ct.product_revision_id = cr.product_revision_id
  LEFT JOIN eff      e  ON e.product_revision_id  = cr.product_revision_id
  LEFT JOIN iout     io ON io.product_revision_id = cr.product_revision_id;

COMMENT ON VIEW v_component_selection IS
  'Selection surface for the hardware around the cell. Each figure carries '
  'the condition it was stated at, because a breaking capacity without its '
  'circuit voltage and L/R, or a rated current without its ambient, is not '
  'a comparable number.';

-- ---------------------------------------------------------------------
-- Resistance, exploded by method. Never presented as a single number.
-- ---------------------------------------------------------------------
CREATE VIEW v_resistance AS
SELECT p.uid AS product_uid, org.name AS manufacturer, p.model_number,
       q.code AS method_family,
       CASE WHEN q.code='internal_resistance_ac'
            THEN 'AC @ ' || COALESCE(c.frequency_hz::text,'?') || ' Hz'
            ELSE 'DC pulse ' || COALESCE(c.pulse_duration_s::text,'?') || ' s'
       END                        AS method,
       o.value_si * 1000          AS resistance_mohm,
       c.frequency_hz,
       c.pulse_duration_s,
       c.pulse_current_a,
       c.direction,
       c.soc_pct,
       c.temperature_c,
       o.statistic,
       pv.evidence,
       src.uid AS source_uid
  FROM observation o
  JOIN quantity q ON q.id=o.quantity_id
   AND q.code IN ('internal_resistance_ac','internal_resistance_dc')
  JOIN condition_set c ON c.id=o.condition_set_id
  JOIN provenance pv ON pv.id=o.provenance_id
  JOIN source_location sl ON sl.id=pv.source_location_id
  JOIN source src ON src.id=sl.source_id
  JOIN product_revision pr ON pr.id=o.product_revision_id
  JOIN product p ON p.id=pr.product_id
  JOIN organization org ON org.id=p.manufacturer_id;

-- ---------------------------------------------------------------------
-- Test campaign overview, including the segment structure that makes
-- aging data interpretable.
-- ---------------------------------------------------------------------
CREATE VIEW v_test_run AS
SELECT tr.uid                AS run_uid,
       tr.test_kind,
       cam.uid               AS campaign_uid,
       cam.title             AS campaign_title,
       p.uid                 AS product_uid,
       p.model_number,
       org.name              AS manufacturer,
       pu.uid                AS unit_uid,
       pu.serial_number,
       pu.prior_cycle_count,
       proto.uid             AS protocol_uid,
       proto.name            AS protocol_name,
       std.uid               AS standard_uid,
       tr.started_at, tr.ended_at,
       tr.current_sign, tr.capacity_accum, tr.cycle_definition,
       tr.c_rate_reference_capacity_ah, tr.c_rate_reference_source,
       tr.dcir_extraction, tr.constraint_mode, tr.clamp_force_n,
       tr.source_format, tr.parser_name, tr.parser_version,
       (SELECT count(*) FROM test_segment s WHERE s.test_run_id=tr.id) AS n_segments,
       (SELECT count(*) FROM test_segment s WHERE s.test_run_id=tr.id
         AND s.role IN ('baseline_rpt','periodic_rpt','final_rpt'))    AS n_rpts,
       (SELECT count(*) FROM dataset d WHERE d.test_run_id=tr.id)      AS n_datasets,
       (SELECT count(*) FROM eis_spectrum e WHERE e.test_run_id=tr.id) AS n_eis_spectra,
       (SELECT count(*) FROM cycle_summary cs WHERE cs.test_run_id=tr.id) AS n_cycles,
       tr.quality_flags,
       tr.access_tier
  FROM test_run tr
  JOIN product_unit pu ON pu.id = tr.product_unit_id
  JOIN product_revision pr ON pr.id = pu.product_revision_id
  JOIN product p ON p.id = pr.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  LEFT JOIN campaign cam ON cam.id = tr.campaign_id
  LEFT JOIN protocol proto ON proto.id = tr.protocol_id
  LEFT JOIN standard std ON std.id = proto.standard_id;

-- ---------------------------------------------------------------------
-- DATA QUALITY. A database that only reports what it has is misleading;
-- this reports what it is missing, per product.
-- ---------------------------------------------------------------------
CREATE VIEW v_completeness AS
WITH wanted(code) AS (
  VALUES ('capacity'),('nominal_voltage'),('mass'),
         ('max_continuous_discharge_current'),('internal_resistance_ac'),
         ('internal_resistance_dc'),('cycle_life'),
         ('operating_temperature_min'),('operating_temperature_max'),
         ('energy'),('charge_cutoff_voltage'),('discharge_cutoff_voltage')
)
SELECT p.uid AS product_uid, org.name AS manufacturer, p.model_number, p.kind,
       count(DISTINCT o.quantity_id) FILTER (WHERE q.code IS NOT NULL) AS fields_present,
       (SELECT count(*) FROM wanted)                                   AS fields_tracked,
       array_agg(DISTINCT w.code) FILTER (
         WHERE NOT EXISTS (
           SELECT 1 FROM observation o2
             JOIN quantity q2 ON q2.id=o2.quantity_id AND q2.code=w.code
            WHERE o2.product_revision_id = cr.product_revision_id))     AS missing_fields,
       count(DISTINCT tr.id)                                            AS n_test_runs,
       bool_or(pv.evidence = 'measured')                                AS has_measured_data,
       bool_or(pv.evidence = 'inferred_by_agent'
               AND pv.review <> 'accepted')                             AS has_unreviewed_agent_data
  FROM v_current_revision cr
  JOIN product p ON p.id = cr.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  CROSS JOIN wanted w
  LEFT JOIN observation o ON o.product_revision_id = cr.product_revision_id
  LEFT JOIN quantity q ON q.id = o.quantity_id
  LEFT JOIN provenance pv ON pv.id = o.provenance_id
  LEFT JOIN product_unit pu ON pu.product_revision_id = cr.product_revision_id
  LEFT JOIN test_run tr ON tr.product_unit_id = pu.id
 GROUP BY p.uid, org.name, p.model_number, p.kind, cr.product_revision_id;

-- ---------------------------------------------------------------------
-- Contradiction detector. Two sources disagreeing about the same
-- quantity under the same conditions is a first-class finding, not an
-- error to be silently resolved by last-write-wins.
-- ---------------------------------------------------------------------
CREATE VIEW v_contradiction AS
SELECT p.uid AS product_uid, p.model_number, q.code AS quantity,
       o.statistic,
       o.condition_set_id,
       count(*)                       AS n_claims,
       min(o.value_si)                AS min_value_si,
       max(o.value_si)                AS max_value_si,
       CASE WHEN min(o.value_si) > 0
            THEN (max(o.value_si)-min(o.value_si))/min(o.value_si) END AS spread_fraction,
       array_agg(DISTINCT src.uid)    AS sources,
       array_agg(DISTINCT pv.evidence::text) AS evidence_classes
  FROM observation o
  JOIN quantity q ON q.id=o.quantity_id
  JOIN provenance pv ON pv.id=o.provenance_id
  JOIN source_location sl ON sl.id=pv.source_location_id
  JOIN source src ON src.id=sl.source_id
  JOIN product_revision pr ON pr.id=o.product_revision_id
  JOIN product p ON p.id=pr.product_id
 WHERE o.value_si IS NOT NULL
 GROUP BY p.uid, p.model_number, q.code, o.statistic, o.condition_set_id
HAVING count(DISTINCT src.id) > 1
   AND (max(o.value_si)-min(o.value_si)) / NULLIF(min(o.value_si),0) > 0.02;

COMMENT ON VIEW v_contradiction IS
  'Same quantity, same statistic, same conditions, different sources, '
  'values more than 2% apart. Surfacing these is the point: a database '
  'that hides disagreement is less useful than one that names it.';
