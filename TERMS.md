<!--
  BEFORE PUBLISHING: replace YOURDOMAIN.example, [legal entity], [jurisdiction],
  [courts], and the pricing/limit placeholders in §9 and §10.
  Find them with:  grep -n "YOURDOMAIN.example\|\[.*\]" TERMS.md
  This is a drafted starting point, not legal advice, and it has not been
  reviewed by a lawyer. Have one read it before you take money against it.
-->

# battery-data API — Terms of Service

**Version 1.0 · Effective [date]**

These terms govern access to the hosted battery-data API and to the curated
corpus it serves. They do **not** govern the public repository at
<https://github.com/Morshedvarzandeh/battery-data>, which is open source and is
covered by [`LICENSING.md`](LICENSING.md) instead.

---

## In plain English, before the clauses

This summary is not the agreement — the clauses below are — but nothing in them
is intended to surprise you, so here is what they say.

**You may:** query the API as much as your plan allows, use the results in your
products, designs, research and reports, store what you need to work with,
publish specific figures with attribution, and keep whatever you have already
put into a finished design or report even after you stop subscribing.

**You may not:** systematically download the corpus, redistribute it in bulk,
resell it, use it to build a competing database, train models on it, or share
your key.

**The difference between those lists** is the difference between *using* the data
and *taking* the collection. Use is what you are paying for. If you need to do
something on the second list, it is available — it is a different licence at a
different price, not a refusal.

**One thing to take seriously:** this data is for selection, comparison and
research. Verify against the manufacturer's controlled datasheet before anything
is built, certified or shipped. See §11.

---

## 1. Definitions

**"Licensor"**, **"we"**, **"us"** — [legal entity], of [address].

**"You"**, **"Subscriber"** — the individual or organisation accepting these
terms. Where an individual accepts on behalf of an organisation, that individual
warrants they are authorised to bind it, and "you" means the organisation.

**"API"** — the hosted battery-data application programming interface and any
endpoint, console, export function or bulk delivery we provide with it.

**"Corpus"** — the curated battery-data database served through the API: product
records, revisions, units, observations, condition sets, test runs, segments,
protocol records, model parameters, crosswalk linkages, provenance chains, and
every extract, export, feed, snapshot or derived dataset supplied from it.

**"Open Repository"** — the public repository, licensed under AGPL-3.0-or-later
and CC-BY-4.0 as set out in `LICENSING.md`. The Open Repository is not part of
the Corpus and nothing in these terms restricts your rights in it.

**"Output"** — the data returned to you in response to your API calls.

**"Plan"** — the subscription tier, quota and fees agreed between us.

---

## 2. Acceptance

These terms take effect when you first do any of: create an account, accept them
in an order form, or make a call to the API using a key issued to you. Continued
use after a change made under §16 is acceptance of the changed terms.

If you do not accept these terms, do not use the API. The Open Repository remains
available to you regardless, under its own licences.

---

## 3. Grant of use

Subject to your Plan, to payment, and to §4, we grant you a **non-exclusive,
non-transferable, non-sublicensable, worldwide, revocable** licence, for the term
of your subscription, to:

**3.1** call the API within your Plan's quota;

**3.2** use, store, process, analyse and internally reproduce the Output for your
own business, engineering, research or academic purposes;

**3.3** incorporate individual values and derived results from the Output into
your own products, designs, simulations, reports, publications and deliverables,
including commercial ones and including deliverables supplied to your own
customers, subject to §6 (attribution) and §4 (restrictions);

**3.4** cache Output for operational purposes — performance, offline working,
reproducibility of a specific analysis — provided the cache is not a substitute
for a subscription, is not exposed to third parties as a data source, and is not
built up into a standing copy of the Corpus.

The grant runs to you and to your employees and contractors acting for you. It
does not run to your affiliates, group companies or customers unless the Plan
says so.

---

## 4. Restrictions

You may not, and may not permit anyone else to:

**4.1 Systematically extract.** Download, scrape, crawl, enumerate or otherwise
extract a substantial part of the Corpus, whether in one operation or by
repeated and systematic extraction of insubstantial parts. Enumerating
identifiers, walking pagination to exhaustion, or issuing queries designed to
reconstruct rather than to answer, are each caught by this clause regardless of
whether your quota permits the call volume.

**4.2 Redistribute in bulk.** Publish, sell, sublicense, lease, transfer or
otherwise make available the Corpus or any substantial part of it, in any form,
to any third party. Publishing *specific figures* under §6 is expressly permitted
and is not a breach of this clause.

**4.3 Build a competing database or service.** Use the Corpus or the Output to
create, train, populate, correct, benchmark or enrich a database, dataset,
product or service that competes with the API or the Corpus.

**4.4 Mine or train.** Use the Corpus or the Output for text and data mining, or
to train, fine-tune, evaluate, distil or ground any machine learning model,
statistical model or AI system, including retrieval-augmented generation over a
stored copy. See §5. Ordinary analysis of retrieved values — curve fitting,
parameter estimation, statistics over a result set for your own engineering
purposes — is *not* caught by this clause and is permitted under §3.

**4.5 Share access.** Disclose, share, resell or transfer an API key, or permit
access by anyone outside §3. Each key identifies one Subscriber.

**4.6 Circumvent.** Evade or attempt to evade a quota, rate limit, access
control, watermark or usage measurement, including by rotating keys, accounts or
addresses.

**4.7 Strip provenance.** Remove, obscure or falsify a provenance record, source
citation, licence notice or attribution attached to Output. The provenance is not
decoration; a value separated from its conditions is the failure mode this whole
project exists to prevent.

**4.8 Misuse.** Use the API unlawfully, to infringe another party's rights, or in
a way that degrades the service for others.

**4.9** Reverse engineer, decompile or disassemble any non-open-source component
of the service, except where that restriction is unenforceable in your
jurisdiction.

**On the boundary between §3.3 and §4.2:** putting a cell's rated capacity into
your pack design and shipping that design is use, and it is permitted. Shipping a
table of 5,000 cells' specifications to your customers is redistribution, and it
needs the bulk licence. If your case genuinely sits between the two, ask us
before you build it — we would rather quote you than argue with you.

---

## 5. Database rights and mining reservation

**5.1** The Licensor asserts the sui generis database right under Directive
96/9/EC and the UK Copyright and Rights in Databases Regulations 1997 in the
Corpus. These rights are reserved and are not licensed by these terms.

**5.2** The Licensor **expressly reserves** the reproduction right for text and
data mining under Article 4(3) of Directive (EU) 2019/790. This reservation is
made in machine-readable form under the W3C TDM Reservation Protocol at
`/.well-known/tdmrep.json`, in `robots.txt`, and in a `tdm-reservation` header on
every API response.

**5.3** §4.1 and §4.4 restate contractually what §5.1 and §5.2 assert as
property rights. They are independent: a breach of one does not require a breach
of the other.

**5.4** A separate licence for mining and model training is available. Write to
[licensing@YOURDOMAIN.example].

---

## 6. Attribution

Where you publish a specific value, figure, chart or table derived from the
Output — in a paper, report, datasheet, marketing material or product interface
— attribute it as:

> Source: battery-data (YOURDOMAIN.example), retrieved [date].

You do not need to attribute internal use, and you do not need to attribute
values you have independently verified against the manufacturer's datasheet and
are citing to that datasheet instead. In fact, we would prefer the latter: the
manufacturer's document is the better citation, and this database's job is to
help you find it.

Where the Output carries a provenance citation to an original source, keep that
citation with the value under §4.7.

---

## 7. API keys and security

**7.1** Keys are issued to you and are confidential. Treat one as a credential,
not a configuration value: keep it out of client-side code, public repositories
and shared documents.

**7.2** You are responsible for all use under your keys, including use by anyone
who obtains one from you, however they obtained it.

**7.3** Tell us promptly at [security@YOURDOMAIN.example] if a key is exposed. We
will rotate it. Prompt disclosure of your own leak is treated as good faith, not
as a breach.

**7.4** We may embed per-subscriber watermarking in Output. It exists to identify
the origin of a leaked bulk copy and for no other purpose.

---

## 8. Availability and support

**8.1** We aim for high availability and will publish maintenance in advance
where we can. Unless your Plan includes a written service level agreement, the
API is provided on a reasonable-efforts basis with **no uptime guarantee**.

**8.2** We may change, deprecate or withdraw endpoints and fields. Breaking
changes to a versioned endpoint will be announced at least **[90] days** in
advance and the previous version kept available during that period. Additive
changes may ship at any time; write clients that tolerate unknown fields.

**8.3** Support channel and response targets are per your Plan.

---

## 9. Fees and payment

**9.1** Fees, quotas and the billing period are as set out in your Plan at
[https://YOURDOMAIN.example/pricing] or in your order form.

**9.2** Fees are exclusive of VAT and other applicable taxes, which you pay in
addition where they apply.

**9.3** Invoices are due within **[30] days**. We may suspend access to an account
overdue by more than **[30] days** after written notice.

**9.4** We may change fees on **[60] days'** notice, effective at your next
renewal. If you do not accept a change, you may terminate under §12.2 before it
takes effect.

**9.5** Fees already paid are non-refundable except as §12.4 provides.

---

## 10. Quotas and fair use

**10.1** Your Plan sets a request quota and rate limit. Exceeding a rate limit
returns `429`; exceeding a quota may return `429` or `402` depending on your
Plan.

**10.2** Sustained traffic patterns consistent with extraction rather than use
may be rate-limited or suspended under §12.3 even where they sit inside your
quota. A quota is a billing ceiling, not permission to do the thing §4.1
prohibits.

**10.3** If you need a bulk delivery, buy one. It is cheaper than the scrape, it
is faster, it comes as a proper snapshot with a version, and it does not put your
account at risk.

---

## 11. Warranties, accuracy, and safety

**11.1** The API and the Corpus are provided **"AS IS" and "AS AVAILABLE"**. To
the fullest extent permitted by law we disclaim all warranties, express or
implied, including merchantability, fitness for a particular purpose,
non-infringement, accuracy and completeness.

**11.2 Accuracy.** The Corpus records what source documents state, with
provenance. It does not warrant that a source document was correct. Manufacturers
publish preliminary specifications, revise them, withdraw them, and publish
different values for the same product in different regions and to different
customers — the schema records that faithfully, which means it faithfully records
documents that were themselves provisional or wrong.

**11.3 SAFETY.** **The Corpus is not a substitute for the manufacturer's
controlled datasheet and is not qualified for safety-critical design.** You must
verify any value against the manufacturer's current controlled document before it
is used in the design, certification, manufacture or operation of any product,
and in particular before it is used in any thermal, electrical, protection,
abuse-tolerance or compliance calculation. You are solely responsible for that
verification. **We accept no liability whatsoever for any loss arising from
reliance on the Corpus in a safety-critical application.**

**11.4** Every value carries a source URL, a content hash and a retrieval date so
that §11.3 is practical rather than rhetorical. Use them.

---

## 12. Term, suspension and termination

**12.1** These terms run from acceptance until terminated.

**12.2 By you.** Cancel at any time, effective at the end of the current billing
period.

**12.3 By us.** We may suspend or terminate immediately on written notice for
material breach — §4 in particular — or for non-payment under §9.3. Where a
suspicion of breach is capable of being cured and is not deliberate, we will give
you **[14] days'** notice and a chance to fix it first.

**12.4** If we terminate for convenience, we refund the unused portion of fees
already paid. If you terminate for our uncured material breach, likewise.

**12.5 On termination:**

- your keys stop working, and your rights under §3 end;
- you must stop using the Output for new work, and delete stored Output and
  caches within **[30] days**;
- **but you may keep, indefinitely:** Output already incorporated into a design,
  analysis, report, publication or deliverable completed before termination, and
  Output you must retain to meet a legal, regulatory or contractual record-keeping
  obligation. You may continue to use those artefacts. You may not mine that
  retained material to reconstitute a working dataset.

**12.6** §§4, 5, 11, 13, 14, 15 and 17 survive termination.

That §12.5 carve-out is deliberate. An engineering record that cannot outlive a
subscription is not usable in engineering, and a term that forces you to gut your
own design history would be one no serious customer could accept.

---

## 13. Confidentiality and your data

**13.1** We log API requests for billing, abuse detection, rate limiting and
service improvement. Query logs are treated as your confidential information and
are not published, sold, or shared with third parties except as needed to run the
service or as required by law.

**13.2** Your queries reveal what you are working on. We will not use identifiable
query patterns to compete with you or to inform anyone else's product decisions.
Aggregate, non-identifiable statistics about API usage may be published.

**13.3** Personal data is handled per our privacy policy at
[https://YOURDOMAIN.example/privacy].

---

## 14. Indemnity

You will indemnify us against third-party claims, and reasonable costs, arising
from your use of the API or Output in breach of these terms, or from your
unlawful use of either.

---

## 15. Liability

**15.1** Neither party excludes liability for death or personal injury caused by
negligence, for fraud, or for anything else that cannot lawfully be excluded.

**15.2** Subject to §15.1, we are not liable for indirect, incidental, special,
consequential or punitive loss, nor for loss of profit, revenue, business,
goodwill, anticipated saving, or data, however arising.

**15.3** Subject to §15.1, our total aggregate liability under these terms is
limited to the fees you paid in the **12 months** preceding the event giving rise
to the claim.

**15.4** §15.2 and §15.3 apply notwithstanding §11.3, and §11.3 applies
notwithstanding anything else in these terms.

---

## 16. Changes to these terms

We may change these terms on **[30] days'** written notice to the email on your
account. Material changes will be identified as such. If you do not accept a
change, terminate under §12.2 before it takes effect; continued use afterwards is
acceptance. The current version is always at
[https://YOURDOMAIN.example/terms] and in the Open Repository.

---

## 17. General

**17.1 Governing law.** These terms are governed by the law of [jurisdiction],
and the courts of [courts] have exclusive jurisdiction.

**17.2 Entire agreement.** These terms and your Plan are the whole agreement
between us on this subject, and replace any prior understanding. Nothing here
excludes liability for fraudulent misrepresentation.

**17.3 Order of precedence.** Where a signed order form or written SLA conflicts
with these terms, the order form or SLA prevails for the conflicting clause only.

**17.4 Severability.** If a clause is unenforceable, it is severed and the rest
stands.

**17.5 No waiver.** Not enforcing a term is not a waiver of it.

**17.6 Assignment.** You may not assign without our written consent, not to be
unreasonably withheld. We may assign to a successor of the business.

**17.7 Force majeure.** Neither party is liable for delay or failure caused by
events beyond its reasonable control.

**17.8 Relationship.** Nothing here creates a partnership, agency or employment
relationship.

---

## 18. Contact

| For | Write to |
|---|---|
| Subscriptions, quotas, pricing | [sales@YOURDOMAIN.example] |
| Bulk, redistribution and model-training licences | [licensing@YOURDOMAIN.example] |
| Key exposure and security | [security@YOURDOMAIN.example] |
| Legal, takedown, contract questions | [legal@YOURDOMAIN.example] |

---

*The public repository is open source and is not governed by this document. See
[`LICENSING.md`](LICENSING.md).*
