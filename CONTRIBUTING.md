<!--
  Section 2 is the legally operative part: it is what allows a contributed row
  to be served through the paid API. [LEGAL ENTITY] is still blank there.
  Not reviewed by a lawyer. Have one read it before you rely on it.
-->

# Contributing

Thank you — genuinely. This project is trying to become the largest well-formed
battery dataset in existence, and that is not a thing one person can do.

Two things before anything else, because both are easier to know now than to
discover later.

**The rule.** A value without its conditions is not accepted. Not
discouraged — refused, by a database constraint, in CI. A capacity with no rate,
no temperature and no cutoff voltage is not data about a cell; it is a number
that looks like data. If you take nothing else from this file, take that.

**The bargain.** This project publishes an open repository and sells a hosted
API over a larger curated corpus. Your contribution may end up in that paid
corpus. §2 sets out exactly what you grant and exactly what you keep, and §3 sets
out what you get back. Read §2 before you open a pull request. If the trade is
not acceptable to you, don't contribute — that is a fair decision and this
document exists so you can make it with the facts.

---

## 1. What a contribution looks like

### Cell data

One YAML file per product, under `contrib/cells/<manufacturer>/<model>.yaml`.
Copy `contrib/cells/samsung-sdi/inr21700-50e.yaml` and work from it.

```bash
python tools/validate_contrib.py contrib/
python tools/check_duplicates.py
```

CI runs both. `validate_contrib.py` refuses a value whose conditions are missing;
`check_duplicates.py` refuses a cell already in the library under a different
alias, and refuses two files that claim different specifications for the same
identifier.

Three things the validator cares about that are easy to get wrong:

- **Every value needs a citation** — a page and a quote from the source document.
  Not a URL for the document as a whole; the place on the page where the number
  actually appears.
- **Conditions the source does not state go in `unstated`, not in a guess.**
  Samsung publishes a 14,700 mA pulse rating and never gives the duration.
  Recording "the document does not say" is required; inventing 10 s is a defect.
  This is the third state between recorded and missing, and it only works if
  people use it honestly.
- **The manufacturer is who made the cell**, not who published the document. A
  test laboratory's report is not evidence the laboratory built the cell.

You can also submit a datasheet without doing the extraction yourself: open a
[datasheet issue](../../issues/new?template=datasheet.yml). A maintainer runs the
extraction; a human reviews it before anything is accepted. See
[`docs/06-submitting-a-datasheet.md`](docs/06-submitting-a-datasheet.md).

### Code

Ordinary pull request. Keep to the surrounding style. `python -m unittest
discover -s tests -p 'test_*.py'`, `python tools/cyclers.py selftest` and
`python api/filter_grammar.py` all run in CI and should pass locally first.

### The one hard prohibition

**Do not commit manufacturer datasheet PDFs.** Store the extracted facts plus a
URL, a content hash and a retrieval date — the schema has fields for all three,
and `source.redistributable` controls whether a document body may be stored at
all. Kept this way, a takedown request is a per-source problem rather than a
project-ending one. A committed PDF makes it the latter.

---

## 2. Contribution licence

**This is the part that has legal effect. By submitting a contribution you agree
to it.**

### 2.1 You keep your copyright

There is no copyright assignment here and there will not be one. You continue to
own everything you contribute. You may use, publish, relicense or sell your own
contribution however you like, including contributing the same work to a
competing project. Nothing in this section takes anything away from you.

### 2.2 What you grant

You grant the Licensor ([LEGAL ENTITY], and its successors in the business) a
**perpetual, worldwide, non-exclusive, royalty-free, irrevocable, transferable
licence, with the right to sub-license through multiple tiers**, to:

reproduce, store, adapt, translate, restructure, combine with other material,
publicly display and perform, distribute, communicate to the public, and
**commercially exploit** your contribution and derivative works of it, in any
medium and by any means now known or later devised, **including by serving it
through a paid API, a paid data feed, and a bulk data licence**.

The grant covers copyright, sui generis database rights, and any other rights you
hold in the contribution that are needed to do those things. You also grant a
patent licence on the same terms, limited to your patent claims that the
contribution necessarily infringes.

### 2.3 Why the grant has to be this broad

An honest explanation, because a broad grant with no reason attached deserves
suspicion.

Curation is the expensive part of this project — verifying a value, chasing the
conditions a datasheet omits, reconciling an AC resistance of 15 mΩ against a DC
resistance of 23 mΩ for the same cell. That work is funded by selling API access.
If contributed rows could not lawfully reach paying customers, then either they
sit in the repository unfunded, or the corpus splits into "rows we may sell" and
"rows we may not" — which is an unmaintainable distinction that would end with
contributions being declined.

**Sub-licensable** is the specific word doing the work: without it, the Licensor
could publish your row but could not pass a usable right to a subscriber.
**Irrevocable** is the other one: a corpus that can have rows withdrawn from it
retroactively cannot be sold to anyone, because no subscriber can build on data
that might vanish. Neither word is there to be clever at your expense.

### 2.4 How your contribution is published

Accepted contributions are published in this repository under the licence for
their part of the tree — **CC-BY-4.0** for data and documentation,
**AGPL-3.0-or-later** for code — as set out in [`LICENSING.md`](LICENSING.md).
That grant to the public is separate from, and additional to, §2.2. It is also
irreversible in practice: once published under CC-BY-4.0, that version stays
available under CC-BY-4.0 to everyone who received it.

You are credited. Provenance rows carry the contributor, and the git history is
the record.

### 2.5 What you promise

You represent that:

**(a)** you have the right to make this contribution and to grant §2.2;

**(b)** the contribution does not knowingly infringe anyone's copyright, database
right, patent, trade secret or contractual right;

**(c)** it is **not** subject to an NDA, a customer confidentiality agreement, or
an employment or contractor agreement that would prevent you from submitting it —
if your employer owns your work product, get their permission first;

**(d)** you have **not** reproduced a copyrighted table, chart or block of text
wholesale from a datasheet, standard, paper or paywalled database. Extracting the
*facts* a public document states, with a citation, is what this project does.
Copying the document's *expression* is not, and it is the thing most likely to
cause real trouble;

**(e)** the source is what you say it is, and you retrieved it from where you say
you did.

If you later discover any of this was wrong, tell us at
legal@lemonergy.com. Reporting your own mistake is treated as good faith.
Concealing one is not.

### 2.6 On facts, honestly

Much of what you contribute will be **facts** — "4900 mAh at 0.2 C to 2.5 V" is a
property of a Samsung cell, and in the United States facts are not copyrightable
at all (*Feist v. Rural Telephone*). Where that is so, §2.2 grants little,
because there is little to grant.

It is written broadly anyway, for the parts where rights **do** subsist: your
selection and arrangement, your review notes and qualifications, your structuring
of the record, and the sui generis database right that may arise in the
extraction work itself in the EU and UK. Rather than assert that your facts are
owned and licensed to us — which would be untrue — this section takes a licence
to whatever rights actually exist and says plainly that it may not be many.

The corresponding honesty in the other direction: your warranty in §2.5(d) is the
clause that matters most to this project, far more than the grant. The risk here
was never that someone contributes a fact. It is that someone pastes in a
copyrighted table.

### 2.7 No obligation

Submitting does not oblige anyone to accept. Contributions are reviewed and may
be declined, edited, restructured, or corrected. A declined contribution is not
used.

### 2.8 No warranty from you

Your contribution is provided as is. Beyond §2.5, you give no warranty and take
no liability for it.

---

## 3. What contributors get

A project that sells contributed work while charging its contributors to see it
would deserve to fail. So:

| You contributed | You get |
|---|---|
| Any accepted contribution | Free read access to the full corpus API, for personal and academic use, for as long as the service runs |
| **10+** accepted cells | Free commercial-tier API access for you or your employer, renewed annually while you remain active |
| **50+** accepted cells, or a merged adapter, parser or schema extension | Permanent free commercial-tier access, no renewal condition |
| A datasheet issue that a maintainer extracts and accepts | Counts as an accepted cell |
| An accepted correction to an existing record | Counts, and is the most valuable kind |

Corrections count deliberately. Finding that a stored value is wrong is worth more
to a database whose entire claim is provenance than adding another row is, and it
is the contribution most projects fail to reward.

Academic and standards-body use of the corpus is free regardless of whether you
have contributed. Write to licensing@lemonergy.com and say which you are.

Claim access at licensing@lemonergy.com with a link to your merged work.

---

## 4. Sign-off

Every commit must carry a `Signed-off-by` line:

```bash
git commit -s -m "Add EVE LF280K"
```

which appends:

```
Signed-off-by: Your Name <your@email.example>
```

That line certifies **both**:

1. the [Developer Certificate of Origin 1.1](DCO) — the standard open-source
   statement that you wrote this or have the right to pass it on; and
2. the contribution licence in **§2** of this file.

Use your real name. Set `user.name` and `user.email` in git once and `-s` handles
it forever.

Missing the sign-off is a fixable mistake, not a rejection — CI will tell you, and
`git commit --amend -s` fixes the last commit.

---

## 5. Review

1. CI runs the validators, the duplicate check, the schema tests and the
   generated-file staleness checks.
2. A maintainer reviews the extraction against the source document. The two
   things that go wrong most often are a quote that does not actually support the
   value claimed, and a condition marked `unstated` that is in fact printed on the
   page. Those are what review is looking for.
3. On acceptance the file lands in `contrib/`, `load_contrib.py` brings it into
   `bd.*`, and it appears in the coverage page on the next build.

Nothing enters the database unreviewed. That is a structural property of the
pipeline, not a promise about diligence.

---

## 6. Where help is most wanted

The coverage page (`web/index.html`) shows what is missing. The gaps that matter
most right now:

- **EV prismatic LFP** — CATL Shenxing, BYD Blade, EVE LF280K, Gotion L600
- **ESS prismatic LFP** in the 280–320 Ah class
- **4680-format cells** — the format the industry is retooling for
- **Corrections to anything already in the library**

---

## 7. Questions

Open an issue. Licensing questions that you would rather not ask in public go to
legal@lemonergy.com, and asking before you contribute is always better than
asking afterwards.
