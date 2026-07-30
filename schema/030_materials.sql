-- =====================================================================
-- battery-data : 030_materials.sql
--
-- The materials layer federates rather than replicates. Materials
-- Project / OQMD / AFLOW are well funded and OPTIMADE-federated; we
-- resolve to their identifiers instead of re-hosting crystal structures.
-- What we own is the link: which commercial cell uses which material,
-- from which supplier, established by which evidence.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE material_role AS ENUM (
  'cathode_active', 'anode_active', 'cathode_coating', 'anode_coating',
  'electrolyte_salt', 'electrolyte_solvent', 'electrolyte_additive',
  'solid_electrolyte', 'separator', 'separator_coating',
  'binder', 'conductive_additive',
  'current_collector_positive', 'current_collector_negative',
  'casing', 'tab', 'sealant', 'terminal', 'other'
);

CREATE TABLE material (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,          -- 'mat/nmc811'
  name           text NOT NULL,                 -- 'LiNi0.8Mn0.1Co0.1O2'
  common_name    text,                          -- 'NMC811'
  role           material_role NOT NULL,
  formula        text,
  formula_reduced text,
  elements       text[],                        -- for HAS ALL / HAS ANY filters
  nelements      int GENERATED ALWAYS AS (cardinality(elements)) STORED,
  -- family lets you ask "all LFP cells" without string matching
  family         text,                          -- 'layered_oxide'|'olivine'|'spinel'|'graphite'|'silicon'|...
  crystal_system text,
  space_group    text,
  density_kg_m3  double precision,
  theoretical_specific_capacity_ah_kg double precision,
  -- external federation, not duplication
  optimade_ids   text[],                        -- ['mp-25502', 'oqmd-1234']
  cas_number     text,
  emmo_iri       text,
  pubchem_cid    text,
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON material USING gin (elements);
CREATE INDEX ON material (family);
CREATE INDEX ON material (role);
CREATE INDEX ON material USING gin (common_name gin_trgm_ops);

CREATE TABLE material_alias (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  material_id bigint NOT NULL REFERENCES material(id) ON DELETE CASCADE,
  alias       text NOT NULL,
  UNIQUE (material_id, alias)
);

-- Who makes the material, and where. This edge is the whole point of the
-- graph layer: "which OEMs depend on cells built with cathode from X".
CREATE TABLE material_supply (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  material_id   bigint NOT NULL REFERENCES material(id) ON DELETE CASCADE,
  supplier_org_id bigint NOT NULL REFERENCES organization(id),
  grade_name    text,
  plant_name    text,
  plant_country text,
  provenance_id bigint NOT NULL REFERENCES provenance(id),
  valid_from    date,
  valid_to      date,
  UNIQUE (material_id, supplier_org_id, grade_name, plant_name)
);
