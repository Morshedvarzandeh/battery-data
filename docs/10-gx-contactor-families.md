# GX11, GX12 and GX14 contactor families

The 2026-09-29 batch adds three Sensata GIGAVAC families to the ordinary component
review pipeline. It contains **99 observations**, with official PDF URLs, literal
revision labels, page/section locators and measurement conditions. The source
manifest is [components/sources-2026-09-29-gx-contactors.json](../components/sources-2026-09-29-gx-contactors.json).
The records remain pending review. Source PDF text was readable, but direct byte
downloads returned HTTP 403 and visual table/curve verification was unavailable.
No PDF hash is invented, and proprietary PDF bodies are not redistributed.

| Family | Source revision | Observation count | Record |
|---|---|---:|---|
| GX11 | Rev 6 10/23/15 | 42 | [GX11](../review/candidates/sensata-gigavac/gx11.yaml) |
| GX12 | Rev 6 10/23/15 | 42 | [GX12](../review/candidates/sensata-gigavac/gx12.yaml) |
| GX14 | Rev A 7/2/18 | 15 | [GX14](../review/candidates/sensata-gigavac/gx14.yaml) |

## Identity and simulation binding

`product.identity_scope: family` and `product.variant_selection.status: required`
explicitly distinguish these records from orderable parts. Coil designation,
termination and auxiliary-contact options are still unspecified. These metadata
fields survive the JSON schema, review index, PostgreSQL loader, flattened
observation view, knowledge-graph product properties and web export. Existing
records without an identity scope remain unspecified; they are not automatically
reclassified as exact parts. Family approval would not select a variant.

Resolve a product UID and pin the dataset revision before simulation. Read the
observations once when binding a component to blocks. Do not query the graph at
each timestep. Preserve the evidence, statistic, bounds, unit and conditions in
the binding. No coil is selected by default from a family record.

The new generic quantities are `contact_resistance`, `operate_time` and
`release_time`. Native units are `mohm` and `ms`, with SI conversions to ohms and
seconds. Each requires a stated temperature or an explicit unstated-temperature
marker. Coil-specific rows use `conditions.extra.coil_designation`; GX11 and GX12
have separate rows for B, C, F, H, J, K, L, S and T. In particular, K and L are AC
coils with maximum release times of 50 and 55 ms, unlike the 12 ms DC options.
GX14 timing is published in the family specification table, so it has no invented
per-coil distinction. Only its operate-time temperature is explicitly given.

All three families state typical contact resistance as an interval, 0.15–0.3
mohm, plus a 0.4 mohm maximum. The typical interval is represented by two endpoint
observations with `value_min`/`value_max`, lower/upper flags and
`conditions.extra.range_kind: typical_interval`. These are interval endpoints,
not guaranteed population bounds or invented scalar typical values. A consumer
must retain the interval or explicitly choose a modelling value. The source
measured resistance above 100 A; applying a constant resistance outside that
measurement condition requires an explicit model assumption.

GX14 provides 13 ms typical and 20 ms maximum operate times; its maximum release
time is 12 ms. Operate time includes up to 7 ms contact bounce at 25°C. These
published timing limits alone do not establish an interruption rating. The
published chart labels retain conductor size and an 85°C terminal-rise condition;
they do not imply an unconditional current rating or a time-to-failure model.
No switching-life curves were digitized or extrapolated. No automotive
qualification or physical cause for failure to OPEN is inferred.

## Rebuild and validate

```sh
python3 tools/build_review_batch.py
python3 tools/render_review_issues.py
python3 tools/build_component_catalog.py
python3 tools/build_web_data.py
python3 tools/validate_contrib.py review/candidates/
python3 tools/validate_review.py
python3 tools/check_duplicates.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The existing rolled-back PostgreSQL component-loader test now covers family
metadata through graph projection, native-unit conversion and interval bounds.
For a fresh database, the ordered schema includes the new columns and quantity
definitions. Existing databases require an additive migration for
`bd.product.identity_scope`, `bd.product.variant_selection`, the three quantities
and the `ms` unit, plus refreshed view/graph definitions, before using the updated
loader. `tools/build_db.sh` recreates its target database and is not an in-place
migration command.
