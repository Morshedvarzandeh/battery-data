# Semi-solid cell source review for a boat design comparison

Reviewed 11 October 2026. The purpose is to support a reproducible engineering
comparison, with missing model inputs visible before a simulation is published.

The library already contains eight accepted [WeLion semi-solid models](../catalog/manufacturers/welion.md).
They remain valid source records. Their public summary sheets do not establish
the DC resistance or continuous current limits required for a complete pack model.
The existing omissions are preserved; adding the same cells again would not close
that modeling gap.

## Added source record

[DSEnergy DSE1175175-30Ah](../contrib/cells/dsenergy/dse1175175-30ah.yaml)
adds 19 observations from the [supplier's exact product page](https://dsnrg.com/product/dsenergy-30ah-3-7v-350wh-kg-semi-solid-battery-cell/).
The source identifies the branded cell and describes continuous discharge,
voltage limits, directional operating temperatures and body dimensions explicitly.
Acceptance confirms the transcription and identity; it does not establish a
measured performance result, factory identity or marine approval.

| Parameter | Source value | Qualification |
|---|---:|---|
| Nominal / minimum capacity | 30 / 29 Ah | 0.2C discharge; test temperature and capacity-test cutoff are unstated |
| Nominal voltage | 3.7 V | NCM cathode; semi-solid technology label |
| Nominal energy | 111 Wh | Supplier calculation, not measured delivered energy |
| Continuous discharge | 150 A | Rating temperature unstated |
| Charge / discharge cutoff | 4.25 / 2.5 V | Described operating endpoints |
| Charge / discharge temperatures | 0–45 / −20–60 °C | Temperature reference unstated |
| AC resistance | ≤2 mΩ | Frequency, SOC and temperature unstated; not DC resistance |
| Body thickness × width × length | ≤11 × ≤75 × ≤175 mm | Excludes exposed tabs and installation allowance |
| Mass | Approximately 308 g | Reference value without a tolerance |

The source's 350 Wh/kg rating and its separately stated approximate mass and
calculated energy do not exactly reconcile. The record keeps those claims
separate instead of modifying one to make the arithmetic agree.

## Simulation boundary

The supplier does not publish DC resistance, an OCV curve or heat capacity on
this page. Charging C-rates describe protocols, not a stated maximum continuous
charge rating. A pulse C-rate also requires an explicit capacity basis before it
can become a qualified amperage limit. These missing inputs must not be filled
with invented manufacturer data.

A runnable screening model may use clearly named engineering assumptions and
sensitivity ranges for its missing inputs. Such parameters belong to the
simulation case, not this source record. The result must distinguish assumed
behavior from supplier specifications and must not imply marine certification.

The current page supplies no printable revision date or linked full datasheet.
The original HTML was retrieved and hashed; its body is not redistributed.
The [review audit](../review/audits/2026-10-11-dsenergy-semisolid-marine.json)
records the source identity, acceptance reasoning and validation. The existing
batch builder and contribution schema are unchanged.
