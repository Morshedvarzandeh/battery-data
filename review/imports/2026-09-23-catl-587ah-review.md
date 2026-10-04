# CATL 587 Ah: September 23 source review

The [user-submitted post](https://lnkd.in/p/edS7ZNYh) concerns CATL's 587 Ah LFP
storage cell. This product already exists in the current-cell research set.
Added one [dated source revision](../revisions/catl/587ah-lfp-ess-cell-mall-2026-09-23.yaml),
linked to the same product UID; no duplicate product was created.

Status: **pending source/revision verification**. The new observations were read
from the store screenshot attached to the post. The live product listing could
not be verified, and the screenshot does not provide an exact part number.
The manufacturer brochure record remains separate and unchanged in its values.

| Property | September screenshot | Earlier record / limitation |
|---|---:|---|
| Capacity | 587 Ah nominal | Brochure: 587 Ah rated; test conditions unstated |
| Nominal voltage | 3.2 V | Not added to the earlier brochure record |
| Listed energy | 1.8784 kWh | Equals nominal voltage × capacity; not measured usable energy |
| Dimensions, source L × W × H | 73.05 × 310 × 221.53 mm | Source axis order preserved |
| Mass | 10.6 ± 0.3 kg | Brochure candidate: 9.83 kg; unresolved variant relationship |
| Listed energy density | 379 Wh/L | Volume and test basis unstated |
| Cycle life | 8,000 cycles at 25 °C, 70% SOH, 0.5P/0.5P | DOD and SOH definition unstated; screenshot does not show ≥ |

The image specifies **0.5P**, a power rate. It must not be transcribed as 0.5C
or treated as a maximum current rating. General charge/discharge rate text is
not assumed to describe the capacity-test protocol.

## Arithmetic check

External rectangular volume is 5.016658 L. Listed nominal energy divided by
this volume is **374.43 Wh/L**, about 1.2% below the screenshot's
379 Wh/L. Using the post's earlier dimensions gives 4.374983 L, a
14.67% increase in external volume and a
12.79% decrease in density at constant energy.
These are calculations, not additional manufacturer observations.

The post's claim of approximately 0.64 L of empty internal space does not follow
from that arithmetic. Internal geometry, electrode loading and inactive material
volume are unknown. Sodium-ion shell sharing and chemistry-upgrade explanations
remain hypotheses and were excluded from the cell specifications.

## Evidence and disposition

- [CATL's June 10, 2025 announcement](https://www.catl.com/news/8537.html)
  confirms a 587 Ah LFP product and a historical 434 Wh/L claim. It does not map
  that announcement to the September screenshot's larger case.
- The [earlier candidate](../candidates/catl/587ah-lfp-ess-cell.yaml) retains the
  brochure's 9.83 kg and ≥8,000-cycle observations. Its PDF was previously
  inspected on September 21; a fresh fetch returned HTML, so no new PDF
  verification is claimed.
- The new source is explicitly classified as a user submission containing a
  reproduced store screenshot. Post and screenshot hashes are in the
  [machine-readable review](2026-09-23-catl-587ah-review.json).
- Price tiers of 0.415–0.435 CNY/Wh remain a dated commercial note, not an
  independently verified current quote.

Acceptance needs a manufacturer product URL or datasheet identifying this
variant and resolving its relationship to the earlier record. The source
revision is available for review; it is not included in accepted API exports.
