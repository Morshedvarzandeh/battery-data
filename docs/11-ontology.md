# Ontology and knowledge-graph alignment

Compatibility means three concrete things here, and each has a generated
artefact behind it:

1. **Every term resolves to a published IRI.** `bd.quantity.emmo_iri`,
   `bd.quantity.qudt_quantity_kind` and `bd.unit.qudt_iri` are populated by
   `schema/175_vocabulary_bindings.sql`, which `tools/sync_vocabularies.py`
   generates from the ontologies themselves. The curated input holds labels,
   never IRIs (`vocab/bindings.json`); the indexes it resolves against are
   committed with the source version and hash (`vocab/emmo-index.json`,
   `vocab/qudt-index.json`); the result is committed too
   (`vocab/resolved.json`, `json-schema/quantity-iris.json`).
2. **The library is available as RDF.** `tools/export_rdf.py` writes
   `rdf/battery-data.ttl` from `contrib/` (JSON-LD with `--jsonld`). It loads
   into any triple store and answers SPARQL without translation. CI checks
   it is current.
3. **The graph projection covers the whole scope.** `bd_graph.node` and
   `bd_graph.edge` now carry applications, certifications, offers,
   component kinds and chemistry families alongside products, revisions,
   materials, tests and sources; `tools/export_graph.py` writes them for
   Neo4j and `tools/load_age.py` populates Apache AGE.

---

## Which vocabulary carries what

| Concept here | External vocabulary | Term | Fidelity |
|---|---|---|---|
| Product | schema.org | `schema:Product` with `schema:manufacturer`, `schema:model`, `schema:alternateName` | exact |
| Product kind | EMMO domain-battery | `BatteryCell`, `BatteryModule`, `BatteryPack`, `BatterySystem`, `PrimaryBattery` | exact |
| Component kinds | none | `bdv:componentKind` literal | EMMO has no contactor, fuse or BMS class |
| Form factor | EMMO domain-battery | `CylindricalBattery`, `PouchCell`, `PrismaticBattery`, `CoinCell` | close |
| Chemistry family | EMMO domain-battery | `LithiumIonBattery`, `LeadAcidBattery`, `SodiumIonBattery`, `NickelMetalHydrideBattery`, `VanadiumRedoxFlowBattery`, … | exact |
| Chemistry designation | EMMO domain-battery | `LithiumIonIronPhosphateBattery`, `LithiumIonNickelManganeseCobaltOxideBattery`, … | close |
| Product revision | EMMO domain-battery, PROV-O | `BatteryCellSpecification` (per kind), `prov:Entity` | exact |
| Manufacturer | schema.org, EMMO | `schema:Organization`, `Manufacturer` | exact |
| Source document | schema.org, PROV-O | `schema:CreativeWork`, `prov:Entity`, `schema:url`, `dcterms:title` | exact |
| Observation | SOSA/SSN | `sosa:Observation`, `sosa:hasFeatureOfInterest` (the revision), `sosa:observedProperty`, `sosa:hasResult` | exact |
| Observed property | EMMO | the quantity's class; per statistic where EMMO distinguishes (`NominalCapacity`, `RatedCapacity`, `TypicalCapacity`, `MinimumCapacity`, `MaximumCapacity`, `NominalEnergy`, `RatedEnergy`) | see `crosswalk/CROSSWALK.md` for each relation |
| Result | QUDT | `qudt:QuantityValue` with `qudt:numericValue`, `qudt:unit`, `qudt:hasQuantityKind` | exact |
| Conditions | none | `bdv:ConditionSet` with one property per condition column, `bdv:unstated` for declared absence | no public vocabulary carries measurement conditions at this granularity |
| Provenance | PROV-O | `prov:wasDerivedFrom` a `bdv:SourceLocation` (`bdv:page`, `bdv:section`, `bdv:quote`, `prov:wasQuotedFrom` the source); `prov:wasAttributedTo` the manufacturer for a manufacturer claim | exact |
| Curves | SOSA, local | `sosa:Observation` typed `bdv:Curve` with axis quantities and JSON value arrays | approximate: SOSA has no array result |
| Applications | schema.org, local | `schema:Thing` typed `bdv:Application`; `bdv:Deployment` carries basis and confidence | approximate |
| Certifications, assemblies, equivalences | local | `bdv:Certification`, `bdv:Assembly`, `bdv:Equivalence` | none published |

The `bdv:` namespace is `https://github.com/Morshedvarzandeh/battery-data/vocab#`;
individuals live under `https://github.com/Morshedvarzandeh/battery-data/id/`.
Every local term is documented by its use in `rdf/battery-data.ttl`; a term
is local only where the survey above found nothing to reuse.

## Where the mapping is only approximate

- **Broader relations.** `rated_power` maps to EMMO `Power`, `ohmic_resistance`
  to `ElectricResistance`, `discharge_cutoff_voltage` to `VoltageLimit`. The
  crosswalk records these as `broader`; a reasoner must not treat them as
  equivalences. `skos:broadMatch` is emitted for them, `skos:exactMatch` only
  for `exact` rows.
- **Temperature.** Stored in kelvin as SI, quoted in Celsius by every
  source; the axis quantity binds to `CelsiusTemperature` as `close`.
- **Thermal conductivity.** EMMO's is scalar; ours is a tensor component
  (`narrower`).
- **QUDT gaps.** No quantity kind for the entropic coefficient or dV/dQ, no
  milliwatt-hour or millivolt-per-kelvin unit. Recorded as null, never
  approximated by a neighbouring unit.
- **EMMO label collisions.** `StateOfCharge` is defined in both the battery
  and the electrochemistry domain; `NickelZincBattery` and `PrismaticBattery`
  twice in the battery domain. The index prefers the battery namespace, then
  the lexically smallest IRI, and keeps every alternative under `also`.

## Graph projection

| Node label | From | Edge | Meaning |
|---|---|---|---|
| Organization, Product, ProductRevision, ProductUnit | bd.organization, product, product_revision, product_unit | MANUFACTURES, HAS_REVISION, INSTANCE_OF, SUPERSEDES | identity split |
| Source | bd.source | DOCUMENTED_BY, EVIDENCED_BY | every fact to its document |
| Material | bd.material | USES_MATERIAL, SUPPLIED_BY | bill of materials and supply chain |
| Application | bd.application | FIELDED_IN (from a revision, a product or a brand family) | where it is used, at the source's granularity |
| Certification | bd.certification | HOLDS_CERTIFICATION, CERTIFIED_TO | claims with scope and status |
| Protocol, Standard, TestRun, Campaign, Dataset | test layer | FOLLOWS_PROTOCOL, IMPLEMENTS_STANDARD, TESTED, PRODUCED | measurement chain |
| Model | bd.model_parameterisation | PARAMETERISES, FITTED_FROM | published parameter sets against their cell |
| (edge only) | bd.product_assembly, product_offer, product_equivalence | CONTAINS, OFFERED_BY, EQUIVALENT_TO | assembly, market, equivalence |

Product nodes carry `component_kind`; revision nodes carry `chemistry`,
`family` and `construction`, so a Cypher query can walk from a grid
container to the chemistry family of every cell in it.

```sql
-- every product that transitively contains a given cell revision
SELECT * FROM bd_graph.reachable('rev:12', ARRAY['CONTAINS'], 6, 'in');
```

```bash
python tools/export_graph.py batterydb          # graph/nodes.csv, edges.csv, load.cypher
python tools/load_age.py --dsn dbname=batterydb # when the AGE extension is installed
python tools/export_rdf.py --jsonld             # rdf/battery-data.ttl and .jsonld
```

## SPARQL, as a check that it works

```sparql
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX bdv:  <https://github.com/Morshedvarzandeh/battery-data/vocab#>
SELECT ?cell ?ah ?rate WHERE {
  ?obs a sosa:Observation ; bdv:quantity bdv:q_capacity ;
       sosa:hasFeatureOfInterest ?rev ; sosa:hasResult ?r ; bdv:conditions ?c .
  ?r qudt:numericValue ?ah . ?c bdv:rate_value ?rate .
  ?rev bdv:revisionOf ?cell .
  FILTER(?ah > 200)
}
```
