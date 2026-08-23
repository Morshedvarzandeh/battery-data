## What this changes

<!-- One or two sentences. If it adds cells, say which and where they came from. -->

## Source

<!-- For data: manufacturer, model, and the document URL each value came from.
     For code: skip this. -->

- Document:
- Retrieved:

## Checks

<!-- CI runs these too; running them locally first saves a round trip. -->

- [ ] `python tools/validate_contrib.py contrib/` passes
- [ ] `python tools/check_duplicates.py` passes
- [ ] Every value carries a page-level citation and a quote that actually supports it
- [ ] Conditions the source does not state are recorded in `unstated`, not guessed
- [ ] No datasheet PDF is committed — facts plus URL, hash and retrieval date only

## Contribution terms

- [ ] Every commit is signed off (`git commit -s`), which certifies both the
      [DCO](../blob/main/DCO) and the contribution licence in
      [CONTRIBUTING.md §2](../blob/main/CONTRIBUTING.md#2-contribution-licence).
- [ ] I have the right to submit this. It is not covered by an NDA, a customer
      confidentiality agreement, or an employment agreement that would prevent it.
- [ ] I have not reproduced a copyrighted table, chart or block of text wholesale
      from a datasheet, standard, paper or paywalled database. Extracted facts
      with citations are what this project stores; copied expression is not.

<!--
  §2 in short: you keep your copyright and may use your own work however you
  like. You grant a sub-licensable licence, which is what lets contributed rows
  be served through the paid API that funds the curation. §3 sets out what
  contributors get back, including free API access. Ask before you submit if
  anything there is unclear — legal@YOURDOMAIN.example.
-->
