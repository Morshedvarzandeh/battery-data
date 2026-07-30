# Ingestion and contribution

Four inbound paths. All of them land in `bd_stage` and none writes to `bd.*`
directly.

```
  datasheet PDFs ──┐
  papers/datasets ─┼──► bd_stage.ingest_job ──► candidate ──► validate ──►
  cycler files ────┤                                            │
  contrib/*.yaml ──┘                                            ▼
                                              review_queue ──► promote ──► bd.*
```

## Why staging is not optional

LLM extraction from datasheets and papers has one dominant failure mode: output
that is fluent, plausible, and wrong. No amount of prompt engineering removes
it. What removes it is making every value cheap to check — a page, a table, a
bounding box, a quoted sentence — and putting a human in front of the ones most
likely to be wrong.

`bd_stage.validate_candidate()` runs first, mechanically:

- a locator exists (quote, page or section) — no evidence, no record
- the quantity code is known
- every `required_conditions` entry is present or explicitly `unstated`
- the unit converts
- **the SI value is physically plausible** — this catches the single most common
  LLM error, the mAh/Ah scale slip

`bd_stage.detect_conflicts()` then compares against accepted data. A candidate
disagreeing by >2% is not an error; it is the most interesting thing the run
produced, and it goes to the top of the queue.

## Review prioritisation

`bd_stage.review_queue` orders by expected value of the review, because reviewer
attention is the bottleneck:

```
priority = 100 × has_conflict
         +  40 × has_validation_warning
         +  30 × (confidence < 0.75)
         +  20 × quantity_has_no_coverage_yet
```

`bd_stage.agent_accuracy` turns reviewer decisions into a per-prompt-version
scoreboard. Watch `mean_conf_rejected` against `mean_conf_accepted`: if they
converge, the confidence signal has stopped being informative and the whole
prioritisation is running blind.

## Community contributions

Versioned YAML in `contrib/`, validated in CI against `json-schema/`. Example:
`contrib/cells/samsung-sdi/inr21700-50e.yaml`.

The format mirrors the database: observations carry conditions and a locator, or
they fail validation in the pull request rather than after merge.

```yaml
observations:
  - quantity: capacity
    statistic: standard
    value: 4900
    unit: mAh
    conditions:
      temperature_c: 25
      rate_value: 0.2
      rate_unit: C
      rate_reference_capacity_ah: 4.9
      voltage_lower_v: 2.5
    locator:
      page: 3
      quote: "Standard Discharge Capacity 4900 mAh (0.2C, 2.5V cut-off)"
```

A contributor cannot submit a capacity without a rate. This is the point.

## Cycler file adapters

| Format | Parser | Trap |
|---|---|---|
| Arbin `.res` | `galvani`, `cellpy` | MS Access DB; OLE automation dates |
| Maccor `.txt` | `maccorcyclingdata`, BEEP | ISO-8859-1; units vary per export; sign is a user setting |
| Neware `.nda`/`.ndax` | `NewareNDA`, `fastnda` | mA/mAh not A/Ah; three cycle-count modes |
| BioLogic `.mpr`/`.mpt` | `galvani`, `eclabfiles`, `yadg` | Many `.mpt` columns are computed at export and absent from `.mpr` |
| BasyTec / Digatron / Landt / PEC | `battery-data-standard`, DATTES | PEC ships an Oracle backend |
| BDF | `batterydf` | — |

Every adapter must record `source_encoding`, `parser_name`, `parser_version`,
and the three conventions (§1–3 of `docs/02-conventions.md`) on the `test_run`.
