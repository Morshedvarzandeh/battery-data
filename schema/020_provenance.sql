-- =====================================================================
-- battery-data : 020_provenance.sql
--
-- Provenance is not a footnote in this schema, it is a hard dependency.
-- Every observation, curve, test run and derived result carries a
-- NOT NULL foreign key to a source_location. If you cannot say where a
-- number came from and point at the exact page, table or figure, the
-- database will not accept it.
--
-- This is also the legal posture: facts are not copyrightable but
-- compilations can be, so per-value attribution plus a retrieval record
-- is what makes a takedown request answerable instead of existential.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Organisations: manufacturers, labs, publishers, distributors, SDOs.
-- ---------------------------------------------------------------------
CREATE TABLE organization (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid          text NOT NULL UNIQUE,            -- 'org/samsung-sdi'
  name         text NOT NULL,
  legal_name   text,
  country      text,                            -- ISO 3166-1 alpha-2
  roles        text[] NOT NULL DEFAULT '{}',    -- manufacturer|lab|publisher|sdo|distributor|integrator
  parent_id    bigint REFERENCES organization(id),
  website      text,
  ror_id       text,                            -- Research Organization Registry
  gleif_lei    text,
  pic          text,                            -- EU Participant Identification Code
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- PIC is the identifier the European Commission uses for every organisation
-- that has ever signed an EU grant. Like ROR and LEI it is externally
-- assigned and stable across renamings, so it belongs beside them rather
-- than in organization_alias, which is for names people actually write.
-- Partial index: most organisations here have never touched EU funding.
CREATE UNIQUE INDEX organization_pic_key ON organization (pic) WHERE pic IS NOT NULL;

-- Sanyo -> Panasonic, E-One Moli -> Molicel, and so on. Without this,
-- the same cell appears under three manufacturers.
CREATE TABLE organization_alias (
  id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id   bigint NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
  alias    text NOT NULL,
  kind     text NOT NULL DEFAULT 'trade_name',  -- trade_name|former_name|brand|abbreviation
  UNIQUE (org_id, alias)
);
CREATE INDEX ON organization_alias USING gin (alias gin_trgm_ops);

-- ---------------------------------------------------------------------
-- Standards, referenced but never redistributed. IEC/ISO/SAE texts are
-- paywalled; we store the citation and our own recorded conditions.
-- ---------------------------------------------------------------------
CREATE TABLE standard (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid          text NOT NULL UNIQUE,            -- 'std/iec-62660-1-2018'
  sdo          text NOT NULL,                   -- IEC, ISO, SAE, UN, GB, USABC, UL
  number       text NOT NULL,                   -- '62660'
  part         text,                            -- '1'
  edition      text,
  year         int,
  title        text NOT NULL,
  url          text,
  is_open_access boolean NOT NULL DEFAULT false,
  notes        text
);

-- ---------------------------------------------------------------------
-- SOURCE: one row per retrievable artefact.
-- ---------------------------------------------------------------------
CREATE TABLE source (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid               text NOT NULL UNIQUE,
  kind              source_kind NOT NULL,
  title             text,
  publisher_org_id  bigint REFERENCES organization(id),
  standard_id       bigint REFERENCES standard(id),

  -- identifiers
  doi               text,
  arxiv_id          text,
  pubmed_id         text,
  isbn              text,
  url               text,
  landing_url       text,             -- human-facing page, if url is a file
  repository        text,             -- zenodo|figshare|osti|batteryarchive|github|...
  repository_id     text,

  -- document identity. One model number does not imply one spec: the
  -- Samsung 50E exists as V0.2, V1.0 and a customer-scoped "Tentative".
  document_number   text,             -- e.g. LG '2020-LSD-MBD-b00082'
  revision          text,             -- 'V1.0', 'Rev B'
  document_date     date,
  is_final          boolean,          -- false when marked draft/tentative
  scope_note        text,             -- 'issued to WPG China Inc', 'AU variant'
  region_scope      text[],           -- ISO country codes this doc applies to

  -- bibliographic
  authors           jsonb,            -- [{given, family, orcid, affiliation}]
  container_title   text,             -- journal / proceedings
  volume            text, issue text, pages text,
  published_year    int,

  -- retrieval and integrity
  retrieved_at      timestamptz,
  retrieved_from    text,
  content_sha256    text,             -- hash of the exact bytes we parsed
  media_type        text,
  byte_size         bigint,
  storage_uri       text,             -- object-store pointer to the archived copy
  source_encoding   text,             -- ISO-8859-1 etc; a real ingest trap

  -- rights
  license           text,             -- SPDX id or 'proprietary'
  license_url       text,
  redistributable   boolean NOT NULL DEFAULT false,
  access_tier       access_tier NOT NULL DEFAULT 'public',
  takedown_state    text NOT NULL DEFAULT 'none',  -- none|requested|honoured

  raw_metadata      jsonb NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  -- A source must be findable again by someone other than its author.
  -- storage_uri covers internally-held datasets, which legitimately have
  -- no DOI or public URL but must still point at retrievable bytes.
  CONSTRAINT source_has_locator CHECK (
    doi IS NOT NULL OR url IS NOT NULL OR content_sha256 IS NOT NULL
      OR standard_id IS NOT NULL OR storage_uri IS NOT NULL
  )
);
CREATE INDEX ON source (kind);
CREATE INDEX ON source (doi) WHERE doi IS NOT NULL;
CREATE INDEX ON source (content_sha256) WHERE content_sha256 IS NOT NULL;
CREATE INDEX ON source USING gin (raw_metadata jsonb_path_ops);

CREATE TRIGGER source_touch BEFORE UPDATE ON source
  FOR EACH ROW EXECUTE FUNCTION bd.touch_updated_at();

-- ---------------------------------------------------------------------
-- SOURCE_LOCATION: the exact place inside a source.
-- "Table 3 on page 4" is the difference between a citation and a claim
-- that can be re-checked by a human in ten seconds.
-- ---------------------------------------------------------------------
CREATE TABLE source_location (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id     bigint NOT NULL REFERENCES source(id) ON DELETE CASCADE,
  page          int,
  section       text,             -- '7.3.1', 'Table 2', 'Fig. 4b'
  locator_kind  text,             -- table|figure|paragraph|caption|si_file|column
  bbox          numeric[],        -- [x0,y0,x1,y1] in PDF user space
  quote         text,             -- verbatim snippet supporting the value
  file_path     text,             -- path inside a dataset archive
  row_ref       text,             -- row/record identifier inside that file
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON source_location (source_id);

-- Convenience: a location that says only "somewhere in this source".
CREATE OR REPLACE FUNCTION bd.whole_source(p_source_id bigint)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_id bigint;
BEGIN
  SELECT id INTO v_id FROM bd.source_location
   WHERE source_id = p_source_id AND locator_kind = 'whole_document' LIMIT 1;
  IF v_id IS NULL THEN
    INSERT INTO bd.source_location (source_id, locator_kind)
    VALUES (p_source_id, 'whole_document') RETURNING id INTO v_id;
  END IF;
  RETURN v_id;
END$$;

-- ---------------------------------------------------------------------
-- Agents and contributors. A record produced by an automated extractor
-- is attributable to a specific model and prompt version, so that when a
-- systematic extraction bug is found the blast radius is a single query.
-- ---------------------------------------------------------------------
CREATE TABLE agent_run (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,
  agent_name     text NOT NULL,        -- 'literature-miner', 'datasheet-extractor'
  agent_version  text NOT NULL,
  model_id       text,                 -- e.g. 'claude-opus-5'
  prompt_sha256  text,
  toolchain      jsonb NOT NULL DEFAULT '{}',   -- {parser: 'NewareNDA 2.1', ...}
  started_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz,
  input_summary  jsonb NOT NULL DEFAULT '{}',
  stats          jsonb NOT NULL DEFAULT '{}',
  notes          text
);

CREATE TABLE contributor (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid         text NOT NULL UNIQUE,
  display_name text NOT NULL,
  orcid       text,
  github      text,
  org_id      bigint REFERENCES organization(id),
  is_bot      boolean NOT NULL DEFAULT false
);

-- ---------------------------------------------------------------------
-- Attribution block, embedded into every fact-bearing table by composition.
-- Implemented as a reusable set of columns rather than a join table so
-- that the NOT NULL constraint is unavoidable.
-- ---------------------------------------------------------------------
CREATE TABLE provenance (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_location_id bigint NOT NULL REFERENCES source_location(id),
  evidence           evidence_class NOT NULL,
  extraction         extraction_method NOT NULL,
  agent_run_id       bigint REFERENCES agent_run(id),
  contributor_id     bigint REFERENCES contributor(id),
  confidence         numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  review             review_state NOT NULL DEFAULT 'pending_review',
  reviewed_by        bigint REFERENCES contributor(id),
  reviewed_at        timestamptz,
  review_note        text,
  -- when a value is derived, record what it was derived from
  derived_from       bigint[] ,
  derivation_note    text,
  created_at         timestamptz NOT NULL DEFAULT now(),

  -- An LLM-extracted value may never be marked accepted without a human
  -- reviewer. This is enforced, not documented.
  CONSTRAINT agent_values_need_review CHECK (
    NOT (evidence = 'inferred_by_agent' AND review = 'accepted' AND reviewed_by IS NULL)
  ),
  CONSTRAINT agent_extraction_has_run CHECK (
    NOT (extraction IN ('text_llm','vision_llm') AND agent_run_id IS NULL)
  )
);
CREATE INDEX ON provenance (source_location_id);
CREATE INDEX ON provenance (review);
CREATE INDEX ON provenance (agent_run_id) WHERE agent_run_id IS NOT NULL;
