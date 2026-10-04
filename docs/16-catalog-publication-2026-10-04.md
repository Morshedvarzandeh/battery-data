# Reviewed catalog publication — 4 October 2026

Published **1,284 additional battery models and 152 electrical components** into
the accepted library. The public catalog now contains **3,454 battery products**
and **152 components**, counted separately. There are **110 pending battery
records** and no pending components from these batches.

The owner had authorized accepting correct, nonduplicate records. Merging the
research PRs had left the files in the review queue. This publication completes
the acceptance step, moves the approved files into `contrib/`, and regenerates
the manufacturer indexes, component catalog and web data.

## Published records

| Research batch | Battery models published | Components published | Holds |
|---|---:|---:|---:|
| LiPol catalog expansion | 1,256 | 0 | 0 from the proposed candidates |
| Sodium-ion, semi-solid and lithium expansion | 28 | 0 | 4 |
| Original electrical components | 0 | 13 | 0 |
| Battery fuses and precharge resistors | 0 | 133 | 0 |
| 4 October electrical components | 0 | 6 | 0 |
| **Total published now** | **1,284** | **152** | **4** |

The battery additions include four HiNa sodium-ion models, eight final WeLion
semi-solid reference specifications, eight LG models, three EVE LFP models,
one CATL model and four CALB manufacturer launch/showcase records. CALB public
capacity-based names remain labelled as such; no orderable part numbers or
unreported chemistry are invented.

The [machine-readable acceptance audit](../review/audits/2026-10-04-catalog-acceptance.json)
records one decision per reviewed product, source identity, record hash and the
accepted file path. Accepted records no longer have duplicate candidate files or
pending issue payloads. Earlier excluded LiPol rows and unsupported resistor
ordering codes remain outside the candidate and accepted counts.

## What acceptance means

Acceptance confirms that the recorded claims and identity passed source,
structure and duplicate review. It is not independent laboratory verification
or approval of a particular design. Manufacturer claims, catalog specifications
and launch announcements retain their source type and limitations.

Missing temperature, rate, cutoff, dimensional scope or other test conditions
remain explicitly unstated. Supported fields can be published without inventing
the missing fields. Original units, bounds, conditions, revisions, source links
and page/section locators remain attached to the observations.

Mersen NH gBat records now use the visually checked **DS-NHGBATF-15-1026_EN**
datasheet. All 50 identities and part-table rows were reconciled. The current
size-specific interruption ratings and the L/R upper bound replace the older
UL-specific overview; 16 newly supported interruption observations bring the
component library to **818 observations**. The audit retains the previous source
metadata so the revision change is traceable without mixing the two revisions.

## Remaining holds

| Record | Concrete reason |
|---|---|
| CATL 587 Ah LFP ESS cell | Brochure and store screenshot disagree on mass/dimensions; exact variant mapping is unresolved. |
| CALB L173F314 | The supplied regulatory appendix is watermarked DRAFT; final supporting evidence is needed. |
| WeLion SHP350-30-TRIAL | Explicitly preliminary trial specifications. |
| WeLion SHP350-40-TRIAL | Explicitly preliminary trial specifications. |

The [earlier acceptance audit](../review/audits/2026-09-16-catalog-review.json)
contains the specific reasons for the other 106 holds, including source
ambiguities and unresolved identities. Those decisions are unchanged.

## Published outputs

- [Battery manufacturer catalog](../catalog/README.md)
- [Electrical component catalog](../components/catalog.md)
- [Accepted battery records](../contrib/cells/)
- [Accepted component records](../contrib/components/)
- [Current cell research set](15-current-cell-research-set.md): 25 accepted and
  15 pending entries, each with its own status and working record link.

`tools/export_catalog_snapshot.py` exports all accepted records, including these
additions, for API ingestion. The hosted Lemonergy API has a separate deployment;
this repository publication does not claim that deployment has been refreshed.

Validation covers accepted and held schemas, duplicate checks, reproducible
imports, record/audit hashes, generated indexes, web display and the accepted-data
snapshot. CI also exercises database loading and confirms that reloading an
accepted chemistry record does not duplicate its observations.
