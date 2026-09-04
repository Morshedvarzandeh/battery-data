# Upstream, distribution and market

A datasheet says nothing about where its lithium was mined, which refinery
turned it into hydroxide, which factory wound the cell, who distributes it,
who tested it, where it will be recycled, or what the market paid for any of
that. Those are the first questions a buyer, an investor or a regulator asks.
This layer answers them with the same rule as every other value here: **a
claim, by a source, under conditions, with the page it came from.**

The conditions are different but they are still conditions:

* a **resource estimate** is meaningless without the reporting code it was
  declared under (JORC, NI 43-101, SAMREC, SEC S-K 1300 and PERC do not agree
  on what may be called a reserve) and the cut-off grade it assumed;
* a **capacity** is nameplate, planned, announced, under construction, actual
  or estimated, and a press release's "40 GWh" is rarely the fifth;
* an **ownership share** has a date, a **supply agreement** a term;
* a **price** has a basis (spot, contract, assessment, exchange settlement,
  annual average), a market, a grade, a currency, a unit and a period;
* a **volume** is production, shipments, installations, sales, capacity or
  demand, for a period, and the four are not interchangeable.

All of that travels with the number or the number is refused. The map of the
layers is [`docs/00-map.md`](00-map.md).

## Sites

`bd.site` is a place where something is dug, refined, made, tested, stocked,
dismantled or recycled. One row per site, keyed `site/<operator>/<site>`,
with a kind, an operator, a country, optional coordinates, a status with its
date, the commodities it handles and the products it makes.

The kinds, and the stage each belongs to (`bd.site_stage()`):

| Kind | Stage | Example of what it produces |
|---|---|---|
| `mine`, `brine_operation` | mining | spodumene concentrate, lithium chloride brine, nickel matte |
| `refinery`, `chemical_plant` | refining | lithium hydroxide, nickel sulphate, spherical graphite |
| `precursor_plant` | precursor | pCAM |
| `cathode_plant`, `anode_plant` | active materials | NMC, LFP, graphite, silicon-carbon |
| `electrolyte_plant`, `separator_plant` | cell components | electrolyte, separator film |
| `cell_factory` | cells | 21700 cells, prismatic LFP |
| `module_pack_factory` | modules and packs | modules, packs |
| `component_factory` | components | contactors, fuses, BMS |
| `distribution_centre`, `port` | distribution | stock |
| `test_laboratory`, `research_facility` | testing, certification and research | UN 38.3, IEC 62660, abuse tests, published measurements |
| `second_life_facility` | second life | repurposed packs |
| `collection_point`, `recycling_plant` | collection and recycling | black mass, recovered sulphates and carbonate |
| `other` | none | |

A **test laboratory** is a site like a factory. Its products are the services
it offers (the standards it tests to), its capacity is `test_channels` and
`test_chambers` in the metrics, its operator is the company (which carries the
`lab` or `certification_body` role). A **recycler** produces black mass and
recovered chemicals, has a `capacity` in tonnes per year that must say whether
it is nameplate or actual, and a `recovery_rate` per element.

### Resources and reserves

`bd.resource_estimate`: commodity, category (measured, indicated, inferred,
measured_indicated, total_resource, proven, probable, total_reserve), the
reporting code, tonnage with unit, grade with unit, cut-off grade with unit,
contained metal with unit, the date, and `unstated[]` for what the source did
not say. The database refuses a row without a reporting code and a cut-off
unless they are listed as unstated, exactly as `condition_set.unstated` works
for a datasheet value. Only a mine or a brine operation may carry one.

### Capacity and output

`bd.site_metric`: a time series per site. `metric` is capacity, production,
throughput, recovery_rate, capex, energy_use, headcount, test_channels,
test_chambers or collection_volume; `subject` says what it is of ("lithium
hydroxide", "cells", "end-of-life batteries"); `status` says nameplate,
planned, announced, under_construction, actual, estimated or unspecified, and
a capacity or production row must say which; the value keeps the unit the
source states (`t/yr`, `GWh/yr`, `kt LCE/yr`, `channels`).

### Ownership

`bd.site_ownership`: organisation, share, role (owner, operator, jv_partner,
royalty_holder), valid from and to. Joint ventures change hands; the date is
what lets the library say who owned what when.

## Companies

`bd.organization` has always been here; [`docs/00-map.md`](00-map.md)
explains the roles, the stages and the one-uid rule. A company file
(`contrib/companies/`) adds legal name, aliases and former names, country and
headquarters, founding year, website, LEI, ROR, ticker, and **dated relations**
(`bd.organization_relation`): parent_of, subsidiary_of, joint_venture_of,
brand_of, formerly, renamed_to, acquired, merged_into, spun_off_from,
minority_stake_in, licensee_of, each with a share where it applies and a
source.

## Supply agreements and distribution

`bd.supply_agreement`: supplier, buyer, kind (offtake, supply, tolling,
licensing, joint_venture, prepayment), subject, the site it draws on, the
traded form, volume with unit and period, validity, the date it was
announced. `bd.distribution`: distributor, manufacturer, status (authorized,
franchised, independent, broker, online_marketplace), regions, product
families, the listing URL, validity. The listings themselves are
`bd.product_offer` rows carried by product files; the distribution row is the
relationship behind them.

## Prices, volumes and trade

`bd.commodity_price`: commodity, the `bd.traded_form` it is quoted for
(lithium carbonate is a price for 18.8% lithium, never for lithium), grade,
basis, market, currency, value, per unit, period, provider.
`bd.price_index`: segment (cell, module, pack, system), chemistry family and
designation, sector, region, currency, value per kWh, basis, period.
`bd.market_volume`: metric, organisation, region, country, sector, chemistry,
value with unit, share, rank, period. `bd.trade_flow`: reporter, partner, HS
code, direction, period, value in USD, quantity with unit.

### The licence rule

The assessments that matter most (Fastmarkets, Benchmark Mineral
Intelligence, SMM, Argus, LME settlements, CME futures, BNEF's price survey,
SNE Research) are licensed. Copying them would make this repository
undistributable. So:

* a market file's source declares `license` and `data_redistributable`;
* the validator and the loader refuse every price, index and volume row
  when `data_redistributable` is false;
* the file lists the licensed feeds under `providers` (name, URL, what they
  cover, terms) so a consumer knows what to join, and `bd.commodity_price.provider`
  names the assessment a public figure was quoted from;
* what may be loaded is public-domain and open-licence series: USGS Mineral
  Commodity Summaries and Minerals Yearbook, UN Comtrade, Eurostat Comext,
  ITC DataWeb, the Australian Resources and Energy Quarterly, Cochilco, the
  IEA outlooks where their terms allow, company filings.

Trade flows and supply agreements are facts from public records and are not
subject to the rule; they still carry their locator.

## Formats

One YAML file per site, per company, per market source and per patent
family. The validator tells a file's layer from its shape and refuses one
under the wrong directory. Fictional examples of every format are under
[`docs/examples/`](examples/README.md); the schemas are in `json-schema/`.

```bash
python tools/validate_layers.py              # contrib/{sites,companies,market,patents}
python tools/validate_layers.py --examples   # the fictional examples as well
python tools/load_layers.py --dsn dbname=batterydb
```

The loader creates an organisation named in any file when it is absent,
resolving the name against existing names, legal names and aliases first,
so that one company never becomes two. A reload of a file replaces what that
file asserted before.

## Queries

Every table above has a view and an API resource ([`docs/13-api.md`](13-api.md)):

```sql
-- lithium mines with a JORC or NI 43-101 reserve, by contained metal
SELECT site, country, category, reporting_code, contained_metal, contained_unit, as_of, source_url
  FROM bd.v_resource_estimate
 WHERE commodity = 'lithium' AND category IN ('proven','probable','total_reserve')
 ORDER BY contained_metal DESC NULLS LAST;

-- who buys from whom, and from which site
SELECT supplier, buyer, subject, site_uid, volume, volume_unit, volume_period, valid_from, valid_to
  FROM bd.v_supply_agreement;

-- every company on the recycling stage
SELECT uid, name, country, roles, stages FROM bd.v_company WHERE 'recycling' = ANY(stages);

-- the chain around one company, three hops, any relationship
SELECT * FROM bd_graph.reachable((SELECT 'org:'||id FROM bd.organization WHERE uid='org/example-lithium'),
                                 NULL, 3, 'both');
```

```bash
curl -G localhost:8080/v1/sites --data-urlencode 'filter=kind = "mine" AND commodities HAS "lithium"'
curl -G localhost:8080/v1/site_metrics --data-urlencode 'filter=metric = "capacity" AND status = "actual"'
curl -G localhost:8080/v1/companies --data-urlencode 'filter=stages HAS "recycling"'
curl -G localhost:8080/v1/commodity_prices --data-urlencode 'filter=commodity = "lithium carbonate" AND basis = "annual_average"'
```

## What is on the coverage list

The Coverage tab of the web page lists the mines and brines, the nickel,
cobalt, manganese and graphite mines, the refineries, the precursor, cathode
and anode plants, the cell and component factories, the test laboratories
and certification bodies, the recyclers and second-life companies, the
distributors, the companies to profile and the open statistical and patent
sources, each marked sourced the day its file lands under `contrib/`. It is
the work order.
