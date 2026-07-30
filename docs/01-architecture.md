# Architecture

## Why Postgres is the store and the graph is a projection

You asked whether relational or graph is the better fit. The answer is that the
question has a false premise: they are good at different halves of this problem,
and the halves are separable.

**What the relational core is good at**, and what this database mostly does:

- Numeric range filtering — "≥5 Ah at ≤1C and ≥15 A continuous". This is the
  primary query and it is a B-tree scan.
- Unit and type enforcement. A graph database will happily store `"4900"` as a
  string in one node and `4.9` as a float in another.
- **Refusing malformed data.** The `validate_observation()` trigger and the
  `c_rate_needs_reference` CHECK are the single most valuable things here, and
  property graphs have no equivalent.
- Bulk analytics over millions of time-series rows.
- Transactional integrity across the review-queue promotion path.

**What a graph is genuinely better at**, and where the relational model strains:

- Unbounded-depth containment: system → pack → module → cell, where the depth
  varies by product.
- Supply-chain reachability: "which OEM products transitively depend on a cell
  whose cathode material comes from supplier X".
- Provenance closure: "shortest path from this published capacity figure back to
  a raw cycler file".
- Similarity and co-occurrence over the citation/campaign/protocol network.

So: **Postgres is the source of truth; the graph is derived and rebuildable.**
Nothing is stored only in the graph. Drop it and one command rebuilds it.

`bd_graph.node` and `bd_graph.edge` are materialised views over the relational
tables. Three consumption paths, all reading the same views:

1. `bd_graph.reachable()` — recursive CTE traversal in plain SQL. **Works with
   no extension installed.** This matters more than it sounds: it means the
   multi-hop queries work on a stock Postgres, and AGE/Neo4j become
   optimisations rather than prerequisites.
2. Apache AGE — openCypher inside the same database.
3. Neo4j — export via `tools/export_graph.py`.

The honest trade-off: the projection is eventually consistent. `bd_graph.refresh()`
must run after bulk loads. For a database whose write path is a human review
queue, that is not a real cost.

## The alternative that was rejected

**Git-native files as the source of truth**, with Postgres and the graph both as
built artefacts, is genuinely attractive — full history for free, maximum
transparency, community PRs as the write path.

It was rejected as the *primary* store because raw time-series data breaks it.
A single aging campaign is millions of rows; Git is a bad database for that, and
splitting "specs in Git, time series in Postgres" gives you two sources of truth
and a synchronisation problem.

What is kept from that idea: `contrib/` holds versioned YAML validated in CI
against JSON Schema, and it is the community contribution path. It just is not
the store.

## Storage strategy for time series

Three tiers, because retention is genuinely heterogeneous — labs keep full raw
for diagnostic cycles and summary-only for the thousands of aging cycles between:

| Tier | Table | When |
|---|---|---|
| Original vendor file | `dataset.original_file_uri` + `original_sha256` | **Always.** Every normalisation is potential information loss; the only defence is keeping the input. |
| Normalised records | `dataset` → Parquet/HDF5, or `timeseries_record` inline | Default Parquet; inline for small or heavily-queried series |
| Per-cycle summary | `cycle_summary` | Always — this is what most analysis actually reads |

`timeseries_record` is declaratively partitioned by `dataset_id` range so a
campaign can be attached and detached as a unit.

## The identity split

```
product          market identity            "INR21700-50E"
product_revision one document's account     V1.0 / rev0 / the AU variant
product_unit     a physical object          serial 2024-A-00417
```

Specification values attach to `product_revision`, never to `product`. Test data
attaches to `product_unit`, because you test a cell, not a datasheet.

The natural key for a spec value is
`(product, document, revision, region/customer scope, quantity, conditions)`.
Every layer of that is a column.

## Enforcement, not documentation

Three mechanisms carry the design:

1. **`quantity.required_conditions`** — an array naming the condition columns
   without which a quantity is uninterpretable. The `validate_observation()`
   trigger raises rather than inserts.
2. **`condition_set.fingerprint`** — content-addressed via a trigger, so
   identical conditions collapse to one row and "find everything measured under
   comparable conditions" is a join.
3. **`provenance` NOT NULL everywhere** — plus a CHECK that an
   `inferred_by_agent` value cannot reach `accepted` without a named human
   reviewer.
