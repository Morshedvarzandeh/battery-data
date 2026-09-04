# Format examples

Every file in this directory is **fictional**. The companies, sites, prices
and patents do not exist; the URLs point at example.org. They show the shape
of a contribution for each layer that is not a product, and CI validates them
with `python tools/validate_layers.py --examples`. Nothing here is ever
loaded into the library: the loaders read `contrib/` only.

| File | Layer | Directory a real one goes in |
|---|---|---|
| `site-mine.yaml` | a mine with a resource estimate, production and ownership | `contrib/sites/<operator>/<site>.yaml` |
| `site-test-laboratory.yaml` | a test centre with its services and channel count | `contrib/sites/<operator>/<site>.yaml` |
| `site-recycler.yaml` | a recycling plant with capacity and recovery rate | `contrib/sites/<operator>/<site>.yaml` |
| `company.yaml` | a company profile with roles and dated relations | `contrib/companies/<slug>.yaml` |
| `market.yaml` | prices, an index, volumes, trade, a supply agreement, a distributor | `contrib/market/<source>.yaml` |
| `patent.yaml` | a reviewed patent family with publications and links | `contrib/patents/<docdb-family-id>.yaml` |

Products (cells, modules, packs, systems, components) have their own format:
`json-schema/cell-contribution.schema.json`, under `contrib/cells/`.
