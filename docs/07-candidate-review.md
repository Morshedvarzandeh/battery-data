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

## Paid extraction boundary

Opening, labelling, editing, or approving an issue cannot invoke a paid model.
`submit-datasheet.yml` runs only from a manual workflow dispatch with the
`allow_paid_api` checkbox explicitly enabled. A stored API key by itself is
insufficient.
