-- =====================================================================
-- battery-data : seed/002_packs_and_valuation.sql
--
-- Pack models, the vehicles they are fielded in, and the end-of-life
-- economics needed to value one.
--
-- GENERATED. Do not hand-edit; regenerate with
--   python tools/export_to_battery_data.py   (in battery-worldcup)
--
-- Attribution is deliberately conservative. Pack-to-vehicle links here
-- are service documentation and teardowns, not manufacturer statements,
-- so they carry basis='teardown' and a confidence below 1. Where a
-- catalogue entry was itself marked medium confidence, that is carried
-- through rather than rounded up.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Organisations
-- ---------------------------------------------------------------------
INSERT INTO organization (uid, name, country, roles) VALUES
  ('org/audi','Audi','DE','{manufacturer}'),
  ('org/bmw','BMW Group','DE','{manufacturer}'),
  ('org/byd','BYD Auto','CN','{manufacturer}'),
  ('org/hyundai','Hyundai Motor Group','KR','{manufacturer}'),
  ('org/nissan','Nissan Motor','JP','{manufacturer}'),
  ('org/polestar','Polestar','SE','{manufacturer}'),
  ('org/renault','Renault Group','FR','{manufacturer}'),
  ('org/stellantis','Stellantis','NL','{manufacturer}'),
  ('org/tesla','Tesla','US','{manufacturer}'),
  ('org/toyota','Toyota Motor','JP','{manufacturer}'),
  ('org/volkswagen','Volkswagen Group','DE','{manufacturer}')
ON CONFLICT (uid) DO NOTHING;

-- ---------------------------------------------------------------------
-- Contributor, sources and provenance
--
-- One provenance row per source, because the evidence class is a
-- property of the source rather than of each value. derivation_note
-- carries the export's own key so the rows below can reference it.
-- ---------------------------------------------------------------------
INSERT INTO contributor (uid, display_name, is_bot) VALUES
  ('user/battery-value-export','battery-value export', true)
ON CONFLICT (uid) DO NOTHING;

INSERT INTO source (uid, kind, title, url, license, redistributable,
                    retrieved_at, scope_note)
VALUES ('src/bv-pack-catalogue','teardown_report','battery-value pack catalogue (teardowns and service documentation)','https://github.com/Morshedvarzandeh/battery-worldcup','MIT', true, now(),
        'Compiled from OEM service documentation, homologation filings and published pack teardowns. Individual figures vary in strength; the confidence column carries that.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO source_location (source_id, locator_kind)
SELECT id,'dataset' FROM source WHERE uid='src/bv-pack-catalogue'
ON CONFLICT DO NOTHING;
INSERT INTO source (uid, kind, title, url, license, redistributable,
                    retrieved_at, scope_note)
VALUES ('src/eu-2023-1542-annex-xii','standard','Regulation (EU) 2023/1542 Annex XII, recycling efficiency and material recovery targets','https://eur-lex.europa.eu/eli/reg/2023/1542/oj','MIT', true, now(),
        'Regulatory minima with fixed compliance dates. These are floors on recovery, and say nothing about what a refiner pays.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO source_location (source_id, locator_kind)
SELECT id,'dataset' FROM source WHERE uid='src/eu-2023-1542-annex-xii'
ON CONFLICT DO NOTHING;
INSERT INTO source (uid, kind, title, url, license, redistributable,
                    retrieved_at, scope_note)
VALUES ('src/bv-recycling-terms','third_party_test','battery-value recycling process and payable terms','https://github.com/Morshedvarzandeh/battery-worldcup','MIT', true, now(),
        'Commercial recovery rates and black-mass payable terms, benchmarked from published plant mass balances and reported offtake structures. Payables in particular are negotiated and move with the market.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO source_location (source_id, locator_kind)
SELECT id,'dataset' FROM source WHERE uid='src/bv-recycling-terms'
ON CONFLICT DO NOTHING;
INSERT INTO source (uid, kind, title, url, license, redistributable,
                    retrieved_at, scope_note)
VALUES ('src/bv-used-parts-market','distributor_listing','battery-value used-parts market observations','https://github.com/Morshedvarzandeh/battery-worldcup','MIT', true, now(),
        'Used module and component values from second-hand marketplace listings. A thin market, so treat as indicative and refresh often.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO source_location (source_id, locator_kind)
SELECT id,'dataset' FROM source WHERE uid='src/bv-used-parts-market'
ON CONFLICT DO NOTHING;
INSERT INTO source (uid, kind, title, url, license, redistributable,
                    retrieved_at, scope_note)
VALUES ('src/bv-degradation-profiles','dataset','battery-value pack degradation profiles','https://github.com/Morshedvarzandeh/battery-worldcup','MIT', true, now(),
        'Fade curves per pack model, calibrated against published fleet telemetry studies, OEM warranty floors and aggregated owner-reported capacity readings. Cohort central estimates with an explicit spread; they describe a population and never an individual pack.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO source_location (source_id, locator_kind)
SELECT id,'dataset' FROM source WHERE uid='src/bv-degradation-profiles'
ON CONFLICT DO NOTHING;

INSERT INTO provenance (source_location_id, evidence, extraction,
                        contributor_id, confidence, review,
                        derivation_note)
SELECT sl.id, 'manufacturer_claim'::evidence_class,'manual_entry'::extraction_method,
       (SELECT id FROM contributor WHERE uid='user/battery-value-export'),
       0.8, 'pending_review'::review_state, 'src/bv-pack-catalogue'
  FROM source_location sl JOIN source s ON s.id=sl.source_id
 WHERE s.uid='src/bv-pack-catalogue'
 LIMIT 1;
INSERT INTO provenance (source_location_id, evidence, extraction,
                        contributor_id, confidence, review,
                        derivation_note)
SELECT sl.id, 'literature_reported'::evidence_class,'manual_entry'::extraction_method,
       (SELECT id FROM contributor WHERE uid='user/battery-value-export'),
       1.0, 'pending_review'::review_state, 'src/eu-2023-1542-annex-xii'
  FROM source_location sl JOIN source s ON s.id=sl.source_id
 WHERE s.uid='src/eu-2023-1542-annex-xii'
 LIMIT 1;
INSERT INTO provenance (source_location_id, evidence, extraction,
                        contributor_id, confidence, review,
                        derivation_note)
SELECT sl.id, 'estimated'::evidence_class,'manual_entry'::extraction_method,
       (SELECT id FROM contributor WHERE uid='user/battery-value-export'),
       0.7, 'pending_review'::review_state, 'src/bv-recycling-terms'
  FROM source_location sl JOIN source s ON s.id=sl.source_id
 WHERE s.uid='src/bv-recycling-terms'
 LIMIT 1;
INSERT INTO provenance (source_location_id, evidence, extraction,
                        contributor_id, confidence, review,
                        derivation_note)
SELECT sl.id, 'estimated'::evidence_class,'manual_entry'::extraction_method,
       (SELECT id FROM contributor WHERE uid='user/battery-value-export'),
       0.6, 'pending_review'::review_state, 'src/bv-used-parts-market'
  FROM source_location sl JOIN source s ON s.id=sl.source_id
 WHERE s.uid='src/bv-used-parts-market'
 LIMIT 1;
INSERT INTO provenance (source_location_id, evidence, extraction,
                        contributor_id, confidence, review,
                        derivation_note)
SELECT sl.id, 'literature_reported'::evidence_class,'manual_entry'::extraction_method,
       (SELECT id FROM contributor WHERE uid='user/battery-value-export'),
       0.7, 'pending_review'::review_state, 'src/bv-degradation-profiles'
  FROM source_location sl JOIN source s ON s.id=sl.source_id
 WHERE s.uid='src/bv-degradation-profiles'
 LIMIT 1;

-- ---------------------------------------------------------------------
-- Traded forms
--
-- contained_fraction is computed from the formula and IUPAC atomic
-- weights, not typed in. Lithium carbonate is 18.785% lithium, which
-- is where the industry's LCE factor of 5.323 comes from.
-- ---------------------------------------------------------------------
INSERT INTO traded_form (uid, code, label, formula, payable_element,
                         contained_fraction, notes) VALUES
  ('form/aluminium-metal','aluminium_metal','Aluminium (LME cash, high grade)',NULL,'Al',1.0000000,NULL),
  ('form/cobalt-metal','cobalt_metal','Cobalt (standard grade)',NULL,'Co',1.0000000,NULL),
  ('form/cobalt-sulphate','cobalt_sulphate','Cobalt sulphate heptahydrate','CoSO4.7H2O','Co',0.2096558,NULL),
  ('form/copper-metal','copper_metal','Copper (LME cash, grade A)',NULL,'Cu',1.0000000,NULL),
  ('form/graphite-flake','graphite_flake','Natural graphite (flake, 94-95% C)',NULL,'C',1.0000000,'Recovered anode graphite rarely meets battery spec; see recovery data.'),
  ('form/lead-metal','lead_metal','Lead (LME cash)',NULL,'Pb',1.0000000,NULL),
  ('form/lithium-carbonate','lithium_carbonate','Lithium carbonate (battery grade, 99.5%)','Li2CO3','Li',0.1878519,'The LCE basis: 1 kg Li = 5.323 kg Li2CO3.'),
  ('form/lithium-hydroxide','lithium_hydroxide','Lithium hydroxide monohydrate (battery grade)','LiOH.H2O','Li',0.1653877,NULL),
  ('form/manganese-sulphate','manganese_sulphate','Manganese sulphate monohydrate','MnSO4.H2O','Mn',0.3250596,NULL),
  ('form/nickel-metal','nickel_metal','Nickel (LME cash, 99.8%)',NULL,'Ni',1.0000000,NULL),
  ('form/nickel-sulphate','nickel_sulphate','Nickel sulphate hexahydrate','NiSO4.6H2O','Ni',0.2233040,'Battery-grade precursor; trades at a premium/discount to LME.'),
  ('form/steel-scrap','steel_scrap','Steel scrap (HMS 1&2)',NULL,'Fe',1.0000000,NULL)
ON CONFLICT (uid) DO NOTHING;

-- ---------------------------------------------------------------------
-- Recovery processes, yields and costs
-- ---------------------------------------------------------------------
INSERT INTO recovery_process (uid, route, name, description,
                              maturity, applies_to) VALUES
  ('process/hydrometallurgical','hydrometallurgical','Mechanical pre-treatment to black mass, then hydrometallurgical refining','Today''s mainstream commercial route in Europe and China. Recovers nickel, cobalt, manganese and (partially) lithium as battery-grade salts.',
   'commercial','{"li-ion","na-ion"}')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO recovery_yield (recovery_process_id, element_symbol,
       traded_form_id, recovery_rate, payable_fraction,
       valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Ni',
   (SELECT id FROM traded_form WHERE code='nickel_sulphate'),0.95,0.68,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Co',
   (SELECT id FROM traded_form WHERE code='cobalt_sulphate'),0.95,0.68,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Li',
   (SELECT id FROM traded_form WHERE code='lithium_carbonate'),0.65,0.4,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Mn',
   (SELECT id FROM traded_form WHERE code='manganese_sulphate'),0.88,0.35,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Cu',
   (SELECT id FROM traded_form WHERE code='copper_metal'),0.92,0.75,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Al',
   (SELECT id FROM traded_form WHERE code='aluminium_metal'),0.8,0.55,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Fe',
   (SELECT id FROM traded_form WHERE code='steel_scrap'),0.85,0.5,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'C',
   (SELECT id FROM traded_form WHERE code='graphite_flake'),0.15,0.1,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));
INSERT INTO treatment_cost (recovery_process_id, stage,
       cost_per_kg, currency, valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'discharge_and_dismantle',0.85,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'shredding_to_black_mass',0.65,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'refining_gate_fee',0.3,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

INSERT INTO recovery_process (uid, route, name, description,
                              maturity, applies_to) VALUES
  ('process/pyrometallurgical','pyrometallurgical','Smelting (pyrometallurgy) with hydrometallurgical refining of the alloy','Robust to mixed and damaged feed and needs no discharge, but lithium, aluminium and graphite are lost to slag or burned as reductant.',
   'commercial','{"li-ion"}')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO recovery_yield (recovery_process_id, element_symbol,
       traded_form_id, recovery_rate, payable_fraction,
       valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'Ni',
   (SELECT id FROM traded_form WHERE code='nickel_metal'),0.95,0.65,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'Co',
   (SELECT id FROM traded_form WHERE code='cobalt_metal'),0.95,0.65,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'Mn',
   (SELECT id FROM traded_form WHERE code='manganese_sulphate'),0.2,0.2,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'Cu',
   (SELECT id FROM traded_form WHERE code='copper_metal'),0.95,0.72,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'Fe',
   (SELECT id FROM traded_form WHERE code='steel_scrap'),0.7,0.4,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));
INSERT INTO treatment_cost (recovery_process_id, stage,
       cost_per_kg, currency, valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'discharge_and_dismantle',0.2,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/pyrometallurgical'),'refining_gate_fee',1.1,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

INSERT INTO recovery_process (uid, route, name, description,
                              maturity, applies_to) VALUES
  ('process/direct-recycling','direct_recycling','Direct cathode-to-cathode recycling','Emerging route that relithiates and reuses the cathode powder instead of dissolving it. Highest theoretical value retention, but needs single-chemistry, well-sorted feed and is not yet at commercial scale.',
   'pilot','{"li-ion"}')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO recovery_yield (recovery_process_id, element_symbol,
       traded_form_id, recovery_rate, payable_fraction,
       valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Ni',
   (SELECT id FROM traded_form WHERE code='nickel_sulphate'),0.98,0.75,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Co',
   (SELECT id FROM traded_form WHERE code='cobalt_sulphate'),0.98,0.75,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Li',
   (SELECT id FROM traded_form WHERE code='lithium_carbonate'),0.9,0.6,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Mn',
   (SELECT id FROM traded_form WHERE code='manganese_sulphate'),0.95,0.5,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Cu',
   (SELECT id FROM traded_form WHERE code='copper_metal'),0.9,0.72,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Al',
   (SELECT id FROM traded_form WHERE code='aluminium_metal'),0.85,0.55,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'Fe',
   (SELECT id FROM traded_form WHERE code='steel_scrap'),0.85,0.5,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'C',
   (SELECT id FROM traded_form WHERE code='graphite_flake'),0.6,0.3,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));
INSERT INTO treatment_cost (recovery_process_id, stage,
       cost_per_kg, currency, valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'discharge_and_dismantle',1.1,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'shredding_to_black_mass',0.55,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/direct-recycling'),'refining_gate_fee',0.45,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

INSERT INTO recovery_process (uid, route, name, description,
                              maturity, applies_to) VALUES
  ('process/nimh-stainless-smelting','stainless_smelting','Stainless-steel smelting of nickel metal hydride packs','NiMH packs are fed to stainless-steel smelters, where nickel and cobalt report to the alloy. Rare earths in the AB5 anode go to slag and are not paid for.',
   'commercial','{"nimh"}')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO recovery_yield (recovery_process_id, element_symbol,
       traded_form_id, recovery_rate, payable_fraction,
       valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'Ni',
   (SELECT id FROM traded_form WHERE code='nickel_metal'),0.9,0.55,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'Co',
   (SELECT id FROM traded_form WHERE code='cobalt_metal'),0.85,0.5,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'Fe',
   (SELECT id FROM traded_form WHERE code='steel_scrap'),0.8,0.35,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'Cu',
   (SELECT id FROM traded_form WHERE code='copper_metal'),0.85,0.6,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));
INSERT INTO treatment_cost (recovery_process_id, stage,
       cost_per_kg, currency, valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'discharge_and_dismantle',0.25,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'shredding_to_black_mass',0.1,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/nimh-stainless-smelting'),'refining_gate_fee',0.2,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

INSERT INTO recovery_process (uid, route, name, description,
                              maturity, applies_to) VALUES
  ('process/lead-acid-smelting','lead_smelting','Secondary lead smelting','A mature closed loop. Lead recovery economics are strong enough that scrap lead-acid batteries carry a positive scrap price almost everywhere.',
   'commercial','{"lead-acid"}')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO recovery_yield (recovery_process_id, element_symbol,
       traded_form_id, recovery_rate, payable_fraction,
       valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/lead-acid-smelting'),'Pb',
   (SELECT id FROM traded_form WHERE code='lead_metal'),0.97,0.7,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/lead-acid-smelting'),'Cu',
   (SELECT id FROM traded_form WHERE code='copper_metal'),0.6,0.6,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/lead-acid-smelting'),'Fe',
   (SELECT id FROM traded_form WHERE code='steel_scrap'),0.7,0.4,'2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));
INSERT INTO treatment_cost (recovery_process_id, stage,
       cost_per_kg, currency, valid_from, region, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/lead-acid-smelting'),'discharge_and_dismantle',0.05,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/lead-acid-smelting'),'shredding_to_black_mass',0.12,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ((SELECT id FROM recovery_process WHERE uid='process/lead-acid-smelting'),'refining_gate_fee',0.08,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

-- Regulatory floors, kept as separate rows from commercial practice.
-- EU 2023/1542 Annex XII, from 31 December 2027 and 2031.
INSERT INTO recovery_yield (recovery_process_id, element_symbol,
       recovery_rate, payable_fraction, valid_from, region,
       is_regulatory_minimum, provenance_id) VALUES
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Co',0.9,NULL,
   '2027-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Cu',0.9,NULL,
   '2027-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Pb',0.9,NULL,
   '2027-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Ni',0.9,NULL,
   '2027-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Li',0.5,NULL,
   '2027-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Co',0.95,NULL,
   '2031-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Cu',0.95,NULL,
   '2031-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Pb',0.95,NULL,
   '2031-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Ni',0.95,NULL,
   '2031-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii')),
  ((SELECT id FROM recovery_process WHERE uid='process/hydrometallurgical'),'Li',0.8,NULL,
   '2031-12-31','EU', true,(SELECT id FROM provenance WHERE derivation_note='src/eu-2023-1542-annex-xii'));

-- Dangerous-goods freight. UN3480/3481 Class 9; damaged and defective
-- packs fall under ADR special provision 376, hence the multipliers.
INSERT INTO logistics_tariff (condition, un_number, cost_per_kg,
       minimum_charge, currency, mode, valid_from, region,
       provenance_id) VALUES
  ('healthy','UN3481',0.55,120.0,'EUR','road','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('degraded','UN3481',0.55,120.0,'EUR','road','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('defective','UN3481',1.43,120.0,'EUR','road','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('damaged','UN3481',2.475,120.0,'EUR','road','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('thermal_event','UN3481',3.3,120.0,'EUR','road','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

-- ---------------------------------------------------------------------
-- Model calibration
-- ---------------------------------------------------------------------
INSERT INTO valuation_assumption (key, pathway, value_num, unit,
       valid_from, region, provenance_id) VALUES
  ('second_life.testing_eur_per_kwh','second_life',8.0,'EUR/kWh','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('second_life.repackaging_eur_per_kwh','second_life',34.0,'EUR/kWh','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('second_life.new_bms_eur_per_pack','second_life',420.0,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('second_life.certification_eur_per_pack','second_life',180.0,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('second_life.warranty_reserve_fraction','second_life',0.08,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('second_life.minimum_viable_soh','second_life',0.6,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('second_life.end_of_life_soh','second_life',0.5,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('reuse.minimum_viable_soh','reuse',0.75,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('reuse.maximum_age_years','reuse',12.0,'years','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('reuse.refurbishment_eur_per_kwh','reuse',12.0,'EUR/kWh','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('reuse.test_and_certify_eur_per_pack','reuse',260.0,'EUR','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('reuse.oem_replacement_price_discount','reuse',0.45,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('reuse.warranty_reserve_fraction','reuse',0.12,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('parts_out.labour_rate_eur_per_hour','parts_out',68.0,'EUR/h','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms')),
  ('parts_out.fixed_setup_minutes','parts_out',45.0,'minutes','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-recycling-terms'));

-- ---------------------------------------------------------------------
-- Pack products (20), their assemblies,
-- the vehicles they are fielded in, and what the parts sell for.
-- ---------------------------------------------------------------------
-- Nissan Leaf ZE0 24 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/nissan/nissan-leaf-ze0-24','pack',(SELECT id FROM organization WHERE uid='org/nissan'),'Nissan Leaf ZE0 24 kWh','Nissan',
        'pouch','unknown', true,
        'Passively cooled. Very strong second-life and DIY demand keeps module resale well above scrap value.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('eM61'),('leaf24'),('nissan-leaf-ze0-24'),('ze0')) AS v(alias)
 WHERE p.uid='pack/nissan/nissan-leaf-ze0-24'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/nissan/nissan-leaf-ze0-24@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/nissan/nissan-leaf-ze0-24' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),'LMO',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'), q.id, 'nominal'::statistic_kind,
       24.0,'kWh',86400000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'), q.id, 'nominal'::statistic_kind,
       294.0,'kg',294.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze0-24-bms','component',(SELECT id FROM organization WHERE uid='org/nissan'),'Battery management system for Nissan Leaf ZE0 24 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze0-24-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze0-24-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze0-24-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze0-24-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze0-24-hv_box','component',(SELECT id FROM organization WHERE uid='org/nissan'),'HV junction box for Nissan Leaf ZE0 24 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze0-24-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze0-24-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze0-24-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze0-24-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze0-24-thermal','component',(SELECT id FROM organization WHERE uid='org/nissan'),'Cooling plate assembly for Nissan Leaf ZE0 24 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze0-24-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze0-24-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze0-24-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze0-24-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/nissan/nissan-leaf-ze0-24','module',(SELECT id FROM organization WHERE uid='org/nissan'),'nissan-leaf-ze0-24-module',
        'Nissan','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/nissan/nissan-leaf-ze0-24@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/nissan/nissan-leaf-ze0-24' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),(SELECT id FROM product_revision WHERE uid='module/nissan/nissan-leaf-ze0-24@bv'),48,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/nissan/nissan-leaf-ze0-24@bv'),42.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),340.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-ze0','Leaf ZE0','passenger_vehicle','Nissan','EU',
        '2010-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-ze0'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-24-kwh','Leaf 24 kWh','passenger_vehicle','Nissan','EU',
        '2010-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-24-kwh'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-acenta','Leaf Acenta','passenger_vehicle','Nissan','EU',
        '2010-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze0-24@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-acenta'
ON CONFLICT DO NOTHING;

-- Nissan Leaf ZE1 40 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/nissan/nissan-leaf-ze1-40','pack',(SELECT id FROM organization WHERE uid='org/nissan'),'Nissan Leaf ZE1 40 kWh','Nissan',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('leaf40'),('nissan-leaf-ze1-40'),('ze1')) AS v(alias)
 WHERE p.uid='pack/nissan/nissan-leaf-ze1-40'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/nissan/nissan-leaf-ze1-40@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/nissan/nissan-leaf-ze1-40' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),'NMC532',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'), q.id, 'nominal'::statistic_kind,
       40.0,'kWh',144000000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'), q.id, 'nominal'::statistic_kind,
       303.0,'kg',303.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze1-40-bms','component',(SELECT id FROM organization WHERE uid='org/nissan'),'Battery management system for Nissan Leaf ZE1 40 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze1-40-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze1-40-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-40-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-40-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze1-40-hv_box','component',(SELECT id FROM organization WHERE uid='org/nissan'),'HV junction box for Nissan Leaf ZE1 40 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze1-40-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze1-40-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-40-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-40-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze1-40-thermal','component',(SELECT id FROM organization WHERE uid='org/nissan'),'Cooling plate assembly for Nissan Leaf ZE1 40 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze1-40-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze1-40-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-40-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-40-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/nissan/nissan-leaf-ze1-40','module',(SELECT id FROM organization WHERE uid='org/nissan'),'nissan-leaf-ze1-40-module',
        'Nissan','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/nissan/nissan-leaf-ze1-40@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/nissan/nissan-leaf-ze1-40' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),(SELECT id FROM product_revision WHERE uid='module/nissan/nissan-leaf-ze1-40@bv'),24,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/nissan/nissan-leaf-ze1-40@bv'),105.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),300.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-ze1','Leaf ZE1','passenger_vehicle','Nissan','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-ze1'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-40-kwh','Leaf 40 kWh','passenger_vehicle','Nissan','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-40@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-40-kwh'
ON CONFLICT DO NOTHING;

-- Nissan Leaf e+ 62 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/nissan/nissan-leaf-ze1-62','pack',(SELECT id FROM organization WHERE uid='org/nissan'),'Nissan Leaf e+ 62 kWh','Nissan',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('leaf62'),('leafeplus'),('nissan-leaf-ze1-62')) AS v(alias)
 WHERE p.uid='pack/nissan/nissan-leaf-ze1-62'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/nissan/nissan-leaf-ze1-62@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/nissan/nissan-leaf-ze1-62' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),'NMC622',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'), q.id, 'nominal'::statistic_kind,
       62.0,'kWh',223200000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'), q.id, 'nominal'::statistic_kind,
       410.0,'kg',410.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze1-62-bms','component',(SELECT id FROM organization WHERE uid='org/nissan'),'Battery management system for Nissan Leaf e+ 62 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze1-62-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze1-62-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-62-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-62-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze1-62-hv_box','component',(SELECT id FROM organization WHERE uid='org/nissan'),'HV junction box for Nissan Leaf e+ 62 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze1-62-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze1-62-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-62-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-62-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/nissan/nissan-leaf-ze1-62-thermal','component',(SELECT id FROM organization WHERE uid='org/nissan'),'Cooling plate assembly for Nissan Leaf e+ 62 kWh',
        'Nissan','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/nissan/nissan-leaf-ze1-62-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/nissan/nissan-leaf-ze1-62-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),(SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-62-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/nissan/nissan-leaf-ze1-62-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/nissan/nissan-leaf-ze1-62','module',(SELECT id FROM organization WHERE uid='org/nissan'),'nissan-leaf-ze1-62-module',
        'Nissan','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/nissan/nissan-leaf-ze1-62@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/nissan/nissan-leaf-ze1-62' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),(SELECT id FROM product_revision WHERE uid='module/nissan/nissan-leaf-ze1-62@bv'),24,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/nissan/nissan-leaf-ze1-62@bv'),155.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),310.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-e','Leaf e+','passenger_vehicle','Nissan','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-e'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/leaf-62-kwh','Leaf 62 kWh','passenger_vehicle','Nissan','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/nissan/nissan-leaf-ze1-62@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/leaf-62-kwh'
ON CONFLICT DO NOTHING;

-- Renault Zoe ZE40 41 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/renault/renault-zoe-ze40','pack',(SELECT id FROM organization WHERE uid='org/renault'),'Renault Zoe ZE40 41 kWh','Renault',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('renault-zoe-ze40'),('ze40'),('zoe41')) AS v(alias)
 WHERE p.uid='pack/renault/renault-zoe-ze40'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/renault/renault-zoe-ze40@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/renault/renault-zoe-ze40' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),'NMC622',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'), q.id, 'nominal'::statistic_kind,
       41.0,'kWh',147600000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'), q.id, 'nominal'::statistic_kind,
       305.0,'kg',305.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/renault/renault-zoe-ze40-bms','component',(SELECT id FROM organization WHERE uid='org/renault'),'Battery management system for Renault Zoe ZE40 41 kWh',
        'Renault','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/renault/renault-zoe-ze40-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/renault/renault-zoe-ze40-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),(SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze40-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze40-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/renault/renault-zoe-ze40-hv_box','component',(SELECT id FROM organization WHERE uid='org/renault'),'HV junction box for Renault Zoe ZE40 41 kWh',
        'Renault','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/renault/renault-zoe-ze40-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/renault/renault-zoe-ze40-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),(SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze40-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze40-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/renault/renault-zoe-ze40-thermal','component',(SELECT id FROM organization WHERE uid='org/renault'),'Cooling plate assembly for Renault Zoe ZE40 41 kWh',
        'Renault','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/renault/renault-zoe-ze40-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/renault/renault-zoe-ze40-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),(SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze40-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze40-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/renault/renault-zoe-ze40','module',(SELECT id FROM organization WHERE uid='org/renault'),'renault-zoe-ze40-module',
        'Renault','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/renault/renault-zoe-ze40@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/renault/renault-zoe-ze40' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),(SELECT id FROM product_revision WHERE uid='module/renault/renault-zoe-ze40@bv'),12,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/renault/renault-zoe-ze40@bv'),130.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),290.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/zoe-ze40','Zoe ZE40','passenger_vehicle','Renault','EU',
        '2017-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/zoe-ze40'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/zoe-r110','Zoe R110','passenger_vehicle','Renault','EU',
        '2017-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/zoe-r110'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/zoe-41-kwh','Zoe 41 kWh','passenger_vehicle','Renault','EU',
        '2017-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze40@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/zoe-41-kwh'
ON CONFLICT DO NOTHING;

-- Renault Zoe ZE50 52 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/renault/renault-zoe-ze50','pack',(SELECT id FROM organization WHERE uid='org/renault'),'Renault Zoe ZE50 52 kWh','Renault',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('renault-zoe-ze50'),('ze50'),('zoe52')) AS v(alias)
 WHERE p.uid='pack/renault/renault-zoe-ze50'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/renault/renault-zoe-ze50@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/renault/renault-zoe-ze50' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),'NMC712',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'), q.id, 'nominal'::statistic_kind,
       52.0,'kWh',187200000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'), q.id, 'nominal'::statistic_kind,
       326.0,'kg',326.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/renault/renault-zoe-ze50-bms','component',(SELECT id FROM organization WHERE uid='org/renault'),'Battery management system for Renault Zoe ZE50 52 kWh',
        'Renault','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/renault/renault-zoe-ze50-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/renault/renault-zoe-ze50-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),(SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze50-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze50-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/renault/renault-zoe-ze50-hv_box','component',(SELECT id FROM organization WHERE uid='org/renault'),'HV junction box for Renault Zoe ZE50 52 kWh',
        'Renault','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/renault/renault-zoe-ze50-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/renault/renault-zoe-ze50-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),(SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze50-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze50-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/renault/renault-zoe-ze50-thermal','component',(SELECT id FROM organization WHERE uid='org/renault'),'Cooling plate assembly for Renault Zoe ZE50 52 kWh',
        'Renault','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/renault/renault-zoe-ze50-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/renault/renault-zoe-ze50-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),(SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze50-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/renault/renault-zoe-ze50-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/renault/renault-zoe-ze50','module',(SELECT id FROM organization WHERE uid='org/renault'),'renault-zoe-ze50-module',
        'Renault','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/renault/renault-zoe-ze50@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/renault/renault-zoe-ze50' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),(SELECT id FROM product_revision WHERE uid='module/renault/renault-zoe-ze50@bv'),12,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/renault/renault-zoe-ze50@bv'),165.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),295.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/zoe-ze50','Zoe ZE50','passenger_vehicle','Renault','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/zoe-ze50'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/zoe-52-kwh','Zoe 52 kWh','passenger_vehicle','Renault','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/renault/renault-zoe-ze50@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/zoe-52-kwh'
ON CONFLICT DO NOTHING;

-- BMW i3 60Ah (22 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/bmw/bmw-i3-60ah','pack',(SELECT id FROM organization WHERE uid='org/bmw'),'BMW i3 60Ah (22 kWh)','BMW',
        'prismatic_hardcase','unknown', true,
        'Prismatic Samsung SDI modules are a favourite for DIY stationary storage, which supports module resale value.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('bmw-i3-60ah'),('i3 60'),('i360')) AS v(alias)
 WHERE p.uid='pack/bmw/bmw-i3-60ah'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/bmw/bmw-i3-60ah@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/bmw/bmw-i3-60ah' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),'NMC111',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'), q.id, 'nominal'::statistic_kind,
       22.6,'kWh',81360000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'), q.id, 'nominal'::statistic_kind,
       233.0,'kg',233.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-60ah-bms','component',(SELECT id FROM organization WHERE uid='org/bmw'),'Battery management system for BMW i3 60Ah (22 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-60ah-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-60ah-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-60ah-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-60ah-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-60ah-hv_box','component',(SELECT id FROM organization WHERE uid='org/bmw'),'HV junction box for BMW i3 60Ah (22 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-60ah-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-60ah-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-60ah-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-60ah-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-60ah-thermal','component',(SELECT id FROM organization WHERE uid='org/bmw'),'Cooling plate assembly for BMW i3 60Ah (22 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-60ah-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-60ah-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-60ah-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-60ah-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/bmw/bmw-i3-60ah','module',(SELECT id FROM organization WHERE uid='org/bmw'),'bmw-i3-60ah-module',
        'BMW','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/bmw/bmw-i3-60ah@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/bmw/bmw-i3-60ah' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),(SELECT id FROM product_revision WHERE uid='module/bmw/bmw-i3-60ah@bv'),8,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/bmw/bmw-i3-60ah@bv'),130.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),400.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-60ah','i3 60Ah','passenger_vehicle','BMW','EU',
        '2013-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-60ah'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-22-kwh','i3 22 kWh','passenger_vehicle','BMW','EU',
        '2013-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-22-kwh'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-rex-60ah','i3 REx 60Ah','passenger_vehicle','BMW','EU',
        '2013-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-60ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-rex-60ah'
ON CONFLICT DO NOTHING;

-- BMW i3 94Ah (33 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/bmw/bmw-i3-94ah','pack',(SELECT id FROM organization WHERE uid='org/bmw'),'BMW i3 94Ah (33 kWh)','BMW',
        'prismatic_hardcase','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('bmw-i3-94ah'),('i3 94'),('i394')) AS v(alias)
 WHERE p.uid='pack/bmw/bmw-i3-94ah'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/bmw/bmw-i3-94ah@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/bmw/bmw-i3-94ah' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),'NMC111',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'), q.id, 'nominal'::statistic_kind,
       33.2,'kWh',119520000.00000001,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'), q.id, 'nominal'::statistic_kind,
       256.0,'kg',256.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-94ah-bms','component',(SELECT id FROM organization WHERE uid='org/bmw'),'Battery management system for BMW i3 94Ah (33 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-94ah-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-94ah-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-94ah-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-94ah-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-94ah-hv_box','component',(SELECT id FROM organization WHERE uid='org/bmw'),'HV junction box for BMW i3 94Ah (33 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-94ah-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-94ah-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-94ah-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-94ah-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-94ah-thermal','component',(SELECT id FROM organization WHERE uid='org/bmw'),'Cooling plate assembly for BMW i3 94Ah (33 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-94ah-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-94ah-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-94ah-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-94ah-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/bmw/bmw-i3-94ah','module',(SELECT id FROM organization WHERE uid='org/bmw'),'bmw-i3-94ah-module',
        'BMW','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/bmw/bmw-i3-94ah@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/bmw/bmw-i3-94ah' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),(SELECT id FROM product_revision WHERE uid='module/bmw/bmw-i3-94ah@bv'),8,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/bmw/bmw-i3-94ah@bv'),175.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),380.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-94ah','i3 94Ah','passenger_vehicle','BMW','EU',
        '2016-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-94ah'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-33-kwh','i3 33 kWh','passenger_vehicle','BMW','EU',
        '2016-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-94ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-33-kwh'
ON CONFLICT DO NOTHING;

-- BMW i3 120Ah (42 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/bmw/bmw-i3-120ah','pack',(SELECT id FROM organization WHERE uid='org/bmw'),'BMW i3 120Ah (42 kWh)','BMW',
        'prismatic_hardcase','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('bmw-i3-120ah'),('i3120')) AS v(alias)
 WHERE p.uid='pack/bmw/bmw-i3-120ah'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/bmw/bmw-i3-120ah@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/bmw/bmw-i3-120ah' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),'NMC622',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'), q.id, 'nominal'::statistic_kind,
       42.2,'kWh',151920000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'), q.id, 'nominal'::statistic_kind,
       278.0,'kg',278.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-120ah-bms','component',(SELECT id FROM organization WHERE uid='org/bmw'),'Battery management system for BMW i3 120Ah (42 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-120ah-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-120ah-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-120ah-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-120ah-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-120ah-hv_box','component',(SELECT id FROM organization WHERE uid='org/bmw'),'HV junction box for BMW i3 120Ah (42 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-120ah-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-120ah-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-120ah-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-120ah-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/bmw/bmw-i3-120ah-thermal','component',(SELECT id FROM organization WHERE uid='org/bmw'),'Cooling plate assembly for BMW i3 120Ah (42 kWh)',
        'BMW','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/bmw/bmw-i3-120ah-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/bmw/bmw-i3-120ah-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),(SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-120ah-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/bmw/bmw-i3-120ah-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/bmw/bmw-i3-120ah','module',(SELECT id FROM organization WHERE uid='org/bmw'),'bmw-i3-120ah-module',
        'BMW','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/bmw/bmw-i3-120ah@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/bmw/bmw-i3-120ah' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),(SELECT id FROM product_revision WHERE uid='module/bmw/bmw-i3-120ah@bv'),8,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/bmw/bmw-i3-120ah@bv'),215.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),370.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-120ah','i3 120Ah','passenger_vehicle','BMW','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-120ah'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3-42-kwh','i3 42 kWh','passenger_vehicle','BMW','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3-42-kwh'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/i3s','i3s','passenger_vehicle','BMW','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/bmw/bmw-i3-120ah@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/i3s'
ON CONFLICT DO NOTHING;

-- Tesla Model 3 Long Range (75 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/tesla/tesla-model3-lr','pack',(SELECT id FROM organization WHERE uid='org/tesla'),'Tesla Model 3 Long Range (75 kWh)','Tesla',
        'cylindrical','unknown', true,
        'Only four large modules, so module-level resale is high-value but the pack is hard to dismantle safely (structural bonding).')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('m3lr'),('model3lr'),('tesla-model3-lr')) AS v(alias)
 WHERE p.uid='pack/tesla/tesla-model3-lr'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/tesla/tesla-model3-lr@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/tesla/tesla-model3-lr' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),'NCA',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'), q.id, 'nominal'::statistic_kind,
       75.0,'kWh',270000000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'), q.id, 'nominal'::statistic_kind,
       478.0,'kg',478.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-model3-lr-bms','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Battery management system for Tesla Model 3 Long Range (75 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-model3-lr-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-model3-lr-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lr-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lr-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-model3-lr-hv_box','component',(SELECT id FROM organization WHERE uid='org/tesla'),'HV junction box for Tesla Model 3 Long Range (75 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-model3-lr-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-model3-lr-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lr-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lr-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-model3-lr-thermal','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Cooling plate assembly for Tesla Model 3 Long Range (75 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-model3-lr-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-model3-lr-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lr-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lr-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/tesla/tesla-model3-lr','module',(SELECT id FROM organization WHERE uid='org/tesla'),'tesla-model3-lr-module',
        'Tesla','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/tesla/tesla-model3-lr@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/tesla/tesla-model3-lr' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),(SELECT id FROM product_revision WHERE uid='module/tesla/tesla-model3-lr@bv'),4,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/tesla/tesla-model3-lr@bv'),1250.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),200.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-3-long-range','Model 3 Long Range','passenger_vehicle','Tesla','EU',
        '2017-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-3-long-range'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-3-lr','Model 3 LR','passenger_vehicle','Tesla','EU',
        '2017-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-3-lr'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-y-long-range','Model Y Long Range','passenger_vehicle','Tesla','EU',
        '2017-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lr@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-y-long-range'
ON CONFLICT DO NOTHING;

-- Tesla Model 3 Standard Range LFP (60 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/tesla/tesla-model3-lfp','pack',(SELECT id FROM organization WHERE uid='org/tesla'),'Tesla Model 3 Standard Range LFP (60 kWh)','Tesla',
        NULL,'unknown', true,
        'LFP: near-zero recycling value, but excellent cycle life makes second life the dominant pathway.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('m3sr'),('model3lfp'),('tesla-model3-lfp')) AS v(alias)
 WHERE p.uid='pack/tesla/tesla-model3-lfp'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/tesla/tesla-model3-lfp@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/tesla/tesla-model3-lfp' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),'LFP',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'), q.id, 'nominal'::statistic_kind,
       60.0,'kWh',216000000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'), q.id, 'nominal'::statistic_kind,
       438.0,'kg',438.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-model3-lfp-bms','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Battery management system for Tesla Model 3 Standard Range LFP (60 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-model3-lfp-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-model3-lfp-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lfp-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lfp-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-model3-lfp-hv_box','component',(SELECT id FROM organization WHERE uid='org/tesla'),'HV junction box for Tesla Model 3 Standard Range LFP (60 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-model3-lfp-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-model3-lfp-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lfp-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lfp-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-model3-lfp-thermal','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Cooling plate assembly for Tesla Model 3 Standard Range LFP (60 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-model3-lfp-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-model3-lfp-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lfp-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-model3-lfp-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/tesla/tesla-model3-lfp','module',(SELECT id FROM organization WHERE uid='org/tesla'),'tesla-model3-lfp-module',
        'Tesla','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/tesla/tesla-model3-lfp@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/tesla/tesla-model3-lfp' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),(SELECT id FROM product_revision WHERE uid='module/tesla/tesla-model3-lfp@bv'),4,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/tesla/tesla-model3-lfp@bv'),780.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),185.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-3-sr','Model 3 SR+','passenger_vehicle','Tesla','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-3-sr'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-3-rwd','Model 3 RWD','passenger_vehicle','Tesla','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-3-rwd'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-y-rwd','Model Y RWD','passenger_vehicle','Tesla','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-model3-lfp@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-y-rwd'
ON CONFLICT DO NOTHING;

-- Tesla Model S 85 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/tesla/tesla-models-85','pack',(SELECT id FROM organization WHERE uid='org/tesla'),'Tesla Model S 85 kWh','Tesla',
        'cylindrical','unknown', true,
        '16 modules of ~5.3 kWh each are the classic off-grid storage building block; module resale usually beats recycling comfortably.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('models85'),('tesla-models-85')) AS v(alias)
 WHERE p.uid='pack/tesla/tesla-models-85'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/tesla/tesla-models-85@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/tesla/tesla-models-85' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),'NCA',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'), q.id, 'nominal'::statistic_kind,
       85.0,'kWh',306000000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'), q.id, 'nominal'::statistic_kind,
       540.0,'kg',540.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-models-85-bms','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Battery management system for Tesla Model S 85 kWh',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-models-85-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-models-85-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-models-85-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-models-85-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-models-85-hv_box','component',(SELECT id FROM organization WHERE uid='org/tesla'),'HV junction box for Tesla Model S 85 kWh',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-models-85-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-models-85-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-models-85-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-models-85-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-models-85-thermal','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Cooling plate assembly for Tesla Model S 85 kWh',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-models-85-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-models-85-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-models-85-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-models-85-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/tesla/tesla-models-85','module',(SELECT id FROM organization WHERE uid='org/tesla'),'tesla-models-85-module',
        'Tesla','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/tesla/tesla-models-85@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/tesla/tesla-models-85' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),(SELECT id FROM product_revision WHERE uid='module/tesla/tesla-models-85@bv'),16,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/tesla/tesla-models-85@bv'),340.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),230.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-s-85','Model S 85','passenger_vehicle','Tesla','EU',
        '2012-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-s-85'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-s-p85','Model S P85','passenger_vehicle','Tesla','EU',
        '2012-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-s-p85'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/model-x-90d','Model X 90D','passenger_vehicle','Tesla','EU',
        '2012-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-models-85@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/model-x-90d'
ON CONFLICT DO NOTHING;

-- Volkswagen ID.3 Pro (58 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/volkswagen/vw-id3-58','pack',(SELECT id FROM organization WHERE uid='org/volkswagen'),'Volkswagen ID.3 Pro (58 kWh)','Volkswagen',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('id3pro'),('meb58'),('vw-id3-58')) AS v(alias)
 WHERE p.uid='pack/volkswagen/vw-id3-58'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/volkswagen/vw-id3-58@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/volkswagen/vw-id3-58' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),'NMC712',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'), q.id, 'nominal'::statistic_kind,
       58.0,'kWh',208800000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'), q.id, 'nominal'::statistic_kind,
       375.0,'kg',375.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/volkswagen/vw-id3-58-bms','component',(SELECT id FROM organization WHERE uid='org/volkswagen'),'Battery management system for Volkswagen ID.3 Pro (58 kWh)',
        'Volkswagen','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/volkswagen/vw-id3-58-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/volkswagen/vw-id3-58-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),(SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id3-58-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id3-58-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/volkswagen/vw-id3-58-hv_box','component',(SELECT id FROM organization WHERE uid='org/volkswagen'),'HV junction box for Volkswagen ID.3 Pro (58 kWh)',
        'Volkswagen','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/volkswagen/vw-id3-58-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/volkswagen/vw-id3-58-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),(SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id3-58-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id3-58-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/volkswagen/vw-id3-58-thermal','component',(SELECT id FROM organization WHERE uid='org/volkswagen'),'Cooling plate assembly for Volkswagen ID.3 Pro (58 kWh)',
        'Volkswagen','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/volkswagen/vw-id3-58-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/volkswagen/vw-id3-58-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),(SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id3-58-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id3-58-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/volkswagen/vw-id3-58','module',(SELECT id FROM organization WHERE uid='org/volkswagen'),'vw-id3-58-module',
        'Volkswagen','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/volkswagen/vw-id3-58@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/volkswagen/vw-id3-58' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),(SELECT id FROM product_revision WHERE uid='module/volkswagen/vw-id3-58@bv'),9,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/volkswagen/vw-id3-58@bv'),260.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),270.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/id-3-pro','ID.3 Pro','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/id-3-pro'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/id-3-58-kwh','ID.3 58 kWh','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/id-3-58-kwh'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/cupra-born-58','Cupra Born 58','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id3-58@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/cupra-born-58'
ON CONFLICT DO NOTHING;

-- Volkswagen ID.4 Pro (77 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/volkswagen/vw-id4-77','pack',(SELECT id FROM organization WHERE uid='org/volkswagen'),'Volkswagen ID.4 Pro (77 kWh)','Volkswagen',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('enyaq80'),('id4pro'),('meb77'),('vw-id4-77')) AS v(alias)
 WHERE p.uid='pack/volkswagen/vw-id4-77'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/volkswagen/vw-id4-77@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/volkswagen/vw-id4-77' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),'NMC712',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'), q.id, 'nominal'::statistic_kind,
       77.0,'kWh',277200000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'), q.id, 'nominal'::statistic_kind,
       493.0,'kg',493.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/volkswagen/vw-id4-77-bms','component',(SELECT id FROM organization WHERE uid='org/volkswagen'),'Battery management system for Volkswagen ID.4 Pro (77 kWh)',
        'Volkswagen','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/volkswagen/vw-id4-77-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/volkswagen/vw-id4-77-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),(SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id4-77-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id4-77-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/volkswagen/vw-id4-77-hv_box','component',(SELECT id FROM organization WHERE uid='org/volkswagen'),'HV junction box for Volkswagen ID.4 Pro (77 kWh)',
        'Volkswagen','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/volkswagen/vw-id4-77-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/volkswagen/vw-id4-77-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),(SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id4-77-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id4-77-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/volkswagen/vw-id4-77-thermal','component',(SELECT id FROM organization WHERE uid='org/volkswagen'),'Cooling plate assembly for Volkswagen ID.4 Pro (77 kWh)',
        'Volkswagen','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/volkswagen/vw-id4-77-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/volkswagen/vw-id4-77-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),(SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id4-77-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/volkswagen/vw-id4-77-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/volkswagen/vw-id4-77','module',(SELECT id FROM organization WHERE uid='org/volkswagen'),'vw-id4-77-module',
        'Volkswagen','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/volkswagen/vw-id4-77@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/volkswagen/vw-id4-77' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),(SELECT id FROM product_revision WHERE uid='module/volkswagen/vw-id4-77@bv'),12,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/volkswagen/vw-id4-77@bv'),275.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),265.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/id-4-pro','ID.4 Pro','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/id-4-pro'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/id-5','ID.5','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/id-5'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/skoda-enyaq-80','Skoda Enyaq 80','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/skoda-enyaq-80'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/audi-q4-e-tron-40','Audi Q4 e-tron 40','passenger_vehicle','Volkswagen','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/volkswagen/vw-id4-77@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/audi-q4-e-tron-40'
ON CONFLICT DO NOTHING;

-- Hyundai Kona Electric 64 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/hyundai/hyundai-kona-64','pack',(SELECT id FROM organization WHERE uid='org/hyundai'),'Hyundai Kona Electric 64 kWh','Hyundai',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('eniro64'),('hyundai-kona-64'),('kona64')) AS v(alias)
 WHERE p.uid='pack/hyundai/hyundai-kona-64'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/hyundai/hyundai-kona-64@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/hyundai/hyundai-kona-64' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),'NMC622',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'), q.id, 'nominal'::statistic_kind,
       64.0,'kWh',230400000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'), q.id, 'nominal'::statistic_kind,
       452.0,'kg',452.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/hyundai/hyundai-kona-64-bms','component',(SELECT id FROM organization WHERE uid='org/hyundai'),'Battery management system for Hyundai Kona Electric 64 kWh',
        'Hyundai','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/hyundai/hyundai-kona-64-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/hyundai/hyundai-kona-64-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),(SELECT id FROM product_revision WHERE uid='component/hyundai/hyundai-kona-64-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/hyundai/hyundai-kona-64-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/hyundai/hyundai-kona-64-hv_box','component',(SELECT id FROM organization WHERE uid='org/hyundai'),'HV junction box for Hyundai Kona Electric 64 kWh',
        'Hyundai','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/hyundai/hyundai-kona-64-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/hyundai/hyundai-kona-64-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),(SELECT id FROM product_revision WHERE uid='component/hyundai/hyundai-kona-64-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/hyundai/hyundai-kona-64-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/hyundai/hyundai-kona-64-thermal','component',(SELECT id FROM organization WHERE uid='org/hyundai'),'Cooling plate assembly for Hyundai Kona Electric 64 kWh',
        'Hyundai','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/hyundai/hyundai-kona-64-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/hyundai/hyundai-kona-64-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),(SELECT id FROM product_revision WHERE uid='component/hyundai/hyundai-kona-64-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/hyundai/hyundai-kona-64-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/hyundai/hyundai-kona-64','module',(SELECT id FROM organization WHERE uid='org/hyundai'),'hyundai-kona-64-module',
        'Hyundai','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/hyundai/hyundai-kona-64@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/hyundai/hyundai-kona-64' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),(SELECT id FROM product_revision WHERE uid='module/hyundai/hyundai-kona-64@bv'),98,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/hyundai/hyundai-kona-64@bv'),40.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),285.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/kona-electric-64','Kona Electric 64','passenger_vehicle','Hyundai','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/kona-electric-64'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/kia-e-niro-64','Kia e-Niro 64','passenger_vehicle','Hyundai','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/kia-e-niro-64'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/kia-e-soul-64','Kia e-Soul 64','passenger_vehicle','Hyundai','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/hyundai/hyundai-kona-64@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/kia-e-soul-64'
ON CONFLICT DO NOTHING;

-- BYD Atto 3 Blade (60 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/byd/byd-atto3-60','pack',(SELECT id FROM organization WHERE uid='org/byd'),'BYD Atto 3 Blade (60 kWh)','BYD',
        'blade','unknown', true,
        'Cell-to-pack construction means there are no serviceable modules: the pack is reused or recycled whole, so the parts-out pathway barely applies.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('atto3'),('blade60'),('byd-atto3-60')) AS v(alias)
 WHERE p.uid='pack/byd/byd-atto3-60'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/byd/byd-atto3-60@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/byd/byd-atto3-60' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),'LFP',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'), q.id, 'nominal'::statistic_kind,
       60.5,'kWh',217800000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'), q.id, 'nominal'::statistic_kind,
       440.0,'kg',440.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/byd/byd-atto3-60-bms','component',(SELECT id FROM organization WHERE uid='org/byd'),'Battery management system for BYD Atto 3 Blade (60 kWh)',
        'BYD','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/byd/byd-atto3-60-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/byd/byd-atto3-60-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),(SELECT id FROM product_revision WHERE uid='component/byd/byd-atto3-60-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/byd/byd-atto3-60-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/byd/byd-atto3-60-hv_box','component',(SELECT id FROM organization WHERE uid='org/byd'),'HV junction box for BYD Atto 3 Blade (60 kWh)',
        'BYD','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/byd/byd-atto3-60-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/byd/byd-atto3-60-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),(SELECT id FROM product_revision WHERE uid='component/byd/byd-atto3-60-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/byd/byd-atto3-60-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/byd/byd-atto3-60-thermal','component',(SELECT id FROM organization WHERE uid='org/byd'),'Cooling plate assembly for BYD Atto 3 Blade (60 kWh)',
        'BYD','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/byd/byd-atto3-60-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/byd/byd-atto3-60-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),(SELECT id FROM product_revision WHERE uid='component/byd/byd-atto3-60-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/byd/byd-atto3-60-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/byd/byd-atto3-60','module',(SELECT id FROM organization WHERE uid='org/byd'),'byd-atto3-60-module',
        'BYD','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/byd/byd-atto3-60@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/byd/byd-atto3-60' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),(SELECT id FROM product_revision WHERE uid='module/byd/byd-atto3-60@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),175.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/atto-3','Atto 3','passenger_vehicle','BYD','EU',
        '2022-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/atto-3'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/yuan-plus','Yuan Plus','passenger_vehicle','BYD','EU',
        '2022-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/yuan-plus'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/dolphin-60','Dolphin 60','passenger_vehicle','BYD','EU',
        '2022-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/byd/byd-atto3-60@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/dolphin-60'
ON CONFLICT DO NOTHING;

-- Stellantis e-CMP 50 kWh
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/stellantis/psa-emp1-50','pack',(SELECT id FROM organization WHERE uid='org/stellantis'),'Stellantis e-CMP 50 kWh','Stellantis',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('e208'),('ecmp50'),('psa-emp1-50')) AS v(alias)
 WHERE p.uid='pack/stellantis/psa-emp1-50'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/stellantis/psa-emp1-50@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/stellantis/psa-emp1-50' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),'NMC622',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'), q.id, 'nominal'::statistic_kind,
       50.0,'kWh',180000000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'), q.id, 'nominal'::statistic_kind,
       345.0,'kg',345.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/stellantis/psa-emp1-50-bms','component',(SELECT id FROM organization WHERE uid='org/stellantis'),'Battery management system for Stellantis e-CMP 50 kWh',
        'Stellantis','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/stellantis/psa-emp1-50-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/stellantis/psa-emp1-50-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),(SELECT id FROM product_revision WHERE uid='component/stellantis/psa-emp1-50-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/stellantis/psa-emp1-50-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/stellantis/psa-emp1-50-hv_box','component',(SELECT id FROM organization WHERE uid='org/stellantis'),'HV junction box for Stellantis e-CMP 50 kWh',
        'Stellantis','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/stellantis/psa-emp1-50-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/stellantis/psa-emp1-50-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),(SELECT id FROM product_revision WHERE uid='component/stellantis/psa-emp1-50-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/stellantis/psa-emp1-50-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/stellantis/psa-emp1-50-thermal','component',(SELECT id FROM organization WHERE uid='org/stellantis'),'Cooling plate assembly for Stellantis e-CMP 50 kWh',
        'Stellantis','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/stellantis/psa-emp1-50-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/stellantis/psa-emp1-50-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),(SELECT id FROM product_revision WHERE uid='component/stellantis/psa-emp1-50-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/stellantis/psa-emp1-50-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/stellantis/psa-emp1-50','module',(SELECT id FROM organization WHERE uid='org/stellantis'),'psa-emp1-50-module',
        'Stellantis','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/stellantis/psa-emp1-50@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/stellantis/psa-emp1-50' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),(SELECT id FROM product_revision WHERE uid='module/stellantis/psa-emp1-50@bv'),18,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/stellantis/psa-emp1-50@bv'),115.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),300.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/peugeot-e-208','Peugeot e-208','passenger_vehicle','Stellantis','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/peugeot-e-208'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/opel-corsa-e','Opel Corsa-e','passenger_vehicle','Stellantis','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/opel-corsa-e'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/ds-3-crossback-e-tense','DS 3 Crossback E-Tense','passenger_vehicle','Stellantis','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/ds-3-crossback-e-tense'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/peugeot-e-2008','Peugeot e-2008','passenger_vehicle','Stellantis','EU',
        '2019-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/stellantis/psa-emp1-50@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/peugeot-e-2008'
ON CONFLICT DO NOTHING;

-- Audi e-tron 55 (95 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/audi/audi-etron-95','pack',(SELECT id FROM organization WHERE uid='org/audi'),'Audi e-tron 55 (95 kWh)','Audi',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('audi-etron-95'),('etron95')) AS v(alias)
 WHERE p.uid='pack/audi/audi-etron-95'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/audi/audi-etron-95@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/audi/audi-etron-95' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),'NMC622',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'), q.id, 'nominal'::statistic_kind,
       95.0,'kWh',342000000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'), q.id, 'nominal'::statistic_kind,
       700.0,'kg',700.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/audi/audi-etron-95-bms','component',(SELECT id FROM organization WHERE uid='org/audi'),'Battery management system for Audi e-tron 55 (95 kWh)',
        'Audi','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/audi/audi-etron-95-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/audi/audi-etron-95-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),(SELECT id FROM product_revision WHERE uid='component/audi/audi-etron-95-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/audi/audi-etron-95-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/audi/audi-etron-95-hv_box','component',(SELECT id FROM organization WHERE uid='org/audi'),'HV junction box for Audi e-tron 55 (95 kWh)',
        'Audi','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/audi/audi-etron-95-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/audi/audi-etron-95-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),(SELECT id FROM product_revision WHERE uid='component/audi/audi-etron-95-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/audi/audi-etron-95-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/audi/audi-etron-95-thermal','component',(SELECT id FROM organization WHERE uid='org/audi'),'Cooling plate assembly for Audi e-tron 55 (95 kWh)',
        'Audi','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/audi/audi-etron-95-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/audi/audi-etron-95-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),(SELECT id FROM product_revision WHERE uid='component/audi/audi-etron-95-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/audi/audi-etron-95-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/audi/audi-etron-95','module',(SELECT id FROM organization WHERE uid='org/audi'),'audi-etron-95-module',
        'Audi','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/audi/audi-etron-95@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/audi/audi-etron-95' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),(SELECT id FROM product_revision WHERE uid='module/audi/audi-etron-95@bv'),36,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/audi/audi-etron-95@bv'),135.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),275.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/e-tron-55','e-tron 55','passenger_vehicle','Audi','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/e-tron-55'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/e-tron-sportback-55','e-tron Sportback 55','passenger_vehicle','Audi','EU',
        '2018-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/audi/audi-etron-95@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/e-tron-sportback-55'
ON CONFLICT DO NOTHING;

-- Polestar 2 Long Range (78 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/polestar/polestar2-78','pack',(SELECT id FROM organization WHERE uid='org/polestar'),'Polestar 2 Long Range (78 kWh)','Polestar',
        'pouch','unknown', true,
        NULL)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('cma78'),('polestar2-78'),('ps2lr')) AS v(alias)
 WHERE p.uid='pack/polestar/polestar2-78'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/polestar/polestar2-78@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/polestar/polestar2-78' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),'NMC712',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'), q.id, 'nominal'::statistic_kind,
       78.0,'kWh',280800000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'), q.id, 'nominal'::statistic_kind,
       500.0,'kg',500.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/polestar/polestar2-78-bms','component',(SELECT id FROM organization WHERE uid='org/polestar'),'Battery management system for Polestar 2 Long Range (78 kWh)',
        'Polestar','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/polestar/polestar2-78-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/polestar/polestar2-78-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),(SELECT id FROM product_revision WHERE uid='component/polestar/polestar2-78-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/polestar/polestar2-78-bms@bv'),260.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/polestar/polestar2-78-hv_box','component',(SELECT id FROM organization WHERE uid='org/polestar'),'HV junction box for Polestar 2 Long Range (78 kWh)',
        'Polestar','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/polestar/polestar2-78-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/polestar/polestar2-78-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),(SELECT id FROM product_revision WHERE uid='component/polestar/polestar2-78-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/polestar/polestar2-78-hv_box@bv'),190.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/polestar/polestar2-78-thermal','component',(SELECT id FROM organization WHERE uid='org/polestar'),'Cooling plate assembly for Polestar 2 Long Range (78 kWh)',
        'Polestar','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/polestar/polestar2-78-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/polestar/polestar2-78-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),(SELECT id FROM product_revision WHERE uid='component/polestar/polestar2-78-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/polestar/polestar2-78-thermal@bv'),70.0,'EUR',0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/polestar/polestar2-78','module',(SELECT id FROM organization WHERE uid='org/polestar'),'polestar2-78-module',
        'Polestar','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/polestar/polestar2-78@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/polestar/polestar2-78' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),(SELECT id FROM product_revision WHERE uid='module/polestar/polestar2-78@bv'),27,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/polestar/polestar2-78@bv'),140.0,'EUR',1.0,0.85,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),280.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/polestar-2-lr','Polestar 2 LR','passenger_vehicle','Polestar','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/polestar-2-lr'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/volvo-xc40-recharge','Volvo XC40 Recharge','passenger_vehicle','Polestar','EU',
        '2020-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/polestar/polestar2-78@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/volvo-xc40-recharge'
ON CONFLICT DO NOTHING;

-- Toyota Prius XW30 NiMH (1.31 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/toyota/toyota-prius-xw30-nimh','pack',(SELECT id FROM organization WHERE uid='org/toyota'),'Toyota Prius XW30 NiMH (1.31 kWh)','Toyota',
        'prismatic_hardcase','unknown', true,
        'The highest-volume used traction pack in the world. Replacement demand is enormous relative to pack energy, so reuse dominates: OEM price per kWh looks extreme only because the pack is tiny.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('priusnimh'),('toyota-prius-xw30-nimh'),('xw30')) AS v(alias)
 WHERE p.uid='pack/toyota/toyota-prius-xw30-nimh'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/toyota/toyota-prius-xw30-nimh@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/toyota/toyota-prius-xw30-nimh' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),'NIMH',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'), q.id, 'nominal'::statistic_kind,
       1.31,'kWh',4716000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'), q.id, 'nominal'::statistic_kind,
       42.0,'kg',42.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/toyota/toyota-prius-xw30-nimh-bms','component',(SELECT id FROM organization WHERE uid='org/toyota'),'Battery management system for Toyota Prius XW30 NiMH (1.31 kWh)',
        'Toyota','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/toyota/toyota-prius-xw30-nimh-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/toyota/toyota-prius-xw30-nimh-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),(SELECT id FROM product_revision WHERE uid='component/toyota/toyota-prius-xw30-nimh-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/toyota/toyota-prius-xw30-nimh-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/toyota/toyota-prius-xw30-nimh-hv_box','component',(SELECT id FROM organization WHERE uid='org/toyota'),'HV junction box for Toyota Prius XW30 NiMH (1.31 kWh)',
        'Toyota','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/toyota/toyota-prius-xw30-nimh-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/toyota/toyota-prius-xw30-nimh-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),(SELECT id FROM product_revision WHERE uid='component/toyota/toyota-prius-xw30-nimh-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/toyota/toyota-prius-xw30-nimh-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/toyota/toyota-prius-xw30-nimh-thermal','component',(SELECT id FROM organization WHERE uid='org/toyota'),'Cooling plate assembly for Toyota Prius XW30 NiMH (1.31 kWh)',
        'Toyota','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/toyota/toyota-prius-xw30-nimh-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/toyota/toyota-prius-xw30-nimh-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),(SELECT id FROM product_revision WHERE uid='component/toyota/toyota-prius-xw30-nimh-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/toyota/toyota-prius-xw30-nimh-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/toyota/toyota-prius-xw30-nimh','module',(SELECT id FROM organization WHERE uid='org/toyota'),'toyota-prius-xw30-nimh-module',
        'Toyota','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/toyota/toyota-prius-xw30-nimh@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/toyota/toyota-prius-xw30-nimh' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),(SELECT id FROM product_revision WHERE uid='module/toyota/toyota-prius-xw30-nimh@bv'),28,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/toyota/toyota-prius-xw30-nimh@bv'),11.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),1600.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/prius-xw30','Prius XW30','passenger_vehicle','Toyota','EU',
        '2009-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/prius-xw30'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/prius-iii','Prius III','passenger_vehicle','Toyota','EU',
        '2009-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/prius-iii'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/auris-hsd','Auris HSD','passenger_vehicle','Toyota','EU',
        '2009-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/auris-hsd'
ON CONFLICT DO NOTHING;
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/prius-xw20','Prius XW20','passenger_vehicle','Toyota','EU',
        '2009-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/toyota/toyota-prius-xw30-nimh@bv'),'traction',1,'teardown',0.85,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/prius-xw20'
ON CONFLICT DO NOTHING;

-- Tesla Powerwall 2 (13.5 kWh)
INSERT INTO product (uid, kind, manufacturer_id, model_number, brand,
                     form_factor, lifecycle, is_rechargeable, notes)
VALUES ('pack/tesla/tesla-powerwall2','pack',(SELECT id FROM organization WHERE uid='org/tesla'),'Tesla Powerwall 2 (13.5 kWh)','Tesla',
        'cylindrical','unknown', true,
        'Already a stationary product, so the second-life pathway is really a straight resale.')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_alias (product_id, alias, kind)
SELECT p.id, v.alias, 'oem_code' FROM product p,
  (VALUES ('powerwall2'),('pw2'),('tesla-powerwall2')) AS v(alias)
 WHERE p.uid='pack/tesla/tesla-powerwall2'
ON CONFLICT (product_id, alias, kind) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label, region_scope)
SELECT 'pack/tesla/tesla-powerwall2@bv', p.id, s.id, 'bv-catalogue', '{EU}'
  FROM product p, source s
 WHERE p.uid='pack/tesla/tesla-powerwall2' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_chemistry (product_revision_id, designation,
                               provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),'NMC111',(SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (product_revision_id) DO NOTHING;
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, condition_set_id,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'), q.id, 'nominal'::statistic_kind,
       13.5,'kWh',48600000.0,
       bd.intern_conditions('{"unstated":["rate_value","rate_unit","temperature_c"]}'::jsonb),
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='energy';
INSERT INTO observation (product_revision_id, quantity_id, statistic,
       value_native, unit_native, value_si, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'), q.id, 'nominal'::statistic_kind,
       114.0,'kg',114.0,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM quantity q WHERE q.code='mass';
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-powerwall2-bms','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Battery management system for Tesla Powerwall 2 (13.5 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-powerwall2-bms@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-powerwall2-bms' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-powerwall2-bms@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-powerwall2-bms@bv'),260.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-powerwall2-hv_box','component',(SELECT id FROM organization WHERE uid='org/tesla'),'HV junction box for Tesla Powerwall 2 (13.5 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-powerwall2-hv_box@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-powerwall2-hv_box' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-powerwall2-hv_box@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-powerwall2-hv_box@bv'),190.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('component/tesla/tesla-powerwall2-thermal','component',(SELECT id FROM organization WHERE uid='org/tesla'),'Cooling plate assembly for Tesla Powerwall 2 (13.5 kWh)',
        'Tesla','unknown', false)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'component/tesla/tesla-powerwall2-thermal@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='component/tesla/tesla-powerwall2-thermal' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id,
       child_revision_id, quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),(SELECT id FROM product_revision WHERE uid='component/tesla/tesla-powerwall2-thermal@bv'),1,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, sell_through, valid_from, region,
       provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='component/tesla/tesla-powerwall2-thermal@bv'),70.0,'EUR',0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO product (uid, kind, manufacturer_id, model_number,
                     brand, lifecycle, is_rechargeable)
VALUES ('module/tesla/tesla-powerwall2','module',(SELECT id FROM organization WHERE uid='org/tesla'),'tesla-powerwall2-module',
        'Tesla','unknown', true)
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_revision (uid, product_id, source_id,
                              revision_label)
SELECT 'module/tesla/tesla-powerwall2@bv', p.id, s.id, 'bv-catalogue'
  FROM product p, source s
 WHERE p.uid='module/tesla/tesla-powerwall2' AND s.uid='src/bv-pack-catalogue'
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_assembly (parent_revision_id, child_revision_id,
       quantity, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),(SELECT id FROM product_revision WHERE uid='module/tesla/tesla-powerwall2@bv'),2,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
ON CONFLICT (parent_revision_id, child_revision_id) DO NOTHING;
INSERT INTO component_market_value (product_revision_id,
       unit_value, currency, assumed_soh, sell_through,
       valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='module/tesla/tesla-powerwall2@bv'),900.0,'EUR',1.0,0.95,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO replacement_price (product_revision_id, price_per_kwh,
       currency, includes_labour, valid_from, region, provenance_id)
SELECT (SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),620.0,'EUR', false,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-used-parts-market');
INSERT INTO application (uid, name, sector, operator_text, region,
                         in_service_from)
VALUES ('app/powerwall-2','Powerwall 2','passenger_vehicle','Tesla','EU',
        '2016-01-01')
ON CONFLICT (uid) DO NOTHING;
INSERT INTO product_application (application_id,
       product_revision_id, role, quantity_per_unit, basis,
       confidence, provenance_id)
SELECT a.id,(SELECT id FROM product_revision WHERE uid='pack/tesla/tesla-powerwall2@bv'),'traction',1,'teardown',0.65,
       (SELECT id FROM provenance WHERE derivation_note='src/bv-pack-catalogue')
  FROM application a WHERE a.uid='app/powerwall-2'
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Degradation profiles: how fast each pack model wears out.
--
-- fade_at_8y already contains the cycling a typical car of this
-- model does, which is what reference_km_per_year records. A
-- consumer that adds a full cycle term on top would bill the same
-- kilometres twice.
-- ---------------------------------------------------------------------
INSERT INTO valuation_assumption (key, value_num, unit,
       valid_from, region, provenance_id) VALUES
  ('degradation.reference_km_per_year',13500,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('degradation.km_per_kwh',5.5,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('degradation.calendar_exponent',0.5,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('degradation.knee_onset_soh',0.68,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('degradation.knee_acceleration',1.35,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('degradation.spread_points_at_8y',5.0,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_factor.cool',0.82,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_factor.temperate',1.0,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_factor.warm',1.25,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_factor.hot',1.55,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_sensitivity.low',0.5,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_sensitivity.medium',1.0,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles')),
  ('climate_sensitivity.high',1.4,'fraction','2026-01-01','EU',
   (SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'));

INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'passive'::thermal_management,
       0.28,'high',0.85,
       'large owner-reported dataset, plus the well-documented hot-climate failures','No cooling at all, and a manganese-spinel cathode that dislikes heat. The fastest-ageing mainstream EV pack ever sold, and the reason every maker since has cooled its packs.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1200, 9000, 7.0
  FROM product p WHERE p.uid='pack/nissan/nissan-leaf-ze0-24'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'passive'::thermal_management,
       0.19,'high',0.85,
       'owner-reported capacity readings and fleet telemetry','Still passively cooled, but a better cathode. Rapid-charges badly in summer, so a pack used mainly on DC fast chargers ages well ahead of this curve.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1500, 11000, 6.0
  FROM product p WHERE p.uid='pack/nissan/nissan-leaf-ze1-40'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'passive'::thermal_management,
       0.16,'high',0.65,
       'owner-reported readings; fewer years in service than the 40 kWh','The bigger pack runs each cell gentler for the same journey, which offsets some of the missing cooling.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1600, 13000, 5.5
  FROM product p WHERE p.uid='pack/nissan/nissan-leaf-ze1-62'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'air'::thermal_management,
       0.17,'medium',0.65,
       'fleet telemetry and leasing-company return data','Air cooling and a low charge rate for most of its life. Many were battery-leased, so their capacity was tracked and weak packs replaced.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1600, 11000, 5.0
  FROM product p WHERE p.uid='pack/renault/renault-zoe-ze40'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'air'::thermal_management,
       0.15,'medium',0.65,
       'fleet telemetry',NULL,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1700, 12000, 4.5
  FROM product p WHERE p.uid='pack/renault/renault-zoe-ze50'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.15,'low',0.85,
       'long service history with refrigerant cooling from new','Directly refrigerant-cooled, so climate barely moves it. The small pack is worked hard per kilometre, which is what keeps this above the later cars.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1600, 9500, 4.0
  FROM product p WHERE p.uid='pack/bmw/bmw-i3-60ah'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.13,'low',0.85,
       'long service history; capacity readings widely published by owners',NULL,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1800, 10500, 3.5
  FROM product p WHERE p.uid='pack/bmw/bmw-i3-94ah'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.12,'low',0.85,
       'service history and owner-reported readings','One of the best-ageing packs of its generation.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 11000, 3.5
  FROM product p WHERE p.uid='pack/bmw/bmw-i3-120ah'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.11,'low',0.85,
       'manufacturer fleet reporting and large owner-telemetry datasets','Loses most of its first few percent quickly, then flattens hard. High annual mileage is normal for this car, and the reference reflects that.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 18000, 3.5
  FROM product p WHERE p.uid='pack/tesla/tesla-model3-lr'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.12,'medium',0.65,
       'owner telemetry; fewer years in service','Charged to 100% routinely by design, which costs a little calendar life but the cell tolerates cycling far better. High-mileage examples age much better than the nickel packs.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 3500, 16000, 3.5
  FROM product p WHERE p.uid='pack/tesla/tesla-model3-lfp'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.13,'low',0.85,
       'very long service history across a large owner-reported dataset','The oldest large fleet on record, and the clearest demonstration of the flattening curve: most of the loss happens in the first three years.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1800, 17000, 4.5
  FROM product p WHERE p.uid='pack/tesla/tesla-models-85'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.13,'low',0.65,
       'warranty floor plus early fleet telemetry',NULL,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 13500, 4.0
  FROM product p WHERE p.uid='pack/volkswagen/vw-id3-58'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.12,'low',0.65,
       'warranty floor plus early fleet telemetry',NULL,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 15000, 4.0
  FROM product p WHERE p.uid='pack/volkswagen/vw-id4-77'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.11,'low',0.85,
       'fleet telemetry across several years and climates','Consistently one of the slowest-ageing packs measured.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 14000, 3.5
  FROM product p WHERE p.uid='pack/hyundai/hyundai-kona-64'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.12,'medium',0.45,
       'manufacturer cycle-life claims; too few years in service to verify calendar fade','The cell outlasts the car on cycles. What limits this pack is calendar time, not use, so mileage barely moves it.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 4000, 14000, 4.0
  FROM product p WHERE p.uid='pack/byd/byd-atto3-60'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.14,'low',0.65,
       'warranty floor plus fleet telemetry',NULL,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 1800, 12000, 4.5
  FROM product p WHERE p.uid='pack/stellantis/psa-emp1-50'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.1,'low',0.85,
       'fleet telemetry; heavily buffered pack','Only about 86% of the pack is ever used. The buffer is expensive in kWh you paid for and never see, and it is why this pack ages so slowly.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 16000, 3.0
  FROM product p WHERE p.uid='pack/audi/audi-etron-95'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.12,'low',0.65,
       'warranty floor plus fleet telemetry',NULL,
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2000, 15000, 4.0
  FROM product p WHERE p.uid='pack/polestar/polestar2-78'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'air'::thermal_management,
       0.2,'high',0.65,
       'very long service history; failures are usually one weak module, not even fade','A hybrid pack cycles shallowly thousands of times a year, so mileage hardly matters. These rarely fade to death; they fail when one module drifts and the others carry it. Cell imbalance is the number to watch, not capacity.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 3000, 15000, 8.0
  FROM product p WHERE p.uid='pack/toyota/toyota-prius-xw30-nimh'
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (product_id, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, reference_km_per_year, spread_points_at_8y)
SELECT p.id,'liquid'::thermal_management,
       0.16,'low',0.65,
       'manufacturer warranty floor of 70% retention at ten years','A stationary product, cycled daily by design. Its cycle count is meaningful where a car''s mileage is not, so the reference mileage does not apply.',
       '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 3500, 0, 4.0
  FROM product p WHERE p.uid='pack/tesla/tesla-powerwall2'
ON CONFLICT DO NOTHING;

-- Chemistry fallbacks, for packs the catalogue does not recognise.
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('LMO','unknown'::thermal_management,
        0.26,'high',0.45,
        NULL,'Manganese dissolves out of the cathode at temperature. Almost every LMO traction pack was passively cooled.',
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 7.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NMC111','unknown'::thermal_management,
        0.15,'medium',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 5.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NMC532','unknown'::thermal_management,
        0.15,'medium',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 5.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NMC622','unknown'::thermal_management,
        0.14,'medium',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 4.5)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NMC712','unknown'::thermal_management,
        0.13,'medium',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 4.5)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NMC811','unknown'::thermal_management,
        0.14,'medium',0.45,
        NULL,'More nickel buys energy density at some cost in stability.',
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 5.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NCA','unknown'::thermal_management,
        0.13,'low',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 4.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, spread_points_at_8y)
VALUES ('LFP','unknown'::thermal_management,
        0.12,'medium',0.45,
        NULL,'Outstanding on cycles, ordinary on calendar time. An LFP pack that sits unused ages much like any other.',
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 3500, 4.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, spread_points_at_8y)
VALUES ('LMFP','unknown'::thermal_management,
        0.13,'medium',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 2800, 4.5)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, spread_points_at_8y)
VALUES ('LTO','unknown'::thermal_management,
        0.07,'low',0.45,
        NULL,'Barely ages. Its problem is energy density and price, never life.',
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 15000, 2.5)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('LCO','unknown'::thermal_management,
        0.3,'high',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 7.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, spread_points_at_8y)
VALUES ('NA_ION','unknown'::thermal_management,
        0.16,'medium',0.45,
        NULL,'Too new for field data. This is an expectation, not an observation.',
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 6.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, spread_points_at_8y)
VALUES ('NIMH','unknown'::thermal_management,
        0.2,'high',0.45,
        NULL,NULL,
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 3000, 8.0)
ON CONFLICT DO NOTHING;
INSERT INTO degradation_profile (chemistry, thermal_management,
       fade_at_8y, climate_sensitivity, confidence, basis, notes,
       valid_from, region, provenance_id, cycle_life_to_80pct, spread_points_at_8y)
VALUES ('LEAD_ACID','unknown'::thermal_management,
        0.45,'high',0.45,
        NULL,'Short-lived by design and cheap to replace, which is why nobody tracks its fade closely.',
        '2026-01-01','EU',(SELECT id FROM provenance WHERE derivation_note='src/bv-degradation-profiles'), 500, 10.0)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Generated 2026-08-03 from battery-value data files.
-- ---------------------------------------------------------------------
