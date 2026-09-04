"""
The resource registry: every queryable surface of the database, registered
once, grouped by layer, with its field map read from the database rather
than typed by hand. A new view becomes queryable the day it exists, with
the same grammar, the same envelope and the same provenance columns as
every other resource.

    /v1/info                  the layers and their resources
    /v1/info/{resource}       the field map of one resource
    /v1/{resource}            filter, sort, page, select fields
    /v1/{resource}/{id}       one row, with its related rows
    POST /v1/query            the same as JSON
    /v1/graph/reachable       multi-hop questions over bd_graph
    /v1/openapi.json          all of the above, generated

Layers are the reading order of docs/00-map.md: the map itself, chemistry
and materials, products, the components around them, companies, the
supply chain, the market, patents, standards, applications, and the
sources and vocabularies everything rests on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------
# Layers: the map, in reading order.
# ---------------------------------------------------------------------
LAYERS = [
    {"code": "map", "label": "The map",
     "description": "The layers of this database and the ordered stages of the supply chain that "
                    "sites and companies are placed on.",
     "resources": ["layers", "stages"]},
    {"code": "chemistry", "label": "Chemistry and materials",
     "description": "Chemistry designations and families as the library uses them, and the materials "
                    "(active materials, electrolytes, separators) with their suppliers.",
     "resources": ["chemistries", "materials"]},
    {"code": "products", "label": "Products",
     "description": "Cells, primary cells, modules, packs and systems: every value with the conditions "
                    "it was stated at and the page it came from.",
     "resources": ["cells", "packs", "products", "observations", "curves", "models"]},
    {"code": "components", "label": "Components around the battery",
     "description": "Contactors, fuses, BMS, converters, chargers, sensors, thermal hardware and "
                    "connectors, each rating with its condition.",
     "resources": ["components"]},
    {"code": "companies", "label": "Companies",
     "description": "Every organisation in the chain with its roles, the stages those roles put it on, "
                    "its identifiers and its dated relations to other companies.",
     "resources": ["companies", "company_relations"]},
    {"code": "supply_chain", "label": "Supply chain",
     "description": "Sites from mine to recycler with resources, capacity and output, ownership, "
                    "supply agreements and distribution relationships.",
     "resources": ["sites", "resource_estimates", "site_metrics", "supply_agreements", "distributions"]},
    {"code": "market", "label": "Market",
     "description": "Commodity prices, cell and pack price indices, market volumes, trade flows and "
                    "product offers, each with basis, market and period, from sources whose licence "
                    "allows redistribution.",
     "resources": ["commodity_prices", "price_indices", "market_volumes", "trade_flows", "offers"]},
    {"code": "patents", "label": "Patents",
     "description": "Reviewed patent families and their publications, categorised under the versioned "
                    "taxonomy and linked to companies, products and materials.",
     "resources": ["patent_families", "patents", "patent_categories"]},
    {"code": "standards", "label": "Standards and certifications",
     "description": "Standards referenced (never redistributed) and the certifications products hold.",
     "resources": ["standards", "certifications"]},
    {"code": "applications", "label": "Applications",
     "description": "The vehicles, installations and devices batteries are fielded in.",
     "resources": ["applications"]},
    {"code": "queue", "label": "The queue",
     "description": "Names of companies and sites recalled without a document and waiting to be "
                    "verified against one. These are NOT facts and are not part of the library: "
                    "they carry no source, no page and no quote, and the database refuses one that "
                    "does. They are here so the work still to be done is as queryable as the work "
                    "already finished.",
     "resources": ["layer_candidates"]},
    {"code": "provenance", "label": "Sources and vocabulary",
     "description": "The documents every row traces to, the quantity registry with its EMMO and QUDT "
                    "bindings, units, and the crosswalk to BDF, BPX and the Battery Passport.",
     "resources": ["sources", "quantities", "units", "crosswalk"]},
]


@dataclass
class Resource:
    view: str | None                 # <schema>.<view>; None for a resource served from Python
    id: str                          # the column that identifies a row
    description: str
    sort: str = ""                   # default ORDER BY, over view columns
    aliases: dict = field(default_factory=dict)   # extra filter names -> {"col","type"}
    related: dict = field(default_factory=dict)   # name -> (view, view_column, row_key)
    examples: list = field(default_factory=list)
    note: str = ""
    schema: str = "bd"               # 'bd_stage' for a queue, which is not accepted data
    accepted: bool = True            # False marks a resource whose rows are not facts yet


RESOURCES: dict[str, Resource] = {
    # -- map ----------------------------------------------------------
    "layers": Resource(None, "code", "The layers of this database, in reading order, with their resources."),
    "stages": Resource("v_stage", "code", "The ordered stages of the supply chain, with the site kinds and "
                       "organisation roles that belong to each and how many sites and companies the library "
                       "holds there.", sort="position",
                       examples=['sites > 0', 'roles HAS "recycler"']),
    # -- chemistry ----------------------------------------------------
    "chemistries": Resource("v_chemistry", "designation", "Chemistry designations and families as the library's "
                            "current revisions state them, with product counts.", sort="products DESC",
                            examples=['family = "lead_acid"', 'designation CONTAINS "LFP"']),
    "materials": Resource("v_material", "uid", "Materials with formula, elements, family, density and their "
                          "OPTIMADE identifiers.", sort="uid",
                          examples=['elements HAS ALL "Li","Fe","P"', 'role = "cathode"']),
    # -- products -----------------------------------------------------
    "cells": Resource("v_cell_selection", "product_uid", "Cells with their specification values: capacity at "
                      "its rate, discharge and charge limits, resistance with its method, cycle life with its "
                      "conditions.", sort="capacity_low_rate_ah DESC NULLS LAST",
                      related={"observations": ("v_observation", "product_revision_id", "product_revision_id"),
                               "curves": ("v_curve", "product_uid", "product_uid"),
                               "certifications": ("v_certification", "product_uid", "product_uid"),
                               "offers": ("v_offer", "product_uid", "product_uid"),
                               "models": ("v_model", "product_uid", "product_uid")},
                      examples=['capacity_ah >= 4.5 AND form_factor_code = "21700"',
                                'manufacturer CONTAINS "Samsung" AND max_cont_discharge_a > 9',
                                'chemistry = "LFP" AND capacity_ah > 200'],
                      note="capacity_ah is the low-rate figure and capacity_1c_ah the ~1C figure. They are "
                           "exposed separately on purpose: vendors publish both and they are not the same "
                           "number."),
    "packs": Resource(None, "product_uid", "Packs with their assembly, applications and market values folded "
                      "in. Filter with ?sector=<sector> only; the aggregate shape does not take the grammar."),
    "products": Resource("v_product", "product_uid", "Every product of every kind (cells, primary cells, "
                         "modules, packs, systems, components) with chemistry, lifecycle, source and counts.",
                         sort="manufacturer, model_number",
                         related={"observations": ("v_observation", "product_revision_id", "product_revision_id"),
                                  "curves": ("v_curve", "product_uid", "product_uid"),
                                  "certifications": ("v_certification", "product_uid", "product_uid"),
                                  "offers": ("v_offer", "product_uid", "product_uid")},
                         examples=['kind = "pack" AND chemistry_family = "sodium_ion"',
                                   'lifecycle = "discontinued"']),
    "observations": Resource("v_observation", "observation_id", "Every value in the library with its statistic, "
                             "conditions, evidence class and page-level citation.",
                             sort="product_uid, quantity",
                             examples=['quantity = "cycle_life" AND temperature_c = 45',
                                       'product_uid = "cell/lg-energy-solution/inr21700-m50lt"']),
    "curves": Resource("v_curve", "uid", "Digitised and tabulated curves with their axes, conditions and source.",
                       sort="uid", examples=['curve_kind = "derating"', 'manufacturer CONTAINS "CATL"']),
    "models": Resource("v_model", "uid", "Published physics and equivalent-circuit parameter sets with the "
                       "article they transcribe.", sort="uid", examples=['kind = "dfn_parameter_set"']),
    # -- components ---------------------------------------------------
    "components": Resource("v_component_selection", "product_uid", "Contactors, fuses, converters, BMS and "
                           "the rest, each rating with the condition it was stated at.",
                           sort="manufacturer, model_number",
                           related={"observations": ("v_observation", "product_revision_id", "product_revision_id"),
                                    "curves": ("v_curve", "product_uid", "product_uid")},
                           examples=['component_kind = "contactor" AND rated_current_a >= 400',
                                     'breaking_capacity_a > 10000 AND breaking_circuit_v >= 800'],
                           note="Each rating keeps the condition it was stated at: a breaking capacity with "
                                "its circuit voltage and L/R, a rated current with its ambient, an efficiency "
                                "with its input voltage and load."),
    # -- companies ----------------------------------------------------
    "companies": Resource("v_company", "uid", "Organisations with roles, the supply-chain stages those roles "
                          "and their sites put them on, identifiers, parent, and counts of what the library "
                          "holds about them.", sort="name",
                          related={"products": ("v_product", "manufacturer", "name"),
                                   "sites_operated": ("v_site", "operator_uid", "uid"),
                                   "supplies": ("v_supply_agreement", "supplier_uid", "uid"),
                                   "buys": ("v_supply_agreement", "buyer_uid", "uid"),
                                   "distributes_for": ("v_distribution", "distributor_uid", "uid"),
                                   "distributed_by": ("v_distribution", "manufacturer_uid", "uid"),
                                   "relations": ("v_company_relation", "organization_uid", "uid"),
                                   "related_from": ("v_company_relation", "related_uid", "uid")},
                          examples=['stages HAS "recycling"', 'country = "AU" AND roles HAS "miner"',
                                    'name CONTAINS "LG"']),
    "company_relations": Resource("v_company_relation", "id", "Dated ownership and identity relations between "
                                  "companies, each with its source.", sort="organization, relation",
                                  examples=['relation = "joint_venture_of"']),
    # -- supply chain -------------------------------------------------
    "sites": Resource("v_site", "uid", "Mines, brine operations, refineries, plants, factories, test "
                      "laboratories, second-life facilities, collection points, recyclers, distribution "
                      "centres and ports, each with its stage, operator, country, status and what it makes.",
                      sort="country, name",
                      related={"resource_estimates": ("v_resource_estimate", "site_uid", "uid"),
                               "metrics": ("v_site_metric", "site_uid", "uid"),
                               "supply_agreements": ("v_supply_agreement", "site_uid", "uid")},
                      examples=['kind = "mine" AND commodities HAS "lithium"',
                                'stage = "recycling" AND status = "operating"',
                                'kind = "test_laboratory" AND country = "DE"']),
    "resource_estimates": Resource("v_resource_estimate", "id", "Mineral resources and reserves with category, "
                                   "reporting code, grade, cut-off and contained metal, dated.",
                                   sort="site_uid, category",
                                   examples=['commodity = "lithium" AND category = "total_reserve"']),
    "site_metrics": Resource("v_site_metric", "id", "Capacity, production, throughput, recovery rate, test "
                             "channels and other per-site series, each saying whether it is nameplate, "
                             "planned, announced or actual.", sort="site_uid, metric, period_start",
                             examples=['metric = "capacity" AND status = "actual"']),
    "supply_agreements": Resource("v_supply_agreement", "uid", "Who has agreed to sell what to whom, from "
                                  "which site, for how long.", sort="uid",
                                  examples=['subject CONTAINS "hydroxide"', 'kind = "offtake"']),
    "distributions": Resource("v_distribution", "id", "Distributors, the makers they carry, their status "
                              "and regions.", sort="distributor, manufacturer",
                              examples=['status = "authorized" AND regions HAS "North America"']),
    # -- market -------------------------------------------------------
    "commodity_prices": Resource("v_commodity_price", "id", "Commodity price series with traded form, grade, "
                                 "basis, market, currency and period, only from redistributable sources.",
                                 sort="commodity, period_start",
                                 examples=['commodity = "lithium carbonate" AND basis = "annual_average"']),
    "price_indices": Resource("v_price_index", "id", "Cell, module, pack and system price indices per "
                              "chemistry, sector and region.", sort="segment, period_start",
                              examples=['segment = "pack" AND chemistry = "LFP"']),
    "market_volumes": Resource("v_market_volume", "id", "Production, shipments, installations, sales, "
                               "capacity and demand by maker, region, sector and chemistry.",
                               sort="metric, period_start", examples=['metric = "shipment" AND rank <= 10']),
    "trade_flows": Resource("v_trade_flow", "id", "Imports and exports by reporter, partner, HS code and period.",
                            sort="reporter_country, hs_code, period_start",
                            examples=['hs_code STARTS WITH "8507" AND direction = "export"']),
    "offers": Resource("v_offer", "id", "Product listings as a price time series: seller, region, price, "
                       "MOQ, lead time, grade, date.", sort="product_uid, observed_at",
                       examples=['currency = "EUR" AND in_stock = "true"']),
    # -- patents ------------------------------------------------------
    "patent_families": Resource("v_patent_family", "uid", "Reviewed DOCDB families with category, "
                                "publications, jurisdictions and the companies, products and materials "
                                "they are linked to.", sort="earliest_priority_date DESC NULLS LAST",
                                related={"publications": ("v_patent", "family_uid", "uid")},
                                examples=['primary_category = "thermal_safety"',
                                          'organizations CONTAINS "Example"']),
    "patents": Resource("v_patent", "uid", "Patent publications with dates, applicants, inventors, categories "
                        "and legal status observed on a date.", sort="publication_date DESC NULLS LAST",
                        examples=['jurisdiction = "EP" AND categories HAS "electrochemistry_materials"',
                                  'grant_date IS KNOWN']),
    "patent_categories": Resource("v_patent_category", "code", "The versioned taxonomy patents are classified "
                                  "under, with counts.", sort="code"),
    # -- standards ----------------------------------------------------
    "standards": Resource("v_standard", "uid", "Standards referenced by certifications and sources; texts are "
                          "never redistributed.", sort="sdo, number", examples=['sdo = "IEC"']),
    "certifications": Resource("v_certification", "id", "Certifications products hold: standard, scope, status, "
                               "certificate number, body, dates, source.", sort="product_uid, standard",
                               examples=['standard CONTAINS "62619" AND status = "certified"']),
    # -- applications -------------------------------------------------
    "applications": Resource("v_application", "uid", "Vehicles, installations and devices with sector, "
                             "operator, region and service dates.", sort="name",
                             examples=['sector = "grid_storage"']),
    # -- provenance and vocabulary -----------------------------------
    "sources": Resource("v_source", "uid", "Every document the library cites, with kind, licence, "
                        "redistributability and how many claims rest on it.", sort="uid",
                        examples=['kind = "datasheet" AND claims > 20']),
    "quantities": Resource("v_quantity", "code", "The quantity registry with required conditions and EMMO, "
                           "QUDT, BDF, BPX and Battery Passport bindings.", sort="code",
                           examples=['required_conditions HAS "temperature_c"']),
    "units": Resource("v_unit", "symbol", "Units with their SI conversion and QUDT IRI.", sort="symbol"),
    "layer_candidates": Resource(
        "v_layer_candidate", "uid",
        "Companies and sites recalled without a document, each with the page to verify it against. "
        "Not facts: no row here has a source, and none enters the library until "
        "tools/verify_layer_candidates.py finds the name on that page and quotes it.",
        sort="candidate_set, entity, uid", schema="bd_stage", accepted=False,
        examples=['entity = "site" AND kind = "cell_factory" AND country = "CN"',
                  'stages HAS "active_material" AND confidence = "high"',
                  'in_library = "false" AND candidate_set = "gigafactories"'],
        note="Every row is a work order, not a record. `confidence` is how sure the recall is, "
             "`status_recalled` is the plant status as recalled and is the field most likely to be "
             "stale, and `in_library` says whether the uid already names something the library holds."),
    "crosswalk": Resource("v_crosswalk", "quantity", "Mapping of every quantity to BDF, EMMO/BattINFO, BPX and "
                          "the EU Battery Passport.", sort="vocabulary, quantity"),
}

# The relationship types bd_graph projects (schema/190_graph.sql), plus the
# company relations it emits as upper(relation).
ORG_RELATION_KINDS = ["parent_of", "subsidiary_of", "joint_venture_of", "brand_of", "formerly", "renamed_to",
                      "acquired", "merged_into", "spun_off_from", "minority_stake_in", "licensee_of"]
GRAPH_RELS = sorted({
    "HAS_REVISION", "SUPERSEDES", "CONTAINS", "INSTANCE_OF", "SUPPLIED_BY", "USES_MATERIAL", "TESTED",
    "FOLLOWS_PROTOCOL", "RPT_PROTOCOL", "PART_OF_CAMPAIGN", "PRODUCED", "EVIDENCED_BY", "DOCUMENTED_BY",
    "IMPLEMENTS_STANDARD", "PARAMETERISES", "FITTED_FROM", "FIELDED_IN", "HOLDS_CERTIFICATION",
    "CERTIFIED_TO", "OFFERED_BY", "EQUIVALENT_TO", "OPERATES", "OWNS", "SUPPLIES", "SUPPLIED_FROM",
    "DISTRIBUTES", "HAS_PUBLICATION", "PUBLISHED_AS", "PATENT_RELATES_TO",
} | {k.upper() for k in ORG_RELATION_KINDS})

FILTER_OPERATORS = ["=", "!=", "<", "<=", ">", ">=", "AND", "OR", "NOT", "CONTAINS", "STARTS WITH",
                    "ENDS WITH", "IS KNOWN", "IS UNKNOWN", "HAS", "HAS ALL", "HAS ANY", "HAS ONLY"]

NUMERIC_TYPES = {"smallint", "integer", "bigint", "numeric", "real", "double precision"}


def layer_of(resource: str) -> str | None:
    for layer in LAYERS:
        if resource in layer["resources"]:
            return layer["code"]
    return None


def field_map(columns: list[dict], aliases: dict | None = None) -> dict:
    """The filter grammar's field map from information_schema.columns rows.

    Numbers filter as numbers; arrays filter with HAS; everything else
    (text, enums, booleans, dates, json) filters as a string against its
    text form, so `in_stock = "true"` and `grant_date >= "2020-01-01"` both
    work without a type of their own.
    """
    fields: dict = {}
    for c in columns:
        name, dt = c["column_name"], c["data_type"]
        q = f'"{name}"'                       # quoted: a view may call a column offset or year
        if dt in NUMERIC_TYPES:
            fields[name] = {"col": q, "type": "number", "column": name}
        elif dt == "ARRAY":
            fields[name] = {"col": q, "type": "list", "column": name}
        elif dt in ("text", "character varying", "character"):
            fields[name] = {"col": q, "type": "string", "column": name}
        else:
            fields[name] = {"col": f"{q}::text", "type": "string", "column": name}
    for alias, spec in (aliases or {}).items():
        if alias not in fields:
            fields[alias] = {**spec, "column": None}
    return fields


def openapi(field_maps: dict[str, dict], base_url: str = "/v1", version: str = "1.0.0") -> dict:
    """An OpenAPI 3.1 document generated from the registry and the field maps."""
    def json_type(t: str) -> dict:
        return {"number": {"type": "number", "nullable": True},
                "list": {"type": "array", "items": {"type": "string"}},
                "string": {"type": "string", "nullable": True}}[t]

    paths, schemas, tags = {}, {}, []
    page = [{"name": "filter", "in": "query", "schema": {"type": "string"},
             "description": "OPTIMADE-style filter over the resource's fields; see /v1/info/{resource}."},
            {"name": "sort", "in": "query", "schema": {"type": "string"},
             "description": "A field name; prefix with - for descending."},
            {"name": "fields", "in": "query", "schema": {"type": "string"},
             "description": "Comma-separated fields to return; the id is always included."},
            {"name": "page_limit", "in": "query", "schema": {"type": "integer", "default": 20, "maximum": 500}},
            {"name": "page_offset", "in": "query", "schema": {"type": "integer", "default": 0}}]
    for layer in LAYERS:
        tags.append({"name": layer["code"], "description": f"{layer['label']}. {layer['description']}"})
    for name, res in RESOURCES.items():
        tag = layer_of(name)
        fm = field_maps.get(name, {})
        props = {f: {**json_type(spec["type"]),
                     "description": f"column {spec['column']}" if spec.get("column") else f"alias of {spec['col']}"}
                 for f, spec in fm.items()}
        schemas[name] = {"type": "object", "properties": props}
        params = page if res.view else [{"name": "sector", "in": "query", "schema": {"type": "string"}}] \
            if name == "packs" else []
        paths[f"{base_url}/{name}"] = {"get": {
            "tags": [tag], "summary": res.description.split(". ")[0],
            "description": res.description + (" " + res.note if res.note else ""),
            "parameters": params,
            "responses": {"200": {"description": "JSON:API envelope: meta, data[], links",
                                  "content": {"application/vnd.api+json": {"schema": {
                                      "type": "object",
                                      "properties": {"meta": {"type": "object"},
                                                     "data": {"type": "array", "items": {
                                                         "type": "object",
                                                         "properties": {"type": {"type": "string"},
                                                                        "id": {"type": "string"},
                                                                        "attributes": {"$ref": f"#/components/schemas/{name}"}}}}}}}}},
                          "400": {"description": "Invalid filter, sort or field"}}}}
        if res.view:
            paths[f"{base_url}/{name}/{{id}}"] = {"get": {
                "tags": [tag], "summary": f"One {name[:-1] if name.endswith('s') else name} by {res.id}",
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "The row, with related rows under relationships"
                                                     + (": " + ", ".join(res.related) if res.related else "")},
                              "404": {"description": "No such id"}}}}
    paths[f"{base_url}/query"] = {"post": {
        "tags": ["map"], "summary": "Query any resource with a JSON body",
        "requestBody": {"required": True, "content": {"application/json": {"schema": {
            "type": "object", "required": ["resource"],
            "properties": {"resource": {"type": "string", "enum": [n for n, r in RESOURCES.items() if r.view]},
                           "filter": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}},
                           "sort": {"type": "string"},
                           "page_limit": {"type": "integer", "default": 20, "maximum": 500},
                           "page_offset": {"type": "integer", "default": 0}}}}}},
        "responses": {"200": {"description": "The same envelope as GET /v1/{resource}"}}}}
    paths[f"{base_url}/graph/reachable"] = {"get": {
        "tags": ["map"], "summary": "Every node reachable from a uid over the graph projection",
        "parameters": [{"name": "start", "in": "query", "required": True, "schema": {"type": "string"},
                        "description": "A uid: cell/..., org/..., site/..., patent/..., mat/..."},
                       {"name": "rels", "in": "query", "schema": {"type": "string"},
                        "description": "Comma-separated relationship types; all when absent. " + ", ".join(GRAPH_RELS)},
                       {"name": "depth", "in": "query", "schema": {"type": "integer", "default": 3, "maximum": 8}},
                       {"name": "direction", "in": "query", "schema": {"type": "string", "enum": ["out", "in", "both"], "default": "both"}}],
        "responses": {"200": {"description": "Nodes with label, uid, title, depth and path"}}}}
    paths[f"{base_url}/info"] = {"get": {"tags": ["map"], "summary": "Layers, resources and endpoints",
                                         "responses": {"200": {"description": "The map"}}}}
    paths[f"{base_url}/info/{{resource}}"] = {"get": {
        "tags": ["map"], "summary": "The field map, operators and examples of one resource",
        "parameters": [{"name": "resource", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": {"description": "Field map"}, "404": {"description": "No such resource"}}}}
    return {"openapi": "3.1.0",
            "info": {"title": "battery-data API", "version": version,
                     "description": "One read API for every layer of the open, provenance-first battery "
                                    "database: chemistry, products, components, companies, the supply chain "
                                    "from mine to recycler, the market, patents, standards, applications and "
                                    "the sources everything traces to. Every row that has a source carries "
                                    "source_uid, source_url and quote.",
                     "license": {"name": "CC-BY-4.0 for curated data; source documents are not redistributed"}},
            "servers": [{"url": base_url.rsplit("/", 1)[0] or "/"}],
            "tags": tags, "paths": paths, "components": {"schemas": schemas}}
