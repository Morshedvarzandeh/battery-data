<!--
  The pre-revenue agreement. Free access, no invoice, no VAT — so it can be
  signed before KBO registration, unlike TERMS.md which cannot be used until
  an enterprise number and VAT number exist.
  Open items: [ADDRESS] (a home address is normal for a sole trader and
  becomes the registered address later) and [DATE] per agreement.
  Drafted with AI assistance by a non-lawyer. Not reviewed by counsel.
-->

# battery-data — Design partner agreement

**Free evaluation access. Version 1.0.**

This is the agreement for the period before battery-data is sold. It gives a
small number of engineering teams full access to the curated corpus at no
charge, in exchange for telling us what is wrong with it.

It is deliberately short, and it is deliberately not a subscription: no fees,
no invoice, no minimum term, and either side can walk away in a day.

---

## Why this exists, plainly

The corpus is useful or it is not, and only engineers with real cell-selection
problems can settle that. Rather than guess at a price and a feature set, the
first users get everything free while the product is shaped around what they
actually do with it.

What we want in return is not money. It is: what you looked for and could not
find, which values you checked against a datasheet and which of those were
wrong, and — when you have used it enough to have a view — what this would have
to be worth before you would pay for it.

---

## 1. The parties

**Us:** Morshed Varzandeh, trading as **Lemonergy**, of [ADDRESS], Belgium.
Contact: **legal@lemonergy.com**.

**You:** the company, university, research institute or other organisation
named in the access email, accepting through the person who requested access.
This agreement is for organisations acting in the course of a trade,
profession or research activity. It is not offered to consumers, and if you
are an individual acting for private purposes, do not accept it.

---

## 2. What you get

**2.1** Access to the battery-data API and the full curated corpus — the same
data a paying subscriber would receive, not a reduced tier — for the term in
§7, free of charge.

**2.2** You may use, store, analyse and internally reproduce what the API
returns for your own engineering, research or business purposes, and you may
incorporate individual values and derived results into your own designs,
analyses, reports and publications, including commercial ones. §3 sets the
limits.

**2.3** **Founding-partner terms.** If and when the service becomes paid, you
will be offered continuation at a materially better rate than the published
one, and you are never obliged to take it. Nothing here commits you to buy
anything.

**2.4** No fee is payable, now or retrospectively, for anything supplied under
this agreement.

---

## 3. What you may not do

The corpus is the thing being built, so these limits are the same ones a
paying subscriber gets, and they are the whole reason this document exists.

**3.1** Do not systematically extract the corpus — no scraping, crawling,
identifier enumeration, or querying designed to reconstruct the database
rather than to answer a question. This covers extraction of a substantial part
in one go, and repeated systematic extraction of small parts whose cumulative
effect would rebuild a substantial part.

**3.2** Do not redistribute the corpus, or a substantial part of it, to anyone
outside your organisation. Publishing *specific values* with attribution under
§4 is fine and encouraged.

**3.3** Do not use it to build or improve a database, dataset or service that
competes with this one.

**3.4** Do not use it to train, fine-tune, evaluate or ground a machine
learning model, and do not mine it for that purpose. Ordinary engineering
analysis of values you retrieved — curve fitting, parameter estimation,
statistics over your own result set — is not caught by this and is welcome.
Nothing in this clause restricts text and data mining for scientific research
to the extent arts. XI.191/1, XI.191/2 and XI.310 of the Belgian Code of
Economic Law permit it notwithstanding contractual restriction.

**3.5** Do not share your access credentials outside your organisation.

**3.6** Do not strip provenance — the source citation attached to a value is
not decoration, and a value separated from its conditions is the failure this
project exists to prevent.

**Rights reserved.** The sui generis database right in the corpus (Directive
96/9/EC; in Belgium, Book XI, Title 7 of the Code of Economic Law) is
reserved, as is the right of reproduction for text and data mining under art.
4(3) of Directive (EU) 2019/790. Free access is not a licence to any of it
beyond §2.

---

## 4. Attribution

If you publish a specific value, figure or table derived from the corpus,
attribute it as *"Source: battery-data (lemonergy.com), retrieved [date]"*.

Internal use needs no attribution. And if you have verified a value against the
manufacturer's own datasheet, cite the datasheet instead — it is the better
citation, and helping you find it is what this database is for.

---

## 5. What we ask from you

Not binding obligations, because a free agreement with homework attached is
neither free nor honest. But this is the exchange:

- **Tell us when a value is wrong.** This is worth more than anything else you
  could give us. A database whose entire claim is provenance needs to hear
  when the provenance failed.
- **Tell us what you could not find.** Gaps are how the ingest queue gets
  prioritised.
- **Tell us, eventually, what it is worth.** An honest number, including zero.

**Being named.** We would like to say you are a design partner. We will not do
it without your written say-so, and you can withdraw it at any time.

---

## 6. Safety — read this one

> **The corpus is not a substitute for the manufacturer's controlled datasheet
> and is not qualified for safety-critical design.**

Values are recorded faithfully from source documents, which means documents
that were themselves preliminary, revised or wrong are recorded faithfully
too. Manufacturers publish different numbers for the same product in different
regions and to different customers.

**Verify every value against the manufacturer's current controlled document
before it is used in the design, certification, manufacture or operation of
anything** — and in particular before any thermal, electrical, protection,
abuse-tolerance or compliance calculation. Every value carries a source URL, a
content hash and a retrieval date so that this is practical rather than
rhetorical.

That this access is free changes nothing about §6. If anything it raises it:
there is no support contract behind this, and no service level.

---

## 7. Term, and how it ends

**7.1** This agreement runs from the day access is granted until either side
ends it. Either side may end it at any time, for any reason, on written
notice. No notice period, no penalty, no explanation required.

**7.2** It also ends automatically if the paid service launches and you decide
not to continue — we will give you at least **30 days'** notice before free
access stops, and an offer under §2.3.

**7.3** The service is provided as-is and as-available, with no uptime
commitment and no support commitment. Endpoints may change or disappear
without notice. This is a pre-release product and it will behave like one.

**7.4 When it ends:** stop using the corpus for new work and delete stored
copies within 30 days — **but you keep, indefinitely, whatever is already in a
completed design, analysis, report or publication**, and anything you must
retain for a legal or regulatory record. You may go on using those. §§3, 6, 8
and 9 survive.

---

## 8. Liability

**8.1** Nothing here excludes or limits either party's liability for fraud
(*bedrog / dol*) or intentional fault (*opzettelijke fout / faute
intentionnelle*), including that of persons for whom it is responsible; for
death or harm to physical or psychological integrity; or for anything else
that cannot lawfully be excluded under Belgian law.

**8.2** Subject to §8.1, and because this access is supplied free of charge, we
accept no liability for any loss arising from your use of or reliance on the
corpus, including indirect and consequential loss and loss of profit, revenue,
data or anticipated saving. To the extent a limit rather than an exclusion is
required for this to be effective, our total liability is limited to **€500**.

**8.3** Subject to §8.1, §8.2 applies to any claim however arising — in
contract, extracontractually or otherwise — and is stipulated also for the
benefit of anyone we engage.

**8.4** You confirm that you have read §6, and that you will not rely on the
corpus in a safety-critical application without the verification §6 requires.

---

## 9. Confidentiality, data, and the law

**9.1 Your queries are yours.** What you search for reveals what you are
building. We log requests to run and improve the service; we do not publish
them, sell them, share them, or use identifiable query patterns to inform
anyone else's product decisions. Only aggregate, non-identifiable statistics
are ever published.

**9.2 Personal data** is handled per [`PRIVACY.md`](PRIVACY.md). Each party
acts as an independent controller; neither processes personal data on the
other's behalf, so no art. 28 GDPR agreement is needed. Do not put personal
data in query text — the API is not designed to receive it.

**9.3** This agreement is governed by **Belgian law**, and the Belgian courts
of the place where we are established have jurisdiction.

**9.4** Notices go by email — to us at legal@lemonergy.com, to you at the
address access was requested from.

**9.5** This is the whole agreement about free access. It replaces nothing and
commits neither side to a paid relationship. When and if you subscribe, the
[Terms of Service](TERMS.md) take over from the start date of that
subscription.

---

## 10. Accepting

Reply to the access email with **"Agreed"**, naming your organisation. We keep
that email, this document's version, and the date — which is the whole
ceremony.

Questions, including awkward ones about §3 or §8: **legal@lemonergy.com**.
Asking before you build something is always better than asking afterwards.
