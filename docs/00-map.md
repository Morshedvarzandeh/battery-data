# The map

This database holds several things that look, at first sight, like several
databases: chemistries, cells and packs, the contactors and fuses around
them, companies, mines and factories, prices, patents, test laboratories and
recyclers. They are one database because every one of them is the same kind
of fact: **a claim, by a source, under conditions, with the page it came
from.** This page is the map. It says what the layers are, where each one's
data lives, how it gets in, and how it comes out.

## The layers

Read top to bottom, this is the order a battery is made and used, and the
order the API lists them in (`GET /v1/info`).

| Layer | What it holds | Data lives in | Gets in through | Comes out as |
|---|---|---|---|---|
| **The map** | the layers below and the ordered stages of the supply chain | `bd.supply_chain_stage`, `bd.organization_role` | `schema/184_companies.sql` (vocabulary, not contributions) | `/v1/layers`, `/v1/stages` |
| **Chemistry and materials** | chemistry designations and families, constructions (lead-acid), active materials, electrolytes, separators, traded forms | `bd.product_chemistry`, `bd.material`, `bd.traded_form` | the `chemistry` block of a product file; `seed/` for materials | `/v1/chemistries`, `/v1/materials` |
| **Products** | cells, primary cells, modules, packs, systems; every value with its statistic, conditions and locator; curves; parameter sets | `bd.product` → `product_revision` → `observation` + `condition_set`, `bd.curve`, `bd.model_parameterisation` | `contrib/cells/<maker>/<model>.yaml` ([format](../json-schema/cell-contribution.schema.json)), `contrib/models/` | `/v1/cells`, `/v1/packs`, `/v1/products`, `/v1/observations`, `/v1/curves`, `/v1/models` |
| **Components around the battery** | contactors, fuses, pyro-fuses, BMS, DC-DC converters, chargers, sensors, isolation monitors, busbars, thermal hardware, connectors | the same product tables with `product.component_kind` | the same product file with `kind: component` | `/v1/components` |
| **Companies** | every organisation with roles, the stages those roles place it on, identifiers (LEI, ROR, ticker), dated relations (parent, subsidiary, joint venture, brand, former name) | `bd.organization`, `organization_alias`, `organization_relation` | `contrib/companies/<slug>.yaml` ([format](../json-schema/company-contribution.schema.json)) | `/v1/companies`, `/v1/company_relations` |
| **Supply chain** | sites from the mine to the recycler: mines, brines, refineries, precursor, cathode, anode, electrolyte and separator plants, cell, module and component factories, test laboratories, research facilities, second-life facilities, collection points, recycling plants, distribution centres, ports; resources and reserves; capacity and output; ownership; supply agreements; distribution relationships | `bd.site`, `resource_estimate`, `site_metric`, `site_ownership`, `supply_agreement`, `distribution` | `contrib/sites/<operator>/<site>.yaml` ([format](../json-schema/site-contribution.schema.json)); agreements and distribution in a market file | `/v1/sites`, `/v1/resource_estimates`, `/v1/site_metrics`, `/v1/supply_agreements`, `/v1/distributions` |
| **Market** | commodity prices, cell and pack price indices, market volumes, trade flows, product offers | `bd.commodity_price`, `price_index`, `market_volume`, `trade_flow`, `product_offer` | `contrib/market/<source>.yaml` ([format](../json-schema/market-contribution.schema.json)); offers in a product file | `/v1/commodity_prices`, `/v1/price_indices`, `/v1/market_volumes`, `/v1/trade_flows`, `/v1/offers` |
| **Patents** | reviewed DOCDB families, their publications, categories under the versioned taxonomy, links to companies, products and materials | `bd.patent_family`, `patent_publication`, `patent_classification`, `patent_entity_link`; raw rows in `bd_stage` | `contrib/patents/<docdb-family-id>.yaml` ([format](../json-schema/patent-contribution.schema.json)) after the review in [`docs/08-patents.md`](08-patents.md) | `/v1/patent_families`, `/v1/patents`, `/v1/patent_categories` |
| **Standards and certifications** | standards referenced (never redistributed), certifications products hold, transport classification | `bd.standard`, `certification`, `transport_classification` | the `certifications` and `transport` blocks of a product file | `/v1/standards`, `/v1/certifications` |
| **Applications** | the vehicles, installations and devices batteries are fielded in | `bd.application`, `product_application` | the `applications` block of a product file | `/v1/applications` |
| **Sources and vocabulary** | every document cited, the quantity registry with its EMMO and QUDT bindings, units, the crosswalk to BDF, BPX and the Battery Passport | `bd.source`, `source_location`, `provenance`, `quantity`, `unit`, `quantity_mapping` | created by every loader; bindings by `tools/sync_vocabularies.py` | `/v1/sources`, `/v1/quantities`, `/v1/units`, `/v1/crosswalk` |

Test data (cycler files, EIS, abuse tests) sits under products as
`test_run → test_segment → dataset`; see [`docs/04-ingestion.md`](04-ingestion.md).

## The stages

Sites and companies are placed on one ordered vocabulary,
`bd.supply_chain_stage`, so that "who is upstream of this cell" is a query
and not a judgement. Every site kind but `other` belongs to exactly one
stage; every organisation role belongs to one stage or to none (publishers,
standards bodies, investors and governments are not in the chain).

| # | Stage | Site kinds | Roles |
|---|---|---|---|
| 1 | Mining and brines | mine, brine_operation | miner |
| 2 | Refining and chemicals | refinery, chemical_plant | refiner |
| 3 | Precursor | precursor_plant | precursor_producer |
| 4 | Active materials | cathode_plant, anode_plant | cathode_producer, anode_producer |
| 5 | Cell components | electrolyte_plant, separator_plant | electrolyte_producer, separator_producer, foil_can_producer |
| 6 | Cells | cell_factory | manufacturer |
| 7 | Modules and packs | module_pack_factory | pack_assembler |
| 8 | Systems | | integrator |
| 9 | Components around the battery | component_factory | component_manufacturer |
| 10 | Distribution | distribution_centre, port | distributor |
| 11 | Application | | oem, fleet_operator |
| 12 | Testing, certification and research | test_laboratory, research_facility | lab, certification_body, research_institute |
| 13 | Second life | second_life_facility | second_life |
| 14 | Collection and recycling | collection_point, recycling_plant | recycler |

`bd.site_stage(kind)` and `bd.organization_stages(org_id)` read this table;
`/v1/stages` returns it with how many sites and companies the library holds
at each stage. A company's stages are the union of its roles' stages and the
stages of the sites it operates or owns, so a miner that owns a refinery is
on two stages without anyone typing that.

## One company, one uid

Products, sites, agreements and patents all name companies. The rule is that
a company has one uid, `org/<slug>`, the same slug its products carry
(`cell/<slug>/...`). A name in any file is resolved against existing names,
legal names and aliases before a new uid is minted, by the loader
(`tools/load_layers.py`) and by the RDF export alike. A company file under
`contrib/companies/` is where the aliases, the legal name and the former
names are declared, which is what makes "LG Energy Solution", "LGES" and
"LG Chem (battery division)" one company and "Sanyo" a former name of
Panasonic rather than a fourth maker.

## What is refused at the door

The same discipline in every layer, enforced by the validators and the
database constraints:

| Layer | Refused |
|---|---|
| Products | a value without its statistic or its required conditions; a C-rate without its reference capacity |
| Sites | a resource estimate without its reporting code and cut-off grade (or their declared absence); a capacity that does not say nameplate, planned, announced or actual; a resource estimate on anything but a mine or a brine |
| Companies | a relation to the company itself; a pinned uid that does not exist; a joint venture or stake without its share |
| Market | any price, index or volume from a source whose data may not be redistributed; unordered periods; a supply agreement between one party and itself |
| Patents | an accepted family without a DOCDB id and a source; a legal status without its jurisdiction and date; a publication whose number does not match its jurisdiction |

## Where to read next

- [`docs/12-market-and-supply-chain.md`](12-market-and-supply-chain.md): sites, resources, capacity, ownership, agreements, distribution, prices, volumes, trade, and the licence rule.
- [`docs/13-api.md`](13-api.md): one API for every layer, the filter grammar, `POST /v1/query`, the graph endpoint, OpenAPI.
- [`docs/10-components-and-chemistries.md`](10-components-and-chemistries.md): components and every chemistry.
- [`docs/08-patents.md`](08-patents.md): the patent pipeline and its review boundary.
- [`docs/11-ontology.md`](11-ontology.md): how every layer is expressed in RDF and in the graph projection.
- [`docs/examples/`](examples/README.md): a fictional example file for each layer.
