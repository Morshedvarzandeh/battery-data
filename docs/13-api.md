# One API for every layer

`api/server.py` serves every layer of the database through one grammar, one
envelope and one set of endpoints. Nothing is typed twice: the resources are
registered once in `api/resources.py`, grouped by layer in the order of
[`docs/00-map.md`](00-map.md), and each resource's field map is read from
`information_schema` at first use, so a column added to a view is filterable
the day it exists.

```bash
python api/server.py --port 8080          # or ./setup.sh --api, or docker compose up
curl localhost:8080/v1/info
```

## Endpoints

| Endpoint | What it returns |
|---|---|
| `GET /v1/info` | the layers, each with its resources, and the operators |
| `GET /v1/info/{resource}` | the field map of one resource: name, type, column, sortable; examples; related rows |
| `GET /v1/{resource}` | rows, with `filter`, `sort`, `fields`, `page_limit`, `page_offset` |
| `GET /v1/{resource}/{id}` | one row and its related rows under `relationships` |
| `POST /v1/query` | the same query as JSON: `{"resource", "filter", "fields", "sort", "page_limit", "page_offset"}` |
| `GET /v1/graph/reachable` | every node reachable from a uid over the graph projection: `start`, `rels`, `depth`, `direction` |
| `GET /v1/openapi.json` | the OpenAPI 3.1 document, generated from the registry and the field maps |
| `GET /v1/links` | the providers this database federates to (Materials Project, Battery Data Alliance) |
| `GET /v1/packs` | packs with assembly, applications and market values folded in; `?sector=` only |

The response is a JSON:API envelope on OPTIMADE's conventions: `meta`
(`api_version`, `data_returned`, `more_data_available`, `layer`, the query),
`data` (one `{type, id, attributes}` per row) and `links` (`next` when there
is more). Errors come back as `errors[]` with a status, a title, the detail
and a hint.

## Resources by layer

| Layer | Resources |
|---|---|
| The map | `layers`, `stages` |
| Chemistry and materials | `chemistries`, `materials` |
| Products | `cells`, `packs`, `products`, `observations`, `curves`, `models` |
| Components | `components` |
| Companies | `companies`, `company_relations` |
| Supply chain | `sites`, `resource_estimates`, `site_metrics`, `supply_agreements`, `distributions` |
| Market | `commodity_prices`, `price_indices`, `market_volumes`, `trade_flows`, `offers` |
| Patents | `patent_families`, `patents`, `patent_categories` |
| Standards | `standards`, `certifications` |
| Applications | `applications` |
| Sources and vocabulary | `sources`, `quantities`, `units`, `crosswalk` |
| The queue (not accepted data) | `layer_candidates` |

Every resource but one serves accepted data. `layer_candidates` serves the
candidate queue described in [`docs/14-candidates.md`](14-candidates.md):
recalled names awaiting verification. It reads from `bd_stage`, not `bd`, its
responses carry `"accepted": false` and a warning, and `/v1/info` marks it so
a client can refuse to treat it as fact.

Every row that has a source carries `source_uid`, `source_url`, `page` and
`quote`. A detail response adds the related rows a reader wants next: a cell
its observations, curves, certifications, offers and parameter sets; a
company the products it makes, the sites it operates, what it supplies and
buys, whom it distributes for, its relations; a site its resource estimates,
metrics and agreements; a patent family its publications.

## The filter grammar

The OPTIMADE filter language, over the resource's fields:

```
capacity_ah >= 4.5 AND form_factor_code = "21700"
kind = "mine" AND commodities HAS "lithium"
stages HAS ALL "mining","refining"
name CONTAINS "LG" OR aliases CONTAINS "LGES"
grant_date IS KNOWN AND jurisdiction = "EP"
NOT (status = "closed") AND period_start >= "2024-01-01"
```

Operators: `=`, `!=`, `<`, `<=`, `>`, `>=`, `AND`, `OR`, `NOT`, `CONTAINS`,
`STARTS WITH`, `ENDS WITH`, `IS KNOWN`, `IS UNKNOWN`, `HAS`, `HAS ALL`,
`HAS ANY`, `HAS ONLY`.

Field types are derived from the column type:

| Column | Field type | Filters as |
|---|---|---|
| numeric, integer, double precision | `number` | `value > 100` |
| text | `string` | `name = "..."`, `CONTAINS` |
| array | `list` | `commodities HAS "lithium"`, `HAS ALL`, `HAS ANY`, `HAS ONLY`; `CONTAINS` searches the elements; `=` is refused |
| boolean, date, timestamp, enum, json | `string` against the text form | `in_stock = "true"`, `period_start >= "2024-01-01"`, `status != "closed"` |

`cells` and `components` also keep their short aliases (`capacity_ah` for
`capacity_low_rate_ah`, `cathode` for `cathode_text`, and so on) from
`api/filter_grammar.py`. An unknown field is refused with the nearest names
suggested; a wrong type is refused with the reason. Identifiers never come
from the request: the view, the columns and the sort key are looked up in the
registry and the field map, and values are bound as parameters.

## Examples

```bash
B=localhost:8080

# the map
curl $B/v1/layers
curl "$B/v1/stages?fields=code,label,sites,companies"

# products
curl -G $B/v1/cells --data-urlencode 'filter=chemistry = "LFP" AND capacity_ah > 200' --data-urlencode 'sort=-capacity_ah'
curl "$B/v1/cells/cell%2Flg-energy-solution%2Finr21700-m50lt"
curl -G $B/v1/observations --data-urlencode 'filter=quantity = "cycle_life" AND temperature_c = 45' \
     --data-urlencode 'fields=product_uid,value_native,unit_native,dod_pct,rate_value,rate_unit,page,quote'
curl -G $B/v1/components --data-urlencode 'filter=component_kind = "contactor" AND breaking_capacity_a > 10000'

# companies and the chain
curl -G $B/v1/companies --data-urlencode 'filter=country = "AU" AND roles HAS "miner"'
curl "$B/v1/companies/org%2Fpanasonic"
curl -G $B/v1/sites --data-urlencode 'filter=stage = "recycling" AND status = "operating"'
curl -G $B/v1/site_metrics --data-urlencode 'filter=metric = "capacity" AND status = "nameplate" AND unit = "GWh/yr"'
curl -G $B/v1/supply_agreements --data-urlencode 'filter=subject CONTAINS "hydroxide"'

# market
curl -G $B/v1/commodity_prices --data-urlencode 'filter=commodity = "lithium carbonate" AND period_start >= "2024-01-01"'
curl -G $B/v1/price_indices --data-urlencode 'filter=segment = "pack" AND chemistry = "LFP"'
curl -G $B/v1/trade_flows --data-urlencode 'filter=hs_code STARTS WITH "8507" AND direction = "export"'

# patents
curl -G $B/v1/patent_families --data-urlencode 'filter=primary_category = "thermal_safety"'
curl -G $B/v1/patents --data-urlencode 'filter=jurisdiction = "EP" AND grant_date IS KNOWN'

# the same as JSON
curl -X POST $B/v1/query -H 'Content-Type: application/json' -d '{
  "resource": "sites",
  "filter": "kind = \"mine\" AND commodities HAS \"lithium\"",
  "fields": ["uid", "name", "country", "operator", "status", "source_url"],
  "sort": "country", "page_limit": 50
}'

# multi-hop: everything within three hops of a company, any relationship
curl -G $B/v1/graph/reachable --data-urlencode 'start=org/example-lithium' --data-urlencode 'depth=3'
# the packs that contain a cell revision
curl -G $B/v1/graph/reachable --data-urlencode 'start=cell/samsung-sdi/inr21700-50e' \
     --data-urlencode 'rels=HAS_REVISION,CONTAINS' --data-urlencode 'direction=in'
```

## Adding a resource

1. Create the view in `schema/` (a view under `bd.` with the row's provenance
   columns, `source_uid`, `source_url`, `page`, `quote`, where the row has a
   source).
2. Register it in `api/resources.py`: the view, the id column, a description,
   a default sort, related rows, examples. Put its name in a layer. A view
   outside `bd` needs `schema=`, and one whose rows are not facts needs
   `accepted=False` so the envelope warns.
3. Nothing else. The field map, the endpoints, `/v1/info`, `POST /v1/query`
   and the OpenAPI document follow from the registry; `tests/test_api_registry.py`
   checks that the view exists and the resource sits in exactly one layer.

## Running it

The server needs a database (`./tools/build_db.sh`, the seeds, the loaders)
and either `psycopg`/`psycopg2` or a `psql` on the path. `BATTERY_DSN` or
`--dsn` selects the database. It listens on 127.0.0.1; put a reverse proxy in
front of it for anything public, and cache `/v1/openapi.json` there.
