<!--
  Open items: the contracting entity, its registered address, the governing law
  and the effective date are still blank in TERMS.md. CI warns until they are
  filled. Find them with:
    grep -rn "\[LEGAL ENTITY\]\|\[REGISTERED ADDRESS\]\|\[GOVERNING LAW\]\|\[COURTS\]\|\[EFFECTIVE DATE\]" .
  This file states a position. It is not legal advice, and it has not been
  reviewed by a lawyer. Have one read it before you take money against it.
-->

# Licensing

This repository is the public, open part of a project whose curated corpus is
sold as a hosted API. Those are two different things under two different sets of
terms, and this document draws the line between them precisely enough to be
relied on.

---

## The short version

| What | Where | Licence | May I sell something built on it? |
|---|---|---|---|
| Code — schema, loaders, adapters, validators, API server | `schema/` `tools/` `api/` `agents/` `tests/` | **AGPL-3.0-or-later** | Yes. Modify it and serve it to others and you owe those users your modifications. |
| Documentation and design notes | `docs/` `*.md` | **CC-BY-4.0** | Yes, with attribution. |
| Standards crosswalk | `crosswalk/` | **CC-BY-4.0** | Yes, with attribution. Deliberately the most permissive thing here. |
| Published sample data | `seed/` `contrib/` `review/` `web/data/` `json-schema/` | **CC-BY-4.0** | Yes, with attribution. This is a sample, not the corpus. |
| **The curated corpus and the hosted API** | **not in this repository** | **Commercial subscription** — [`TERMS.md`](TERMS.md) | Only under a subscription agreement. |

The single sentence that matters: **everything you can see here is genuinely
open; the thing that is sold is not here.**

---

## Why it is split this way, and not some other way

It would be easier to put one licence file at the root and move on. That would
also be wrong, for a reason worth stating plainly.

**Facts are not copyrightable.** In the United States, *Feist v. Rural Telephone*
holds that a compilation of facts attracts copyright only in its selection and
arrangement, and only thinly. "4900 mAh at 0.2 C to 2.5 V" is a fact about a
Samsung cell. No licence this project publishes can stop anyone from repeating
it, and any document claiming otherwise is bluffing — expensively, because a
bluff that gets tested in court is worse than no claim at all.

So the protection this project actually relies on is not a data licence. It is
four other things, in descending order of strength:

1. **Contract.** Every API subscriber agrees to [`TERMS.md`](TERMS.md) before
   receiving a key. Contract binds regardless of whether the underlying material
   is copyrightable, which is exactly why it is the primary instrument here.
2. **The sui generis database right** (EU and UK). This one *does* protect a
   factual compilation as such — see below. It is the reason the corpus is worth
   defending in Europe in a way it would not be in the US alone.
3. **AGPL-3.0 on the code.** A competitor may self-host. A competitor may not
   take the API server, improve it, and run the improved version as a closed
   rival service.
4. **Freshness and provenance.** A scraped copy is a photograph of a moving
   thing. It has no new revisions, no takedown answerability, no corrections and
   no linkage upkeep. This is not a legal protection, and it is the one that
   does the most work in practice.

The README of this project already made this argument about the market — "the
defensible value is in linkage, freshness, provenance, and API guarantees, not
in the rows." This licensing structure is that sentence, made operative.

---

## What is in this repository, and under what licence

Machine-readable equivalent: [`REUSE.toml`](REUSE.toml). Where this table and
`REUSE.toml` disagree, `REUSE.toml` is authoritative for tooling and this table
is authoritative for humans; report the discrepancy as a bug.

### AGPL-3.0-or-later — the code

```
schema/                 DDL: 67 tables, 10 views, constraint logic
tools/                  cycler adapters, validators, loaders, exporters, builders
api/                    read API server and the OPTIMADE-style filter grammar
agents/                 literature-miner pipeline
tests/                  SQL and Python test suites
.github/scripts/        issue-form parsing, candidate promotion
setup.sh  Dockerfile  docker-compose.yml
```

Full text: [`LICENSES/AGPL-3.0-or-later.txt`](LICENSES/AGPL-3.0-or-later.txt).

What this means concretely is in the FAQ below, because the AGPL is widely
misunderstood in a direction that costs projects adopters. Short version: using
this over a network triggers nothing, running it inside your company triggers
nothing you must publish, and only modifying-and-offering-to-third-parties
triggers the copyleft.

### CC-BY-4.0 — documentation, crosswalk, and the published sample

```
docs/                   architecture, conventions, ingestion, review
crosswalk/              BDF <-> EMMO/BattINFO <-> BPX <-> EU Battery Passport
json-schema/            contribution schema, quantity registry
seed/                   the four reference cells
contrib/                accepted community contributions
review/                 the candidate queue and its batches
web/data/               generated coverage and claims data
README.md  START-HERE.md  and the other root prose files
```

Full text: [`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt).

Attribution is the only condition. Every row already carries the provenance
needed to give it, so satisfying the licence costs you nothing you were not
already storing.

**`crosswalk/` is CC-BY-4.0 on purpose and that will not change.** Nobody has
published a mapping between BDF, BattINFO, BPX and the EU Battery Passport. A
mapping that a standards body cannot adopt is a mapping nobody adopts, and this
project would rather that artefact be used than owned. If you are at the Battery
Data Alliance, EMMO, or a passport implementer: take it, and tell us what is
wrong with it.

Note that CC-BY-4.0 Section 4 licenses the sui generis database right *in the
material it covers*. That grant reaches the sample published here. It does not
reach the corpus, which is not published under it.

---

## What is not in this repository

The following have never been published under an open licence and are not
licensed by anything in this repository:

- **The curated corpus** — the full accumulated set of products, revisions,
  observations, condition sets, test runs, protocol records and provenance
  chains held in the production database.
- **The hosted API** at `lemonergy.com`, and any extract, export, feed,
  snapshot or derived dataset supplied from it.
- **Ingestion output not yet published here**, including extractions awaiting
  review.

These are governed by [`TERMS.md`](TERMS.md) and by your subscription agreement.
See [`LICENSES/LicenseRef-battery-data-commercial.txt`](LICENSES/LicenseRef-battery-data-commercial.txt).

**The boundary is deliberate and it is the whole commercial model.** The sample
in `contrib/` exists so you can evaluate the schema, the conventions and the
provenance discipline against real cells before paying for anything. It is not a
teaser for the corpus; it is a working demonstration of the method. If the
method is not convincing at 64 cells it will not become convincing at 6,400.

---

## The database right

**The Licensor asserts the sui generis database right under Directive 96/9/EC
and the UK Copyright and Rights in Databases Regulations 1997 in the curated
corpus and in this repository's compilation, to the extent such rights subsist.**

This is the one intellectual property right that protects a collection of facts
*as a collection*, and it is worth understanding rather than reciting:

- It arises from **substantial investment** in obtaining, verifying or presenting
  the contents — not from creativity. This project's investment is overwhelmingly
  in *verification*: refusing a capacity that has no rate, temperature and cutoff;
  reconciling an AC resistance of 15 mΩ against a DC resistance of 23 mΩ for the
  same cell; recording that Samsung states a 14,700 mA pulse and never gives a
  duration. That is textbook qualifying investment.
- It prohibits **extraction or re-utilisation of a substantial part**, measured
  qualitatively or quantitatively, and prohibits **repeated and systematic
  extraction of insubstantial parts** where that conflicts with normal
  exploitation. Scraping the API a page at a time is the second of those.
- It runs **15 years**, restarting on each substantial new investment. A database
  under continuous curation is, in practice, continuously renewed.

The grant in CC-BY-4.0 Section 4 applies to the sample published in this
repository. **All database rights in the corpus are reserved.**

---

## Text and data mining, and model training

The Licensor **expressly reserves** the right of reproduction for text and data
mining in the corpus and the API, under Article 4(3) of Directive (EU) 2019/790.
This reservation is made in machine-readable form at
[`web/.well-known/tdmrep.json`](web/.well-known/tdmrep.json) and in [`web/robots.txt`](web/robots.txt), per the
W3C TDM Reservation Protocol. The API serves the same reservation at
`/.well-known/tdmrep.json` and in a `TDM-Reservation` header on every response.

In plain terms:

- **The CC-BY-4.0 sample in this repository**: mining and model training are
  permitted. CC licences do not prohibit TDM, and this project does not attempt
  to add a restriction the licence does not contain. Attribute it.
- **The corpus and the API**: training, fine-tuning, embedding, distillation or
  benchmark construction requires a separate written licence. Ask — this is a
  product, not a refusal, and the answer is usually a price rather than a no.

A reservation only works if it is stated before the mining happens, which is why
it is stated here, in the terms, in `robots.txt` and in an HTTP header on every
API response.

---

## Trademarks

Neither the AGPL nor CC-BY-4.0 grants trademark rights, and this document grants
none either. The project name, any logo, and any product name used for the
hosted service are reserved.

You may say your product "uses battery-data" or "is built on the battery-data
schema". You may not name a fork or a competing service in a way that suggests it
is this project, is endorsed by it, or is its official version. Rename your fork.

---

## Warranty, fitness, and one specific warning

All material here is provided **as is**, without warranty of any kind. That is
the standard clause and it is in both licences.

The non-standard part, which matters more:

> **This database is not a substitute for the manufacturer's datasheet, and
> nothing in it is qualified for safety-critical design.**

A cell specification that is wrong by 15% is not an inconvenience; downstream it
is a pack that vents. Every value here traces to a source document with a URL, a
hash and a retrieval date precisely so that you can check it against the original
— so check it. Manufacturers revise specifications, withdraw preliminary
documents, and publish different numbers for different regions of the same
product. The schema records all of that faithfully, which means it faithfully
records documents that were themselves provisional or wrong.

Use this for selection, comparison, screening and research. Verify against the
controlled document before anything is built, certified or shipped.

---

## Third-party material

Some things here arrived under someone else's terms, and this repository's
licence does not reach them.

| Material | Status |
|---|---|
| **Manufacturer datasheets** | **Not redistributed.** `source.redistributable` governs whether a document body may be stored at all; the default is no. Every value keeps a URL, a content hash and a retrieval date, so a takedown request is answerable per source rather than being project-ending. |
| **Extracted facts from datasheets** | Facts, recorded with provenance. Published here under CC-BY-4.0 as part of this compilation. |
| **Standards text** (IEC, ISO, SAE, UN 38.3) | Copyright the issuing body, never reproduced. This project stores *identifiers and citations* to clauses — "IEC 62660-1:2018 §7.2" — which is reference, not reproduction. Buy the standard from the issuer. |
| **Vocabularies** — BDF, EMMO/BattINFO, OPTIMADE, BPX | Under their own licences, recorded per-row in `vocabulary.license`. Mostly CC-BY-4.0 and Apache-2.0. Federated by IRI where possible rather than copied. |
| **Materials data** — Materials Project, OQMD, AFLOW, NOMAD | Federated by ID. Not re-hosted. Their terms govern their data. |
| **Open cycling datasets** | Under the terms each was published under, recorded on `bd.source`. `source.license` records what a source arrived under, which is a different question from what this repository ships under. |

`source.license` and `source.redistributable` are columns, not a policy document,
because a policy document does not stop a bad ingest and a `NOT NULL` constraint
does.

---

## If you contribute

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) — it is short, and the licensing part
of it is the part that matters.

The summary, so nobody is surprised later:

- **You keep your copyright.** There is no assignment. Nothing is taken from you.
- **You grant a licence broad enough to sub-license**, which is what allows your
  contribution to be served through the paid API. Without that grant your rows
  could be published here and nowhere else, and the project could not fund the
  curation that makes them useful.
- **You may still do anything you like with your own work**, including
  contributing it elsewhere. The grant is non-exclusive.
- **Contributors get API access.** A project that monetises contributed work
  while charging contributors for it deserves to fail. The policy is in
  `CONTRIBUTING.md` and it is a real one, not a gesture.

If that trade is not acceptable to you, do not contribute — that is a legitimate
choice and it is better made now than after a dispute.

---

## Commercial licences

Three separate things are for sale. They are unrelated and you may want one
without the others.

**1. API subscription** — hosted access to the curated corpus. The main product.
Terms: [`TERMS.md`](TERMS.md).

**2. Bulk / redistribution licence** — a snapshot you may hold, embed in a
product, or redistribute to your own customers. Not available under the API
terms, which prohibit exactly this; that is what makes it a separate licence
rather than an abuse of the first one.

**3. Commercial licence for the code** — a licence to use the AGPL components
inside a proprietary product without the AGPL's obligations. If the AGPL works
for you, you do not need this and should not buy it.

**Model training** sits under (2), priced separately.

Ask at **licensing@lemonergy.com**. If you are an academic
group, a standards body, or an open-source project, say so — the answer is
different and it is usually free.

---

## FAQ

Written against the questions that actually get asked, including the ones whose
honest answer is "no".

**Can I query the API from my closed-source commercial product?**
Yes. That is the product. Consuming an HTTP API triggers no AGPL obligation of
any kind — the AGPL binds people who modify and convey or serve the program, not
people who talk to a server someone else runs. Your code is yours.

**Does using the API make my company's code AGPL?**
No. This is the most common fear about the AGPL and it is unfounded here. Nothing
you do as an API client can impose the AGPL on your code.

**Can I self-host the API server for my own company?**
Yes, with no obligation to publish anything. Internal use is not conveying. If
you modify it, AGPL §13 obliges you to offer the source to the people using it
over the network — inside a company that is your own colleagues, and it makes
nothing public.

**Can I modify the server and offer it to my customers?**
Yes, and then AGPL §13 applies for real: those users must be offered the
Corresponding Source of your modified version. If that does not work for you,
buy the commercial code licence.

**Can I fork the whole repository?**
Yes. AGPL and CC-BY-4.0 both permit it. Rename it, keep the notices, and
understand that you have forked the sample and the method, not the corpus.

**Can I take the 64 cells in `contrib/` and put them in my own product?**
Yes — CC-BY-4.0, attribute it. That is a real grant and it is not going to be
withdrawn.

**Can I scrape the API to rebuild the corpus?**
No. It breaches the terms you accepted for your key, and in the EU and UK it
infringes the database right independently of the contract. It is also the
specific behaviour the terms are written to catch.

**Can I train a model on it?**
On the CC-BY-4.0 sample here, yes, with attribution. On the corpus or API output,
not without a separate licence — see the TDM section. Ask; it is priced, not
prohibited.

**Can I cite it in a paper?**
Please do — see Citation below. Academic use of the corpus is free; write and say
what you need.

**I contributed a cell. Can you sell it?**
Yes, and you should know that before you contribute rather than after. That is
exactly what the grant in `CONTRIBUTING.md` permits, it is stated in the issue
form you submit through, and it is why contributors get API access. You keep your
copyright and can use your own work however you like.

**I found my company's datasheet data in here.**
Then the provenance chain is doing its job — mail
**legal@lemonergy.com**. Every value carries the source
URL, the content hash and the retrieval date, so a source can be identified and
removed precisely rather than approximately. Note that facts stated in a
published datasheet are generally not removable as a matter of copyright, but
this project would rather have the conversation than win the argument.

**Why AGPL and not MIT?**
This repository was MIT and moved to AGPL. Under MIT, a well-funded competitor
takes the schema, the adapters and the API server, adds a corpus, and sells the
result with nothing owed back. Under AGPL they may still self-host — the freedom
that matters to users is intact — but they cannot run a closed improved fork as a
rival service. Earlier commits remain MIT and those rights do not expire; the
relicence applies going forward only.

**Why not CC-BY-NC on the data?**
Because "non-commercial" is genuinely ambiguous — a consultant's report, a
university with industrial funding, a paid newsletter all sit in the grey — and
because it would disqualify the project from the standards-body and academic
collaboration it depends on. NC would protect a corpus that is not published
anyway, at the cost of the credibility of the part that is. The corpus is
protected by not being published, which is stronger than NC and clearer.

**Is any of this legal advice?**
No. It is a statement of position by the copyright holder, written carefully and
not by a lawyer.

---

## Citation

```bibtex
@misc{battery-data,
  author = {Varzandeh, Morshed and {battery-data contributors}},
  title  = {battery-data: a provenance-first database of battery
            specifications, performance data and test conditions},
  year   = {2026},
  url    = {https://github.com/Morshedvarzandeh/battery-data}
}
```

If you use the standards crosswalk specifically, cite it as well — it is the part
most likely to be useful to someone who never touches the rest.

---

## Contact

| For | Write to |
|---|---|
| API subscriptions, pricing, bulk and model-training licences | licensing@lemonergy.com |
| Commercial licence for the AGPL code | licensing@lemonergy.com |
| Takedown, source removal, IP questions | legal@lemonergy.com |
| Academic, standards-body and open-source use | licensing@lemonergy.com — say which, the terms differ |
| Anything about the schema itself | GitHub issues |

---

## Version

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026 | First consolidated licensing statement. Establishes the code/sample/corpus split, asserts the database right, reserves TDM, and introduces the contributor grant and the API terms. |

Material licences do not apply retroactively to material already published under
a prior licence. Whatever you received under earlier terms, you keep under those
terms.
