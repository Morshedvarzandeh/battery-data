-- =====================================================================
-- battery-data : 045_application.sql
--
-- WHERE A CELL ACTUALLY ENDS UP.
--
-- product_assembly already carries cell -> module -> pack -> system, with
-- the topology string that makes 2P52S recoverable. What it does not carry
-- is the thing everyone actually asks first: which car, which bus, which
-- grid installation. A pack is a product; a Model Y is not, and forcing it
-- into product_kind would make every query over cells trip on vehicles.
--
-- So applications are their own subject, and the link carries the
-- granularity the source actually supports: a revision, a product, or just
-- a brand family. That distinction matters both ways. "The 2170 in a Model
-- Y" is a claim about a particular revision, because vehicles change cell
-- supplier mid-production without renaming the car. "SCiB is in a Suzuki
-- mild hybrid" is all Toshiba's catalogue will commit to, and rounding it
-- up to a part number would be inventing the missing half.
--
-- THE HARD PART IS NOT THE SCHEMA, IT IS THE EVIDENCE.
--
-- Cell-to-vehicle attribution is mostly teardown journalism, supplier
-- press releases and forum consensus. Very little of it is stated by a
-- manufacturer in a document you can quote. So product_application carries
-- the same provenance discipline as observation: a source, an evidence
-- class, and a confidence. An unsourced "everyone knows the Model Y uses
-- 2170s" is exactly the kind of claim this table exists to keep out.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE application_sector AS ENUM (
  'passenger_vehicle',
  'commercial_vehicle',        -- vans, trucks
  'bus',
  'rail',
  'marine',
  'aviation',
  'off_highway',               -- forklift, mining, agriculture
  'grid_storage',              -- BESS, frequency regulation
  'behind_meter_storage',      -- home and commercial storage
  'backup_power',              -- UPS, telecom
  'industrial',
  'consumer',
  'micromobility',             -- e-bike, scooter
  'defence',
  'other'
);

-- How firmly the cell-to-application link is established. Kept separate
-- from evidence_class because the failure mode is different: an
-- observation can be wrong about a number, this can be wrong about
-- whether the relationship exists at all.
CREATE TYPE attribution_basis AS ENUM (
  'manufacturer_stated',       -- the cell or vehicle maker says so, in a document
  'teardown',                  -- someone opened one and looked
  'regulatory_filing',         -- homologation, battery passport, recall notice
  'press_release',
  'trade_press',
  'community_reported',        -- forum or enthusiast consensus
  'inferred'                   -- deduced from form factor, capacity, timing
);

CREATE TABLE application (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid             text NOT NULL UNIQUE,
  name            text NOT NULL,             -- 'Tesla Model Y Long Range'
  sector          application_sector NOT NULL,
  -- the organisation that fields it, which is rarely the cell maker
  operator_org_id bigint REFERENCES organization(id),
  operator_text   text,                      -- when the org is not modelled
  programme       text,                      -- 'Ginza Line 1000-series'
  region          text,                      -- 'US', 'EU', 'JP', 'global'
  in_service_from date,
  in_service_to   date,                      -- NULL while still in service
  -- nameplate of the whole installation, for grid storage especially
  system_energy_kwh   double precision,
  system_power_kw     double precision,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (in_service_to IS NULL OR in_service_from IS NULL
         OR in_service_to >= in_service_from)
);

CREATE INDEX ON application (sector);
CREATE INDEX ON application (operator_org_id);

-- The link, and the claim.
CREATE TABLE product_application (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id      bigint NOT NULL REFERENCES application(id) ON DELETE CASCADE,

  -- GRANULARITY OF THE CLAIM, in the observation-table idiom: exactly one.
  --
  -- Sources state adoption at whatever level suits them. Toshiba's catalogue
  -- says "this battery has been adopted for" a Suzuki mild hybrid and never
  -- names a cell; pinning that to a revision would manufacture precision the
  -- page does not have. A teardown, by contrast, names the exact part on the
  -- exact revision. Both are worth keeping, and they are not the same claim.
  product_revision_id bigint REFERENCES product_revision(id) ON DELETE CASCADE,
  product_id          bigint REFERENCES product(id) ON DELETE CASCADE,
  brand_org_id        bigint REFERENCES organization(id),
  brand_family        text,                  -- 'SCiB', 'Blade', 'Qilin'

  -- what the battery does there. A cell used for regenerative capture and
  -- one used for traction are answering different design questions even
  -- when they are the same part number.
  role                text,                  -- traction|regenerative|backup|starter|buffer
  quantity_per_unit   int CHECK (quantity_per_unit IS NULL OR quantity_per_unit > 0),
  topology_string     text,                  -- as fielded, may differ from the pack product

  basis               attribution_basis NOT NULL,
  confidence          numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  -- second sourcing is normal and is not a contradiction: a vehicle can
  -- ship with two cell suppliers in the same model year.
  is_exclusive        boolean NOT NULL DEFAULT false,
  superseded_by       bigint REFERENCES product_application(id),
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),

  CHECK (num_nonnulls(product_revision_id, product_id, brand_org_id) = 1),
  CHECK ((brand_org_id IS NULL) = (brand_family IS NULL)),
  -- NULLS NOT DISTINCT because an unstated role is a role, and because three
  -- of the five key columns are null on any given row by construction.
  -- Without it every duplicate claim would slip through.
  UNIQUE NULLS NOT DISTINCT
    (application_id, product_revision_id, product_id, brand_org_id,
     brand_family, role)
);

CREATE INDEX ON product_application (application_id);
CREATE INDEX ON product_application (basis);
CREATE INDEX ON product_application (product_revision_id) WHERE product_revision_id IS NOT NULL;
CREATE INDEX ON product_application (product_id) WHERE product_id IS NOT NULL;
CREATE INDEX ON product_application (brand_org_id, brand_family) WHERE brand_org_id IS NOT NULL;

-- Readable form: every fielded use, flattened across the three granularities
-- so a reader does not have to know which one a given claim was made at.
-- `granularity` is deliberately in the output: 'Toshiba SCiB is in a Suzuki
-- mild hybrid' and 'this exact revision is in that car' should never look
-- alike in a result set.
CREATE OR REPLACE VIEW v_cell_deployment AS
SELECT CASE
         WHEN pa.product_revision_id IS NOT NULL THEN 'revision'
         WHEN pa.product_id          IS NOT NULL THEN 'product'
         ELSE 'brand_family'
       END                                       AS granularity,
       COALESCE(p.uid, prp.uid)                  AS product_uid,
       COALESCE(p.model_number, prp.model_number,
                pa.brand_family)                 AS product_label,
       COALESCE(mo.name, pmo.name, bo.name)      AS manufacturer,
       pr.revision_label,
       a.uid                                     AS application_uid,
       a.name                                    AS application,
       a.sector,
       COALESCE(op.name, a.operator_text)        AS operator,
       a.programme,
       a.region,
       a.in_service_from,
       a.system_energy_kwh,
       pa.role,
       pa.quantity_per_unit,
       pa.basis,
       pa.confidence,
       pa.is_exclusive,
       pa.superseded_by IS NOT NULL              AS is_superseded,
       s.uid                                     AS source_uid,
       s.url                                     AS source_url,
       sl.page                                   AS source_page,
       sl.quote                                  AS source_quote
  FROM product_application pa
  JOIN application       a   ON a.id  = pa.application_id
  LEFT JOIN organization op  ON op.id = a.operator_org_id
  -- revision-level subject
  LEFT JOIN product_revision pr  ON pr.id  = pa.product_revision_id
  LEFT JOIN product          prp ON prp.id = pr.product_id
  LEFT JOIN organization     pmo ON pmo.id = prp.manufacturer_id
  -- product-level subject
  LEFT JOIN product          p   ON p.id   = pa.product_id
  LEFT JOIN organization     mo  ON mo.id  = p.manufacturer_id
  -- brand-family subject
  LEFT JOIN organization     bo  ON bo.id  = pa.brand_org_id
  JOIN provenance        pv  ON pv.id = pa.provenance_id
  JOIN source_location   sl  ON sl.id = pv.source_location_id
  JOIN source            s   ON s.id  = sl.source_id;

COMMENT ON TABLE application IS
  'An end use a battery product is fielded in: a vehicle model, a rail '
  'programme, a grid installation. Deliberately not a product_kind, so '
  'queries over cells never have to filter out vehicles.';

COMMENT ON TABLE product_application IS
  'Claims that a product, revision or brand family is used in an application. '
  'Carries an attribution basis because most cell-to-vehicle knowledge is '
  'teardown journalism rather than anything a manufacturer will put in '
  'writing, and a granularity because sources rarely name the actual cell.';

COMMENT ON COLUMN product_application.brand_family IS
  'Set when the source claims adoption for a marketing family rather than a '
  'part number. Not a product: nobody buys "SCiB", they buy a 20Ah cell.';
