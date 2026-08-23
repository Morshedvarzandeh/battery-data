<!--
  Adapted to Belgian law (B2B). Open items: [ENTERPRISE NUMBER] (assigned when
  the business is registered with a guichet d'entreprises / ondernemingsloket),
  [REGISTERED ADDRESS], [EFFECTIVE DATE]. The clauses marked for Belgium's B2B
  unfair-terms rules (arts. VI.91/1-10 CDE): 8.2, 9.4, 15, 16.
  Drafted with AI assistance by a non-lawyer and not reviewed by counsel.
  A one-time professional review before the first paying subscriber is still
  the strong recommendation.
-->

# battery-data API — Terms of Service

**Version 1.0 · Effective [EFFECTIVE DATE]**

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

**And one gate:** the API is offered to businesses only — engineering teams,
companies, universities, research groups. You will be asked for a company,
enterprise or VAT registration number at signup, and it is verified before a
key is issued. The API is not offered to consumers (§2.2).

**One thing to take seriously:** this data is for selection, comparison and
research. Verify against the manufacturer's controlled datasheet before anything
is built, certified or shipped. See §11.

---

## 1. Definitions

**"Licensor"**, **"we"**, **"us"** — Morshed Varzandeh, trading as **Lemonergy**, an enterprise registered in Belgium under enterprise number [ENTERPRISE NUMBER], of [REGISTERED ADDRESS]. If the business is incorporated, the company succeeds to this agreement under §17.6.

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

**2.1** These terms take effect when you first do any of: create an account,
accept them in an order form, or make a call to the API using a key issued to
you — provided in each case that the current version of these terms was made
available to you beforehand. Continued use after a change made under §16 is
acceptance of the changed terms.

**2.2 Business use only.** The API is offered exclusively to subscribers acting
for purposes relating to their trade, business, craft or profession — including
universities and research institutes. Consumers may not subscribe, and by
accepting these terms you confirm you are not accepting them as a consumer.
These terms are written for the business-to-business rules of Belgian law; they
are not drafted to govern a consumer relationship, and we would rather decline
a subscription than hold a consumer to terms that were never designed for one.
We require a company, enterprise or VAT registration number at signup and
verify it before issuing a key, and we may decline — or cancel with a pro-rata
refund of prepaid fees — any subscription we reasonably believe has been taken
by a consumer.

**2.3** If you do not accept these terms, do not use the API. The Open
Repository remains available to you regardless, under its own licences.

---

## 3. Grant of use

Subject to your Plan, to payment, and to §4, we grant you a **non-exclusive,
non-transferable, non-sublicensable, worldwide** licence — revocable only as
§12 provides — for the term of your subscription, to:

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
purposes — is *not* caught by this clause and is permitted under §3. Nothing in
this clause or §4.1 restricts text and data mining for scientific research to
the extent arts. XI.191/1, XI.191/2 and XI.310 of the Belgian Code of Economic
Law (art. 3 of Directive (EU) 2019/790) permit it notwithstanding contractual
restriction.

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

**5.1** The Licensor asserts the sui generis database right in the Corpus,
arising under Directive 96/9/EC as implemented in the member states of the
European Union and the European Economic Area — in Belgium, in Book XI, Title 7
(articles XI.305 and following) of the Code of Economic Law. These rights are
reserved and are not licensed by these terms. No UK database right is claimed:
none subsists for a corpus made by a Belgian maker after 2020, and UK-side
protection rests on these terms and on copyright in the code and documentation.

**5.2** The Licensor **expressly reserves** the reproduction right for text and
data mining under Article 4(3) of Directive (EU) 2019/790, as transposed in
Book XI of the Belgian Code of Economic Law. The reservation is made in these
terms and, in machine-readable form, in a `tdmrep.json` file at `/.well-known/`
under the TDM Reservation Protocol (a W3C Community Group Final Report), in a
`tdm-reservation` header on every API response, and separately in `robots.txt`.

**5.3** §4.1 and §4.4 restate contractually what §5.1 and §5.2 assert as
property rights. They are independent: a breach of one does not require a breach
of the other.

**5.4** A separate licence for mining and model training is available. Write to
licensing@lemonergy.com.

---

## 6. Attribution

Where you publish a specific value, figure, chart or table derived from the
Output — in a paper, report, datasheet, marketing material or product interface
— attribute it as:

> Source: battery-data (lemonergy.com), retrieved [date].

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

**7.2** You are responsible for use under your keys, including by anyone who
obtains one from you — except to the extent the use results from our own fault
or a failure of our security, and except for use occurring after you have
reported an exposure under §7.3 that timely rotation on our side would have
prevented.

**7.3** Tell us promptly at security@lemonergy.com if a key is exposed. We
will rotate it. Prompt disclosure of your own leak is treated as good faith, not
as a breach.

**7.4** We may embed per-subscriber watermarking in Output. It exists to identify
the origin of a leaked bulk copy and for no other purpose.

---

## 8. Availability and support

**8.1** We aim for high availability and will publish maintenance in advance
where we can. Unless your Plan includes a written service level agreement, the
API is provided on a reasonable-efforts basis with **no uptime guarantee**. If
the API is continuously unavailable for more than 72 hours for reasons within
our reasonable control, you may terminate the affected Plan and we will refund
the unused portion of prepaid fees pro rata.

**8.2** We may change, deprecate or withdraw endpoints and fields for valid
technical, security, legal or product reasons. Withdrawal of an endpoint or
field is a breaking change for the purposes of this clause. Breaking changes to
a versioned endpoint will be announced at least **90 days** in advance and the
previous version kept available during that period. Additive changes may ship
at any time; write clients that tolerate unknown fields. If a change under this
clause materially reduces the Corpus coverage or API functionality your Plan is
priced on, you may terminate the affected Plan and we will refund the unused
portion of prepaid fees.

**8.3** Support channel and response targets are per your Plan.

---

## 9. Fees and payment

**9.1** Fees, quotas and the billing period are as set out in your Plan at
https://www.lemonergy.com/pricing or in your order form.

**9.2** Fees are exclusive of VAT and other applicable taxes, which you pay in
addition where they apply.

**9.3** Invoices are due within **30 days**. Late payment accrues interest and
the fixed €40 recovery indemnity under the Belgian Law of 2 August 2002 on
combating late payment in commercial transactions, as amended, without further
notice. We
may suspend access to an account overdue by more than **30 days** after
written notice.

**9.4** We may change fees only for a valid reason: a demonstrable change in
our costs, in the scope or coverage of the Corpus, or in legal or regulatory
requirements applying to the service. Fee changes take effect at your next
renewal, on **60 days'** notice that states the reason relied on. If you do not
accept a change, you may terminate under §12.2 before it takes effect.

**9.5** Fees already paid are non-refundable except as §§2.2, 8.1, 8.2, 12.4
and 16 provide.

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

**11.1** Our undertaking is an obligation of means (middelenverbintenis /
obligation de moyens), and it is this: to provide access per your Plan and to
reproduce what source documents state, faithfully and with each value's
provenance intact, using reasonable professional care. That is our essential
obligation, and §15.5 applies to it. Beyond it, the API and the Corpus are
provided **as is and as available**: we do not warrant fitness for a particular
purpose or non-infringement, and we do not warrant that any source document was
correct, complete or current.

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
verification. **To the extent liability can lawfully be excluded, we accept no liability for
loss arising from reliance on the Corpus in a safety-critical application
without the verification this §11.3 requires.**

**11.4** Every value carries a source URL, a content hash and a retrieval date so
that §11.3 is practical rather than rhetorical. Use them.

---

## 12. Term, suspension and termination

**12.1** These terms run from acceptance until terminated. A subscription
renews automatically for successive periods equal to its billing period unless
cancelled under §12.2 before the renewal date; for billing periods of one year
or longer, we send a renewal reminder to the email on your account at least 30
days before each renewal.

**12.2 By you.** Cancel at any time, effective at the end of the current
billing period. No advance-notice window applies to cancellation under this
clause.

**12.3 By us.** We may suspend or terminate immediately on written notice for
material breach — §4 in particular — or for non-payment under §9.3. Where a
breach is capable of being cured and is not deliberate, we will give you **14
days'** notice and a chance to fix it first. On reasonable, documented
suspicion of a §4.1 breach we may suspend — not terminate — while we
investigate, for no longer than necessary; if the suspension proves
unjustified, we extend your subscription by its length or credit the
corresponding fees, at your choice. We may also refuse, suspend or terminate a
subscription, without indemnity, where providing the service or receiving
payment would breach applicable sanctions or export-control law — §12.4 does
not apply to the extent a refund payment is itself prohibited. Finally, we may
terminate for convenience on **90 days'** written notice, in which case §12.4
applies.

**12.4** If we terminate for convenience, we refund the unused portion of fees
already paid. If you terminate for our uncured material breach, likewise.

**12.5 On termination:**

- your keys stop working, and your rights under §3 end;
- you must stop using the Output for new work, and delete stored Output and
  caches within **30 days**;
- **but you may keep, indefinitely:** Output already incorporated into a design,
  analysis, report, publication or deliverable completed before termination, and
  Output you must retain to meet a legal, regulatory or contractual record-keeping
  obligation. You may continue to use those artefacts. You may not mine that
  retained material to reconstitute a working dataset.

**12.6** §§4, 5, 6, 9 (as to fees accrued and their collection), 11, 12.5, 13,
14, 15 and 17 survive termination.

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
https://www.lemonergy.com/privacy ([`PRIVACY.md`](PRIVACY.md) in the Open
Repository). The Licensor is the controller. The supervisory authority is the
Belgian Data Protection Authority (APD/GBA), and you may complain to it directly.

**13.4** Each party acts as an independent controller of the personal data it
processes in connection with these terms; neither processes personal data on
the other's behalf, and no data-processing agreement under art. 28 GDPR is
required. The API is not designed to receive personal data — do not include
personal data in query text or other input. You will bring our privacy policy
to the attention of the individuals whose access you arrange.

---

## 14. Indemnity

You will indemnify us against third-party claims, and reasonable costs, arising
from your use of the API or Output in breach of these terms, or from your
unlawful use of either.

---

## 15. Liability

**15.1** Nothing in these terms excludes or limits either party's liability
for its fraud (bedrog / dol) or intentional fault (opzettelijke fout / faute
intentionnelle), including that of persons for whom it is responsible; for
death or harm to physical or psychological integrity; or for anything else that
cannot lawfully be excluded or limited under Belgian law.

**15.2** Subject to §15.1 and §15.5, we are not liable for indirect,
incidental, special, consequential or punitive loss, nor for loss of profit,
revenue, business, goodwill, anticipated saving, or data, however arising.

**15.3** Subject to §15.1 and §15.5, our total aggregate liability under these
terms is limited to the fees you paid in the **12 months** preceding the event
giving rise to the claim. The fees are calculated on this allocation of risk,
and §11.3 is part of the same allocation: the subscriber, not the Licensor, is
the party in a position to verify a value against the manufacturer's controlled
document before relying on it.

**15.4** §15.2 and §15.3 apply notwithstanding §11.3. §11.3 applies subject to
§15.1 and §15.5.

**15.5** The exclusions and the cap in this section do not apply to loss caused
by our gross negligence (zware fout / faute lourde), and nothing in this
section is to be read as emptying our essential obligations under these terms
of their substance.

**15.6** Subject to §15.1, the exclusions and the cap in this section apply to
any claim however arising — in contract, extracontractually (in tort) or
otherwise — and are stipulated also for the benefit of our employees,
contractors and suppliers, each of whom may invoke them directly. To the extent
permitted by law, extracontractual claims between the parties for facts
governed by these terms are excluded, except for damage to physical or
psychological integrity or damage caused by intentional fault.

---

## 16. Changes to these terms

We may change these terms for valid reasons — a change in law, a security
requirement, or an evolution of the service or of its cost base — on **30
days'** written notice to the email on your account. Each notice states the
valid reason relied on and includes or links the changed text; material changes
will be identified as such. If you do not accept a material change, you may
terminate with effect from the date the change takes effect, and we will refund
the unused portion of fees already paid for the current billing period;
continued use afterwards is acceptance. The current version is always at
https://www.lemonergy.com/terms and in the Open Repository.

---

## 17. General

**17.1 Governing law.** These terms are governed by Belgian law. Disputes are
subject to the exclusive jurisdiction of the enterprise court
(ondernemingsrechtbank / tribunal de l'entreprise) of the judicial district of
the Licensor's registered office or, for so long as the Licensor is a natural
person, of its principal establishment as recorded in the Crossroads Bank for
Enterprises (KBO/BCE). The United Nations Convention on Contracts for
the International Sale of Goods does not apply.

**17.2 Entire agreement.** These terms and your Plan are the whole agreement
between us on this subject, and replace any prior understanding. Nothing here
excludes liability for fraudulent misrepresentation.

**17.3 Order of precedence.** Where a signed order form or written SLA conflicts
with these terms, the order form or SLA prevails for the conflicting clause only.

**17.4 Severability.** If a clause is unenforceable, it is severed and the rest
stands.

**17.5 No waiver.** Not enforcing a term is not a waiver of it.

**17.6 Assignment.** You may not assign without our written consent, not to be
unreasonably withheld. We may assign or transfer this agreement in whole to a
successor of the business, including a company incorporated by the Licensor to
continue it. You consent in advance to that transfer; it takes effect on
written notice to you, from which point the transferee replaces the Licensor
and the transferring natural person is released from obligations arising after
the notice.

**17.7 Force majeure.** Neither party is liable for delay or failure caused by
events beyond its reasonable control.

**17.8 Relationship.** Nothing here creates a partnership, agency or employment
relationship.

**17.9 Language.** The parties choose English as the language of these terms
and of their commercial relationship, without prejudice to any mandatory
language requirement that applies to specific documents such as invoices.

**17.10 Notices.** Formal notices under these terms are given by email — to us
at legal@lemonergy.com, to you at the email on your account — and are deemed
received on the first business day after sending. Notices of default,
suspension or termination may additionally be sent by registered post. Each
party keeps its notice address current.

---

## 18. Contact

| For | Write to |
|---|---|
| Subscriptions, quotas, pricing | sales@lemonergy.com |
| Bulk, redistribution and model-training licences | licensing@lemonergy.com |
| Key exposure and security | security@lemonergy.com |
| Legal, takedown, contract questions | legal@lemonergy.com |

---

*The public repository is open source and is not governed by this document. See
[`LICENSING.md`](LICENSING.md).*
