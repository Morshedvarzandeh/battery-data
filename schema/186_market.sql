-- =====================================================================
-- battery-data : 186_market.sql
--
-- WHAT THE MARKET PAID, MADE, SHIPPED AND TRADED.
--
-- Every row here is true of a market, in a region, in a period, and stops
-- being true without anything about a battery changing. So every row
-- carries a period and a basis, and the same provenance as everything
-- else.
--
-- THE LICENCE RULE. The price series that matter most are licensed
-- assessments (Fastmarkets, Benchmark, SMM, Argus, LME) whose terms forbid
-- redistribution. They are never copied here. They are recorded as sources
-- to join (docs/05-data-sources.md), and the rows in commodity_price and
-- price_index come from sources whose licence allows redistribution:
-- government statistics, public-domain surveys, company reports quoting a
-- realised price, openly licensed outlooks. The loader refuses a price row
-- whose source does not say its data may be redistributed.
-- =====================================================================

SET search_path = bd, public;

CREATE TYPE price_basis AS ENUM (
  'spot', 'contract', 'assessment', 'exchange_settlement', 'annual_average',
  'monthly_average', 'tender', 'list_price', 'realised', 'unspecified'
);

CREATE TYPE market_metric AS ENUM (
  'production', 'shipment', 'installation', 'sales', 'capacity', 'demand',
  'inventory', 'unspecified'
);

CREATE TYPE trade_direction AS ENUM ('import', 'export', 're_export');

-- ---------------------------------------------------------------------
-- COMMODITY PRICE: a price for a traded form, on a basis, in a market,
-- over a period. "USD 14,000 per tonne of lithium carbonate" is a price
-- for 187.9 kg of lithium (traded_form.contained_fraction), never for a
-- tonne of lithium.
-- ---------------------------------------------------------------------
CREATE TABLE commodity_price (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  commodity       text NOT NULL,                    -- 'lithium carbonate', 'cobalt metal', 'nickel sulphate'
  traded_form_id  bigint REFERENCES traded_form(id),
  grade           text,                             -- 'battery grade', '99.5% min'
  basis           price_basis NOT NULL DEFAULT 'unspecified',
  market          text NOT NULL,                    -- 'China domestic', 'CIF Asia', 'LME cash', 'US annual average'
  currency        char(3) NOT NULL,
  value           numeric(16,4) NOT NULL CHECK (value >= 0),
  per_unit        text NOT NULL,                    -- 't', 'kg', 'lb', 'mtu'
  period_start    date NOT NULL,
  period_end      date NOT NULL,
  provider        text,                             -- who assessed or published it
  provenance_id   bigint NOT NULL REFERENCES provenance(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (period_end >= period_start),
  UNIQUE NULLS NOT DISTINCT (commodity, grade, basis, market, currency, per_unit,
                             period_start, period_end, provenance_id)
);
CREATE INDEX ON commodity_price (commodity, period_start);

-- ---------------------------------------------------------------------
-- PRICE INDEX: cell, module, pack or system price per kWh.
-- ---------------------------------------------------------------------
CREATE TABLE price_index (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  segment          text NOT NULL,                   -- 'cell', 'module', 'pack', 'system'
  chemistry_family chemistry_family,
  sector           text,                            -- 'EV', 'ESS', 'consumer', 'all'
  region           text NOT NULL,
  currency         char(3) NOT NULL,
  value            numeric(12,4) NOT NULL CHECK (value >= 0),
  per_unit         text NOT NULL DEFAULT 'kWh',
  basis            price_basis NOT NULL DEFAULT 'unspecified',
  period_start     date NOT NULL,
  period_end       date NOT NULL,
  provider         text,
  provenance_id    bigint NOT NULL REFERENCES provenance(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (period_end >= period_start)
);
CREATE INDEX ON price_index (segment, region, period_start);

-- ---------------------------------------------------------------------
-- MARKET VOLUME: production, shipments, installations, sales, capacity
-- or demand, by maker, region, segment and chemistry, per period.
-- ---------------------------------------------------------------------
CREATE TABLE market_volume (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  metric           market_metric NOT NULL,
  org_id           bigint REFERENCES organization(id),
  region           text,                            -- 'global', 'Europe', 'China'
  country          text,                            -- ISO 3166-1 alpha-2
  sector           text,                            -- 'EV', 'ESS', 'consumer', 'two_wheeler', 'all'
  chemistry_family chemistry_family,
  value            numeric(18,4) NOT NULL CHECK (value >= 0),
  unit             text NOT NULL,                   -- 'GWh', 'MWh', 'units', 't'
  share_pct        numeric(6,3) CHECK (share_pct IS NULL OR share_pct BETWEEN 0 AND 100),
  rank             int,
  period_start     date NOT NULL,
  period_end       date NOT NULL,
  provider         text,
  provenance_id    bigint NOT NULL REFERENCES provenance(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (period_end >= period_start)
);
CREATE INDEX ON market_volume (metric, period_start);
CREATE INDEX ON market_volume (org_id);

-- ---------------------------------------------------------------------
-- TRADE FLOW: customs statistics by HS code. 850760 is lithium-ion
-- accumulators; 283691 lithium carbonate; 282520 lithium oxide and
-- hydroxide; 850750 nickel-metal hydride; 850710 lead-acid starters.
-- ---------------------------------------------------------------------
CREATE TABLE trade_flow (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  reporter_country text NOT NULL,                   -- ISO 3166-1 alpha-2
  partner_country  text NOT NULL,                   -- alpha-2, or 'WLD' for world
  hs_code          text NOT NULL,
  commodity        text,
  direction        trade_direction NOT NULL,
  period_start     date NOT NULL,
  period_end       date NOT NULL,
  value_usd        numeric(18,2) CHECK (value_usd IS NULL OR value_usd >= 0),
  quantity         double precision CHECK (quantity IS NULL OR quantity >= 0),
  quantity_unit    text,                            -- 'kg', 'units'
  provenance_id    bigint NOT NULL REFERENCES provenance(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (period_end >= period_start),
  CHECK (value_usd IS NOT NULL OR quantity IS NOT NULL),
  UNIQUE NULLS NOT DISTINCT (reporter_country, partner_country, hs_code, direction,
                             period_start, period_end, provenance_id)
);
CREATE INDEX ON trade_flow (hs_code, period_start);
