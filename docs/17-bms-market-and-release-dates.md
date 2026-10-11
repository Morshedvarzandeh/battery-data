# BMS market coverage and release evidence

[Compare BMS products](../components/bms.md) · [All electrical components](../components/catalog.md)

## October 2026 expansion

The library adds **24 reviewed BMS records / 53 numeric observations**, covering
**12 manufacturers and brands**: Lithium Balance, Ewert Energy Systems (Orion),
Nuvation Energy, Enepaq, EMUS, REC, Prohelion, Wattius, Elithion, JK/Jikong and DALY,
plus Batrium. This is a sourced starting inventory, not a claim to cover every BMS
sold worldwide. Families, controllers and explicit configurations have distinct
scope labels; a family is not expanded into unverified purchasing codes.

Five Lithium Balance records cover n3-BMS with CMU12, n-BMS with 12-channel CMUs,
c-BMS24, c-BMS24X and i-BMS15. Historical Sensata branding is kept within the same
product identity. Lithium Balance's [ownership announcement](https://lithiumbalance.com/lithium-balance-a-s-departs-from-sensata-technologies-ownership-and-continues-as-an-independent-global-supplier-of-battery-management-systems/)
does not establish a new product launch.

The total accepted component library becomes **176 records / 871 observations**.
Battery counts stay at 3,454 accepted products; the 110 previously held battery
records are unchanged. The separate weekly Schaltbau candidates are not promoted
by this BMS review.

## Dates and present market status

- **c-BMS24X:** 17 May 2023 is a [launch announcement](https://www.sensata.com/contact/newsroom/sensata-technologies-launches-c-bms24x-battery-management-system), not proven first shipment.
- **Lithiumate Pro / HD:** the [manufacturer comparison](https://www.elithion.com/lithiumate_controllers.php)
  gives release years **2007 / 2015**. The records retain year precision. Elithion's
  [current notice](https://www.elithion.com/index.php) limits new-system availability:
  both are marked **legacy support only**.
- **Nuvation G5:** its [shipping article](https://nuvationenergy.com/news/nuvation-energys-made-in-us-and-canada-g5-battery-management-system-for-energy-storage-begins-volume-shipping/)
  disagrees between a 25 March 2024 header and a 26 March 2023 body dateline.
  Release status is **conflicting**, with both texts retained.
- **Nuvation G5 Plus:** [evaluation units are planned for 2027](https://nuvationenergy.com/battery-management-systems/g5-plus-high-voltage-bms/).
  The product is marked **announced**, not currently released. The voltage is a
  stated design capability, not independent verification of shipped hardware.
- n3-BMS and i-BMS announcement evidence is retained separately. The n3-BMS
  historical “early 2023” availability plan stays imprecise; no January 1 date is created.
- Enepaq datasheet revisions dated 17 August 2026 are document events only.
  The other original releases remain **not established** in the inspected sources.

There are 21 manufacturer-listed records, one announced record and two legacy
records. “Manufacturer-listed” records the state observed on the cited page; it
is not a stock check. A release field exists for every BMS, including explicit
unknowns. Three have dated release/launch evidence, one has conflicting evidence
and 20 have no verified original release date.

## Technical interpretation

- BMS pack-voltage support is separate from auxiliary supply voltage, insulation
  withstand and an attached shunt's voltage rating.
- Series-channel limits retain whole-system, controller and configured-module
  scope. Orion's 180-channel main-unit limit is distinct from its expanded
  system's 800 V limit. Cell banks are not cell counts.
- Enepaq CAN/Bluetooth adapters and the Orion Jr 2 CAN option are explicit;
  neither becomes an assumed native CAN port.
- Lithium Balance PDF/web current and mass conflicts, the n-BMS MCU ordering-code
  disagreement, and unconstrained switch currents are omitted as numeric claims.
- BMS balancing and charge/discharge power paths are different. Datasheets remain
  linked; proprietary document bodies are not committed. Nine PDFs were retrieved
  and hashed; unavailable original bytes are explicitly left without a hash.

## Data structure and database upgrade

Every record uses the existing contribution pipeline:

```text
product.component_type = bms
bms = identity_scope, architecture, balancing, interfaces, locator, note
lifecycle = checked_at, market_status, market_evidence, release, events
observations = quantities with native units, scope and source locators
```

`lifecycle.release` is `documented`, `not_found` or `conflicting`. A documented
release carries an event type, original date precision and evidence URL/locator.
Announcements, planned availability, volume shipping and document revisions can
be retained as other events. The validator rejects impossible dates, mismatched
precision, future observed events and a document revision used as a release.

The PostgreSQL loader stores the complete evidence in
`bd.product_revision.lifecycle_evidence` and `bms_details`. It does not coerce a
partial year or announcement into `bd.product.first_released`. JSON exports,
the generated GitHub comparison and the web specification/Markdown view retain
these details.

Fresh installations use the normal schema. Existing installations should apply
`migrations/2026-10-09-bms-lifecycle.sql` before loading BMS records. The migration
is additive for data and can be rerun; it is exercised on a disposable database
in CI. No production database or Lemonergy hosted API was changed by this batch.

## Review and continuation

The [acceptance audit](../review/audits/2026-10-11-bms-acceptance.json) records
source/identity review, held fields and the exact accepted bytes. The
[coverage backlog](../components/bms-coverage.json) records additional families
and manufacturers to inspect. The existing weekly research instructions now
include BMS as the eighth component category; no second automation is created.

Maintained by **Lemonergy** · [Data tools](https://lemonergy.com/data/) · Free source data on GitHub.
