-- =====================================================================
-- battery-data : 184_companies.sql
--
-- THE SUPPLY CHAIN AS A NAMED, ORDERED VOCABULARY, AND COMPANIES IN IT.
--
-- A reader who opens this database meets chemistries, products, patents,
-- companies, mines, factories, prices and test laboratories. Without a
-- fixed map of how those relate, every one of them looks like a separate
-- database. The map is data, not prose: bd.supply_chain_stage is the
-- ordered list of stages from the ground to the recycler, every site kind
-- and every organisation role names its stage, and the API and the docs
-- are generated from the same rows.
--
-- Companies were already here as bd.organization; this file gives them
-- what a reader asks for first: where they sit in the chain, who owns
-- them, and the identifiers that stop "LG Energy Solution", "LG Chem" and
-- "LGES" from becoming three companies.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- STAGE. Position is the reading order from mine to recycler; site_kinds
-- and roles are the vocabulary that maps a site or a company onto it.
-- ---------------------------------------------------------------------
CREATE TABLE supply_chain_stage (
  code        text PRIMARY KEY,
  position    int  NOT NULL UNIQUE,
  label       text NOT NULL,
  definition  text NOT NULL,
  site_kinds  text[] NOT NULL DEFAULT '{}',
  roles       text[] NOT NULL DEFAULT '{}'
);

INSERT INTO supply_chain_stage (code, position, label, definition, site_kinds, roles) VALUES
  ('mining',          1, 'Mining and brines',
   'Where lithium, nickel, cobalt, manganese, graphite, phosphate and the rest leave the ground: hard-rock mines, brine and clay operations.',
   '{mine,brine_operation}', '{miner}'),
  ('refining',        2, 'Refining and chemicals',
   'Concentrate and brine turned into battery-grade chemicals: lithium carbonate and hydroxide, nickel and cobalt sulphate, spherical graphite.',
   '{refinery,chemical_plant}', '{refiner}'),
  ('precursor',       3, 'Precursor',
   'Mixed hydroxide precursor (pCAM) and other intermediates between the chemical and the active material.',
   '{precursor_plant}', '{precursor_producer}'),
  ('active_material', 4, 'Active materials',
   'Cathode and anode active material: NMC, LFP, LCO, NCA, sodium layered oxides, graphite, silicon.',
   '{cathode_plant,anode_plant}', '{cathode_producer,anode_producer}'),
  ('cell_component',  5, 'Cell components',
   'Electrolyte, separator, current-collector foil, cans, lids and tabs.',
   '{electrolyte_plant,separator_plant}', '{electrolyte_producer,separator_producer,foil_can_producer}'),
  ('cell',            6, 'Cells',
   'Cell and primary battery manufacturing.',
   '{cell_factory}', '{manufacturer}'),
  ('module_pack',     7, 'Modules and packs',
   'Modules and packs assembled from cells, with their BMS, busbars and housings.',
   '{module_pack_factory}', '{pack_assembler}'),
  ('system',          8, 'Systems',
   'Complete storage systems and battery products integrated for an application: containers, home storage, vehicle batteries.',
   '{}', '{integrator}'),
  ('component',       9, 'Components around the battery',
   'Contactors, fuses, BMS, converters, chargers, sensors, thermal hardware and connectors made for batteries.',
   '{component_factory}', '{component_manufacturer}'),
  ('distribution',   10, 'Distribution',
   'Authorised distributors, brokers, marketplaces, warehouses and ports.',
   '{distribution_centre,port}', '{distributor}'),
  ('application',    11, 'Application',
   'The vehicle, installation or device the battery serves, and the organisation that fields it.',
   '{}', '{oem,fleet_operator}'),
  ('testing',        12, 'Testing, certification and research',
   'Test laboratories, certification bodies and research facilities that measure and certify what the other stages make.',
   '{test_laboratory,research_facility}', '{lab,certification_body,research_institute}'),
  ('second_life',    13, 'Second life',
   'Diagnosis, repurposing and redeployment of batteries after their first use.',
   '{second_life_facility}', '{second_life}'),
  ('recycling',      14, 'Collection and recycling',
   'Collection points, discharge and dismantling, black mass, hydro- and pyrometallurgical recovery back to the refining stage.',
   '{collection_point,recycling_plant}', '{recycler}');

-- ---------------------------------------------------------------------
-- ROLE. organization.roles has always been free text; this is the list
-- the contribution format accepts and the stage each role belongs to.
-- Roles outside the chain (publisher, standards body, investor) have no
-- stage and are still valid.
-- ---------------------------------------------------------------------
CREATE TABLE organization_role (
  code        text PRIMARY KEY,
  label       text NOT NULL,
  stage       text REFERENCES supply_chain_stage(code),
  definition  text NOT NULL
);

INSERT INTO organization_role (code, label, stage, definition) VALUES
  ('miner',                  'Miner',                    'mining',          'Operates or owns mines or brine operations.'),
  ('refiner',                'Refiner',                  'refining',        'Produces battery-grade chemicals from concentrate, brine or black mass.'),
  ('precursor_producer',     'Precursor producer',       'precursor',       'Produces pCAM or other precursors.'),
  ('cathode_producer',       'Cathode material producer','active_material', 'Produces cathode active material.'),
  ('anode_producer',         'Anode material producer',  'active_material', 'Produces anode active material.'),
  ('electrolyte_producer',   'Electrolyte producer',     'cell_component',  'Produces electrolyte or its salts and solvents.'),
  ('separator_producer',     'Separator producer',       'cell_component',  'Produces separators.'),
  ('foil_can_producer',      'Foil and can producer',    'cell_component',  'Produces current-collector foil, cans, lids or tabs.'),
  ('manufacturer',           'Cell or battery manufacturer', 'cell',        'Makes cells, primary batteries, or the modules, packs and systems sold under its name.'),
  ('pack_assembler',         'Pack assembler',           'module_pack',     'Assembles modules and packs from purchased cells.'),
  ('integrator',             'System integrator',        'system',          'Integrates packs into storage systems or vehicles.'),
  ('component_manufacturer', 'Component manufacturer',   'component',       'Makes contactors, fuses, BMS, converters, sensors or thermal hardware for batteries.'),
  ('distributor',            'Distributor',              'distribution',    'Sells other makers'' products; authorised, franchised, independent or marketplace.'),
  ('oem',                    'OEM',                      'application',     'Fields batteries in vehicles, devices or installations sold under its brand.'),
  ('fleet_operator',         'Operator',                 'application',     'Operates the vehicles, installations or devices the batteries serve.'),
  ('lab',                    'Test laboratory',          'testing',         'Tests cells, packs or systems; accredited or in-house.'),
  ('certification_body',     'Certification body',       'testing',         'Certifies products against standards (UL, TUV, CSA, and the notified bodies).'),
  ('research_institute',     'Research institute',       'testing',         'University or institute that measures and publishes.'),
  ('second_life',            'Second-life company',      'second_life',     'Diagnoses, repurposes and redeploys used batteries.'),
  ('recycler',               'Recycler',                 'recycling',       'Collects, dismantles or recovers materials from batteries.'),
  ('site_operator',          'Site operator',            NULL,              'Operates a site; the stage is the site''s stage.'),
  ('owner',                  'Owner',                    NULL,              'Holds a share of a site; the stage is the site''s stage.'),
  ('supplier',               'Supplier',                 NULL,              'Party that sells under a supply agreement; the stage is the subject''s.'),
  ('buyer',                  'Buyer',                    NULL,              'Party that buys under a supply agreement.'),
  ('publisher',              'Publisher',                NULL,              'Publishes sources this database cites.'),
  ('sdo',                    'Standards body',           NULL,              'Develops the standards products are certified to.'),
  ('investor',               'Investor',                 NULL,              'Holds shares in companies or sites without operating them.'),
  ('government',             'Government body',          NULL,              'Ministry, agency or survey that publishes statistics or grants permits.');

-- ---------------------------------------------------------------------
-- COMPANY PROFILE COLUMNS. Nullable: the seed and the product loaders
-- only know a name. A company contribution fills them with provenance.
-- ---------------------------------------------------------------------
ALTER TABLE organization
  ADD COLUMN founded_year  int CHECK (founded_year BETWEEN 1600 AND 2100),
  ADD COLUMN hq_region     text,
  ADD COLUMN hq_locality   text,
  ADD COLUMN ticker        text,
  ADD COLUMN exchange      text,
  ADD COLUMN description   text,
  ADD COLUMN provenance_id bigint REFERENCES provenance(id);

CREATE INDEX ON organization USING gin (roles);

-- ---------------------------------------------------------------------
-- RELATIONS BETWEEN COMPANIES, DATED. parent_id on organization is the
-- undated shortcut; this is the record. A joint venture has two parents
-- with shares, a brand belongs to a company, a company was formerly
-- another, and each of those has a source.
-- ---------------------------------------------------------------------
CREATE TYPE organization_relation_kind AS ENUM (
  'parent_of', 'subsidiary_of', 'joint_venture_of', 'brand_of', 'formerly',
  'renamed_to', 'acquired', 'merged_into', 'spun_off_from', 'minority_stake_in',
  'licensee_of'
);

CREATE TABLE organization_relation (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id          bigint NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
  related_org_id  bigint NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
  relation        organization_relation_kind NOT NULL,
  share_pct       numeric(6,3) CHECK (share_pct IS NULL OR share_pct BETWEEN 0 AND 100),
  valid_from      date,
  valid_to        date,
  notes           text,
  provenance_id   bigint NOT NULL REFERENCES provenance(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (org_id <> related_org_id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  UNIQUE NULLS NOT DISTINCT (org_id, related_org_id, relation, valid_from)
);
CREATE INDEX ON organization_relation (related_org_id);

-- The stages an organisation works in: from its roles, and from the
-- sites it operates or owns. Sites are defined in 185; the function is
-- created there once site_kind exists, and this one is role-only.
CREATE OR REPLACE FUNCTION bd.role_stages(p_roles text[])
RETURNS text[] LANGUAGE sql STABLE AS $$
  SELECT COALESCE(array_agg(DISTINCT r.stage ORDER BY r.stage), '{}')
    FROM bd.organization_role r
   WHERE r.code = ANY(p_roles) AND r.stage IS NOT NULL;
$$;

COMMENT ON TABLE supply_chain_stage IS
  'The ordered map of the battery supply chain. Every site kind and every '
  'organisation role belongs to one stage; the API and the docs read this table.';
COMMENT ON TABLE organization_relation IS
  'Dated ownership and identity relations between companies, each with a source.';
