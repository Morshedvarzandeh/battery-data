-- =====================================================================
-- battery-data : 165_patent_staging.sql
-- Raw patent/IP source rows and canonical publication candidates.
-- =====================================================================

SET search_path = bd_stage, bd, public;

CREATE TABLE bd_stage.patent_observation (
  id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id                   bigint NOT NULL REFERENCES bd_stage.ingest_job(id) ON DELETE CASCADE,
  observation_uid          text NOT NULL UNIQUE,
  cordis_project_id        text NOT NULL,
  project_acronym          text,
  cordis_result_id         text NOT NULL,
  title                    text NOT NULL,
  battery_relevance        text NOT NULL,
  identity_state           bd.patent_identity_state NOT NULL,
  publication_number       text,
  obvious_non_patent_title boolean NOT NULL DEFAULT false,
  primary_category         text REFERENCES bd.patent_category(code),
  categories               text[] NOT NULL DEFAULT '{}',
  raw_payload              jsonb NOT NULL,
  state                    bd_stage.candidate_state NOT NULL DEFAULT 'queued',
  reviewed_by              bigint REFERENCES bd.contributor(id),
  reviewed_at              timestamptz,
  review_note              text,
  created_at               timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT verified_source_row_has_publication CHECK (
    identity_state <> 'verified_publication' OR publication_number IS NOT NULL
  )
);
CREATE INDEX ON bd_stage.patent_observation (identity_state);
CREATE INDEX ON bd_stage.patent_observation (publication_number) WHERE publication_number IS NOT NULL;
CREATE INDEX ON bd_stage.patent_observation (primary_category);
CREATE INDEX ON bd_stage.patent_observation USING gin (raw_payload jsonb_path_ops);

CREATE TABLE bd_stage.patent_publication_candidate (
  id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id                   bigint NOT NULL REFERENCES bd_stage.ingest_job(id) ON DELETE CASCADE,
  publication_uid          text NOT NULL UNIQUE,
  publication_number       text NOT NULL UNIQUE,
  title                    text NOT NULL,
  publication_url          text NOT NULL,
  battery_relevance        text NOT NULL,
  primary_category         text REFERENCES bd.patent_category(code),
  categories               text[] NOT NULL DEFAULT '{}',
  source_observation_uids  text[] NOT NULL,
  raw_payload              jsonb NOT NULL,
  state                    bd_stage.candidate_state NOT NULL DEFAULT 'queued',
  reviewed_by              bigint REFERENCES bd.contributor(id),
  reviewed_at              timestamptz,
  review_note              text,
  created_at               timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT publication_candidate_has_sources CHECK (cardinality(source_observation_uids) > 0)
);
CREATE INDEX ON bd_stage.patent_publication_candidate (primary_category);
CREATE INDEX ON bd_stage.patent_publication_candidate (state);
CREATE INDEX ON bd_stage.patent_publication_candidate USING gin (raw_payload jsonb_path_ops);

CREATE TABLE bd_stage.patent_company_candidate (
  id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id                   bigint NOT NULL REFERENCES bd_stage.ingest_job(id) ON DELETE CASCADE,
  company_uid              text NOT NULL UNIQUE,
  canonical_name           text NOT NULL,
  legal_name               text,
  country                  text CHECK (country IS NULL OR country ~ '^[A-Z]{2}$'),
  organization_type        text NOT NULL CHECK (organization_type IN ('company','research_institution','government','unknown_organization')),
  aliases                  text[] NOT NULL,
  primary_category         text REFERENCES bd.organization_category(code),
  categories               text[] NOT NULL,
  publication_count        integer NOT NULL CHECK (publication_count > 0),
  earliest_publication_date date,
  latest_publication_date   date,
  website                  text,
  raw_payload              jsonb NOT NULL,
  state                    bd_stage.candidate_state NOT NULL DEFAULT 'queued',
  reviewed_by              bigint REFERENCES bd.contributor(id),
  reviewed_at              timestamptz,
  review_note              text,
  created_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON bd_stage.patent_company_candidate (primary_category);
CREATE INDEX ON bd_stage.patent_company_candidate (country);
CREATE INDEX ON bd_stage.patent_company_candidate (publication_count DESC);
CREATE INDEX ON bd_stage.patent_company_candidate USING gin (aliases);
CREATE INDEX ON bd_stage.patent_company_candidate USING gin (raw_payload jsonb_path_ops);

CREATE TABLE bd_stage.patent_publication_company_link (
  job_id                   bigint NOT NULL REFERENCES bd_stage.ingest_job(id) ON DELETE CASCADE,
  publication_uid          text NOT NULL REFERENCES bd_stage.patent_publication_candidate(publication_uid) ON DELETE CASCADE,
  company_uid              text NOT NULL REFERENCES bd_stage.patent_company_candidate(company_uid) ON DELETE CASCADE,
  relation                 text NOT NULL CHECK (relation IN ('applicant','assignee','owner_observed','licensee')),
  raw_name                 text NOT NULL,
  country                  text CHECK (country IS NULL OR country ~ '^[A-Z]{2}$'),
  raw_payload              jsonb NOT NULL,
  state                    bd_stage.candidate_state NOT NULL DEFAULT 'queued',
  reviewed_by              bigint REFERENCES bd.contributor(id),
  reviewed_at              timestamptz,
  review_note              text,
  created_at               timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (publication_uid, company_uid, relation, raw_name)
);
CREATE INDEX ON bd_stage.patent_publication_company_link (company_uid, relation);

COMMENT ON TABLE bd_stage.patent_observation IS
  'Immutable source observations. CORDIS PATENT_IP is a source label, not an acceptance decision.';
COMMENT ON TABLE bd_stage.patent_publication_candidate IS
  'Publication-number-deduplicated candidates awaiting DOCDB family resolution and human review.';
COMMENT ON TABLE bd_stage.patent_company_candidate IS
  'Normalised applicant organisations awaiting entity-curator approval; profiles and value-chain categories remain provisional.';
COMMENT ON TABLE bd_stage.patent_publication_company_link IS
  'Applicant links from source metadata. An applicant link is not evidence of current ownership.';
