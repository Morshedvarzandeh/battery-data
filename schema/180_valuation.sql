-- =====================================================================
-- battery-data : 180_valuation.sql
--
-- WHAT A BATTERY IS WORTH WHEN IT COMES OUT.
--
-- Everything up to here describes what a battery IS: its chemistry, its
-- assembly, what it measured under stated conditions, which vehicle it
-- ended up in. None of that says what happens to it afterwards, and the
-- question every holder of a retired pack actually asks is what it is
-- worth and what to do with it.
--
-- THIS LAYER IS COMMERCIAL, NOT PHYSICAL, AND THAT CHANGES THE RULES.
--
-- A capacity measurement is true forever given its conditions. "Refiners
-- pay 68% of contained nickel value" is true of a market, in a region, in
-- a period, and stops being true without anything about the battery
-- changing. So every row here carries a validity window and a region, and
-- the same provenance discipline as observation. The failure mode this
-- prevents is quiet: a payable term negotiated in 2024 silently pricing a
-- pack in 2027.
--
-- THE DISTINCTION THAT MATTERS MOST: RECOVERY IS NOT PAYABLE.
--
-- Two different haircuts sit between contained metal and money, and
-- collapsing them into one "recovery" number is the largest single source
-- of over-valuation in this field:
--
--   recovery_rate     the share that physically survives the process
--   payable_fraction  the share of THAT which the refiner actually pays for
--
-- Nickel through hydrometallurgy recovers at ~95% and is paid at ~68%, so
-- it returns about 65% of its headline market value. A schema with one
-- column keeps whichever number the source happened to quote and loses the
-- other, which is exactly the pattern this project exists to refuse.
--
-- WHAT IS DELIBERATELY NOT HERE.
--
-- Metal prices themselves. They are a daily time series, the ones that
-- matter (lithium carbonate, cobalt and nickel sulphate, black mass
-- payables) are licensed assessments from Fastmarkets, Benchmark, SMM and
-- Argus, and their terms forbid redistribution. Storing them here would
-- make the repository undistributable. Consumers hold their own price feed
-- and join it to traded_form.
-- =====================================================================

SET search_path = bd, public;

-- ---------------------------------------------------------------------
-- Vocabulary
-- ---------------------------------------------------------------------

-- How a retired battery is processed. Kept separate from the pathway a
-- holder chooses: a pack can be recycled by any of these, and which one
-- it goes to changes what comes back.
CREATE TYPE recovery_route AS ENUM (
  'hydrometallurgical',     -- shred to black mass, then leach to salts
  'pyrometallurgical',      -- smelt; lithium and aluminium go to slag
  'direct_recycling',       -- relithiate and reuse the cathode powder
  'stainless_smelting',     -- NiMH into the stainless alloy stream
  'lead_smelting',          -- the mature closed loop
  'mechanical_only'         -- separation without chemistry
);

-- How far from a laboratory a route actually is. A value quoted against a
-- process nobody can currently sell into overstates what a holder can
-- realise today, so consumers filter on this rather than discovering it.
CREATE TYPE process_maturity AS ENUM (
  'laboratory', 'pilot', 'commercial'
);

-- What can be done with a retired pack. Ordered by how much of the
-- original engineering survives, which is usually but not always the
-- order of value.
CREATE TYPE eol_pathway AS ENUM (
  'reuse',          -- refitted to another vehicle, doing the same job
  'parts_out',      -- dismantled, modules and electronics sold separately
  'second_life',    -- rebuilt as stationary storage
  'recycling'       -- shredded, materials recovered
);

-- Condition drives dangerous-goods freight cost far more than mass does.
-- ADR special provision 376 forces individually approved packaging for
-- damaged or defective cells, which multiplies the tariff several-fold.
CREATE TYPE pack_condition AS ENUM (
  'healthy', 'degraded', 'defective', 'damaged', 'thermal_event'
);

-- ---------------------------------------------------------------------
-- Traded forms
--
-- Battery metals are almost never traded as the pure metal. Lithium
-- trades as carbonate or hydroxide, nickel and cobalt as sulphate
-- hydrates. A price of "USD 14,000 per tonne of lithium carbonate" is not
-- a price for a tonne of lithium; it is a price for 187.9 kg of lithium
-- and a lot of carbonate.
--
-- This table is the bridge, and it exists so that the bridging factor is
-- stored next to the formula it comes from rather than appearing as a
-- bare 5.323 in somebody's spreadsheet.
-- ---------------------------------------------------------------------

CREATE TABLE traded_form (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid                text NOT NULL UNIQUE,        -- 'form/lithium-carbonate'
  code               text NOT NULL UNIQUE,        -- 'lithium_carbonate'
  label              text NOT NULL,
  -- NULL when the form is the pure metal, e.g. LME nickel.
  formula            text,
  payable_element    text NOT NULL,               -- 'Li', 'Ni', 'Co'
  -- kg of payable element per kg of the traded form. Derived from the
  -- formula and IUPAC atomic weights; stored so a query need not compute
  -- molar mass, with the formula kept alongside so it can be checked.
  contained_fraction numeric(8,7) NOT NULL
                     CHECK (contained_fraction > 0 AND contained_fraction <= 1),
  -- the material this form delivers, where one is modelled
  material_id        bigint REFERENCES material(id),
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now(),

  -- A pure metal is 100% itself. Anything with a formula is not, and a
  -- fraction of exactly 1 alongside a formula means somebody forgot to
  -- divide.
  CONSTRAINT pure_metal_is_whole CHECK (
    (formula IS NULL AND contained_fraction = 1)
    OR (formula IS NOT NULL AND contained_fraction < 1)
  )
);

COMMENT ON TABLE traded_form IS
  'The physical forms battery metals are bought and sold in, with the '
  'factor converting a price per kg of form into a price per kg of '
  'contained element.';

-- ---------------------------------------------------------------------
-- Recovery processes and their yields
-- ---------------------------------------------------------------------

CREATE TABLE recovery_process (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  uid           text NOT NULL UNIQUE,             -- 'process/hydrometallurgical'
  route         recovery_route NOT NULL,
  name          text NOT NULL,
  description   text,
  maturity      process_maturity NOT NULL DEFAULT 'commercial',
  -- which chemistry families the route can physically take, matched
  -- against material.family and the pack's chemistry
  applies_to    text[] NOT NULL,                  -- ['li-ion','na-ion']
  operator_org_id bigint REFERENCES organization(id),
  region        text,                             -- 'EU','CN','US', NULL = general
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (cardinality(applies_to) > 0)
);

CREATE TABLE recovery_yield (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recovery_process_id bigint NOT NULL REFERENCES recovery_process(id) ON DELETE CASCADE,
  element_symbol     text NOT NULL,               -- 'Ni','Co','Li','Cu','Al','Fe','C','Pb'
  traded_form_id     bigint REFERENCES traded_form(id),

  -- The two haircuts, kept apart on purpose. See the header.
  recovery_rate      numeric(4,3) NOT NULL
                     CHECK (recovery_rate BETWEEN 0 AND 1),
  payable_fraction   numeric(4,3)
                     CHECK (payable_fraction BETWEEN 0 AND 1),

  -- A commercial term is true of a market in a period, not forever.
  valid_from         date NOT NULL,
  valid_to           date,                        -- NULL = still current
  region             text,

  -- Regulatory floors are a different claim from what a plant achieves,
  -- and both are worth storing. EU 2023/1542 Annex XII sets minima that
  -- rise on fixed dates; a commercial rate may sit above or below them.
  is_regulatory_minimum boolean NOT NULL DEFAULT false,

  provenance_id      bigint NOT NULL REFERENCES provenance(id),
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now(),

  CHECK (valid_to IS NULL OR valid_to > valid_from),
  -- A regulatory minimum is about physical recovery; it says nothing
  -- about what anyone pays.
  CONSTRAINT regulatory_minima_have_no_payable CHECK (
    NOT (is_regulatory_minimum AND payable_fraction IS NOT NULL)
  ),
  UNIQUE NULLS NOT DISTINCT
    (recovery_process_id, element_symbol, region, valid_from, is_regulatory_minimum)
);

COMMENT ON COLUMN recovery_yield.recovery_rate IS
  'Share of contained element that physically leaves the process as a '
  'saleable product.';
COMMENT ON COLUMN recovery_yield.payable_fraction IS
  'Share of the recovered element''s market value the refiner actually '
  'pays the holder. NULL for a regulatory minimum, which makes no claim '
  'about payment.';

-- ---------------------------------------------------------------------
-- Costs
-- ---------------------------------------------------------------------

CREATE TYPE treatment_stage AS ENUM (
  'discharge_and_dismantle',
  'shredding_to_black_mass',
  'refining_gate_fee',
  'testing_and_grading',
  'repackaging',
  'certification'
);

CREATE TABLE treatment_cost (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  recovery_process_id bigint REFERENCES recovery_process(id) ON DELETE CASCADE,
  pathway             eol_pathway,
  stage               treatment_stage NOT NULL,

  -- Costs scale on different things and saying which is not optional:
  -- grading scales with module count, freight with mass, certification is
  -- flat per pack. A single "cost per kg" column would force two of those
  -- three to be wrong.
  cost_per_kg         numeric(12,4),
  cost_per_kwh        numeric(12,4),
  cost_per_unit       numeric(12,4),
  currency            char(3) NOT NULL DEFAULT 'EUR',

  valid_from          date NOT NULL,
  valid_to            date,
  region              text,
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),

  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (num_nonnulls(cost_per_kg, cost_per_kwh, cost_per_unit) >= 1),
  CHECK (num_nonnulls(recovery_process_id, pathway) = 1)
);

CREATE TABLE logistics_tariff (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  condition     pack_condition NOT NULL,
  -- End-of-life lithium batteries move as UN3480/UN3481 Class 9. Damaged
  -- or defective packs fall under ADR special provision 376.
  un_number     text,
  cost_per_kg   numeric(12,4) NOT NULL,
  minimum_charge numeric(12,2),
  currency      char(3) NOT NULL DEFAULT 'EUR',
  mode          text,                          -- 'road','sea','air'
  valid_from    date NOT NULL,
  valid_to      date,
  region        text,
  provenance_id bigint NOT NULL REFERENCES provenance(id),
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  UNIQUE NULLS NOT DISTINCT (condition, region, mode, valid_from)
);

-- ---------------------------------------------------------------------
-- What used hardware sells for
--
-- These attach to a product_revision rather than floating free, because
-- "a used battery module" is not a price: a Leaf ZE1 module and a Model S
-- module are different goods with different buyers.
-- ---------------------------------------------------------------------

CREATE TABLE component_market_value (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id bigint NOT NULL REFERENCES product_revision(id) ON DELETE CASCADE,
  unit_value          numeric(12,2) NOT NULL CHECK (unit_value >= 0),
  currency            char(3) NOT NULL DEFAULT 'EUR',

  -- The state of health the quoted price assumes. A module price without
  -- one is unusable, because most of what a buyer is paying for is the
  -- remaining energy.
  assumed_soh         numeric(4,3) CHECK (assumed_soh BETWEEN 0 AND 1),
  -- Share of units that actually find a buyer. A thin market is the
  -- difference between a catalogue price and realisable value.
  sell_through        numeric(4,3) CHECK (sell_through BETWEEN 0 AND 1),

  valid_from          date NOT NULL,
  valid_to            date,
  region              text,
  marketplace         text,                    -- 'ebay-de','specialist-dismantler'
  sample_size         int CHECK (sample_size IS NULL OR sample_size > 0),
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE TABLE replacement_price (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_revision_id bigint REFERENCES product_revision(id) ON DELETE CASCADE,
  application_id      bigint REFERENCES application(id) ON DELETE CASCADE,

  -- The retail over-the-counter price of the new part, which is far above
  -- the maker's own cost and sets the ceiling a used pack is discounted
  -- from.
  price_per_kwh       numeric(12,2),
  price_total         numeric(12,2),
  currency            char(3) NOT NULL DEFAULT 'EUR',
  includes_labour     boolean NOT NULL DEFAULT false,

  valid_from          date NOT NULL,
  valid_to            date,
  region              text,
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),

  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (num_nonnulls(price_per_kwh, price_total) >= 1),
  CHECK (num_nonnulls(product_revision_id, application_id) >= 1)
);

-- ---------------------------------------------------------------------
-- How fast a pack wears out
--
-- A state-of-health figure is a number without a yardstick. 87% is
-- excellent on a nine-year-old car and disappointing on a two-year-old
-- one, and nothing in the reading itself says which. What supplies the
-- yardstick is a fade curve for the pack model, and that belongs here
-- rather than in a consumer: it is a claim about a product, from sources,
-- and it goes stale exactly the way a payable term does.
--
-- WHY THIS HANGS OFF THE PRODUCT AND NOT THE CHEMISTRY.
--
-- Cooling design predicts how a fleet ages better than cathode chemistry
-- does. Two NMC packs of the same vintage diverge sharply if one is
-- liquid-cooled and the other is not, which is the whole story of the
-- early Leaf. So a profile attaches to a product where one is known, and
-- falls back to a chemistry designation only where it is not.
--
-- WHAT MAKES A CURVE MEAN ANYTHING: THE SPREAD.
--
-- Real packs of one model at one age differ by several points of state of
-- health. Without spread_points_at_8y a consumer can only say "yours is
-- below average", which is true of half of everything. With it, the same
-- consumer can say whether a pack is genuinely unusual. A single-number
-- curve invites a verdict the data does not support.
--
-- THE DOUBLE-COUNTING TRAP.
--
-- fade_at_8y comes from cars that were being driven, so it already
-- contains a typical amount of cycling. reference_km_per_year records how
-- much, so a consumer can charge only the DIFFERENCE between a pack's
-- actual use and that reference. Storing fade and cycle life without the
-- reference lets a consumer add both in full and bill the same kilometres
-- twice.
-- ---------------------------------------------------------------------

CREATE TYPE thermal_management AS ENUM (
  'passive',                -- no cooling system at all
  'air',                    -- forced air over the modules
  'liquid',                 -- a coolant loop, including direct refrigerant
  'unknown'
);

CREATE TABLE degradation_profile (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- Exactly one of these. A profile is about a specific pack, or it is a
  -- stated fallback for a chemistry; anything else is an unattributed
  -- claim about batteries in general.
  product_id          bigint REFERENCES product(id) ON DELETE CASCADE,
  chemistry           text,

  thermal_management  thermal_management NOT NULL DEFAULT 'unknown',

  -- Capacity lost after eight years at reference_km_per_year in a
  -- temperate climate. Eight years because that is where the warranty
  -- floors and the fleet studies both land, so sources are comparable.
  fade_at_8y          numeric(4,3) NOT NULL CHECK (fade_at_8y BETWEEN 0 AND 1),

  -- Equivalent full cycles to 80% state of health. Prices the deviation
  -- from reference use, not the use itself. See the header.
  cycle_life_to_80pct int CHECK (cycle_life_to_80pct IS NULL
                                 OR cycle_life_to_80pct > 0),
  reference_km_per_year numeric(8,1) CHECK (reference_km_per_year IS NULL
                                            OR reference_km_per_year >= 0),
  km_per_kwh          numeric(5,2) CHECK (km_per_kwh IS NULL OR km_per_kwh > 0),

  -- Fade goes with time to this power. 0.5 is the square root, which is
  -- what diffusion-limited film growth predicts and what field data shows:
  -- a visible drop in the first year, then a long flattening.
  calendar_exponent   numeric(3,2) CHECK (calendar_exponent IS NULL
                                          OR calendar_exponent BETWEEN 0.1 AND 2),

  -- Where the curve steepens near end of life, and by how much.
  knee_onset_soh      numeric(4,3) CHECK (knee_onset_soh IS NULL
                                          OR knee_onset_soh BETWEEN 0 AND 1),
  knee_acceleration   numeric(4,2) CHECK (knee_acceleration IS NULL
                                          OR knee_acceleration >= 1),

  -- How exposed this pack is to heat, which is the largest difference
  -- between two otherwise identical batteries in different places.
  climate_sensitivity text NOT NULL DEFAULT 'medium'
                      CHECK (climate_sensitivity IN ('low','medium','high')),

  -- One standard deviation in state-of-health points across real packs of
  -- this model at eight years. The number that turns "below average" into
  -- "genuinely unusual".
  spread_points_at_8y numeric(4,1) CHECK (spread_points_at_8y IS NULL
                                          OR spread_points_at_8y >= 0),

  confidence          numeric(3,2) CHECK (confidence BETWEEN 0 AND 1),
  basis               text,                    -- what it was calibrated against

  valid_from          date NOT NULL,
  valid_to            date,
  region              text,
  provenance_id       bigint NOT NULL REFERENCES provenance(id),
  notes               text,
  created_at          timestamptz NOT NULL DEFAULT now(),

  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CONSTRAINT profile_is_product_or_chemistry CHECK (
    num_nonnulls(product_id, chemistry) = 1
  ),
  UNIQUE NULLS NOT DISTINCT (product_id, chemistry, region, valid_from)
);

COMMENT ON TABLE degradation_profile IS
  'Fade curve for a pack model, or for a chemistry as a stated fallback. '
  'Describes a population, never an individual pack: a measured state of '
  'health always outranks anything here.';
COMMENT ON COLUMN degradation_profile.fade_at_8y IS
  'Capacity lost after eight years at reference_km_per_year in a temperate '
  'climate. Already includes the cycling a typical car of this model does.';
COMMENT ON COLUMN degradation_profile.spread_points_at_8y IS
  'One standard deviation in state-of-health points across packs of this '
  'model at eight years. Without it, a consumer can only say a pack is '
  'below average, which is true of half of them.';

-- ---------------------------------------------------------------------
-- Model calibration
--
-- Deliberately generic, and the only table here that is. The rows are not
-- observations about a battery; they are the thresholds and factors a
-- valuation model is calibrated with -- the state of health below which
-- buyers stop taking replacement packs, the warranty reserve a
-- remanufacturer holds back, the hourly rate of an HV-qualified
-- technician. Giving each of those a typed table would be a table per
-- constant, and they change together when a market moves.
--
-- They still carry provenance, because a threshold somebody made up and a
-- threshold from a dismantler's price list are not the same claim.
-- ---------------------------------------------------------------------

CREATE TABLE valuation_assumption (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  key           text NOT NULL,                 -- 'reuse.minimum_soh'
  pathway       eol_pathway,
  value_num     double precision,
  value_text    text,
  unit          text,                          -- 'fraction','EUR/h','EUR/kWh','years'
  valid_from    date NOT NULL,
  valid_to      date,
  region        text,
  provenance_id bigint NOT NULL REFERENCES provenance(id),
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (num_nonnulls(value_num, value_text) = 1),
  UNIQUE NULLS NOT DISTINCT (key, pathway, region, valid_from)
);

-- ---------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------

-- The number a consumer actually wants: what share of a metal's headline
-- market value reaches the holder. Exposed as a view so nobody has to
-- remember to multiply the two haircuts together, and nobody gets to
-- forget the second one.
CREATE VIEW v_recovery_economics AS
SELECT
  p.uid                AS process_uid,
  p.route,
  p.name               AS process_name,
  p.maturity,
  p.applies_to,
  y.element_symbol,
  f.code               AS traded_form,
  f.contained_fraction,
  y.recovery_rate,
  y.payable_fraction,
  (y.recovery_rate * y.payable_fraction) AS value_yield,
  y.is_regulatory_minimum,
  y.valid_from,
  y.valid_to,
  y.region,
  y.provenance_id
FROM recovery_yield y
JOIN recovery_process p ON p.id = y.recovery_process_id
LEFT JOIN traded_form f ON f.id = y.traded_form_id;

COMMENT ON VIEW v_recovery_economics IS
  'Recovery and payable terms with their product. value_yield is the '
  'share of headline market value that reaches the holder: a metal '
  'recovered at 95% and paid at 68% returns 65%, not 95%.';

-- Which pack is in which vehicle, with everything a valuation needs and
-- the attribution kept visible. Consumers filter on basis and confidence
-- rather than being handed a claim with its evidence stripped off.
CREATE VIEW v_pack_application AS
SELECT
  a.uid                AS application_uid,
  a.name               AS application_name,
  a.sector,
  a.region,
  a.in_service_from,
  a.in_service_to,
  p.uid                AS product_uid,
  p.kind               AS product_kind,
  p.model_number,
  p.brand,
  p.form_factor,
  r.id                 AS product_revision_id,
  pa.role,
  pa.quantity_per_unit,
  pa.topology_string,
  pa.basis,
  pa.confidence,
  pa.is_exclusive,
  pa.provenance_id
FROM product_application pa
JOIN application a ON a.id = pa.application_id
LEFT JOIN product_revision r ON r.id = pa.product_revision_id
LEFT JOIN product p ON p.id = COALESCE(pa.product_id, r.product_id)
WHERE pa.superseded_by IS NULL;

-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------

CREATE INDEX recovery_yield_lookup
  ON recovery_yield (recovery_process_id, element_symbol, valid_from DESC);
CREATE INDEX treatment_cost_lookup
  ON treatment_cost (recovery_process_id, stage, valid_from DESC);
CREATE INDEX component_market_value_lookup
  ON component_market_value (product_revision_id, valid_from DESC);
CREATE INDEX replacement_price_revision
  ON replacement_price (product_revision_id, valid_from DESC);
CREATE INDEX replacement_price_application
  ON replacement_price (application_id, valid_from DESC);
CREATE INDEX valuation_assumption_lookup
  ON valuation_assumption (key, valid_from DESC);
CREATE INDEX degradation_profile_product
  ON degradation_profile (product_id, valid_from DESC);
CREATE INDEX degradation_profile_chemistry
  ON degradation_profile (chemistry, valid_from DESC)
  WHERE chemistry IS NOT NULL;
