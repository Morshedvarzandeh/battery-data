-- =====================================================================
-- Patent intelligence invariants and representative queries.
-- =====================================================================
\set ON_ERROR_STOP on
SET search_path = bd, bd_stage, bd_graph, public;

INSERT INTO bd.contributor (uid, display_name, github)
VALUES ('contrib/patent-fixture-reviewer', 'Patent fixture reviewer', 'fixture-reviewer')
ON CONFLICT (uid) DO NOTHING;

INSERT INTO bd.source (uid, kind, title, url, repository, repository_id,
                       retrieved_at, retrieved_from, license,
                       redistributable, raw_metadata)
VALUES ('source/patent-fixture-shard', 'patent', 'Patent fixture source shard',
        'https://example.test/patents/fixture', 'fixture', 'fixture-2026-08-24',
        '2026-08-24T20:00:00Z', 'https://example.test/patents/fixture',
        'fixture-metadata-only', false, '{"fixture":true}')
ON CONFLICT (uid) DO NOTHING;

INSERT INTO bd.patent_release
  (uid, release_version, taxonomy_version, classifier_version,
   source_snapshot, manifest_sha256, intended_records, validation_report)
VALUES
  ('patent-release/fixture-v1', 'fixture-v1', '1.0.0', 'patent-miner-0.1.0',
   '{"fixture":{"retrieved_at":"2026-08-24T20:00:00Z"}}',
   repeat('a',64), 1,
   '{"records":1,"families":1,"duplicates":0,"invalid":0,"unclassified":0,"source_errors":0}')
ON CONFLICT (uid) DO NOTHING;

-- A pending release must not be able to populate the accepted core.
DO $$
DECLARE release_id_ bigint; source_id_ bigint; gate_worked boolean := false;
BEGIN
  SELECT id INTO release_id_ FROM bd.patent_release WHERE uid='patent-release/fixture-v1';
  SELECT id INTO source_id_ FROM bd.source WHERE uid='source/patent-fixture-shard';
  BEGIN
    INSERT INTO bd.patent_document
      (uid, release_id, publication_number, authority, document_number,
       kind_code, publication_date, source_id, source_record_id, record_sha256)
    VALUES
      ('patent/EP3998669A1', release_id_, 'EP3998669A1', 'EP', '3998669A1',
       'A1', '2022-05-18', source_id_, 'EP-3998669-A1', repeat('b',64));
  EXCEPTION WHEN OTHERS THEN
    gate_worked := SQLERRM LIKE '%not in a human-approved release%';
  END;
  IF NOT gate_worked THEN
    RAISE EXCEPTION 'patent release gate did not reject a pending release';
  END IF;
END$$;

UPDATE bd.patent_release
   SET status='accepted',
       approved_by=(SELECT id FROM bd.contributor WHERE uid='contrib/patent-fixture-reviewer'),
       approved_at='2026-08-24T21:00:00Z'
 WHERE uid='patent-release/fixture-v1';

INSERT INTO bd.patent_document
  (uid, release_id, publication_number, authority, document_number,
   kind_code, application_number, priority_date, publication_date,
   source_id, source_record_id, source_record_url, record_sha256)
SELECT 'patent/EP3998669A1', r.id, 'EP3998669A1', 'EP', '3998669A1',
       'A1', 'EP20734926.7', '2019-07-12', '2022-05-18', s.id,
       'EP-3998669-A1', 'https://example.test/patents/EP3998669A1', repeat('b',64)
  FROM bd.patent_release r, bd.source s
 WHERE r.uid='patent-release/fixture-v1' AND s.uid='source/patent-fixture-shard'
ON CONFLICT (uid) DO NOTHING;

INSERT INTO bd.source_location (source_id, locator_kind, section, quote)
SELECT s.id, 'api_field', 'cpc[0]', 'H01M 10/625'
  FROM bd.source s WHERE s.uid='source/patent-fixture-shard'
  AND NOT EXISTS (
    SELECT 1 FROM bd.source_location sl
     WHERE sl.source_id=s.id AND sl.locator_kind='api_field' AND sl.section='cpc[0]');

INSERT INTO bd.provenance
  (source_location_id, evidence, extraction, confidence, review,
   reviewed_by, reviewed_at, review_note)
SELECT sl.id, 'literature_reported', 'api_import', 1.0, 'accepted',
       c.id, '2026-08-24T21:00:00Z', 'fixture release review'
  FROM bd.source_location sl
  JOIN bd.source s ON s.id=sl.source_id AND s.uid='source/patent-fixture-shard'
  CROSS JOIN bd.contributor c
 WHERE sl.locator_kind='api_field' AND sl.section='cpc[0]'
   AND c.uid='contrib/patent-fixture-reviewer'
   AND NOT EXISTS (
     SELECT 1 FROM bd.provenance p
      WHERE p.source_location_id=sl.id AND p.review_note='fixture release review');

INSERT INTO bd.patent_title (patent_document_id, language, text)
SELECT id, 'en', 'Battery module with thermal management system'
  FROM bd.patent_document WHERE uid='patent/EP3998669A1'
ON CONFLICT DO NOTHING;

INSERT INTO bd.patent_abstract (patent_document_id, language, text)
SELECT id, 'en', 'A battery module uses a coolant path to control cell temperature.'
  FROM bd.patent_document WHERE uid='patent/EP3998669A1'
ON CONFLICT DO NOTHING;

INSERT INTO bd.patent_family
  (uid, kind, provider, provider_family_id, earliest_priority, canonical_title)
VALUES
  ('patent-family/simple/778899', 'simple', 'fixture', '778899', '2019-07-12',
   'Battery module with thermal management system')
ON CONFLICT (uid) DO NOTHING;

INSERT INTO bd.patent_family_member
  (patent_family_id, patent_document_id, is_representative)
SELECT f.id, d.id, true
  FROM bd.patent_family f, bd.patent_document d
 WHERE f.uid='patent-family/simple/778899' AND d.uid='patent/EP3998669A1'
ON CONFLICT DO NOTHING;

INSERT INTO bd.patent_classification
  (patent_document_id, scheme, code, inventive, first_position, source_location_id)
SELECT d.id, 'CPC', 'H01M10/625', true, true, sl.id
  FROM bd.patent_document d
  JOIN bd.source s ON s.uid='source/patent-fixture-shard'
  JOIN bd.source_location sl ON sl.source_id=s.id AND sl.section='cpc[0]'
 WHERE d.uid='patent/EP3998669A1'
ON CONFLICT DO NOTHING;

INSERT INTO bd.patent_taxon
  (uid, taxonomy_version, facet, code, label, description)
VALUES
  ('patent-taxon/1.0.0/pack_system/thermal_management', '1.0.0',
   'pack_system', 'thermal_management', 'Battery thermal management',
   'Fixture taxonomy row')
ON CONFLICT (uid) DO NOTHING;

INSERT INTO bd.patent_annotation
  (patent_document_id, taxon_id, method, score, rule_id, evidence_text, provenance_id)
SELECT d.id, t.id, 'classification_rule', 0.98,
       '1.0.0:pack_system/thermal_management', 'H01M10/625', p.id
  FROM bd.patent_document d
  CROSS JOIN bd.patent_taxon t
  CROSS JOIN bd.provenance p
 WHERE d.uid='patent/EP3998669A1'
   AND t.uid='patent-taxon/1.0.0/pack_system/thermal_management'
   AND p.review_note='fixture release review'
   AND NOT EXISTS (
     SELECT 1 FROM bd.patent_annotation a
      WHERE a.patent_document_id=d.id AND a.taxon_id=t.id);

-- Agent candidate stays staged and is validated from source, rights and
-- battery-relevance evidence. It is not an accepted patent_document.
INSERT INTO bd_stage.patent_candidate
  (candidate_uid, publication_number, family_key, source_provider,
   source_record_id, source_record_url, taxonomy_version, record_sha256,
   payload, relevance_reasons)
VALUES
  ('patent-candidate/fixture', 'US2024999999A1', 'fixture:simple:999',
   'fixture', 'US-2024-999999-A1', 'https://example.test/patents/US2024999999A1',
   '1.0.0', repeat('c',64),
   '{"titles":[{"language":"en","text":"Battery separator","machine_translation":false}],"abstracts":[],"classifications":[{"scheme":"CPC","code":"H01M50/40"}],"rights":{"metadata_license":"fixture","fulltext_redistributable":false}}',
   '[{"taxon_id":"component/separator","method":"classification_rule","score":0.92,"evidence":["H01M50/40"]}]')
ON CONFLICT (candidate_uid) DO NOTHING;

SELECT bd_stage.validate_patent_candidate(
  (SELECT id FROM bd_stage.patent_candidate WHERE candidate_uid='patent-candidate/fixture'));

DO $$
DECLARE state_ bd.patent_candidate_state; accepted_count bigint;
BEGIN
  SELECT state INTO state_ FROM bd_stage.patent_candidate
   WHERE candidate_uid='patent-candidate/fixture';
  IF state_ <> 'valid' THEN
    RAISE EXCEPTION 'valid patent candidate was rejected: %', state_;
  END IF;
  SELECT count(*) INTO accepted_count FROM bd.patent_document
   WHERE publication_number='US2024999999A1';
  IF accepted_count <> 0 THEN
    RAISE EXCEPTION 'staged candidate leaked into accepted patent_document';
  END IF;
END$$;

SELECT publication_number, title_en, classifications, battery_taxonomy,
       patent_families
  FROM bd.v_patent_search
 WHERE publication_number='EP3998669A1';

\echo 'ok: patent release gate, staging, family, classification and taxonomy'
