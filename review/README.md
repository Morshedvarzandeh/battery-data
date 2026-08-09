# Candidate review queue

Files under `review/candidates/` are **not accepted battery data**. They are
source-backed proposals waiting for a human decision.

Every candidate has one GitHub issue containing:

- the product type and source revision;
- every proposed value, unit, condition, and exact source excerpt;
- one owner-only approval checkbox;
- a hidden, path-safe link to exactly one candidate file.

When the repository owner checks **Approve this battery for the accepted
library**, `.github/workflows/approve-candidate.yml` validates the candidate,
moves it into `contrib/cells/`, rebuilds the public catalog, commits the change,
and closes the issue. A failed validation leaves the issue open and the product
outside the accepted library.

The workflow is serialised so two quick approvals cannot overwrite each other.
It does not use a model API, and it does not read any model API secret.

`tools/build_review_batch.py` deterministically rebuilds every candidate file
and `index.json`. `tools/render_review_issues.py` produces the matching issue
payloads. `tools/validate_review.py` is a dependency-free preflight; CI also
runs the full contribution validator after promotion.

## Where a candidate is declared

Two kinds of declaration feed the builder, and both are checked in:

| Declaration | Emitted by | Covers |
|---|---|---|
| Python builders in `tools/build_review_batch.py` | the six manufacturer functions | the 2026-08-06 batch |
| JSON files in `review/batches/` | `recovered()` | candidates re-derived from their issues |

The second kind exists because the research process opens `[candidate]` issues
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
