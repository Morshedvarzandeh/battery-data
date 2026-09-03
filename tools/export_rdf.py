#!/usr/bin/env python3
"""Emit the accepted library as RDF, so a triple store loads it unchanged.

Ontology and knowledge-graph compatibility is not a column of IRIs; it is
being able to hand the whole library to a SPARQL endpoint, a graph database
or a reasoner without translation. This writes Turtle (and, with --jsonld,
JSON-LD) from contrib/ and the generated bindings, using vocabularies that
already exist rather than a private one where a public one fits:

    sosa:Observation            each stated value, with its feature of
                                interest (the product revision), its observed
                                property (the EMMO class, per statistic where
                                EMMO has one) and a qudt:QuantityValue result
    qudt:unit / qudt:hasQuantityKind
                                the unit and quantity kind, verified IRIs
    prov:wasDerivedFrom         the source location: page, section, quote
    prov:wasAttributedTo        the manufacturer, for a manufacturer claim
    schema:Product / schema:Organization / schema:CreativeWork
                                the product, its maker and its document
    EMMO / BattINFO classes     the product kind, form factor, chemistry
                                family and designation, the specification
    bdv:                        this schema's own terms, for what no public
                                vocabulary carries: the condition set and its
                                columns, declared absence, the statistic,
                                evidence class, curves, bill of materials

Deterministic: same input, same bytes, so CI can check the committed file.

    python tools/export_rdf.py                 # writes rdf/battery-data.ttl
    python tools/export_rdf.py --check         # CI: the file is current
    python tools/export_rdf.py --jsonld        # also rdf/battery-data.jsonld
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IRIS = os.path.join(ROOT, "json-schema", "quantity-iris.json")
OUT_TTL = os.path.join(ROOT, "rdf", "battery-data.ttl")
OUT_JSONLD = os.path.join(ROOT, "rdf", "battery-data.jsonld")

BASE = "https://github.com/Morshedvarzandeh/battery-data/"
ID = BASE + "id/"
VOCAB = BASE + "vocab#"

PREFIXES = {
    "bdv": VOCAB,
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/",
    "prov": "http://www.w3.org/ns/prov#",
    "sosa": "http://www.w3.org/ns/sosa/",
    "qudt": "http://qudt.org/schema/qudt/",
    "quantitykind": "http://qudt.org/vocab/quantitykind/",
    "unit": "http://qudt.org/vocab/unit/",
    "schema": "https://schema.org/",
    "emmo": "https://w3id.org/emmo#",
    "battery": "https://w3id.org/emmo/domain/battery#",
    "echem": "https://w3id.org/emmo/domain/electrochemistry#",
}

# Condition columns exported as bdv: properties. Everything else in a
# condition block (extra, verbatim) is kept as a JSON literal.
CONDITION_KEYS = [
    "temperature_c", "temperature_reference", "rate_value", "rate_unit",
    "rate_reference_capacity_ah", "rate_reference_source", "direction",
    "voltage_upper_v", "voltage_lower_v", "soc_pct", "soc_method", "dod_pct",
    "pulse_duration_s", "pulse_current_a", "frequency_hz", "rest_before_s",
    "cycle_index", "duration_s", "constraint_mode", "clamp_force_n", "boundary",
    "load_value", "load_unit", "duty_schedule", "cutoff_voltage_v", "area_cm2",
    "area_kind", "circuit_voltage_v", "time_constant_ms",
]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def lit(value) -> str:
    """A Turtle literal for a Python value."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        r = repr(value)
        if "e" in r or "E" in r:
            return f'"{r}"^^xsd:double'
        return r if "." in r else r + ".0"
    s = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    return f'"{s}"'


def iri(s: str) -> str:
    return "<" + s.replace(" ", "%20").replace('"', "%22").replace("<", "%3C").replace(">", "%3E") + ">"


def curie(full: str) -> str:
    """Prefixed name where a prefix applies and the local part is safe."""
    for prefix, ns in PREFIXES.items():
        if full.startswith(ns):
            local = full[len(ns):]
            if local and all(ch.isalnum() or ch in "_-." for ch in local) and not local[0].isdigit() \
                    and not local.endswith("."):
                return f"{prefix}:{local}"
    return iri(full)


def slug(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in str(s).lower()).strip("-")


class Writer:
    def __init__(self):
        self.lines: list[str] = []

    def block(self, subject: str, pairs: list[tuple[str, str]]):
        """One subject, its predicate-object pairs, deterministic order as given."""
        if not pairs:
            return
        self.lines.append(subject)
        for i, (p, o) in enumerate(pairs):
            end = " ." if i == len(pairs) - 1 else " ;"
            self.lines.append(f"    {p} {o}{end}")
        self.lines.append("")


def bnode(pairs: list[tuple[str, str]]) -> str:
    inner = " ; ".join(f"{p} {o}" for p, o in pairs)
    return f"[ {inner} ]"


def conditions_node(cond: dict, unstated: list) -> str:
    pairs = [("rdf:type", "bdv:ConditionSet")]
    for key in CONDITION_KEYS:
        if cond.get(key) is not None:
            pairs.append((f"bdv:{key}", lit(cond[key])))
    for u in unstated or []:
        pairs.append(("bdv:unstated", lit(u)))
    if cond.get("extra"):
        pairs.append(("bdv:extra", lit(json.dumps(cond["extra"], sort_keys=True))))
    if cond.get("verbatim"):
        pairs.append(("bdv:verbatim", lit(cond["verbatim"])))
    return bnode(pairs)


def location_node(loc: dict, source_iri: str) -> str:
    pairs = [("rdf:type", "bdv:SourceLocation"), ("prov:wasQuotedFrom", source_iri)]
    if loc.get("page") is not None:
        pairs.append(("bdv:page", lit(loc["page"])))
    if loc.get("section"):
        pairs.append(("bdv:section", lit(loc["section"])))
    if loc.get("quote"):
        pairs.append(("bdv:quote", lit(loc["quote"])))
    return bnode(pairs)


EVIDENCE = {"datasheet": "manufacturer_claim", "manufacturer_web": "manufacturer_claim",
            "distributor_listing": "manufacturer_claim", "regulatory_filing": "manufacturer_claim",
            "third_party_test": "measured", "teardown_report": "measured", "dataset": "measured",
            "journal_article": "literature_reported", "preprint": "literature_reported"}


def export(products: list[tuple[str, dict]], iris: dict) -> str:
    w = Writer()
    w.lines.append("# battery-data: the accepted library as RDF. GENERATED by tools/export_rdf.py;")
    w.lines.append("# edit the contributions under contrib/, never this file.")
    w.lines.append("")
    for prefix, ns in PREFIXES.items():
        w.lines.append(f"@prefix {prefix}: <{ns}> .")
    w.lines.append("")

    q_iris, classes = iris["quantities"], iris["classes"]
    unit_iris = iris["units"]
    orgs_done, sources_done, quantities_done, units_done = set(), set(), set(), set()

    # local quantity and unit terms, once each, with their bindings
    for code in sorted(q_iris):
        b = q_iris[code]
        pairs = [("rdf:type", "bdv:Quantity"), ("skos:notation", lit(code))]
        if b.get("emmo_iri"):
            rel = {"exact": "skos:exactMatch", "close": "skos:closeMatch",
                   "broader": "skos:broadMatch", "narrower": "skos:narrowMatch",
                   "related": "skos:relatedMatch"}.get(b.get("emmo_relation"), "skos:relatedMatch")
            pairs.append((rel, curie(b["emmo_iri"])))
        if b.get("qudt_quantity_kind"):
            pairs.append(("qudt:hasQuantityKind", curie(b["qudt_quantity_kind"])))
        w.block(f"bdv:q_{code}", pairs)
    for symbol in sorted(unit_iris):
        pairs = [("rdf:type", "qudt:Unit"), ("qudt:symbol", lit(symbol))]
        if unit_iris[symbol]:
            pairs.append(("owl:sameAs", curie(unit_iris[symbol])))
        w.block(f"bdv:unit_{slug(symbol) or 'one'}", pairs)

    for path, doc in products:
        p, src = doc["product"], doc.get("source") or {}
        chem = doc.get("chemistry") or {}
        uid = p["uid"]
        product_iri = iri(ID + uid)
        maker_slug = uid.split("/")[1]
        org_iri = iri(ID + "org/" + maker_slug)
        label = src.get("revision") or src.get("document_date") or "unversioned"
        rev_iri = iri(ID + f"rev/{maker_slug}/{uid.split('/', 2)[2]}/{slug(label)}")
        source_iri = iri(ID + src["uid"])
        evidence = EVIDENCE.get(src.get("kind"), "manufacturer_claim")

        if maker_slug not in orgs_done:
            pairs = [("rdf:type", "schema:Organization"), ("schema:name", lit(p["manufacturer"]))]
            if iris.get("organization"):
                pairs.insert(1, ("rdf:type", curie(iris["organization"])))
            w.block(org_iri, pairs)
            orgs_done.add(maker_slug)

        if src["uid"] not in sources_done:
            pairs = [("rdf:type", "schema:CreativeWork"), ("rdf:type", "prov:Entity"),
                     ("rdf:type", "bdv:Source"), ("bdv:sourceKind", lit(src.get("kind")))]
            for key, pred in (("title", "dcterms:title"), ("url", "schema:url"),
                              ("doi", "bdv:doi"), ("revision", "bdv:revision"),
                              ("document_date", "dcterms:date"), ("license", "schema:license"),
                              ("sha256", "bdv:sha256"), ("note", "rdfs:comment")):
                if src.get(key):
                    pairs.append((pred, iri(src["url"]) if key == "url" else lit(src[key])))
            if src.get("is_final") is not None:
                pairs.append(("bdv:isFinal", lit(src["is_final"])))
            w.block(source_iri, pairs)
            sources_done.add(src["uid"])

        pairs = [("rdf:type", "schema:Product"), ("rdf:type", "bdv:Product")]
        kind_class = classes["product_kinds"].get(p["kind"])
        if kind_class:
            pairs.append(("rdf:type", curie(kind_class)))
        ff_class = classes["form_factors"].get(p.get("form_factor") or "")
        if ff_class:
            pairs.append(("rdf:type", curie(ff_class)))
        fam_class = classes["chemistry_families"].get(chem.get("family") or "")
        if fam_class:
            pairs.append(("rdf:type", curie(fam_class)))
        des_class = classes["chemistry_designations"].get(chem.get("designation") or "")
        if des_class:
            pairs.append(("rdf:type", curie(des_class)))
        pairs += [("bdv:uid", lit(uid)), ("schema:name", lit(f"{p['manufacturer']} {p['model_number']}")),
                  ("schema:model", lit(p["model_number"])), ("schema:manufacturer", org_iri),
                  ("bdv:kind", lit(p["kind"]))]
        for key, pred in (("form_factor", "bdv:formFactor"), ("form_factor_code", "bdv:formFactorCode"),
                          ("component_kind", "bdv:componentKind"), ("iec_designation", "bdv:iecDesignation"),
                          ("ansi_neda", "bdv:ansiNeda"), ("lifecycle", "bdv:lifecycle")):
            if p.get(key):
                pairs.append((pred, lit(p[key])))
        if p.get("is_rechargeable") is not None:
            pairs.append(("bdv:isRechargeable", lit(p["is_rechargeable"])))
        for alias in p.get("aliases") or []:
            pairs.append(("schema:alternateName", lit(alias)))
        pairs.append(("bdv:hasRevision", rev_iri))
        w.block(product_iri, pairs)

        pairs = [("rdf:type", "bdv:ProductRevision"), ("rdf:type", "prov:Entity")]
        spec_class = classes["product_revision_by_kind"].get(p["kind"]) or iris.get("product_revision")
        if spec_class:
            pairs.append(("rdf:type", curie(spec_class)))
        pairs += [("bdv:revisionOf", product_iri), ("dcterms:source", source_iri),
                  ("bdv:revisionLabel", lit(label))]
        if src.get("document_date"):
            pairs.append(("dcterms:date", lit(src["document_date"])))
        for key, pred in (("designation", "bdv:chemistryDesignation"), ("family", "bdv:chemistryFamily"),
                          ("construction", "bdv:construction"), ("cathode_text", "bdv:cathode"),
                          ("anode_text", "bdv:anode"), ("electrolyte_text", "bdv:electrolyte"),
                          ("separator_text", "bdv:separator")):
            if chem.get(key):
                pairs.append((pred, lit(chem[key])))
        w.block(rev_iri, pairs)

        for i, o in enumerate(doc.get("observations") or []):
            obs_iri = iri(ID + f"obs/{uid}/{i}")
            cond = dict(o.get("conditions") or {})
            unstated = cond.pop("unstated", []) or []
            b = q_iris.get(o["quantity"]) or {}
            pairs = [("rdf:type", "sosa:Observation"), ("rdf:type", "bdv:Observation"),
                     ("sosa:hasFeatureOfInterest", rev_iri),
                     ("bdv:quantity", f"bdv:q_{o['quantity']}")]
            prop = None
            if b.get("emmo_statistics") and o.get("statistic") in b["emmo_statistics"]:
                prop = b["emmo_statistics"][o["statistic"]]
            elif b.get("emmo_iri"):
                prop = b["emmo_iri"]
            if prop:
                pairs.append(("sosa:observedProperty", curie(prop)))
            if o.get("statistic"):
                pairs.append(("bdv:statistic", lit(o["statistic"])))
            result = [("rdf:type", "qudt:QuantityValue"), ("qudt:numericValue", lit(o["value"])),
                      ("qudt:unit", f"bdv:unit_{slug(o['unit']) or 'one'}")]
            if unit_iris.get(o["unit"]):
                result.append(("qudt:unit", curie(unit_iris[o["unit"]])))
            if b.get("qudt_quantity_kind"):
                result.append(("qudt:hasQuantityKind", curie(b["qudt_quantity_kind"])))
            pairs.append(("sosa:hasResult", bnode(result)))
            for key, pred in (("tol_plus", "bdv:tolPlus"), ("tol_minus", "bdv:tolMinus"),
                              ("value_min", "bdv:valueMin"), ("value_max", "bdv:valueMax"),
                              ("n_samples", "bdv:nSamples")):
                if o.get(key) is not None:
                    pairs.append((pred, lit(o[key])))
            if o.get("is_lower_bound"):
                pairs.append(("bdv:isLowerBound", "true"))
            if o.get("is_upper_bound"):
                pairs.append(("bdv:isUpperBound", "true"))
            if cond or unstated:
                pairs.append(("bdv:conditions", conditions_node(cond, unstated)))
            pairs.append(("prov:wasDerivedFrom", location_node(o.get("locator") or {}, source_iri)))
            pairs.append(("bdv:evidence", lit(evidence)))
            if evidence == "manufacturer_claim":
                pairs.append(("prov:wasAttributedTo", org_iri))
            w.block(obs_iri, pairs)

        for i, c in enumerate(doc.get("curves") or []):
            curve_iri = iri(ID + f"curve/{uid}/{i}")
            cond = dict(c.get("conditions") or {})
            unstated = cond.pop("unstated", []) or []
            pairs = [("rdf:type", "bdv:Curve"), ("rdf:type", "sosa:Observation"),
                     ("sosa:hasFeatureOfInterest", rev_iri), ("bdv:curveKind", lit(c["curve_kind"])),
                     ("bdv:xQuantity", f"bdv:q_{c['x_quantity']}"), ("bdv:yQuantity", f"bdv:q_{c['y_quantity']}"),
                     ("bdv:xUnit", lit(c["x_unit"])), ("bdv:yUnit", lit(c["y_unit"])),
                     ("bdv:xValues", lit(json.dumps(c["x_values"]))),
                     ("bdv:yValues", lit(json.dumps(c["y_values"])))]
            if c.get("z_quantity"):
                pairs += [("bdv:zQuantity", f"bdv:q_{c['z_quantity']}"), ("bdv:zUnit", lit(c.get("z_unit") or "")),
                          ("bdv:zValues", lit(json.dumps(c.get("z_values") or [])))]
            if cond or unstated:
                pairs.append(("bdv:conditions", conditions_node(cond, unstated)))
            if c.get("processing"):
                pairs.append(("bdv:processing", lit(json.dumps(c["processing"], sort_keys=True))))
            pairs.append(("prov:wasDerivedFrom", location_node(c.get("locator") or {}, source_iri)))
            w.block(curve_iri, pairs)

        for i, a in enumerate(doc.get("applications") or []):
            app_iri = iri(ID + a["uid"])
            pairs = [("rdf:type", "bdv:Application"), ("rdf:type", "schema:Thing"),
                     ("schema:name", lit(a["name"])), ("bdv:sector", lit(a["sector"]))]
            for key, pred in (("operator", "bdv:operator"), ("programme", "bdv:programme"),
                              ("region", "bdv:region"), ("in_service_from", "bdv:inServiceFrom"),
                              ("in_service_to", "bdv:inServiceTo"), ("system_energy_kwh", "bdv:systemEnergyKwh"),
                              ("system_power_kw", "bdv:systemPowerKw")):
                if a.get(key) is not None:
                    pairs.append((pred, lit(a[key])))
            w.block(app_iri, pairs)
            link = [("rdf:type", "bdv:Deployment"), ("bdv:application", app_iri), ("bdv:basis", lit(a["basis"]))]
            for key, pred in (("role", "bdv:role"), ("confidence", "bdv:confidence"),
                              ("quantity_per_unit", "bdv:quantityPerUnit"), ("topology_string", "bdv:topology")):
                if a.get(key) is not None:
                    link.append((pred, lit(a[key])))
            link.append(("prov:wasDerivedFrom", location_node(a.get("locator") or {}, source_iri)))
            w.block(iri(ID + f"deployment/{uid}/{i}"), link + [("bdv:deploymentOf", rev_iri)])

        for i, cert in enumerate(doc.get("certifications") or []):
            pairs = [("rdf:type", "bdv:Certification"), ("bdv:certificationOf", rev_iri),
                     ("bdv:standard", lit(cert["standard"])),
                     ("bdv:scope", lit(cert.get("scope") or "unspecified")),
                     ("bdv:status", lit(cert.get("status") or "claimed"))]
            for key, pred in (("certificate_number", "bdv:certificateNumber"),
                              ("certifying_body", "bdv:certifyingBody"), ("listing_type", "bdv:listingType"),
                              ("issued_date", "bdv:issuedDate"), ("expiry_date", "bdv:expiryDate")):
                if cert.get(key):
                    pairs.append((pred, lit(cert[key])))
            pairs.append(("prov:wasDerivedFrom", location_node(cert.get("locator") or {}, source_iri)))
            w.block(iri(ID + f"certification/{uid}/{i}"), pairs)

        for i, link in enumerate(doc.get("contains") or []):
            pairs = [("rdf:type", "bdv:Assembly"), ("bdv:parent", rev_iri),
                     ("bdv:child", iri(ID + link["uid"])), ("bdv:quantity", lit(link["quantity"]))]
            for key, pred in (("series_count", "bdv:seriesCount"), ("parallel_count", "bdv:parallelCount"),
                              ("topology", "bdv:topology")):
                if link.get(key) is not None:
                    pairs.append((pred, lit(link[key])))
            pairs.append(("prov:wasDerivedFrom", location_node(link.get("locator") or {}, source_iri)))
            w.block(iri(ID + f"assembly/{uid}/{i}"), pairs)

        for i, link in enumerate(doc.get("equivalences") or []):
            pairs = [("rdf:type", "bdv:Equivalence"), ("bdv:from", product_iri),
                     ("bdv:to", iri(ID + link["uid"])), ("bdv:relation", lit(link["relation"])),
                     ("prov:wasDerivedFrom", location_node(link.get("locator") or {}, source_iri))]
            w.block(iri(ID + f"equivalence/{uid}/{i}"), pairs)

    return "\n".join(w.lines) + "\n"


def to_jsonld(ttl_path: str, out: str):
    try:
        import rdflib
    except ImportError:
        sys.exit("pip install rdflib   (only --jsonld needs it)")
    g = rdflib.Graph()
    g.parse(ttl_path, format="turtle")
    context = {k: v for k, v in PREFIXES.items()}
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(g.serialize(format="json-ld", context=context, indent=1, sort_keys=True))
    print(f"  wrote {os.path.relpath(out, ROOT)} ({len(g)} triples)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--jsonld", action="store_true")
    a = ap.parse_args()
    iris = load(IRIS)
    files = sorted(glob.glob(os.path.join(ROOT, "contrib", "**", "*.y*ml"), recursive=True))
    products = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            products.append((f, yaml.safe_load(fh)))
    products.sort(key=lambda t: t[1]["product"]["uid"])
    body = export(products, iris)
    if a.check:
        current = open(OUT_TTL, encoding="utf-8").read() if os.path.exists(OUT_TTL) else ""
        if current != body:
            print("rdf/battery-data.ttl is stale. Run: python tools/export_rdf.py", file=sys.stderr)
            return 1
        print(f"rdf/battery-data.ttl is up to date ({len(products)} products)")
        return 0
    os.makedirs(os.path.dirname(OUT_TTL), exist_ok=True)
    with open(OUT_TTL, "w", encoding="utf-8") as fh:
        fh.write(body)
    n_obs = sum(len(d.get("observations") or []) for _, d in products)
    print(f"  wrote {os.path.relpath(OUT_TTL, ROOT)}: {len(products)} products, {n_obs} observations, "
          f"{len(body):,} bytes")
    if a.jsonld:
        to_jsonld(OUT_TTL, OUT_JSONLD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
