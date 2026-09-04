-- =====================================================================
-- battery-data : 185_supply_chain.sql
--
-- WHERE THE MATERIALS COME FROM, WHERE THE CELLS ARE MADE, WHO SELLS THEM.
--
-- A datasheet says nothing about the mine its lithium came from, the
-- refinery that made it hydroxide, the factory that wound the cell, or the
-- distributor that stocks it. Those are the first questions a buyer, an
-- investor or a regulator asks, and they have the same shape as every
-- other fact here: a claim, by a source, under conditions.
--
-- The conditions are different but they are still conditions:
--   * a resource estimate is meaningless without the reporting code it was
--     declared under (JORC, NI 43-101, SAMREC, S-K 1300 differ on what may
--     be called a reserve) and the cut-off grade it assumed;
--   * a capacity is nameplate, planned, announced or actual, and a press
--     release's "40 GWh" is rarely the third;
--   * an ownership share has a date, and a supply agreement a term.
-- All of that travels with the number or the number is refused.
-- =====================================================================

SET search_path = bd, public;

-- One kind per site, and every kind but 'other' belongs to a stage in
-- bd.supply_chain_stage (184). Test laboratories, research facilities,
-- collection points, second-life facilities and recyclers are sites like
-- any factory: they have an operator, a country, a status and a capacity.
CREATE TYPE site_kind AS ENUM (
  'mine', 'brine_operation', 'refinery', 'chemical_plant', 'precursor_plant',
  'cathode_plant', 'anode_plant', 'electrolyte_plant', 'separator_plant',
  'cell_factory', 'module_pack_factory', 'component_factory',
  'distribution_centre', 'port',
  'test_laboratory', 'research_facility',
  'second_life_facility', 'collection_point', 'recycling_plant',
  'other'
);

-- The stage a site kind belongs to, read from the map rather than typed
-- twice. 'other' has none.
CREATE OR REPLACE FUNCTION bd.site_stage(p_kind site_kind)
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT code FROM bd.supply_chain_stage WHERE p_kind::text = ANY(site_kinds) LIMIT 1;
$$;

CREATE TYPE site_status AS ENUM (
  'exploration', 'development', 'construction', 'commissioning', 'operating',
  'care_and_maintenance', 'idle', 'closed', 'announced', 'cancelled', 'unknown'
);

-- JORC and NI 43-101 categories; 'total_*' for sources that roll them up.
CREATE TYPE resource_category AS ENUM (
  'measured', 'indicated', 'inferred', 'measured_indicated', 'total_resource',
  'proven', 'probable', 'total_reserve', 'unspecified'
);

-- A capacity figure without this word is a press release.
CREATE TYPE capacity_status AS ENUM (
  'nameplate', 'planned', 'announced', 'under_construction', 'actual',
  'estimated', 'unspecified'
);

CREATE TYPE agreement_kind AS ENUM (
  'offtake', 'supply', 'tolling', 'licensing', 'joint_venture', 'prepayment',
  'unspecified'
);

CREATE TYPE distribution_status AS ENUM (
  'authorized', 'franchised', 'independent', 'broker', 'online_marketplace',
  'unspecified'
);

-- ---------------------------------------------------------------------
-- SITE: a place where something is dug, refined, made, stocked or
-- recycled. Coordinates are optional because a datasheet-level source
-- rarely gives them; a country is not.
-- ---------------------------------------------------------------------
CREATE TABLE site (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid              text NOT NULL UNIQUE,            -- 'site/talison-lithium/greenbushes'
  kind             site_kind NOT NULL,
  name             text NOT NULL,
  operator_org_id  bigint REFERENCES organization(id),
  country          text NOT NULL,                   -- ISO 3166-1 alpha-2
  region           text,                            -- state, province
  locality         text,
  latitude         double precision CHECK (latitude BETWEEN -90 AND 90),
  longitude        double precision CHECK (longitude BETWEEN -180 AND 180),
  status           site_status NOT NULL DEFAULT 'unknown',
  status_as_of     date,
  commodities      text[] NOT NULL DEFAULT '{}',    -- 'lithium', 'cobalt', 'nickel', 'graphite'
  products         text[] NOT NULL DEFAULT '{}',    -- 'spodumene concentrate', '21700 cells'
  deposit_type     text,                            -- 'spodumene', 'brine', 'clay', 'laterite', 'sulfide'
  opened_year      int,
  notes            text,
  provenance_id    bigint NOT NULL REFERENCES provenance(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK ((latitude IS NULL) = (longitude IS NULL))
);
CREATE INDEX ON site (kind, country);
CREATE INDEX ON site USING gin (commodities);
CREATE INDEX ON site (operator_org_id);

CREATE TABLE site_alias (
  id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  site_id  bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
  alias    text NOT NULL,
  UNIQUE (site_id, alias)
);

-- ---------------------------------------------------------------------
-- RESOURCE ESTIMATE. The reporting code and the cut-off grade are the
-- conditions; declared absence works exactly as condition_set.unstated.
-- ---------------------------------------------------------------------
CREATE TABLE resource_estimate (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  site_id          bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
  commodity        text NOT NULL,
  category         resource_category NOT NULL DEFAULT 'unspecified',
  reporting_code   text NOT NULL DEFAULT 'unspecified',  -- 'JORC 2012', 'NI 43-101', 'SAMREC', 'SEC S-K 1300'
  tonnage          double precision,
  tonnage_unit     text,                            -- 't', 'kt', 'Mt', 'm3' (brine)
  grade            double precision,
  grade_unit       text,                            -- '% Li2O', 'ppm Li', 'mg/L Li', '% Co', '% Ni', '% Cg'
  cutoff_grade     double precision,
  cutoff_unit      text,
  contained_metal  double precision,
  contained_unit   text,                            -- 't LCE', 't Li', 't Co', 't Ni'
  as_of            date,
  unstated         text[] NOT NULL DEFAULT '{}',
  notes            text,
  provenance_id    bigint NOT NULL REFERENCES provenance(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (reporting_code <> 'unspecified' OR 'reporting_code' = ANY(unstated)),
  CHECK (cutoff_grade IS NOT NULL OR 'cutoff_grade' = ANY(unstated)),
  CHECK (tonnage IS NOT NULL OR contained_metal IS NOT NULL)
);
CREATE INDEX ON resource_estimate (site_id);

-- ---------------------------------------------------------------------
-- SITE METRIC: capacity and output as a time series, each row saying
-- whether it is nameplate, planned, announced or actual.
-- ---------------------------------------------------------------------
CREATE TABLE site_metric (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  site_id        bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
  metric         text NOT NULL,                     -- 'capacity', 'production', 'throughput', 'recovery_rate', 'capex'
  subject        text,                              -- 'lithium hydroxide', 'spodumene concentrate', 'cells'
  status         capacity_status NOT NULL DEFAULT 'unspecified',
  value          double precision NOT NULL,
  unit           text NOT NULL,                     -- 't/yr', 'GWh/yr', 't', 'GWh', 'kt LCE/yr'
  period_start   date NOT NULL,
  period_end     date,
  as_of          date,
  notes          text,
  provenance_id  bigint NOT NULL REFERENCES provenance(id),
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (period_end IS NULL OR period_end >= period_start)
);
CREATE INDEX ON site_metric (site_id, metric, period_start);

-- ---------------------------------------------------------------------
-- OWNERSHIP, with a date. Joint ventures change hands.
-- ---------------------------------------------------------------------
CREATE TABLE site_ownership (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  site_id        bigint NOT NULL REFERENCES site(id) ON DELETE CASCADE,
  org_id         bigint NOT NULL REFERENCES organization(id),
  share_pct      numeric(6,3) CHECK (share_pct IS NULL OR share_pct BETWEEN 0 AND 100),
  role           text NOT NULL DEFAULT 'owner',     -- owner|operator|jv_partner|royalty_holder
  valid_from     date,
  valid_to       date,
  provenance_id  bigint NOT NULL REFERENCES provenance(id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  UNIQUE NULLS NOT DISTINCT (site_id, org_id, role, valid_from)
);

-- ---------------------------------------------------------------------
-- SUPPLY AGREEMENT: who has agreed to sell what to whom, for how long.
-- ---------------------------------------------------------------------
CREATE TABLE supply_agreement (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid              text NOT NULL UNIQUE,
  supplier_org_id  bigint NOT NULL REFERENCES organization(id),
  buyer_org_id     bigint NOT NULL REFERENCES organization(id),
  kind             agreement_kind NOT NULL DEFAULT 'unspecified',
  subject          text NOT NULL,                   -- 'spodumene concentrate', 'lithium hydroxide', 'LFP cells'
  site_id          bigint REFERENCES site(id),
  material_id      bigint REFERENCES material(id),
  traded_form_id   bigint REFERENCES traded_form(id),
  volume           double precision,
  volume_unit      text,                            -- 't', 'GWh'
  volume_period    text,                            -- 'per year', 'total'
  valid_from       date,
  valid_to         date,
  announced_on     date,
  notes            text,
  provenance_id    bigint NOT NULL REFERENCES provenance(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (supplier_org_id <> buyer_org_id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX ON supply_agreement (supplier_org_id);
CREATE INDEX ON supply_agreement (buyer_org_id);

-- ---------------------------------------------------------------------
-- DISTRIBUTION: who sells whose products, where. The listings themselves
-- are product_offer rows; this is the relationship behind them.
-- ---------------------------------------------------------------------
CREATE TABLE distribution (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  distributor_org_id  bigint NOT NULL REFERENCES organization(id),
  manufacturer_org_id bigint REFERENCES organization(id),
  status              distribution_status NOT NULL DEFAULT 'unspecified',
  regions             text[] NOT NULL DEFAULT '{}',
  product_families    text[] NOT NULL DEFAULT '{}',
  url                 text,
  valid_from          date,
  valid_to            date,
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  UNIQUE NULLS NOT DISTINCT (distributor_org_id, manufacturer_org_id, valid_from)
);

-- Every stage an organisation works in: its roles, plus the stages of the
-- sites it operates or owns.
CREATE OR REPLACE FUNCTION bd.organization_stages(p_org_id bigint)
RETURNS text[] LANGUAGE sql STABLE AS $$
  SELECT COALESCE(array_agg(DISTINCT st ORDER BY st), '{}')
    FROM (
      SELECT unnest(bd.role_stages(o.roles)) AS st FROM bd.organization o WHERE o.id = p_org_id
      UNION
      SELECT bd.site_stage(s.kind) FROM bd.site s WHERE s.operator_org_id = p_org_id
      UNION
      SELECT bd.site_stage(s.kind) FROM bd.site_ownership so JOIN bd.site s ON s.id = so.site_id
       WHERE so.org_id = p_org_id
    ) x WHERE st IS NOT NULL;
$$;

COMMENT ON TABLE site IS
  'A mine, refinery, plant, factory, recycler or distribution centre. The '
  'link from a cell back to the ground it came from runs through here.';
COMMENT ON TABLE resource_estimate IS
  'Mineral resources and reserves with the reporting code and cut-off grade '
  'they were declared under, because JORC, NI 43-101 and S-K 1300 do not '
  'agree on what may be called a reserve.';
