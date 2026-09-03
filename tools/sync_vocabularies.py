#!/usr/bin/env python3
"""Bind this schema's terms to published ontologies, from their source files.

docs/03-crosswalk.md says it in one line: do NOT hand-copy IRIs from
documentation, generate them. EMMO class IRIs are opaque UUIDs
(BatteryCell = battery_68ed592a_7924_45d0_a108_94d6275d57f0) and a
hand-typed one is wrong the moment the ontology is regenerated. QUDT names are
readable but still drift between releases. So the curated file,
vocab/bindings.json, holds LABELS, and this tool resolves every label against
the ontology it came from and refuses to emit a binding it cannot find.

    python tools/sync_vocabularies.py fetch          # download the vocabularies
    python tools/sync_vocabularies.py index          # label -> IRI tables, checked in
    python tools/sync_vocabularies.py bind           # bindings SQL + JSON, checked in
    python tools/sync_vocabularies.py check          # CI: outputs are current

Outputs, all generated and all committed:

    vocab/emmo-index.json          every EMMO class in the battery domain
                                   closure: prefLabel, altLabels, IRI
    vocab/qudt-index.json          QUDT quantity kinds and units, label -> IRI
    vocab/resolved.json            the curated bindings with their IRIs
    schema/175_vocabulary_bindings.sql
                                   UPDATE bd.quantity ... emmo_iri, qudt_*;
                                   verified rows in bd.quantity_mapping
    json-schema/quantity-iris.json the same, for the offline validator and
                                   the RDF export

Needs rdflib (pip install rdflib) for fetch/index; bind and check read the
committed indexes and need nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB = os.path.join(ROOT, "vocab")
CACHE = os.path.join(VOCAB, "cache")
BINDINGS = os.path.join(VOCAB, "bindings.json")
EMMO_INDEX = os.path.join(VOCAB, "emmo-index.json")
QUDT_INDEX = os.path.join(VOCAB, "qudt-index.json")
RESOLVED = os.path.join(VOCAB, "resolved.json")
SQL_OUT = os.path.join(ROOT, "schema", "175_vocabulary_bindings.sql")
JSON_OUT = os.path.join(ROOT, "json-schema", "quantity-iris.json")

QUDT_QK = "http://qudt.org/vocab/quantitykind/"
QUDT_UNIT = "http://qudt.org/vocab/unit/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
# EMMO annotation properties are themselves opaque IRIs.
EMMO_ELUCIDATION = "https://w3id.org/emmo#EMMO_967080e5_2f42_4eb2_a3a9_c58143e835f9"
EMMO_IEV = "https://w3id.org/emmo#EMMO_50c298c2_55a2_4068_b3ac_4e948c33181f"


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, payload, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=indent, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sources(bindings):
    return {
        "emmo": bindings["emmo"]["source"]["url"],
        "qudt-quantitykinds": bindings["qudt"]["source"]["quantitykinds"],
        "qudt-units": bindings["qudt"]["source"]["units"],
    }


def cache_path(name):
    return os.path.join(CACHE, name + ".ttl")


def fetch(bindings):
    os.makedirs(CACHE, exist_ok=True)
    for name, url in sources(bindings).items():
        dest = cache_path(name)
        print(f"  fetching {url}")
        with urllib.request.urlopen(url, timeout=300) as resp, open(dest, "wb") as out:
            out.write(resp.read())
        print(f"    -> {dest} ({os.path.getsize(dest):,} bytes, sha256 {sha256(dest)[:16]}...)")


def graph(path):
    try:
        import rdflib
    except ImportError:
        sys.exit("pip install rdflib   (only fetch/index need it)")
    g = rdflib.Graph()
    g.parse(path, format="turtle")
    return g, rdflib


def index_emmo(bindings):
    """Every owl:Class in the inferred battery ontology, by prefLabel.

    The inferred file is the whole import closure -- battery, electrochemistry,
    chemical substance and EMMO core -- which is why one file resolves labels
    from all of them. Labels are unique across that closure in practice; a
    collision is reported rather than silently resolved.
    """
    path = cache_path("emmo")
    if not os.path.exists(path):
        sys.exit("run `fetch` first")
    g, rdflib = graph(path)
    version = None
    for _, _, v in g.triples((None, rdflib.OWL.versionIRI, None)):
        version = str(v)
    # A label can name two classes: the battery domain and the electrochemistry
    # domain both define StateOfCharge, and the battery domain itself carries
    # a duplicated NickelZincBattery. The choice has to be deterministic or the
    # committed index flaps between runs, so: prefer the battery namespace,
    # then the lexically smallest IRI, and keep every alternative visible.
    prefixes = bindings["emmo"]["source"]["namespace_prefixes"]
    rank = {prefixes["battery"]: 0, prefixes["echem"]: 1, prefixes["emmo"]: 2}

    def order(iri):
        ns = iri.rsplit("#", 1)[0] + "#" if "#" in iri else iri
        return (rank.get(ns, 3), iri)

    by_label = {}
    for cls in g.subjects(rdflib.RDF.type, rdflib.URIRef(OWL_CLASS)):
        if isinstance(cls, rdflib.BNode):
            continue
        for label in sorted(str(o) for o in g.objects(cls, rdflib.URIRef(SKOS + "prefLabel")))[:1]:
            by_label.setdefault(label, []).append(cls)
    classes, collisions = {}, {}
    for label, iris in by_label.items():
        chosen = sorted(iris, key=lambda c: order(str(c)))[0]
        entry = {
            "iri": str(chosen),
            "alt": sorted(str(o) for o in g.objects(chosen, rdflib.URIRef(SKOS + "altLabel"))),
        }
        if len(iris) > 1:
            entry["also"] = sorted(str(c) for c in iris if c != chosen)
            collisions[label] = sorted(str(c) for c in iris)
        classes[label] = entry
    payload = {
        "source": {"url": bindings["emmo"]["source"]["url"], "version_iri": version,
                   "sha256": sha256(path)},
        "classes": classes,
        "label_collisions": collisions,
    }
    dump(EMMO_INDEX, payload, indent=None)
    print(f"  {len(classes)} EMMO classes indexed from {version}; "
          f"{len(set(collisions))} label collisions")


def index_qudt(bindings):
    out = {"source": {}, "quantitykinds": {}, "units": {}}
    for name, key, ns in (("qudt-quantitykinds", "quantitykinds", QUDT_QK),
                          ("qudt-units", "units", QUDT_UNIT)):
        path = cache_path(name)
        if not os.path.exists(path):
            sys.exit("run `fetch` first")
        g, rdflib = graph(path)
        for s in set(g.subjects()):
            iri = str(s)
            if not iri.startswith(ns):
                continue
            local = iri[len(ns):]
            labels = [str(o) for o in g.objects(s, rdflib.RDFS.label)]
            symbol = [str(o) for o in g.objects(s, rdflib.URIRef("http://qudt.org/schema/qudt/symbol"))]
            out[key][local] = {"label": labels[0] if labels else local,
                               **({"symbol": symbol[0]} if symbol else {})}
        out["source"][key] = {"url": bindings["qudt"]["source"][key], "sha256": sha256(path)}
        print(f"  {len(out[key])} QUDT {key} indexed")
    dump(QUDT_INDEX, out, indent=None)


def resolve(bindings, emmo, qudt):
    """Every label in the curated file, resolved; unresolved ones are errors."""
    errors, out = [], {"emmo": {}, "qudt": {}}
    classes = emmo["classes"]

    def emmo_iri(label, where):
        if label is None:
            return None
        if label not in classes:
            errors.append(f"{where}: EMMO has no class labelled {label!r}")
            return None
        return classes[label]["iri"]

    e = bindings["emmo"]
    out["emmo"]["source"] = emmo["source"]
    out["emmo"]["quantities"] = {}
    for code, b in e["quantities"].items():
        if b is None:
            out["emmo"]["quantities"][code] = None
            continue
        entry = {"label": b["label"], "iri": emmo_iri(b["label"], f"quantities.{code}"),
                 "relation": b["relation"]}
        if b.get("note"):
            entry["note"] = b["note"]
        if b.get("statistics"):
            entry["statistics"] = {
                stat: {"label": lab, "iri": emmo_iri(lab, f"quantities.{code}.statistics.{stat}")}
                for stat, lab in b["statistics"].items()}
        out["emmo"]["quantities"][code] = entry
    for group in ("product_kinds", "form_factors", "chemistry_families",
                  "chemistry_designations", "lead_acid_constructions",
                  "product_revision_by_kind"):
        out["emmo"][group] = {k: ({"label": v, "iri": emmo_iri(v, f"{group}.{k}")} if v else None)
                              for k, v in e[group].items()}
    for single in ("product_revision", "organization"):
        out["emmo"][single] = {"label": e[single], "iri": emmo_iri(e[single], single)}

    q = bindings["qudt"]
    out["qudt"]["source"] = qudt["source"]
    out["qudt"]["quantity_kinds"], out["qudt"]["units"] = {}, {}
    for code, local in q["quantity_kinds"].items():
        if local is None:
            out["qudt"]["quantity_kinds"][code] = None
            continue
        if local not in qudt["quantitykinds"]:
            errors.append(f"qudt.quantity_kinds.{code}: no quantitykind:{local}")
            continue
        out["qudt"]["quantity_kinds"][code] = {"local": local, "iri": QUDT_QK + local,
                                               "label": qudt["quantitykinds"][local]["label"]}
    for symbol, local in q["units"].items():
        if local is None:
            out["qudt"]["units"][symbol] = None
            continue
        if local not in qudt["units"]:
            errors.append(f"qudt.units.{symbol!r}: no unit:{local}")
            continue
        out["qudt"]["units"][symbol] = {"local": local, "iri": QUDT_UNIT + local,
                                        "label": qudt["units"][local]["label"]}
    return out, errors


def registry_codes():
    return set(load(os.path.join(ROOT, "json-schema", "quantity-registry.json")))


def render_sql(resolved):
    L = ["-- =====================================================================",
         "-- battery-data : 175_vocabulary_bindings.sql",
         "--",
         "-- GENERATED by tools/sync_vocabularies.py from vocab/bindings.json and",
         "-- the published ontologies. Do not edit; edit the labels in",
         "-- vocab/bindings.json and rerun `bind`.",
         "--",
         f"-- EMMO: {resolved['emmo']['source'].get('version_iri')}",
         f"--       sha256 {resolved['emmo']['source'].get('sha256')}",
         f"-- QUDT quantity kinds sha256 {resolved['qudt']['source']['quantitykinds']['sha256']}",
         f"-- QUDT units          sha256 {resolved['qudt']['source']['units']['sha256']}",
         "-- =====================================================================",
         "", "SET search_path = bd, public;", ""]
    emmo_version = resolved["emmo"]["source"].get("version_iri") or "unversioned"
    for code, b in sorted(resolved["emmo"]["quantities"].items()):
        if not b or not b.get("iri"):
            continue
        L.append(f"UPDATE quantity SET emmo_iri = '{b['iri']}' WHERE code = '{code}';")
        note = (b.get("note") or "").replace("'", "''")
        note_sql = f"'{note}'" if note else "NULL"
        L.append(
            "INSERT INTO quantity_mapping (quantity_id, vocabulary_id, external_term, external_iri, "
            "relation, note, verified, verified_against)\n"
            f"SELECT q.id, v.id, '{b['label']}', '{b['iri']}', '{b['relation']}', "
            f"{note_sql}, true, '{emmo_version}'\n"
            "  FROM quantity q, vocabulary v\n"
            f" WHERE q.code = '{code}' AND v.code = 'emmo_battery'\n"
            "ON CONFLICT (quantity_id, vocabulary_id, external_term) DO UPDATE\n"
            "   SET external_iri = EXCLUDED.external_iri, relation = EXCLUDED.relation,\n"
            "       note = EXCLUDED.note, verified = true, verified_against = EXCLUDED.verified_against;")
    L.append("")
    for code, b in sorted(resolved["qudt"]["quantity_kinds"].items()):
        if b:
            L.append(f"UPDATE quantity SET qudt_quantity_kind = '{b['iri']}' WHERE code = '{code}';")
    L.append("")
    for symbol, b in sorted(resolved["qudt"]["units"].items()):
        if b:
            L.append(f"UPDATE unit SET qudt_iri = '{b['iri']}' WHERE symbol = '{symbol}';")
    L.append("")
    return "\n".join(L)


def render_json(resolved):
    out = {}
    for code in sorted(set(resolved["emmo"]["quantities"]) | set(resolved["qudt"]["quantity_kinds"])):
        e = resolved["emmo"]["quantities"].get(code)
        q = resolved["qudt"]["quantity_kinds"].get(code)
        out[code] = {
            "emmo_iri": e["iri"] if e else None,
            "emmo_label": e["label"] if e else None,
            "emmo_relation": e["relation"] if e else None,
            "emmo_statistics": ({s: v["iri"] for s, v in e["statistics"].items()}
                                if e and e.get("statistics") else None),
            "qudt_quantity_kind": q["iri"] if q else None,
        }
    return {"quantities": out,
            "units": {s: (b["iri"] if b else None) for s, b in resolved["qudt"]["units"].items()},
            "classes": {g: {k: (v["iri"] if v else None) for k, v in resolved["emmo"][g].items()}
                        for g in ("product_kinds", "form_factors", "chemistry_families",
                                  "chemistry_designations", "lead_acid_constructions",
                                  "product_revision_by_kind")},
            "product_revision": resolved["emmo"]["product_revision"]["iri"],
            "organization": resolved["emmo"]["organization"]["iri"],
            "sources": {"emmo": resolved["emmo"]["source"], "qudt": resolved["qudt"]["source"]}}


def bind(bindings, check=False):
    emmo, qudt = load(EMMO_INDEX), load(QUDT_INDEX)
    resolved, errors = resolve(bindings, emmo, qudt)
    codes = registry_codes()
    for code in sorted(codes - set(bindings["emmo"]["quantities"])):
        errors.append(f"registry quantity {code!r} has no entry in bindings.emmo.quantities (use null to say EMMO has no term)")
    for code in sorted(set(bindings["emmo"]["quantities"]) - codes):
        errors.append(f"bindings.emmo.quantities.{code}: not in the registry")
    for code in sorted(codes - set(bindings["qudt"]["quantity_kinds"])):
        errors.append(f"registry quantity {code!r} has no QUDT quantity kind")
    if errors:
        for e in errors:
            print("  " + e, file=sys.stderr)
        sys.exit(f"{len(errors)} binding error(s)")
    outputs = {RESOLVED: json.dumps(resolved, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
               SQL_OUT: render_sql(resolved),
               JSON_OUT: json.dumps(render_json(resolved), indent=1, ensure_ascii=False, sort_keys=True) + "\n"}
    stale = [p for p, body in outputs.items()
             if not os.path.exists(p) or open(p, encoding="utf-8").read() != body]
    if check:
        if stale:
            sys.exit("stale: " + ", ".join(os.path.relpath(p, ROOT) for p in stale)
                     + "\nrun: python tools/sync_vocabularies.py bind")
        print("vocabulary bindings are current")
        return
    for p, body in outputs.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
    n_e = sum(1 for b in resolved["emmo"]["quantities"].values() if b and b.get("iri"))
    n_q = sum(1 for b in resolved["qudt"]["quantity_kinds"].values() if b)
    n_u = sum(1 for b in resolved["qudt"]["units"].values() if b)
    print(f"  bound {n_e} quantities to EMMO, {n_q} to QUDT quantity kinds, {n_u} units to QUDT")
    print("  wrote " + ", ".join(os.path.relpath(p, ROOT) for p in outputs))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "index", "bind", "check"])
    a = ap.parse_args()
    bindings = load(BINDINGS)
    if a.command == "fetch":
        fetch(bindings)
    elif a.command == "index":
        index_emmo(bindings)
        index_qudt(bindings)
    elif a.command == "bind":
        bind(bindings)
    else:
        bind(bindings, check=True)


if __name__ == "__main__":
    main()
