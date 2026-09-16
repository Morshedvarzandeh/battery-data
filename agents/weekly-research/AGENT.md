# Weekly battery patents and electrical components research

## Purpose and schedule

Maintain this repository's patent research and electrical component library. The
owner requested patents **and all six component categories**. The Codex task
heartbeat `weekly-battery-patents-and-components` runs Mondays at 09:00 in
Europe/Brussels. Its schedule lives in Codex; this file is its working contract.
Do not create a second schedule or paid service. Local automation requires the
Codex application and this checkout to be available.

## Each run

1. Read repository instructions, this file, `components/README.md`, the source
   backlog, the latest dated report, and current Git status. Preserve unrelated
   edits. Start a `codex/` branch for new research. Inspect open PRs for overlapping
   work, especially patent intelligence PR #460; reuse its implementation if merged.
2. Inspect accepted and pending records before research. Count battery kinds,
   electrical components, patent publications and patent families separately.
3. Check all six category backlogs for new manufacturer datasheets or revisions;
   rotate deeper research across manufacturers. Prefer a small verified batch to
   filling a quota. Default ceiling: 20 new component models and 20 new patent
   publication candidates per run. Record categories searched even with no results.
4. For patents, use a date-bounded search since the last successful run with a
   seven-day overlap, then deduplicate. Prefer EPO, WIPO and national patent-office
   records. Record searched dates, jurisdiction and search terms. Publication
   identity includes country, number and kind code; revisions of one publication
   are not new inventions. Resolve DOCDB or equivalent family identifiers from
   evidence, retain priority/applicant provenance, and distinguish an applicant
   from current ownership. Do not infer legal status or validity. This task is
   technical research, not a freedom-to-operate opinion.
5. For components, use official manufacturer datasheets and product pages. Capture
   exact orderable part or a clearly scoped configuration, category, source URL,
   revision, retrieval date, byte hash when retrievable, and a page/section locator
   for every observation. Preserve native units, bounds, qualifiers, operating
   modes and required conditions; explicitly name missing conditions as unstated.
   Do not copy family headline ratings onto incompatible variants. Keep contact
   voltage separate from coil voltage, carry current from breaking current, fuse
   nameplate current from allowable current, and inverter watts from volt-amperes.
6. Check canonical manufacturer/model identity, aliases and existing revisions in
   both accepted and pending queues. A precharge role is a use of a contactor:
   never create two products for the same part merely to list it in two categories.
   Retain conflicts and source changes for review without overwriting accepted
   facts. Do not fabricate facts or skip rows to reach a count.
7. Add components as deterministic `review/batches/YYYY-MM-DD-*.json` documents;
   rebuild the normal review queue. They use `kind: component`, one of the six
   `component_type` values and `component/<manufacturer>/<model>` identities.
   Reuse the existing patent import, taxonomy, validation and review directories.
   Do not put unreviewed patents into accepted tables or invent a parallel store.
   Raw proprietary PDF bodies stay outside Git; commit facts and provenance.
8. Run applicable checks below. Create/update a reviewable PR with counts, evidence,
   exclusions, unresolved questions and tests. Future research additions remain
   pending until reviewed under the repository's approval policy. Prior permission
   to accept the September battery batch is not blanket approval of future claims.
9. Update `source-backlog.json` and write `reports/YYYY-MM-DD.md`. Record attempted
   and successful checks, duplicates, missing hashes, failures and next sources.
   Stay quiet when nothing actionable changed. Notify only for meaningful verified
   additions/revisions, milestones, failure or required user action.

## Existing patent pipeline

`patents/` contains CORDIS and EPO imports, staging and taxonomy. The baseline is
1,056 deduplicated publication candidates, 383 organisation profiles and 856
applicant links; no accepted patent publications. Reconcile live counts each run.
Use `tools/validate_patents.py`, `tools/validate_epo_patents.py` and
`tools/check_patent_duplicates.py --fail-on exact`.

`tools/fetch_epo_linked_patents.py` is a bounded IPC-shard fetch, **not** a
last-week search. Its results must not be described as complete weekly coverage.
PR #460 adds a date-bounded patent-agent plan and review workflow. It was open at
setup. Its paid BigQuery path requires explicit budget authorization. Do not run
paid queries, billed LLM extraction or new subscriptions without authorization.
If access fails, report the concrete missing access and continue other sources.

## Component checks

```bash
python tools/build_review_batch.py
python tools/render_review_issues.py
python tools/build_component_catalog.py
python tools/validate_contrib.py contrib/
python tools/validate_contrib.py review/candidates/
python tools/validate_review.py
python tools/check_duplicates.py
python tools/build_web_data.py
python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Accepted components eventually live under `contrib/components/` and use the same
PostgreSQL product/source/revision/observation/condition/provenance tables. Never
run the destructive database rebuild script against a live database. CI exercises
an isolated disposable database. Components and patents never count toward the
2,000-battery milestone.
