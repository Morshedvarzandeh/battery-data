# Product dates and technology generations

[Date coverage and timeline](../catalog/dates.md) · [Battery models](../catalog/README.md) · [Components](../components/catalog.md)

## What each date means

Every battery and electrical component uses the same date view. Dates describe
different facts and must stay separate when comparing products:

| Field | Meaning | What it does not establish |
|---|---|---|
| Announcement / launch | A dated public announcement for a named product, family or generation | First shipment, stock availability or invention of a chemistry |
| Commercial release / volume shipping | The event explicitly described by the source | Availability in every region or of every variant |
| Planned availability | A manufacturer or official distributor's roadmap target | Completed production, even after the target date passes |
| Source document date / revision | The specification edition used for this record | Product launch |
| Specification source retrieved | When that specification source was inspected | A new product, a new edition, or a current stock check |
| Lifecycle checked | When the cited release/status evidence was reviewed | When unrelated electrical ratings were rechecked |
| Discontinuation | A sourced end-of-life event | An inference from an old document or a missing web page |

Dates retain **day, month or year precision**. “Q4 2025” and “early 2023” retain
their original text with `precision: unspecified`; no first-of-month date is
invented. Unknown dates remain empty. Original release evidence has four states:

- `documented`: a dated launch announcement or commercial release with evidence;
- `not_found`: a release review found no date in the checked sources;
- `conflicting`: the cited evidence disagrees;
- `not_researched`: no structured release review is recorded yet (derived view only).

The current catalog has many historical specifications. Uniform date fields do
not mean every release date has been found. The generated coverage table reports
these gaps by product kind and all eight electrical component categories.
Git commit dates, URL timestamps and document filenames are never substituted
for release dates or source checks.

## Technology scope

`technology/milestones.json` contains reviewed events about a **named manufacturer
platform, product family or product**. Each event has a source URL, locator,
retrieval day, precision, scope note and source basis. Original response hashes
are recorded when bytes can be retrieved. Manufacturer pages and an official
distributor roadmap are distinguished. Proprietary source bodies remain outside Git.

This first set contains 11 milestones across sodium-ion, fast-charge LFP,
long-cycle storage cells and semi-solid / fully solid-state roadmaps. It is not
a complete history of these chemistries. In particular:

- CALB's ZHIJIU family event is **2026-04-01**, while the source article is dated
  **2026-04-02**. Neither date is assigned to its unrelated 684Ah cell.
- CATL's Naxtra launch and later full-scale production plan stay separate.
- WeLion's 2026/2028 roadmap targets do not become release dates for SHP270 or
  SHP320 cells. A semi-solid electrolyte does not become all-solid-state.
- HiTHIUM's historical Q4 2025 production target remains a plan until its
  completion has separate evidence. A timeline entry does not accept its pending
  numerical specification candidate.

See the [timeline and individual source links](../catalog/dates.md). Existing
accepted product lifecycle events, including BMS conflicts and legacy releases,
are also listed there directly from their contribution records.

## Data structure and integrations

The existing contribution `lifecycle` object works for **every product kind**,
not only BMS. Use it for new product release/status reviews with evidence.
`source.document_date`, `source.revision` and `source.retrieved_at` retain the
specification provenance. Existing accepted contribution bytes are preserved.

`tools/catalog_dates.py` produces the same derived `dates` view for the generated
web catalog and each record in the read snapshot:

```text
dates.source_document  = status, date, precision
dates.source_revision  = printed revision label or null
dates.source_retrieved = status, date, precision
dates.lifecycle_checked = status, date, precision
dates.release          = status, note, optional sourced event
dates.market_status    = observed state or unknown
dates.events           = original sourced lifecycle events
```

`tools/export_catalog_snapshot.py` keeps `record` unchanged and adds sibling
`dates` metadata to each entry, plus top-level `technology_milestones`. These
are additive fields in snapshot format 1 and are covered by the release digest.
Uncommitted contribution or milestone edits prevent a normal release export.
Milestones do not add accepted products or observations and never implicitly
override a product's release. Pending records remain outside the snapshot.

PostgreSQL already stores the underlying source dates/revisions and product
`lifecycle_evidence`; no database migration is required for this projection.
The separate platform timeline is published as JSON and in the snapshot, not
loaded as product facts into PostgreSQL. Existing hosted API consumers must read
the new snapshot fields before exposing them; this repository change does not
deploy the private Lemonergy API or website.

The web comparison filter explicitly uses **source document year**. Unknown
years sort last in either direction. Product sheets and Markdown downloads show
retrieval and lifecycle-check dates separately. GitHub manufacturer and component
indexes show document date, source retrieval and release-review state.

## Ongoing research and checks

Review release evidence for current sodium-ion, semi-solid, LG, EVE, CATL and CALB
models first, then BMS and the remaining electrical categories. Preserve exact
identity and generation, and retain conflicting evidence for review. A new
source check must not silently overwrite historical measurements or prior plans.
The weekly agent's existing instructions now require these date distinctions
across its component research and any battery research it performs. No new
scheduled task is created.

Patent priority, filing and publication dates remain in the patent layer. They
must not be displayed as product release or technology commercialization dates.

```bash
python tools/build_date_catalog.py
python tools/build_browse_catalog.py
python tools/build_component_catalog.py
python tools/build_web_data.py
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_web_observations.cjs
```

CI validates the dates and source chronology and checks generated views for
drift. The validators reject impossible dates, mismatched precision, observed
events after their evidence check and a document revision used as a release.

Maintained by **Lemonergy** · [Data tools](https://lemonergy.com/data/) · Free data on GitHub.
