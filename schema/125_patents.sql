-- =====================================================================
-- battery-data : 125_patents.sql
-- Patent-family and publication layer. Raw automated imports stay in
-- bd_stage; only reviewed records may enter these accepted tables.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE patent_identity_state AS ENUM (
  'source_label_only',      -- a source called it patent/IP; no office identity yet
  'verified_publication',   -- a publication number is backed by an office/search source
  'family_resolved'         -- publication has been resolved to a DOCDB family
);

CREATE TABLE patent_category (
  code                 text PRIMARY KEY,
  label                text NOT NULL,
  requested_domain     text CHECK (requested_domain IN ('electrical','mechanical','software','hardware')),
  definition           text NOT NULL,
  taxonomy_version     text NOT NULL
);

INSERT INTO patent_category (code, label, requested_domain, definition, taxonomy_version) VALUES
  ('electrical_power', 'Electrical & power', 'electrical', 'Power paths, BMS electrical functions, switching, conversion, charging and grid interfaces.', 'battery-patent-taxonomy-1.0.0'),
  ('mechanical_structures', 'Mechanical', 'mechanical', 'Structures, housings, compression, joining, impact protection, sealing and vent mechanics.', 'battery-patent-taxonomy-1.0.0'),
  ('software_control', 'Software & control', 'software', 'Algorithms, estimation, diagnostics, optimisation, digital twins, cybersecurity and control software.', 'battery-patent-taxonomy-1.0.0'),
  ('electronics_hardware', 'Electronics & hardware', 'hardware', 'Circuits, PCBs, ASICs, controllers, sensors, gateways and physical electronic devices.', 'battery-patent-taxonomy-1.0.0'),
  ('electrochemistry_materials', 'Electrochemistry & materials', NULL, 'Active materials, electrolytes, separators, electrodes and cell chemistry.', 'battery-patent-taxonomy-1.0.0'),
  ('manufacturing_process', 'Manufacturing', NULL, 'Electrode, cell, module and pack production, assembly, coating and process control.', 'battery-patent-taxonomy-1.0.0'),
  ('thermal_safety', 'Thermal & safety', NULL, 'Thermal management, abuse prevention, fire protection, runaway detection and venting safety.', 'battery-patent-taxonomy-1.0.0'),
  ('charging_infrastructure', 'Charging infrastructure', NULL, 'Charging equipment, grid interfaces and vehicle, marine or stationary charging.', 'battery-patent-taxonomy-1.0.0'),
  ('recycling_second_life', 'Recycling & second life', NULL, 'Recovery, disassembly, sorting, repurposing and second-life use.', 'battery-patent-taxonomy-1.0.0');

CREATE TABLE patent_family (
  id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                    text NOT NULL UNIQUE,
  docdb_family_id        text UNIQUE,
  title                  text NOT NULL,
  abstract               text,
  earliest_priority_date date,
  primary_category       text REFERENCES patent_category(code),
  taxonomy_version       text NOT NULL DEFAULT 'battery-patent-taxonomy-1.0.0',
  provenance_id          bigint REFERENCES provenance(id),
  review                 review_state NOT NULL DEFAULT 'pending_review',
  raw_metadata           jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT accepted_patent_family_is_resolved CHECK (
    review <> 'accepted' OR (docdb_family_id IS NOT NULL AND provenance_id IS NOT NULL)
  )
);
CREATE INDEX ON patent_family (primary_category);
CREATE INDEX ON patent_family (review);
CREATE INDEX ON patent_family USING gin (raw_metadata jsonb_path_ops);
CREATE TRIGGER patent_family_touch BEFORE UPDATE ON patent_family
  FOR EACH ROW EXECUTE FUNCTION bd.touch_updated_at();

CREATE TABLE patent_publication (
  id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                    text NOT NULL UNIQUE,
  family_id              bigint REFERENCES patent_family(id),
  publication_number     text NOT NULL UNIQUE,
  application_number     text,
  jurisdiction           text,
  kind_code              text,
  title                  text NOT NULL,
  abstract               text,
  priority_date          date,
  filing_date            date,
  publication_date       date,
  grant_date             date,
  applicants             jsonb NOT NULL DEFAULT '[]',
  assignees              jsonb NOT NULL DEFAULT '[]',
  inventors              jsonb NOT NULL DEFAULT '[]',
  source_id              bigint REFERENCES source(id),
  provenance_id          bigint REFERENCES provenance(id),
  publication_url        text,
  legal_status           text,
  legal_status_jurisdiction text,
  legal_status_as_of     date,
  review                 review_state NOT NULL DEFAULT 'pending_review',
  raw_metadata           jsonb NOT NULL DEFAULT '{}',
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT accepted_patent_publication_is_grounded CHECK (
    review <> 'accepted' OR (family_id IS NOT NULL AND source_id IS NOT NULL AND provenance_id IS NOT NULL)
  ),
  CONSTRAINT legal_status_is_dated CHECK (
    legal_status IS NULL OR (legal_status_jurisdiction IS NOT NULL AND legal_status_as_of IS NOT NULL)
  )
);
CREATE INDEX ON patent_publication (family_id);
CREATE INDEX ON patent_publication (jurisdiction);
CREATE INDEX ON patent_publication (review);
CREATE TRIGGER patent_publication_touch BEFORE UPDATE ON patent_publication
  FOR EACH ROW EXECUTE FUNCTION bd.touch_updated_at();

CREATE TABLE patent_classification (
  publication_id         bigint NOT NULL REFERENCES patent_publication(id) ON DELETE CASCADE,
  category_code          text NOT NULL REFERENCES patent_category(code),
  is_primary             boolean NOT NULL DEFAULT false,
  confidence             numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  basis                  jsonb NOT NULL DEFAULT '{}',
  taxonomy_version       text NOT NULL,
  review                 review_state NOT NULL DEFAULT 'pending_review',
  PRIMARY KEY (publication_id, category_code)
);
CREATE UNIQUE INDEX patent_one_primary_category
  ON patent_classification (publication_id) WHERE is_primary;

CREATE TABLE patent_project_link (
  publication_id         bigint NOT NULL REFERENCES patent_publication(id) ON DELETE CASCADE,
  cordis_project_id      text NOT NULL,
  project_acronym        text,
  battery_relevance      text NOT NULL,
  source_observation_uid text NOT NULL,
  PRIMARY KEY (publication_id, cordis_project_id, source_observation_uid)
);

CREATE TABLE patent_entity_link (
  id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  family_id              bigint NOT NULL REFERENCES patent_family(id) ON DELETE CASCADE,
  relation               text NOT NULL,
  product_id             bigint REFERENCES product(id),
  product_revision_id    bigint REFERENCES product_revision(id),
  material_id            bigint REFERENCES material(id),
  organization_id        bigint REFERENCES organization(id),
  confidence             numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  provenance_id          bigint NOT NULL REFERENCES provenance(id),
  review                 review_state NOT NULL DEFAULT 'pending_review',
  CONSTRAINT patent_link_has_one_target CHECK (
    num_nonnulls(product_id, product_revision_id, material_id, organization_id) = 1
  )
);
CREATE INDEX ON patent_entity_link (family_id);
CREATE INDEX ON patent_entity_link (product_id) WHERE product_id IS NOT NULL;
CREATE INDEX ON patent_entity_link (material_id) WHERE material_id IS NOT NULL;

COMMENT ON TABLE patent_family IS
  'One reviewed DOCDB family. A publication is never treated as a family until DOCDB resolution.';
COMMENT ON COLUMN patent_publication.legal_status IS
  'Jurisdiction-specific status observed on legal_status_as_of; not freedom-to-operate advice.';
