# Sodium-ion, semi-solid and lithium cell expansion — 21 September 2026

> Publication update, 4 October: reviewed records have now been promoted.
> This report preserves the research-stage counts and decisions. See the
> [acceptance report](../../docs/16-catalog-publication-2026-10-04.md) for current counts and remaining holds.

**32 additional pending cell entries / 262 observations**, based on 35 hashed evidence files. No accepted records are changed or counted as new.

| Manufacturer | Added cells | Scope |
|---|---:|---|
| HiNa Battery | 4 | Sodium-ion: MP10, HE240, NE170, MP200 |
| WeLion | 10 | NMC+ semi-solid pouch cells; two explicitly marked TRIAL |
| LG Energy Solution | 8 | NCMA, NCM and LFP cells from the public cell specification sheet |
| EVE Energy | 3 | LFP: LF206, LF235L and MB30 |
| CATL | 2 | Public 314Ah and 587Ah LFP ESS cell designations |
| CALB | 5 | L173F314; ZHIJIU 392Ah/588Ah/661Ah; 684Ah showcase |

26 entries have named model codes; six CATL/CALB entries use the manufacturer’s published capacity-based cell designations. Those six do not establish orderable part numbers. CALB launch/showcase records are intentionally sparse; exact cathode chemistry is unreported for four entries.

After this batch: **2,170 accepted battery products and 1,394 pending battery products**. The separate component queue remains **146 pending models**. This brings the combined pending queue to **1,540**; components never increase battery counts.

## Evidence and structure

- Every numeric observation retains its source page or section, original units, rating label where supplied, qualifiers and an excerpt. Missing test conditions are explicitly declared `unstated`.
- Quoted C-rates retain a descriptive reference explaining that the numerical capacity basis is not stated. `rate_reference_capacity_ah` stays explicitly unstated; these C-rates are not converted to amperes.
- Manufacturer statements remain claims. Neither a launch announcement nor a regulatory citation is presented as an independent performance measurement.
- `chemistry.designation` records sodium-ion or the stated cathode family. WeLion’s `NMC+` is separate from `chemistry.electrolyte_text = Semi-Solid-State`; no all-solid-state classification or unreported anode is invented.
- The database importer now retains `electrolyte_text`, `separator_text` and the chemistry locator. Legacy chemistry without a locator still uses whole-source provenance. Web exports retain the electrolyte locator when present. Existing ingested files are not automatically backfilled by this change.
- The contribution schema now accepts `regulatory_filing`, already supported by the database and importer, so CALB’s public docket evidence keeps its correct source type.
- Source bodies stay outside Git. The [manifest](2026-09-21-sodium-semisolid-lithium-cells.json) stores facts, source URLs, SHA-256 hashes, aliases and reasons for omitted values. `retrieved_at` is distinct from a printed publication date.
- WeLion sheets are hosted by its official European distributor, Universal Transmissions GmbH. That publisher is disclosed in source notes. Product-page hashes support the PL-code aliases; separate article/shop codes are not counted as cells.
- PDF page numbers are one-based file pages. CATL file page 9 spans printed pages 15–16. CALB file page 114 is HMA printed page 12. The CALB HMA is watermarked DRAFT; its record is marked preliminary.

## Decisions that prevent misleading comparisons

- **LG:** JP3 uses a 0.5C minimum-capacity claim, while M50L/M52V use nominal reference capacities at 0.2C. The common header supplies 25°C. E72B says Graphite+SiO. JF2/JH4 voltage fields and JH4 dimension axes are held. No voltage is computed from Wh/Ah.
- **CATL:** The 314Ah row says ≥7,000 cycles even though a general headline says >8,000. Both added cells specify 0.5P/0.5P, 25°C and 70% SOH; depth of discharge and the definition of SOH are not stated. P is retained as constant-power rate.
- **HiNa:** HE240 and NE170 life claims use P; MP10 and MP200 use C. Strict greater-than signs are retained in excerpts and `conditions.extra.source_comparator`. General working temperatures are not promoted into charging guarantees. MP10’s pulse-event lifetime is not imported as full-cycle life.
- **WeLion:** Typical capacity, energy, dimensional/mass tolerances and directional temperatures survive. Standard C-rate rows are not assigned to capacity tests. “Ultrafast” rates are not converted to continuous current limits. SHP350 sheets retain their TRIAL suffixes and printed revisions/dates.
- **EVE:** LF206 specifies 1C charge/0.5C discharge for life testing. LF235L’s life graphic is mislabelled LF356L, so the separate model-specific table provides the cycle count without borrowing the graphic’s test conditions. Bare initial IR is held because AC/DC method is unspecified.
- **CALB:** L173F314 is 3.2 V per cell; the 332.8 V figure belongs to a module. The 684Ah showcase’s 6.8MWh+ figure belongs to a container and is excluded. ZHIJIU life figures keep unknown test conditions rather than inheriting conditions from another product.

## Existing identities and held evidence

Existing accepted and pending files were checked alongside the four SQL reference cells. LG M50L is held as a potential short designation of the seeded INR21700-M50LT: the nominal voltage/energy agree, but the public summary does not establish whether it is a separate physical part. Its full transcription remains in the manifest, outside the new-cell count. EVE MB31 and LF280K, CATL’s two sodium-ion entries and 280Ah ESS entry, and HiTHIUM’s N162Ah are not counted again. A manufacturer revision is not automatically a new cell identity.

EVE C46M-V1/V2 are held because their LFP descriptions and 3.6 V nominal-voltage ratings require reconciliation. CALB’s generic 314Ah Gen2.0 showcase is held because its relationship to L173F314 is unresolved. All field-level omissions are listed in the manifest.

## New records

| Manufacturer | Model | Specifications | Evidence level |
|---|---|---|---|
| CALB | [684Ah ESS cell](../candidates/calb/684ah-ess-cell.yaml) | 2 | Manufacturer launch/showcase |
| CALB | [L173F314](../candidates/calb/l173f314.yaml) | 2 | Draft regulatory appendix |
| CALB | [ZHIJIU 392Ah long-cycle ESS cell](../candidates/calb/zhijiu-392ah-long-cycle-ess-cell.yaml) | 3 | Manufacturer launch/showcase |
| CALB | [ZHIJIU 588Ah long-cycle ESS cell](../candidates/calb/zhijiu-588ah-long-cycle-ess-cell.yaml) | 3 | Manufacturer launch/showcase |
| CALB | [ZHIJIU 661Ah long-cycle ESS cell](../candidates/calb/zhijiu-661ah-long-cycle-ess-cell.yaml) | 3 | Manufacturer launch/showcase |
| CATL | [314Ah LFP ESS cell](../candidates/catl/314ah-lfp-ess-cell.yaml) | 3 | datasheet |
| CATL | [587Ah LFP ESS cell](../candidates/catl/587ah-lfp-ess-cell.yaml) | 3 | datasheet |
| EVE Energy | [LF206](../candidates/eve/lf206.yaml) | 8 | manufacturer web |
| EVE Energy | [LF235L](../candidates/eve/lf235l.yaml) | 11 | manufacturer web |
| EVE Energy | [MB30](../candidates/eve/mb30.yaml) | 4 | manufacturer web |
| HiNa Battery | [HE240](../candidates/hina-battery/he240.yaml) | 6 | manufacturer web |
| HiNa Battery | [MP10](../candidates/hina-battery/mp10.yaml) | 6 | manufacturer web |
| HiNa Battery | [MP200](../candidates/hina-battery/mp200.yaml) | 6 | manufacturer web |
| HiNa Battery | [NE170](../candidates/hina-battery/ne170.yaml) | 6 | manufacturer web |
| LG Energy Solution | [E101A](../candidates/lg-energy-solution/e101a.yaml) | 9 | datasheet |
| LG Energy Solution | [E72B](../candidates/lg-energy-solution/e72b.yaml) | 9 | datasheet |
| LG Energy Solution | [E79](../candidates/lg-energy-solution/e79.yaml) | 9 | datasheet |
| LG Energy Solution | [JF1](../candidates/lg-energy-solution/jf1.yaml) | 9 | datasheet |
| LG Energy Solution | [JF2](../candidates/lg-energy-solution/jf2.yaml) | 8 | datasheet |
| LG Energy Solution | [JH4](../candidates/lg-energy-solution/jh4.yaml) | 5 | datasheet |
| LG Energy Solution | [JP3](../candidates/lg-energy-solution/jp3.yaml) | 9 | datasheet |
| LG Energy Solution | [M52V](../candidates/lg-energy-solution/m52v.yaml) | 8 | datasheet |
| WeLion | [SHP270-16](../candidates/welion/shp270-16.yaml) | 13 | datasheet |
| WeLion | [SHP270-22](../candidates/welion/shp270-22.yaml) | 13 | datasheet |
| WeLion | [SHP270-27](../candidates/welion/shp270-27.yaml) | 13 | datasheet |
| WeLion | [SHP270-30](../candidates/welion/shp270-30.yaml) | 13 | datasheet |
| WeLion | [SHP320-20](../candidates/welion/shp320-20.yaml) | 13 | datasheet |
| WeLion | [SHP320-25](../candidates/welion/shp320-25.yaml) | 13 | datasheet |
| WeLion | [SHP320-32](../candidates/welion/shp320-32.yaml) | 13 | datasheet |
| WeLion | [SHP320-35](../candidates/welion/shp320-35.yaml) | 13 | datasheet |
| WeLion | [SHP350-30-TRIAL](../candidates/welion/shp350-30-trial.yaml) | 13 | Trial datasheet |
| WeLion | [SHP350-40-TRIAL](../candidates/welion/shp350-40-trial.yaml) | 13 | Trial datasheet |

## Inspected evidence

| Evidence | Role | Original source |
|---|---|---|
| CALB ZHIJIU long-cycle energy-storage cell launch at ESIE 2026 | specifications | [Open source](https://www.calb-tech.com/newsDetails/25.html) |
| Prairie Song Reliability Project — Data Request Response 2 Part 6; BESS HMA Rev B | specifications | [Open source](https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=103666&tn=266609) |
| CALB current product showcase — 684Ah energy-storage cell | specifications | [Open source](https://www.calb-tech.com/) |
| CATL energy storage solutions and products — LFP cell parameters | specifications | [Open source](https://www.catl.com/uploads/1/file/public/202604/20260409212143_f2npbuioci.pdf) |
| EVE C46M-V1 investigated product page | held | [Open source](https://www.evemall.eu/power-battery/cylindrical-lfp-cell/c46m1) |
| EVE C46M-V2 investigated product page | held | [Open source](https://www.evemall.eu/power-battery/cylindrical-lfp-cell/c46m2) |
| EVE Energy LF206 product specifications | specifications | [Open source](https://www.evemall.eu/power-battery/prismatic-lfp-cell/lf206) |
| EVE Energy LF235L product specifications | specifications | [Open source](https://www.evemall.eu/power-battery/prismatic-lfp-cell/lf235l) |
| EVE MB31 vs. MB30 vs. 280K-V3 in Commercial ESS | specifications | [Open source](https://www.evemall.eu/selection-guide/eve-mb31-vs-mb30-vs-280k-v3-commercial-ess) |
| HiNa HE240 sodium-ion cell specification slide | specifications | [Open source](https://www.hinabattery.com/data/upload/image/20251101/1761960297460023.png) |
| HiNa NE170 sodium-ion cell specification slide | specifications | [Open source](https://www.hinabattery.com/data/upload/image/20251101/1761960340685001.png) |
| HiNa MP200 sodium-ion cell specification slide | specifications | [Open source](https://www.hinabattery.com/data/upload/image/20251101/1761960356537762.png) |
| HiNa MP10 sodium-ion cell specification slide | specifications | [Open source](https://www.hinabattery.com/data/upload/image/20251101/1761960446647304.png) |
| HiNa — Sodium-Ion Batteries Enter the Commercial Era | context_only | [Open source](https://www.hinabattery.com/en/index.php?id=77) |
| LG Energy Solution — Cell Solutions for Powerful EV Performance | specifications | [Open source](https://www.lgensol.com/assets/file/LGES_spec_sheet_cells_2024.pdf) |
| WeLion SHP270-16 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/fb/ef/b0/1730133629/SHP270-16%20datasheet.pdf?ts=1744633054) |
| WeLion SHP270-16 identity page | identity_only | [Open source](https://welion-energy.com/SHP270-16/30000109) |
| WeLion SHP270-22 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/11/5d/0c/1730133512/SHP270-22%20datasheet.pdf?ts=1744633076) |
| WeLion SHP270-22 identity page | identity_only | [Open source](https://welion-energy.com/SHP270-22/30000110) |
| WeLion SHP270-27 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/fd/9f/6d/1730133270/SHP270-27%20datasheet.pdf?ts=1744633120) |
| WeLion SHP270-27 identity page | identity_only | [Open source](https://welion-energy.com/SHP270-27/30000111) |
| WeLion SHP270-30 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/18/4d/f1/1730133143/SHP270-30%20datasheet.pdf?ts=1744633138) |
| WeLion SHP270-30 identity page | identity_only | [Open source](https://welion-energy.com/SHP270-30/30000112) |
| WeLion SHP320-20 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/8f/ba/05/1730132824/SHP320-20%20datasheet.pdf?ts=1744633185) |
| WeLion SHP320-20 identity page | identity_only | [Open source](https://welion-energy.com/SHP320-20/30000105) |
| WeLion SHP320-25 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/07/1a/f0/1730132707/SHP320-25%20datasheet.pdf?ts=1744633210) |
| WeLion SHP320-25 identity page | identity_only | [Open source](https://welion-energy.com/SHP320-25/30000106) |
| WeLion SHP320-32 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/9b/92/ca/1730132597/SHP320-32%20datasheet.pdf?ts=1744633235) |
| WeLion SHP320-32 identity page | identity_only | [Open source](https://welion-energy.com/SHP320-32/30000107) |
| WeLion SHP320-35 Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/1e/02/33/1730132463/SHP320-35%20datasheet.pdf?ts=1744633262) |
| WeLion SHP320-35 identity page | identity_only | [Open source](https://welion-energy.com/SHP320-35/30000108) |
| WeLion SHP350-30-TRIAL Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/3a/98/71/1782371864/SHP350-30-TRIAL_datasheet1.pdf?ts=1782371864) |
| WeLion SHP350-30-TRIAL identity page | identity_only | [Open source](https://welion-energy.com/SHP350-30/30000170) |
| WeLion SHP350-40-TRIAL Semi-Solid-State datasheet | specifications | [Open source](https://welion-energy.com/media/4c/a6/07/1782223390/SHP350-40-TRIAL_datasheet%202.pdf?ts=1782223390) |
| WeLion SHP350-40-TRIAL identity page | identity_only | [Open source](https://welion-energy.com/SHP350-40/30000171) |

## Reproduce and validate

```sh
python3 tools/import_chemistry_cells.py --check
# Optional: verify the exact original files already held outside the repository
python3 tools/import_chemistry_cells.py --check --source-dir /path/to/evidence
python3 tools/build_review_batch.py
python3 tools/render_review_issues.py
python3 tools/validate_contrib.py contrib/
python3 tools/validate_contrib.py review/candidates/
python3 tools/validate_review.py
python3 tools/check_duplicates.py
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_web_observations.cjs
```

CI additionally promotes all 32 cells and their 262 observations in a disposable PostgreSQL transaction, verifies chemistry/electrolyte provenance, mixed C/P rates, LG nominal/minimum distinctions and the CALB cell/module boundary, then rolls back all test records. Candidates remain pending throughout.
