# Electrical components

[Browse models and datasheets](catalog.md). The initial batch contains **13 pending
models / 62 observations** across all six requested categories:

| Category | Initial models | Key observations |
|---|---:|---|
| Main contactors | 2 | Contact voltage, coil voltage, qualified carry current |
| Fuses | 3 | Part-specific rated current/voltage, interruption capacity |
| Precharge contactors | 2 | Contact and coil voltage, conductor-dependent carry current |
| Inverters | 2 | DC input range, AC output, continuous watts at 25/40°C |
| DC/DC converters | 2 | Input range, output voltage/current, derating context |
| Chargers | 2 | AC input, normal/low output current, absorption-mode voltage |

These are source-backed review candidates, not accepted design selections. The
1,056 existing patent publication candidates stay in the separate patent layer.
Neither components nor patents count toward the 2,000-battery milestone.

## One provenance pipeline

```text
components/categories.json                  six electrical categories
components/sources-2026-09-16.json           source URLs, revisions, retrieval evidence
review/batches/YYYY-MM-DD-*.json            reproducible research batches
review/candidates/<manufacturer>/*.yaml     unaccepted product documents
review/index.json                           pending / accepted state
contrib/components/<manufacturer>/*.yaml    accepted components after review
agents/weekly-research/                     research instructions, backlog, reports
patents/                                   existing patent imports and review layer
```

A component uses `kind: component` and `component_type: contactor | fuse |
precharge_contactor | inverter | dc_dc_converter | charger`. Stable identity is
manufacturer plus exact part/configuration, independent of the application. Do
not duplicate a contactor as a second product merely because it can be used for
precharge. Configuration-level Victron entries explicitly leave the regional
plug/outlet SKU unspecified; do not merge them with a later exact SKU without
identity review.

The ordinary contribution schema, quantity registry, duplicate check, issue
approval workflow, PostgreSQL loader and generated accepted web catalog also
handle components. Approval places their files under `contrib/components/`.
`components/catalog.md` displays both accepted and pending components with their
state. Refresh it after any promotion; CI checks it for drift.

In PostgreSQL, component identity is in `bd.product.component_type` (nullable
for existing unclassified BOM items such as BMS units); source,
revision, observation, conditions and provenance reuse the existing tables.
Twelve added quantity codes cover electrical switching/protection and power
conversion. `kA` retains its native unit and converts to amperes in `value_si`.
The observation view exposes component category, AC/DC, interruption test
voltage, conductor description, unstated conditions and extra mode qualifiers.

```sql
SELECT manufacturer, model_number, component_type, quantity,
       value_native, unit_native, electrical_system, test_voltage_v,
       conductor_description, temperature_c, condition_extra, source_url
FROM bd.v_observation
WHERE product_kind = 'component' AND review = 'accepted';
```

This query returns no component records until candidates are approved and loaded.
Schema SQL files are used for fresh installations and disposable CI databases.
An existing deployed database needs an additive migration before the updated
loader is used; `tools/build_db.sh` drops and recreates its target database.

## Evidence and review limits

- Eight official manufacturer datasheets support the initial batch. The TE PDF and three Victron
  PDFs were downloaded and hashed. Four Sensata/Littelfuse documents were
  readable through web retrieval but direct byte retrieval was unavailable; their
  records explicitly omit the hash. Source revisions remain literal when the date
  format is ambiguous. Availability is not inferred from a historical datasheet.
- TE EV200AAANA has a 9–36 V coil; its contact-circuit rating is separate. GV200
  headline current is not imported as a precisely conditioned carry-current value.
- P195 operating voltage is not its switching-voltage limit. GV211BAX carries
  different continuous currents for 8 AWG and 4 AWG conductors; both are retained.
- The 125 A Littelfuse 25EV1K variant is rated at 900 V DC. The 70/100 A variants
  are rated at 1,000 V DC. Nameplate current is separate from allowable load current.
- Inverter watts remain watts; the VA product name is not converted into watts.
  Charger voltage is tied to the normal absorption stage, not treated as a
  universal output or a battery-specific charging recommendation.

The [weekly agent](../agents/weekly-research/AGENT.md) searches patents and all six
component categories on Mondays at 09:00 Europe/Brussels, through a Codex task
heartbeat. New findings go to review with a dated report and duplicate checks.
