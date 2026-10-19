# Reviewed data publication — 20 October 2026

The owner's request to review and publish the final data accepts **two Schaltbau
C310A configurations** from PR 504. The accepted library contains **3,455 battery
products and 178 electrical components**, including 24 BMS records. These are
separate counts; components do not inflate battery totals.

## Review result

- C310A/300 and C310A/500 are published as configurations with coil and auxiliary
  options unspecified. They are not fully specified ordering codes.
- The manufacturer page supports 1,000 V operating voltage and conditioned
  conventional thermal currents of 300 A (185 mm², 70°C) and 500 A (2 × 150 mm²,
  40°C). The temperature reference remains unstated. Numerical observations
  are unchanged from the reviewed candidates.
- The separate feature paragraph naming C360 conflicts with the C310 table;
  that paragraph is excluded and the discrepancy remains recorded.
- The two records carry source-retrieval and lifecycle-review dates, current
  manufacturer-listing evidence and an explicit unknown release date.
- There are no exact or probable duplicates. Three Renata identity collisions
  remain within the held candidates, with conflicting capacities.

The [acceptance audit](../review/audits/2026-10-20-final-publication.json) records
original candidate and accepted-record hashes, the specific authorization,
limitations and all 110 retained battery holds. Existing accepted records are
unchanged. This publication is not a fresh source verification of every
historical catalog entry.

## Retained holds

All **110 battery candidates** retain their previous source/identity decisions.
No new evidence resolves them in this publication. The audit links the previous
per-record decisions and freezes the unchanged candidate hashes. The CATL 587 Ah
variant conflict, draft CALB L173F314 evidence and preliminary WeLion trial cells
remain outside the accepted catalog. No component candidates remain pending.

## Dates and access

The [date coverage and technology timeline](../catalog/dates.md) applies the
shared date structure to every accepted product and keeps the 11 scoped
technology milestones separate. Missing release dates remain unknown. Datasheet
editions, retrieval dates, commercial releases and roadmap targets are not
interchangeable.

Public outputs are the [battery indexes](../catalog/README.md),
[component catalog](../components/catalog.md), [BMS comparison](../components/bms.md)
and generated web catalog. The accepted-only snapshot carries the same dates,
observations, units, conditions and provenance for Lemonergy API ingestion.

Validation: all accepted and pending contribution schemas, the deterministic
review queue, duplicate checks, acceptance/hold hashes, 109 Python regression
tests, and browser sheet/Markdown checks. GitHub CI also validates the disposable
database and generated views before merge. Hosted publication is verified
separately; a data-repository merge alone does not refresh Lemonergy's server.
