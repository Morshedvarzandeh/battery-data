# Electrical components

[Browse models and datasheets](catalog.md). As of 4 October 2026, the library has **152 pending
component models / 802 observations** across seven categories, with none accepted.
The [battery-fuse and precharge-resistor batch](../agents/weekly-research/reports/2026-09-21-components.md)
adds 133 models / 712 observations to the initial 13-model batch. The
[4 October batch](../agents/weekly-research/reports/2026-10-04.md) adds six further
models / 28 observations and records source-revision checks.

| Category | Pending models | Key observations |
|---|---:|---|
| Main contactors | 3 | Contact voltage, coil voltage, qualified carry current |
| Fuses | 85 | Rated current/voltage, trigger current, minimum/maximum interruption and circuit conditions |
| Precharge contactors | 3 | Contact and coil voltage, conductor-dependent carry current |
| Precharge resistors | 52 | Resistance/tolerance, mounting-dependent power, qualified pulse energy and voltage limits |
| Inverters | 3 | DC input range, AC output, continuous watts at 25/40°C |
| DC/DC converters | 3 | Input range, output voltage/current, derating context |
| Chargers | 3 | AC input, normal/low output current, absorption-mode voltage |

These are source-backed review candidates, not accepted design selections. The
1,056 existing patent publication candidates stay in the separate patent layer.
Neither components nor patents count toward the 2,000-battery milestone.

## One provenance pipeline

```text
components/categories.json                  seven electrical categories
components/sources-2026-09-16.json           source URLs, revisions, retrieval evidence
review/batches/YYYY-MM-DD-*.json            reproducible research batches
review/candidates/<manufacturer>/*.yaml     unaccepted product documents
review/index.json                           pending / accepted state
contrib/components/<manufacturer>/*.yaml    accepted components after review
agents/weekly-research/                     research instructions, backlog, reports
patents/                                   existing patent imports and review layer
```

A component uses `kind: component` and `component_type: contactor | fuse |
precharge_contactor | precharge_resistor | inverter | dc_dc_converter | charger`. Stable identity is
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
Nineteen dedicated quantity codes cover electrical switching/protection, precharge
resistors and power conversion. `kA` retains its native unit and converts to amperes in `value_si`.
The observation view exposes component category, AC/DC, interruption test
voltage, conductor description, mounting, pulse waveform, recovery wait, unstated
conditions and extra mode qualifiers. `component_case` temperature differs from
ambient; resistor heat dissipation differs from converter output power. Resistance
and tolerance decoded from actual manufacturer-listed ordering codes are labelled
as such and retain the identity-page URL/hash/row. They are not measured values.

```sql
SELECT manufacturer, model_number, component_type, quantity,
       value_native, unit_native, electrical_system, test_voltage_v,
       conductor_description, temperature_c, temperature_reference,
       mounting_condition, pulse_duration_s, pulse_waveform, pulse_wait_s,
       condition_extra, source_url
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
- The September 21 batch uses Sensata GFP400, five Mersen battery-fuse families,
  and Vishay HRHA/LTO150H. Seven PDF bodies and two identity pages were hashed;
  Sensata original bytes and visual verification remain unavailable. Exact source
  versions, parsed rows and five held custom resistor codes are in the
  [import manifest](../review/imports/2026-09-21-battery-fuses-precharge-resistors.json).
- Mersen aBat minimum breaking currents are separate from maximum interruption.
  NH gBat UL ratings vary by size/current; the generic 150 kA headline is not copied
  onto every part. Sensata 400 A continuous, 1500 A trigger, and interruption at
  650/850 V are separate observations. Its 1000 V nameplate does not establish a
  10 kA breaking rating at that voltage.
- HRHA power and energy retain the 6 mm mounting material, 30°C ambient, waveform,
  pulse duration and recovery wait. LTO150H 150 W at 45°C case and 4.5 W in free air
  at 25°C stay separate. Its headline pulse-energy limit is withheld pending
  assessment of the applicable curves. Dielectric withstand is not operating voltage.

The [weekly agent](../agents/weekly-research/AGENT.md) searches patents and all seven
component categories on Mondays at 09:00 Europe/Brussels, through a Codex task
heartbeat. New findings go to review with a dated report and duplicate checks.
