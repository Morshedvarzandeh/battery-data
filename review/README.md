# Candidate review queue

Files under `review/candidates/` are **not accepted battery data**. They are
source-backed proposals waiting for a human decision.

Every candidate has a generated review payload. When posted as a GitHub issue,
it contains:

- the product type and source revision;
- every proposed value, unit, condition, and source locator excerpt, with any
  normalized table transcription disclosed in the source notes;
- one owner-only approval checkbox;
- a hidden, path-safe link to exactly one candidate file.

The [21 September LiPol batch](../docs/14-lipol-expansion-2026-09-21.md) adds
1,256 candidates with a complete source-row reconciliation. It is available for
batch review through its files and pull request; generating payloads does not
automatically open individual issues or accept records.

The [sodium-ion, semi-solid and lithium cell batch](imports/2026-09-21-sodium-semisolid-lithium-cells.md)
adds 32 further cell candidates from HiNa, WeLion, LG, EVE, CATL and CALB.
Its manifest records source hashes, omitted ambiguous fields and existing
identities excluded from the new count. Trial and announcement evidence stays
explicitly qualified.

When the repository owner checks **Approve this battery for the accepted
library**, `.github/workflows/approve-candidate.yml` validates the candidate,
moves it into `contrib/cells/`, rebuilds the public catalog, commits the change,
and closes the issue. A failed validation leaves the issue open and the product
outside the accepted library.

The workflow is serialised so two quick approvals cannot overwrite each other.
It does not use a model API, and it does not read any model API secret.

`tools/build_review_batch.py` deterministically rebuilds every candidate file
and `index.json`. `tools/render_review_issues.py` produces the matching issue
payloads; use `--unmapped-only` when opening issues for a new batch so existing
pending candidates are not filed again. `tools/validate_review.py` is a
dependency-free preflight; CI also runs the full contribution validator after
promotion. `tools/check_duplicates.py` compares pending and accepted products
using exact UIDs, normalized identities, aliases, sources and key physical
specifications.

## Where a candidate is declared

The declarations feeding the builder are checked in:

| Declaration | Emitted by | Covers |
|---|---|---|
| Python builders in `tools/build_review_batch.py` | the original six manufacturer functions | the 2026-08-06 batch |
| `tools/expansion_aug_2026.py` | Maxell, Panasonic Energy and EEMB tables | the 2026-08-16 152-cell expansion |
| `tools/expansion_catalogs_2026.py` | earlier manufacturer catalog facts | the September catalog review |
| JSON files in `review/batches/` | `recovered()` | issue recoveries and documented import batches |

Issue-recovery declarations exist because the research process opens `[candidate]` issues
without committing their candidate files. Approving such an issue could not
work: the promotion script resolves the path the issue names and finds nothing
there. `tools/recover_issue_candidates.py` reads those issues back out of the
GitHub API and rebuilds each declaration from the rendered body — which is the
same text the owner reviews, so what gets accepted is what was on screen.
`.github/workflows/adopt-candidate.yml` runs it on every newly opened candidate
issue (and on manual dispatch), so an orphaned issue is adopted before anyone
reads it. Issues that fail its shape, vocabulary or registry checks are skipped
with a warning in the run log and stay unapprovable.

Recovery cannot restore what the renderer never printed: the per-value
`statistic` label (rated, typical, minimum, maximum) and `locator.page`. Every
recovered record says so in `source.note`. Where a product listed the same
quantity twice — a minimum and a typical capacity, say — the two rows survive
with their values and their shared quote, but nothing marks which was which.

`review/index.json` stays a pure function of these declarations. CI regenerates
it and fails on any difference, so a hand-edit to a candidate file cannot
quietly become accepted data.
