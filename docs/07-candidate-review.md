# One-click candidate review

The customer catalog and the technical review queue have different publication
boundaries:

| Layer | Audience | Contents |
|---|---|---|
| Customer catalog | Public | Accepted, source-backed products only |
| Technical workspace | Signed-in reviewer | Pending candidates, revisions, conditions, curves, test coverage, datasets and provenance |
| Relational library | Backend | Accepted revisions and claims |
| Knowledge graph | Backend projection | Trace paths derived from the accepted relational library |

## Approval flow

1. Research creates one file in `review/candidates/` and one GitHub issue.
2. The issue shows all proposed claims and their evidence.
3. A reviewer comments if correction is needed; the approval box remains empty.
4. The repository owner checks the approval box when the record is correct.
5. GitHub Actions revalidates the exact file referenced by the issue.
6. The file moves to `contrib/cells/`, the public catalog is rebuilt, and the
   issue closes only after the commit succeeds.

The issue editor is treated as a security boundary: only
`github.repository_owner` can operate the checkbox. Candidate paths are parsed
as data, restricted to `review/candidates/`, resolved before use, and never
interpolated from untrusted issue text into a shell command.

A refusal is quoted back onto the issue. Checking the box and getting a red
cross with only a link to a run log tells the owner nothing about which of the
refusals they hit, and the two that read alike are worth telling apart: a path
that escapes the review queue is an attack, while a path with no file behind it
is an issue that outlived its candidate. Only the second is fixable, by
`tools/recover_issue_candidates.py`.

## When the issue is the only surviving copy

Step 1 can fail silently: an issue gets opened and its candidate file never
reaches the default branch. The issue then shows a full table of reviewable
claims that no approval can act on.

`tools/recover_issue_candidates.py` rebuilds those declarations from the issue
bodies into `review/batches/`, which `tools/build_review_batch.py` emits like
any other batch. The rendered issue is a lossy view of the extraction behind
it — no `statistic`, no page numbers — so a recovered record is weaker than a
freshly extracted one and says so in `source.note`. Re-extracting from the
datasheet through `submit-datasheet.yml` is the way to get those fields back,
and it costs an API call per product.

## Paid extraction boundary

Opening, labelling, editing, or approving an issue cannot invoke a paid model.
`submit-datasheet.yml` runs only from a manual workflow dispatch with the
`allow_paid_api` checkbox explicitly enabled. A stored API key by itself is
insufficient.
