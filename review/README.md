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

`tools/build_review_batch.py` deterministically rebuilds the manufacturer
batch. `tools/render_review_issues.py` produces the matching issue payloads.
`tools/validate_review.py` is a dependency-free preflight; CI also runs the full
contribution validator after promotion.
