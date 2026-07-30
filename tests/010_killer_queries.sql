-- =====================================================================
-- battery-data : tests/010_killer_queries.sql
--
-- These are the questions the database exists to answer. Each one is
-- also a regression test: if a schema change breaks the answer, it
-- breaks here.
-- =====================================================================

\pset border 2
\pset format aligned

\echo
\echo '### Q1  The same cell has two capacities. Both are preserved.'
\echo '###     A naive schema keeps one and silently loses the other.'
SELECT model_number, statistic, value_native||' '||unit_native AS capacity,
       rate_value||' '||rate_unit AS rate, temperature_c AS temp_c,
       voltage_lower_v AS cutoff_v
  FROM bd.v_observation
 WHERE quantity='capacity' AND model_number='INR21700-50E'
 ORDER BY rate_value;

\echo
\echo '### Q2  Internal resistance is never one number.'
\echo '###     LG publishes 15 mOhm AC and 23 mOhm DC for the same cell.'
SELECT model_number, method, resistance_mohm, soc_pct, temperature_c AS temp_c,
       pulse_duration_s AS pulse_s
  FROM bd.v_resistance
 ORDER BY manufacturer, method;

\echo
\echo '### Q3  ENGINEERING SELECTION - the primary use case.'
\echo '###     21700 cells, >= 4.5 Ah at low rate, >= 9 A continuous.'
SELECT manufacturer, model_number, chemistry,
       round(capacity_low_rate_ah::numeric,3)  AS cap_low_ah,
       capacity_low_rate_c                     AS at_c_rate,
       round(capacity_1c_ah::numeric,3)        AS cap_1c_ah,
       round(max_cont_discharge_a::numeric,1)  AS max_cont_a,
       round(specific_energy_wh_per_kg_derived::numeric,1) AS wh_per_kg,
       discharge_temp_min_c                    AS min_temp_c
  FROM bd.v_cell_selection
 WHERE form_factor_code = '21700'
   AND capacity_low_rate_ah >= 4.5
   AND max_cont_discharge_a >= 9
 ORDER BY capacity_low_rate_ah DESC;

\echo
\echo '### Q4  Temperature-banded current limits are a surface, not a scalar.'
\echo '###     LG M50LT: three different max discharge currents.'
SELECT model_number,
       (condition_verbatim IS NOT NULL) AS has_verbatim,
       value_native||' '||unit_native AS max_discharge,
       temperature_c AS measured_at_c
  FROM bd.v_observation
 WHERE quantity='max_continuous_discharge_current'
   AND model_number='INR21700-M50LT'
 ORDER BY temperature_c;

\echo
\echo '### Q5  Rate expressed as constant POWER, not current.'
\echo '###     EVE rates the LF280K at 0.5P. Not convertible to a C-rate.'
SELECT model_number, value_native||' '||unit_native AS capacity,
       rate_value||' '||rate_unit AS rate, is_lower_bound,
       condition_verbatim
  FROM bd.v_observation
 WHERE quantity='capacity' AND model_number='LF280K';

\echo
\echo '### Q6  A primary cell has no capacity at all - only service hours.'
SELECT model_number, quantity, value_native||' '||unit_native AS value,
       (SELECT load_value||' '||load_unit FROM bd.condition_set c
         WHERE c.id = (SELECT condition_set_id FROM bd.observation o2
                        WHERE o2.id = v.observation_id)) AS load,
       (SELECT duty_schedule FROM bd.condition_set c
         WHERE c.id = (SELECT condition_set_id FROM bd.observation o2
                        WHERE o2.id = v.observation_id)) AS schedule
  FROM bd.v_observation v
 WHERE model_number='E91' AND quantity='service_life_hours';

\echo
\echo '### Q7  DECLARED ABSENCE. Samsung publishes a pulse current with'
\echo '###     no duration. The omission is recorded, not hidden as NULL.'
SELECT v.model_number, v.quantity,
       v.value_native||' '||v.unit_native AS value,
       c.unstated                          AS source_does_not_state,
       c.extra->>'note'                    AS note
  FROM bd.v_observation v
  JOIN bd.observation o ON o.id = v.observation_id
  JOIN bd.condition_set c ON c.id = o.condition_set_id
 WHERE cardinality(c.unstated) > 0;

\echo
\echo '### Q8  Every value traces to a page and a quote. Non-negotiable.'
SELECT model_number, quantity, value_native||' '||unit_native AS value,
       evidence, source_revision AS rev, page,
       left(quote, 58)||'...' AS supporting_quote
  FROM bd.v_observation
 WHERE quantity IN ('capacity','internal_resistance_dc')
 ORDER BY model_number LIMIT 5;

\echo
\echo '### Q9  DATA COMPLETENESS - report what is missing, not just what is there.'
SELECT manufacturer, model_number, fields_present, fields_tracked,
       array_length(missing_fields,1) AS n_missing,
       array_to_string(missing_fields[1:3], ', ')||'...' AS sample_missing
  FROM bd.v_completeness
 ORDER BY fields_present DESC;

\echo
\echo '### Q10 GRAPH TRAVERSAL - multi-hop with no graph extension needed.'
SELECT bd_graph.refresh();
SELECT label, uid, title, depth
  FROM bd_graph.reachable(
         (SELECT node_key FROM bd_graph.node
           WHERE uid='cell/lg-energy-solution/inr21700-m50lt'),
         NULL, 3, 'both')
 ORDER BY depth, label LIMIT 12;

\echo
\echo '### Q11 Two contradictory end-of-life definitions on ONE datasheet.'
SELECT v.model_number, v.quantity, v.value_native, v.unit_native,
       c.extra->>'definition' AS definition,
       left(c.extra->>'note', 90) AS note
  FROM bd.v_observation v
  JOIN bd.observation o ON o.id=v.observation_id
  JOIN bd.condition_set c ON c.id=o.condition_set_id
 WHERE v.model_number='LF280K'
   AND (c.extra ? 'eol_criterion_pct' OR c.extra ? 'definition');
