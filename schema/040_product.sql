-- =====================================================================
-- battery-data : 040_product.sql
--
-- THE CENTRAL SPLIT
--
--   product           the thing the market calls "INR21700-50E"
--   product_revision  one specification document's account of it
--   product_unit      a physical object with a serial number
--
-- Datasheets are revised, are issued per customer, and differ per region.
-- Tesla publishes different Powerwall 3 numbers for AU, UK, IE and MT.
-- The Samsung 50E exists at V0.2, V1.0 and a customer-scoped "Tentative".
-- Keying specs on the model number alone silently overwrites all of that.
--
-- The natural key for a specification value is therefore
--   (product, document, revision, region/customer scope, field, conditions)
-- and every layer of that appears below.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- PRODUCT: stable market identity. Deliberately thin - it holds only
-- what cannot change between revisions of a datasheet.
-- ---------------------------------------------------------------------
CREATE TABLE product (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid              text NOT NULL UNIQUE,        -- 'cell/samsung-sdi/inr21700-50e'
  kind             product_kind NOT NULL,
  manufacturer_id  bigint NOT NULL REFERENCES organization(id),
  model_number     text NOT NULL,
  brand            text,
  product_family   text,
  form_factor      form_factor,
  form_factor_code text,                        -- '21700', '4680', 'AA', 'CR2032'
  -- which piece of the hardware around the cell this is, when kind='component'
  component_kind   component_kind,
  -- designation systems for consumer / primary cells. These are NOT one
  -- string: an AA alkaline is simultaneously ANSI 15A and IEC LR6.
  iec_designation  text,                        -- 'LR6', 'INR21700', 'CR2032'
  ansi_neda        text,
  jis_designation  text,
  first_released   date,
  lifecycle        lifecycle_status NOT NULL DEFAULT 'unknown',
  is_rechargeable  boolean,
  notes            text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (manufacturer_id, model_number, kind)
);
CREATE INDEX ON product (kind, form_factor);
CREATE INDEX ON product USING gin (model_number gin_trgm_ops);

-- Cross-references: ER14505 = LS14500 = SB-AA11 = TL-5903 = SL-360.
CREATE TABLE product_alias (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_id bigint NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  alias      text NOT NULL,
  kind       text NOT NULL DEFAULT 'part_number',  -- part_number|sku|oem_code|equivalent
  UNIQUE (product_id, alias, kind)
);
CREATE INDEX ON product_alias USING gin (alias gin_trgm_ops);

CREATE TABLE product_equivalence (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_a_id  bigint NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  product_b_id  bigint NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  relation      text NOT NULL,   -- 'drop_in'|'rebadge'|'second_source'|'successor'
  provenance_id bigint NOT NULL REFERENCES provenance(id),
  CHECK (product_a_id <> product_b_id),
  UNIQUE (product_a_id, product_b_id, relation)
);

-- ---------------------------------------------------------------------
-- PRODUCT_REVISION: one document's account of one product.
-- All specification values attach here, never to product.
-- ---------------------------------------------------------------------
CREATE TABLE product_revision (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid            text NOT NULL UNIQUE,
  product_id     bigint NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  source_id      bigint NOT NULL REFERENCES source(id),
  revision_label text,                     -- copied from source.revision for querying
  effective_date date,
  region_scope   text[],
  customer_scope text,
  is_preliminary boolean NOT NULL DEFAULT false,
  supersedes_id  bigint REFERENCES product_revision(id),
  review         review_state NOT NULL DEFAULT 'pending_review',
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (product_id, source_id)
);
CREATE INDEX ON product_revision (product_id, effective_date DESC);

-- ---------------------------------------------------------------------
-- Chemistry designation. Kept separate from materials because most
-- datasheets give only a marketing string ("Ni-based (high Ni)") and the
-- material-level breakdown comes from teardowns, not the vendor.
-- ---------------------------------------------------------------------
CREATE TABLE product_chemistry (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id   bigint NOT NULL REFERENCES product_revision(id) ON DELETE CASCADE,
  designation           text,                 -- 'NMC811','LFP','NCA','Li-SOCl2','Zn/MnO2'
  family                chemistry_family,     -- the enum a query filters on
  construction          lead_acid_construction, -- flooded / AGM / gel, lead-acid only
  cathode_text          text,                 -- verbatim from the source
  anode_text            text,
  electrolyte_text      text,
  separator_text        text,
  system_string         text,                 -- e.g. 'Graphite - LiNixMnyCozO2'
  provenance_id         bigint NOT NULL REFERENCES provenance(id),
  UNIQUE (product_revision_id),
  CONSTRAINT construction_is_lead_acid CHECK (
    construction IS NULL OR family IS NULL OR family = 'lead_acid'
  )
);

-- Resolved material composition, typically from teardown/literature.
CREATE TABLE product_material (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id bigint NOT NULL REFERENCES product_revision(id) ON DELETE CASCADE,
  material_id         bigint NOT NULL REFERENCES material(id),
  role                material_role NOT NULL,
  mass_fraction       numeric(6,5) CHECK (mass_fraction BETWEEN 0 AND 1),
  mass_g              double precision,
  supplier_org_id     bigint REFERENCES organization(id),
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  UNIQUE (product_revision_id, material_id, role)
);
CREATE INDEX ON product_material (material_id);

-- ---------------------------------------------------------------------
-- Assembly hierarchy: cell -> module -> pack -> system.
-- Stored as a recursive edge so a container BESS resolves down to cells
-- without any special-casing per level.
-- ---------------------------------------------------------------------
CREATE TABLE product_assembly (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_revision_id bigint NOT NULL REFERENCES product_revision(id) ON DELETE CASCADE,
  child_revision_id  bigint NOT NULL REFERENCES product_revision(id),
  quantity          int NOT NULL CHECK (quantity > 0),
  series_count      int,                  -- the S in 2P52S
  parallel_count    int,                  -- the P
  topology_string   text,                 -- '2P52S', '5P2P416S', '4S3P'
  provenance_id     bigint NOT NULL REFERENCES provenance(id),
  CHECK (parent_revision_id <> child_revision_id),
  UNIQUE (parent_revision_id, child_revision_id)
);
CREATE INDEX ON product_assembly (child_revision_id);

-- ---------------------------------------------------------------------
-- Certification claims. Scope and status both matter: a Megapack is
-- "system listed to UL 9540, cells listed to UL 1642", and VARTA prints
-- "UN 38.3 pending" - which is not the same as certified.
-- ---------------------------------------------------------------------
CREATE TABLE certification (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id bigint NOT NULL REFERENCES product_revision(id) ON DELETE CASCADE,
  standard_id         bigint REFERENCES standard(id),
  standard_text       text NOT NULL,        -- verbatim, e.g. 'IEC 62133-2:2017+AMD1:2021'
  scope               text NOT NULL DEFAULT 'unspecified',  -- cell|module|rack|system|installation
  status              text NOT NULL DEFAULT 'claimed',      -- claimed|certified|pending|withdrawn
  certificate_number  text,                 -- 'MH14002'
  certifying_body     text,                 -- 'UL', 'TUV'
  listing_type        text,                 -- 'listed'|'recognized_component'
  issued_date         date,
  expiry_date         date,
  provenance_id       bigint NOT NULL REFERENCES provenance(id)
);
CREATE INDEX ON certification (product_revision_id);
CREATE INDEX ON certification (standard_text);

-- ---------------------------------------------------------------------
-- Transport classification. Threshold-driven and legally consequential;
-- the Wh rating that decides PI965 vs PI966 depends on the nominal
-- voltage convention, which is itself a stored choice (see 050).
-- ---------------------------------------------------------------------
CREATE TABLE transport_classification (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id bigint NOT NULL REFERENCES product_revision(id) ON DELETE CASCADE,
  un_number           text,                 -- UN3480, UN3481, UN3090, UN3091, UN3536
  hazard_class        text,
  packing_instruction text,                 -- PI965..PI970
  watt_hour_rating    double precision,
  lithium_content_g   double precision,
  max_soc_for_transport numeric(5,2),
  un38_3_summary_url  text,
  provenance_id       bigint NOT NULL REFERENCES provenance(id)
);

-- ---------------------------------------------------------------------
-- Commercial availability. Deliberately time-stamped and multi-row:
-- price is a time series, not an attribute.
-- ---------------------------------------------------------------------
CREATE TABLE product_offer (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_id          bigint NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  seller_org_id       bigint REFERENCES organization(id),
  region              text,
  currency            char(3),
  unit_price          numeric(14,4),
  price_per_kwh       numeric(14,4),
  min_order_qty       int,
  price_break_qty     int,
  lead_time_days      int,
  in_stock            boolean,
  grade               text,                 -- 'A'|'B'|'used'|'recovered'
  observed_at         timestamptz NOT NULL,
  provenance_id       bigint NOT NULL REFERENCES provenance(id)
);
CREATE INDEX ON product_offer (product_id, observed_at DESC);

-- ---------------------------------------------------------------------
-- PRODUCT_UNIT: a physical object. Required by the EU battery passport
-- (instance-level identity distinct from type-level spec) and required
-- by any test record, because you test a cell, not a datasheet.
-- ---------------------------------------------------------------------
CREATE TABLE product_unit (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                 text NOT NULL UNIQUE,
  product_revision_id bigint NOT NULL REFERENCES product_revision(id),
  serial_number       text,
  barcode             text,
  lot_code            text,
  manufacture_date    date,
  manufacture_site    text,
  passport_id         text,                 -- EU battery passport identifier
  battery_status      text NOT NULL DEFAULT 'original',  -- original|reused|repurposed|remanufactured|waste
  -- prior history. Losing this is the single most common defect in
  -- published datasets: a "fresh" cell that already has 200 cycles.
  prior_cycle_count   int,
  prior_throughput_ah double precision,
  prior_equivalent_full_cycles double precision,
  formation_complete  boolean,
  storage_history     text,
  acquired_at         date,
  owner_org_id        bigint REFERENCES organization(id),
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (product_revision_id, serial_number)
);
CREATE INDEX ON product_unit (product_revision_id);
