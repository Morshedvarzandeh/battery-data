-- =====================================================================
-- battery-data : tests/020_valuation_queries.sql
--
-- The questions the valuation layer exists to answer, and the traps it
-- exists to avoid. Each one is a regression test: if a schema change
-- breaks the answer, it breaks here.
--
-- Requires seed/002_packs_and_valuation.sql.
-- =====================================================================

\pset border 2
\pset format aligned

\echo
\echo '### Q1  Which pack is in which car, and on what evidence.'
\echo '###     The attribution travels with the claim. A consumer that'
\echo '###     values a pack against a guess should be able to see that.'
SELECT application_name, model_number, basis, confidence
  FROM bd.v_pack_application
 WHERE application_name LIKE 'Leaf%'
 ORDER BY application_name
 LIMIT 6;

\echo
\echo '### Q2  Recovery is not payable, and the difference is the point.'
\echo '###     Nickel through hydrometallurgy recovers at 95% and is paid'
\echo '###     at 68%, so it returns 65% of headline value. A schema with'
\echo '###     one column keeps whichever number the source happened to'
\echo '###     quote and loses the other.'
SELECT element_symbol, traded_form, recovery_rate, payable_fraction,
       round(value_yield::numeric, 4) AS value_yield
  FROM bd.v_recovery_economics
 WHERE process_uid = 'process/hydrometallurgical'
   AND NOT is_regulatory_minimum
   AND element_symbol IN ('Ni','Co','Li')
 ORDER BY value_yield DESC;

\echo
\echo '### Q3  A regulatory floor is a different claim from what a plant'
\echo '###     achieves. Both are stored, and the regulatory one makes no'
\echo '###     assertion about payment at all.'
SELECT element_symbol, recovery_rate, payable_fraction, valid_from
  FROM bd.v_recovery_economics
 WHERE is_regulatory_minimum AND element_symbol = 'Li'
 ORDER BY valid_from;

\echo
\echo '### Q4  A traded form is not the metal. Lithium carbonate is 18.8%'
\echo '###     lithium, which is where the LCE factor of 5.323 comes from.'
SELECT code, formula, payable_element, contained_fraction,
       round((1 / contained_fraction)::numeric, 3) AS form_per_kg_element
  FROM bd.traded_form
 WHERE payable_element IN ('Li','Co','Ni') AND formula IS NOT NULL
 ORDER BY code;

\echo
\echo '### Q5  Nameplate energy with no stated conditions says so, rather'
\echo '###     than pretending to a temperature nobody published.'
SELECT p.model_number, o.value_native::text || ' ' || o.unit_native AS energy,
       cs.unstated
  FROM bd.observation o
  JOIN bd.quantity q            ON q.id = o.quantity_id
  JOIN bd.product_revision r    ON r.id = o.product_revision_id
  JOIN bd.product p             ON p.id = r.product_id
  JOIN bd.condition_set cs      ON cs.id = o.condition_set_id
 WHERE q.code = 'energy' AND p.kind = 'pack'
 ORDER BY p.model_number
 LIMIT 3;

\echo
\echo '### Q6  Dangerous-goods freight is driven by condition, not mass.'
\echo '###     ADR special provision 376 is why a damaged pack costs'
\echo '###     several times more to move than a healthy one.'
SELECT condition, un_number, cost_per_kg, minimum_charge, currency
  FROM bd.logistics_tariff
 WHERE valid_to IS NULL
 ORDER BY cost_per_kg;

\echo
\echo '### Q7  How fast a pack wears out is a property of the pack, not of'
\echo '###     its chemistry. Cooling design separates real fleets far more'
\echo '###     sharply than the cathode does: two NMC packs of the same'
\echo '###     vintage part company entirely if one is cooled and the other'
\echo '###     is not, which is the whole story of the early Leaf.'
SELECT p.model_number, d.thermal_management, d.fade_at_8y,
       d.spread_points_at_8y, d.climate_sensitivity
  FROM bd.degradation_profile d
  JOIN bd.product p ON p.id = d.product_id
 WHERE d.valid_to IS NULL
 ORDER BY d.fade_at_8y DESC
 LIMIT 6;

\echo
\echo '### Q8  The spread is what makes a verdict possible. Without it a'
\echo '###     consumer can only say a pack is below average, which is true'
\echo '###     of half of them. reference_km_per_year is the other half of'
\echo '###     the contract: fade_at_8y already contains that much cycling,'
\echo '###     so only the difference from it may be charged again. Both'
\echo '###     columns should be populated for every pack-level profile.'
SELECT count(*) AS profiles,
       count(*) FILTER (WHERE spread_points_at_8y IS NULL) AS missing_spread,
       count(*) FILTER (WHERE product_id IS NOT NULL
                          AND reference_km_per_year IS NULL) AS missing_reference,
       count(*) FILTER (WHERE product_id IS NOT NULL) AS by_pack,
       count(*) FILTER (WHERE chemistry IS NOT NULL) AS by_chemistry
  FROM bd.degradation_profile;

\echo
\echo '### Q9  Everything in this layer is dated. A payable term agreed in'
\echo '###     one year silently pricing a pack in another is the failure'
\echo '###     mode the validity window exists to prevent.'
SELECT 'recovery_yield' AS relation, count(*) AS rows,
       count(*) FILTER (WHERE valid_from IS NULL) AS undated
  FROM bd.recovery_yield
UNION ALL SELECT 'treatment_cost', count(*),
       count(*) FILTER (WHERE valid_from IS NULL) FROM bd.treatment_cost
UNION ALL SELECT 'component_market_value', count(*),
       count(*) FILTER (WHERE valid_from IS NULL) FROM bd.component_market_value
UNION ALL SELECT 'replacement_price', count(*),
       count(*) FILTER (WHERE valid_from IS NULL) FROM bd.replacement_price
UNION ALL SELECT 'degradation_profile', count(*),
       count(*) FILTER (WHERE valid_from IS NULL) FROM bd.degradation_profile;
