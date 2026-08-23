<!--
  Published at https://www.lemonergy.com/privacy and kept in the repository so
  TERMS.md §13.3 points at something real. Drafted with AI assistance by a
  non-lawyer against the GDPR and Belgian practice; fill the [bracketed] items
  when the business registers, and list the actual processors before launch.
-->

# Privacy policy — battery-data API

**Version 1.0 · Effective [EFFECTIVE DATE]**

This policy covers the battery-data API and the lemonergy.com website. It is
written to be read, not to be scrolled past.

## Who is responsible

The controller is Morshed Varzandeh, trading as **Lemonergy**, registered in
Belgium under enterprise number [ENTERPRISE NUMBER], [REGISTERED ADDRESS].
Contact: privacy@lemonergy.com.

## What we process, and why

| Data | Why | Legal basis (GDPR art. 6) |
|---|---|---|
| Account data — name, work email, organisation, VAT number | To open and run your subscription, and to invoice it | Contract (6.1.b); legal obligation for invoicing (6.1.c) |
| Billing records | Belgian tax and accounting law requires keeping them | Legal obligation (6.1.c) |
| API request logs — key ID, endpoint, query text, IP address, timestamps, response size | Billing and quota administration, abuse and extraction detection, security, service improvement | Legitimate interest (6.1.f); contract (6.1.b) where the subscriber is a natural person; legal obligation (6.1.c) once a log line becomes invoicing evidence |
| Support correspondence | To answer you | Legitimate interest (6.1.f) |
| Website analytics, if any | Aggregate usage only, no advertising | Legitimate interest (6.1.f), or consent where required |

If your organisation subscribes, the people in these records include its
staff: we receive your name and work email from your organisation to set up
your access, and your key ID and IP address appear in the request logs. The
API itself is not designed to receive personal data — do not include personal
data in query text.

We do not sell personal data, we do not run advertising, and we do not use
personal data to train models.

## The part specific to this service

**Your queries reveal what you are working on.** A pattern of API queries about
specific cells is commercially sensitive information about your engineering
roadmap. As TERMS.md §13 promises: query logs are treated as your confidential
information, are not published, sold or shared except as needed to run the
service or as required by law, and identifiable query patterns are not used to
compete with you or to inform anyone else's product decisions. Only aggregate,
non-identifiable statistics are ever published.

## How long we keep it

| Data | Retention |
|---|---|
| Account data | Life of the subscription, then 12 months |
| Billing records | 10 years, as Belgian VAT and accounting law requires |
| API request logs | 12 months in identifiable form, then deleted or irreversibly aggregated |
| Support correspondence | 24 months after the thread closes |

## Who else touches it

Hosting, payment and email providers act as processors under GDPR art. 28
agreements. The current list: [PROCESSORS — name them before launch, e.g.
hosting provider, payment provider, email provider]. Where a processor is
outside the EEA, transfers rest on an adequacy decision or Standard
Contractual Clauses.

## Your rights

Access, rectification, erasure, restriction, portability, and objection to
processing based on legitimate interest — write to privacy@lemonergy.com and
we answer within a month. Where we rely on consent, you can withdraw it at any
time, with effect for the future. You can complain to the Belgian Data Protection
Authority (APD/GBA, <https://www.dataprotectionauthority.be>), or to your own
member state's authority.

## What this policy does not cover

The public GitHub repository is operated by GitHub under GitHub's own privacy
terms. Git commit metadata (names, email addresses, sign-offs) is public by
the nature of the contribution process, as the DCO itself states.

## Changes

Changes are announced the same way as changes to TERMS.md (§16): 30 days'
notice to the email on your account, and the current version always at
<https://www.lemonergy.com/privacy>.
