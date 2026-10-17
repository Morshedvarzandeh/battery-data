-- =====================================================================
-- battery-data : 145_patents.sql
--
-- Patent intelligence is not a list of documents. One invention may be
-- published in many jurisdictions, ownership can change, legal status is
-- time-dependent, and a classification attached by an office is different
-- from a battery-domain label inferred by an agent. This schema keeps those
-- identities and evidence classes separate.
--
-- The agent writes only to bd_stage.patent_candidate. Rows enter bd.* only
-- through a human-approved, content-addressed release. The release trigger
-- makes that boundary enforceable instead of aspirational.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE patent_family_kind AS ENUM (
  'simple', 'inpadoc', 'national', 'artificial'
);

CREATE TYPE patent_relation_kind AS ENUM (
  'priority', 'continuation', 'continuation_in_part', 'divisional',
  'national_phase', 'grant_of', 'correction_of', 'reissue_of',
  'equivalent', 'other'
);

CREATE TYPE patent_party_role AS ENUM (
  'inventor', 'applicant', 'assignee', 'owner', 'agent', 'representative'
);

CREATE TYPE patent_classification_scheme AS ENUM (
  'IPC', 'CPC', 'USPC', 'FI', 'F_TERM', 'DEKLA', 'other'
);

CREATE TYPE patent_annotation_method AS ENUM (
  'source_asserted', 'classification_rule', 'keyword_rule',
  'embedding_model', 'llm', 'human'
);

CREATE TYPE patent_candidate_state AS ENUM (
  'new', 'valid', 'invalid', 'queued', 'approved', 'rejected',
  'released', 'duplicate'
);

-- ---------------------------------------------------------------------
-- Immutable release gate. A release is approved before its records are
-- promoted. The manifest hash covers the ordered record hashes, taxonomy,
-- source snapshot, classifier version and validation report.
-- ---------------------------------------------------------------------
CREATE TABLE patent_release (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                 text NOT NULL UNIQUE,
  release_version     text NOT NULL UNIQUE,
  taxonomy_version    text NOT NULL,
  classifier_version  text NOT NULL,
  source_snapshot     jsonb NOT NULL,
  manifest_sha256     text NOT NULL UNIQUE
                        CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  intended_records    bigint NOT NULL CHECK (intended_records >= 0),
  validation_report   jsonb NOT NULL DEFAULT '{}',
  sample_review       jsonb NOT NULL DEFAULT '{}',
  status              review_state NOT NULL DEFAULT 'pending_review',
  approved_by         bigint REFERENCES contributor(id),
  approved_at         timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT patent_release_human_gate CHECK (
    NOT (status = 'accepted' AND (approved_by IS NULL OR approved_at IS NULL))
  )
);

-- ---------------------------------------------------------------------
-- Document identity. publication_number is the office publication identity;
-- it must never be used as an invention/family identity.
-- ---------------------------------------------------------------------
CREATE TABLE patent_document (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                   text NOT NULL UNIQUE,
  release_id            bigint NOT NULL REFERENCES patent_release(id),
  publication_number    text NOT NULL UNIQUE,
  authority             text NOT NULL,
  document_number       text NOT NULL,
  kind_code             text,
  application_number    text,
  pct_number            text,
  filing_date           date,
  priority_date         date,
  publication_date      date,
  grant_date            date,
  withdrawn             boolean,
  source_id             bigint NOT NULL REFERENCES source(id),
  source_record_id      text NOT NULL,
  source_record_url     text,
  source_updated_at     timestamptz,
  record_sha256         text NOT NULL CHECK (record_sha256 ~ '^[0-9a-f]{64}$'),
  raw_metadata          jsonb NOT NULL DEFAULT '{}',
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT patent_document_number_parts CHECK (
    authority ~ '^[A-Z]{2}$' AND document_number ~ '^[0-9A-Z./-]+$'
  )
);
CREATE INDEX ON patent_document (application_number) WHERE application_number IS NOT NULL;
CREATE INDEX ON patent_document (priority_date);
CREATE INDEX ON patent_document (publication_date);
CREATE INDEX ON patent_document (release_id);
CREATE INDEX ON patent_document USING gin (raw_metadata jsonb_path_ops);
CREATE TRIGGER patent_document_touch BEFORE UPDATE ON patent_document
  FOR EACH ROW EXECUTE FUNCTION bd.touch_updated_at();

CREATE OR REPLACE FUNCTION bd.patent_document_release_gate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM bd.patent_release r
     WHERE r.id = NEW.release_id
       AND r.status = 'accepted'
       AND r.approved_by IS NOT NULL
       AND r.approved_at IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'patent document % is not in a human-approved release',
      NEW.publication_number;
  END IF;
  RETURN NEW;
END$$;

CREATE TRIGGER patent_document_release_gate
  BEFORE INSERT OR UPDATE OF release_id ON patent_document
  FOR EACH ROW EXECUTE FUNCTION bd.patent_document_release_gate();

-- Multilingual text is stored as rows. Machine translations are never allowed
-- to overwrite office-published text.
CREATE TABLE patent_title (
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  language           text NOT NULL,
  text               text NOT NULL,
  is_machine_translation boolean NOT NULL DEFAULT false,
  PRIMARY KEY (patent_document_id, language, is_machine_translation)
);
CREATE INDEX patent_title_search ON patent_title
  USING gin (to_tsvector('simple', text));

CREATE TABLE patent_abstract (
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  language           text NOT NULL,
  text               text NOT NULL,
  is_machine_translation boolean NOT NULL DEFAULT false,
  PRIMARY KEY (patent_document_id, language, is_machine_translation)
);
CREATE INDEX patent_abstract_search ON patent_abstract
  USING gin (to_tsvector('simple', text));

CREATE TABLE patent_claim (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  patent_document_id  bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  claim_number        int NOT NULL CHECK (claim_number > 0),
  language            text NOT NULL,
  text                text,
  text_sha256         text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
  is_independent      boolean,
  depends_on          int[] NOT NULL DEFAULT '{}',
  source_location_id  bigint NOT NULL REFERENCES source_location(id),
  redistributable     boolean NOT NULL DEFAULT false,
  UNIQUE (patent_document_id, claim_number, language)
);
CREATE INDEX patent_claim_document ON patent_claim (patent_document_id);
CREATE INDEX patent_claim_search ON patent_claim
  USING gin (to_tsvector('simple', COALESCE(text, '')))
  WHERE text IS NOT NULL AND redistributable;

-- ---------------------------------------------------------------------
-- Families and document relationships. Both simple and INPADOC family IDs
-- may coexist; callers must name which definition they mean.
-- ---------------------------------------------------------------------
CREATE TABLE patent_family (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,
  kind              patent_family_kind NOT NULL,
  provider          text NOT NULL,
  provider_family_id text NOT NULL,
  earliest_priority date,
  canonical_title   text,
  UNIQUE (kind, provider, provider_family_id)
);

CREATE TABLE patent_family_member (
  patent_family_id   bigint NOT NULL REFERENCES patent_family(id) ON DELETE CASCADE,
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  is_representative  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (patent_family_id, patent_document_id)
);
CREATE UNIQUE INDEX patent_family_one_representative
  ON patent_family_member (patent_family_id) WHERE is_representative;

CREATE TABLE patent_priority_claim (
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  sequence_no        int NOT NULL CHECK (sequence_no > 0),
  priority_number    text NOT NULL,
  authority          text,
  priority_date      date,
  PRIMARY KEY (patent_document_id, sequence_no)
);

CREATE TABLE patent_relation (
  from_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  to_document_id   bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  relation         patent_relation_kind NOT NULL,
  source_location_id bigint NOT NULL REFERENCES source_location(id),
  PRIMARY KEY (from_document_id, to_document_id, relation),
  CHECK (from_document_id <> to_document_id)
);

-- ---------------------------------------------------------------------
-- Parties. Names are source assertions, not reliable corporate identities.
-- organization_id is populated only by a separately reviewed resolution.
-- ---------------------------------------------------------------------
CREATE TABLE patent_party (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid             text NOT NULL UNIQUE,
  name_as_published text NOT NULL,
  normalized_name text,
  country         text,
  organization_id bigint REFERENCES organization(id),
  resolution_provenance_id bigint REFERENCES provenance(id)
);
CREATE INDEX patent_party_name_trgm ON patent_party
  USING gin ((COALESCE(normalized_name, name_as_published)) gin_trgm_ops);

CREATE TABLE patent_document_party (
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  patent_party_id    bigint NOT NULL REFERENCES patent_party(id),
  role               patent_party_role NOT NULL,
  sequence_no        int,
  source_location_id bigint NOT NULL REFERENCES source_location(id),
  PRIMARY KEY (patent_document_id, patent_party_id, role)
);
CREATE INDEX patent_document_party_role ON patent_document_party (role, patent_party_id);

-- Office classification is preserved exactly and separately from our own
-- editable battery taxonomy.
CREATE TABLE patent_classification (
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  scheme             patent_classification_scheme NOT NULL,
  code               text NOT NULL,
  version            text,
  inventive          boolean,
  first_position     boolean,
  source_location_id bigint NOT NULL REFERENCES source_location(id),
  PRIMARY KEY (patent_document_id, scheme, code)
);
CREATE INDEX patent_classification_code ON patent_classification (scheme, code text_pattern_ops);

CREATE TABLE patent_citation (
  citing_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  cited_publication_number text NOT NULL,
  cited_document_id  bigint REFERENCES patent_document(id),
  category           text,
  cited_by           text,
  source_location_id bigint NOT NULL REFERENCES source_location(id),
  PRIMARY KEY (citing_document_id, cited_publication_number)
);
CREATE INDEX patent_citation_target ON patent_citation (cited_document_id)
  WHERE cited_document_id IS NOT NULL;

CREATE TABLE patent_legal_event (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  event_date         date,
  event_code         text NOT NULL,
  jurisdiction       text,
  description        text,
  source_location_id bigint NOT NULL REFERENCES source_location(id),
  raw_event          jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX patent_legal_event_document_date
  ON patent_legal_event (patent_document_id, event_date DESC);

-- ---------------------------------------------------------------------
-- User-controlled, versioned battery taxonomy. The hierarchy is relational;
-- the graph is a projection. Agents may propose labels but cannot accept them.
-- ---------------------------------------------------------------------
CREATE TABLE patent_taxon (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid              text NOT NULL UNIQUE,
  taxonomy_version text NOT NULL,
  facet             text NOT NULL,
  code              text NOT NULL,
  label             text NOT NULL,
  description       text,
  parent_id         bigint REFERENCES patent_taxon(id),
  active            boolean NOT NULL DEFAULT true,
  UNIQUE (taxonomy_version, facet, code)
);

CREATE TABLE patent_annotation (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  patent_document_id bigint REFERENCES patent_document(id) ON DELETE CASCADE,
  patent_family_id   bigint REFERENCES patent_family(id) ON DELETE CASCADE,
  patent_claim_id    bigint REFERENCES patent_claim(id) ON DELETE CASCADE,
  taxon_id           bigint NOT NULL REFERENCES patent_taxon(id),
  method             patent_annotation_method NOT NULL,
  score              numeric(5,4) CHECK (score BETWEEN 0 AND 1),
  rule_id            text,
  evidence_text      text,
  provenance_id      bigint NOT NULL REFERENCES provenance(id),
  created_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT patent_annotation_one_subject CHECK (
    num_nonnulls(patent_document_id, patent_family_id, patent_claim_id) = 1
  )
);
CREATE INDEX patent_annotation_document ON patent_annotation (patent_document_id);
CREATE INDEX patent_annotation_family ON patent_annotation (patent_family_id);
CREATE INDEX patent_annotation_taxon ON patent_annotation (taxon_id, score DESC);

CREATE OR REPLACE FUNCTION bd.patent_annotation_review_gate()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p bd.provenance%ROWTYPE;
BEGIN
  SELECT * INTO p FROM bd.provenance WHERE id = NEW.provenance_id;
  IF NEW.method IN ('embedding_model','llm')
     AND p.review = 'accepted' AND p.reviewed_by IS NULL THEN
    RAISE EXCEPTION 'agent patent annotation % has no identified human reviewer', NEW.id;
  END IF;
  RETURN NEW;
END$$;

CREATE TRIGGER patent_annotation_review_gate
  BEFORE INSERT OR UPDATE OF method, provenance_id ON patent_annotation
  FOR EACH ROW EXECUTE FUNCTION bd.patent_annotation_review_gate();

-- Reviewed links from patent intelligence to the rest of battery-data.
CREATE TABLE patent_entity_link (
  patent_document_id bigint NOT NULL REFERENCES patent_document(id) ON DELETE CASCADE,
  entity_key         text NOT NULL, -- org:12 | mat:9 | prod:30 | rev:41
  relation           text NOT NULL, -- ASSIGNED_TO | ABOUT_MATERIAL | ABOUT_PRODUCT
  provenance_id      bigint NOT NULL REFERENCES provenance(id),
  PRIMARY KEY (patent_document_id, entity_key, relation),
  CHECK (entity_key ~ '^(org|mat|prod|rev):[0-9]+$')
);

-- ---------------------------------------------------------------------
-- Staging: one self-contained normalized patent per row. Large full-text
-- bodies stay out of the payload; hashes and retrievable source locators stay.
-- ---------------------------------------------------------------------
CREATE TABLE bd_stage.patent_candidate (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  candidate_uid       text NOT NULL UNIQUE,
  agent_run_id        bigint REFERENCES bd.agent_run(id),
  publication_number  text NOT NULL,
  family_key          text NOT NULL,
  source_provider     text NOT NULL,
  source_record_id    text NOT NULL,
  source_record_url   text,
  taxonomy_version    text NOT NULL,
  record_sha256       text NOT NULL CHECK (record_sha256 ~ '^[0-9a-f]{64}$'),
  payload             jsonb NOT NULL,
  relevance_reasons   jsonb NOT NULL DEFAULT '[]',
  validation          jsonb NOT NULL DEFAULT '{}',
  state               patent_candidate_state NOT NULL DEFAULT 'new',
  reviewed_by         bigint REFERENCES bd.contributor(id),
  reviewed_at         timestamptz,
  review_note         text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_provider, source_record_id),
  UNIQUE (publication_number, record_sha256)
);
CREATE INDEX patent_candidate_state ON bd_stage.patent_candidate (state);
CREATE INDEX patent_candidate_family ON bd_stage.patent_candidate (family_key);
CREATE INDEX patent_candidate_payload ON bd_stage.patent_candidate
  USING gin (payload jsonb_path_ops);

CREATE OR REPLACE FUNCTION bd_stage.validate_patent_candidate(p_id bigint)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
  c bd_stage.patent_candidate%ROWTYPE;
  errs text[] := '{}';
  warns text[] := '{}';
BEGIN
  SELECT * INTO c FROM bd_stage.patent_candidate WHERE id = p_id;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('errors', ARRAY['no such candidate'], 'warnings', warns);
  END IF;

  IF c.publication_number !~ '^[A-Z]{2}[0-9A-Z./-]+$' THEN
    errs := errs || 'publication_number is not normalized';
  END IF;
  IF c.source_record_url IS NULL AND c.source_record_id = '' THEN
    errs := errs || 'source has no retrievable record locator';
  END IF;
  IF NOT (c.payload ? 'titles') AND NOT (c.payload ? 'abstracts') THEN
    errs := errs || 'neither title nor abstract is present';
  END IF;
  IF jsonb_array_length(COALESCE(c.relevance_reasons, '[]'::jsonb)) = 0 THEN
    errs := errs || 'no battery relevance evidence';
  END IF;
  IF c.payload #>> '{rights,metadata_license}' IS NULL THEN
    errs := errs || 'metadata rights are not recorded';
  END IF;
  IF COALESCE((c.payload #>> '{rights,fulltext_redistributable}')::boolean, false)
     AND c.payload #>> '{rights,fulltext_license}' IS NULL THEN
    errs := errs || 'redistributable full text has no recorded licence';
  END IF;
  IF NOT (c.payload ? 'classifications') THEN
    warns := warns || 'no IPC/CPC/source classification supplied';
  END IF;

  UPDATE bd_stage.patent_candidate
     SET validation = jsonb_build_object('errors', errs, 'warnings', warns),
         state = CASE WHEN cardinality(errs) = 0 THEN 'valid'::patent_candidate_state
                      ELSE 'invalid'::patent_candidate_state END
   WHERE id = p_id;
  RETURN jsonb_build_object('errors', errs, 'warnings', warns);
END$$;

CREATE VIEW bd_stage.patent_review_queue AS
SELECT c.*,
       (CASE WHEN jsonb_array_length(COALESCE(c.validation->'warnings','[]')) > 0
             THEN 40 ELSE 0 END
        + CASE WHEN jsonb_array_length(c.relevance_reasons) = 1 THEN 20 ELSE 0 END
        + CASE WHEN NOT (c.payload ? 'abstracts') THEN 10 ELSE 0 END) AS priority
  FROM bd_stage.patent_candidate c
 WHERE c.state IN ('valid','queued')
 ORDER BY priority DESC, c.created_at, c.id;

-- Search view intentionally returns family and taxonomy fields together while
-- keeping the underlying document/family distinction explicit.
CREATE VIEW v_patent_search AS
SELECT d.uid,
       d.publication_number,
       d.application_number,
       d.priority_date,
       d.publication_date,
       max(t.text) FILTER (WHERE t.language = 'en' AND NOT t.is_machine_translation)
         AS title_en,
       max(a.text) FILTER (WHERE a.language = 'en' AND NOT a.is_machine_translation)
         AS abstract_en,
       array_remove(array_agg(DISTINCT pc.scheme::text || ':' || pc.code), NULL)
         AS classifications,
       array_remove(array_agg(DISTINCT tx.facet || ':' || tx.code), NULL)
         AS battery_taxonomy,
       array_remove(array_agg(DISTINCT pf.uid), NULL) AS patent_families
  FROM patent_document d
  LEFT JOIN patent_title t ON t.patent_document_id = d.id
  LEFT JOIN patent_abstract a ON a.patent_document_id = d.id
  LEFT JOIN patent_classification pc ON pc.patent_document_id = d.id
  LEFT JOIN patent_annotation pa ON pa.patent_document_id = d.id
  LEFT JOIN patent_taxon tx ON tx.id = pa.taxon_id
  LEFT JOIN patent_family_member pfm ON pfm.patent_document_id = d.id
  LEFT JOIN patent_family pf ON pf.id = pfm.patent_family_id
 GROUP BY d.id;

COMMENT ON TABLE bd_stage.patent_candidate IS
  'Agent output only. Promotion requires a content-addressed patent_release '
  'with an identified human approver; agents cannot write patent_document directly.';
