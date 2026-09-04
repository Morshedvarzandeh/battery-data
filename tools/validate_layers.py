#!/usr/bin/env python3
"""Validate the contributions that are not products: sites, companies, market
series and patents.

Each layer has a directory under contrib/ and a JSON schema, and a file says
which layer it belongs to by its top-level key: `site`, `organization`,
`family`, or the market series keys. A file under the wrong directory is an
error, so a reader never finds a mine under contrib/market.

Beyond the schemas, the rules the schemas cannot say:
  * a resource estimate names its reporting code and cut-off grade, or
    declares them unstated;
  * a capacity or production figure says whether it is nameplate, planned,
    announced or actual;
  * every period and validity range is ordered;
  * an organisation pinned by uid exists (in contrib/companies or as the
    maker of a product in contrib/cells), and a relation never points at
    the organisation itself;
  * a supply agreement's site is in contrib/sites and its parties differ;
  * price, index and volume rows are refused when the source does not say
    its data may be redistributed: the assessments that matter most are
    licensed, and this repository must stay distributable;
  * a patent publication's jurisdiction matches its number, a legal status
    carries its jurisdiction and date, and one category per publication is
    primary.

    python tools/validate_layers.py                  # contrib/{sites,companies,market,patents}
    python tools/validate_layers.py --examples       # docs/examples too (fictional, never loaded)
    python tools/validate_layers.py path/to/file.yaml
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys

import jsonschema
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = os.path.join(ROOT, "json-schema")

LAYERS = {
    "sites":     {"dir": "sites",     "schema": "site-contribution.schema.json",    "key": "site"},
    "companies": {"dir": "companies", "schema": "company-contribution.schema.json", "key": "organization"},
    "patents":   {"dir": "patents",   "schema": "patent-contribution.schema.json",  "key": "family"},
    "market":    {"dir": "market",    "schema": "market-contribution.schema.json",  "key": None},
}
MARKET_KEYS = ("commodity_prices", "price_indices", "market_volumes", "trade_flows",
               "supply_agreements", "distributions", "providers")


def plain(value):
    """YAML reads a bare 2025-06-30 as a date; the schemas speak ISO strings."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def layer_of(doc) -> str | None:
    """Which layer a document belongs to, from its shape."""
    if not isinstance(doc, dict):
        return None
    for name, spec in LAYERS.items():
        if spec["key"] and spec["key"] in doc:
            return name
    if "product" in doc:
        return "products"
    if any(k in doc for k in MARKET_KEYS) or set(doc) <= {"schema_version", "source"}:
        return "market"
    return None


def ordered(where: str, a, b, la: str, lb: str) -> list[str]:
    if a and b and str(b) < str(a):
        return [f"{where}: {lb} {b} precedes {la} {a}"]
    return []


def known_uids() -> dict[str, set[str]]:
    """Uids the layers may point at: products and their makers, companies, sites."""
    products, orgs, sites = set(), set(), set()
    for f in glob.glob(os.path.join(ROOT, "contrib", "cells", "**", "*.y*ml"), recursive=True):
        try:
            uid = yaml.safe_load(open(f, encoding="utf-8"))["product"]["uid"]
        except Exception:                                  # noqa: BLE001
            continue
        products.add(uid)
        orgs.add("org/" + uid.split("/")[1])
    for f in glob.glob(os.path.join(ROOT, "contrib", "companies", "**", "*.y*ml"), recursive=True):
        try:
            orgs.add(yaml.safe_load(open(f, encoding="utf-8"))["organization"]["uid"])
        except Exception:                                  # noqa: BLE001
            continue
    for f in glob.glob(os.path.join(ROOT, "contrib", "sites", "**", "*.y*ml"), recursive=True):
        try:
            sites.add(yaml.safe_load(open(f, encoding="utf-8"))["site"]["uid"])
        except Exception:                                  # noqa: BLE001
            continue
    return {"products": products, "orgs": orgs, "sites": sites}


# ---------------------------------------------------------------------
# Per-layer rules
# ---------------------------------------------------------------------
def check_site(path: str, doc: dict, known: dict) -> list[str]:
    errs = []
    site = doc["site"]
    if site.get("operator") is None and site.get("operator_uid") is None and \
            site.get("kind") not in ("port", "other"):
        errs.append(f"{path}: site has no operator; name the organisation the source names")
    if site.get("operator_uid") and site["operator_uid"] not in known["orgs"]:
        errs.append(f"{path}: operator_uid {site['operator_uid']} is not a known organisation; "
                    f"name it with `operator:` or add contrib/companies/{site['operator_uid'][4:]}.yaml")
    for i, r in enumerate(doc.get("resources") or []):
        where = f"{path}: resources[{i}] ({r.get('commodity')})"
        unstated = set(r.get("unstated") or [])
        if not r.get("reporting_code") and "reporting_code" not in unstated:
            errs.append(f"{where}: reporting_code is required, or list it in unstated: "
                        f"JORC, NI 43-101 and S-K 1300 do not agree on what a reserve is")
        if r.get("cutoff_grade") is None and "cutoff_grade" not in unstated:
            errs.append(f"{where}: cutoff_grade is required, or list it in unstated")
        if r.get("tonnage") is None and r.get("contained_metal") is None:
            errs.append(f"{where}: a tonnage or a contained metal figure is needed")
        if (r.get("grade") is None) != (r.get("grade_unit") is None):
            errs.append(f"{where}: grade and grade_unit go together")
        if site.get("kind") not in ("mine", "brine_operation"):
            errs.append(f"{where}: a resource estimate belongs to a mine or a brine operation, "
                        f"not a {site.get('kind')}")
    for i, m in enumerate(doc.get("metrics") or []):
        where = f"{path}: metrics[{i}] ({m.get('metric')})"
        errs += ordered(where, m.get("period_start"), m.get("period_end"), "period_start", "period_end")
        if m.get("metric") in ("capacity", "production") and not m.get("status"):
            errs.append(f"{where}: a capacity or production figure must say nameplate, planned, "
                        f"announced, under_construction, actual or estimated")
    for i, o in enumerate(doc.get("ownership") or []):
        where = f"{path}: ownership[{i}]"
        errs += ordered(where, o.get("valid_from"), o.get("valid_to"), "valid_from", "valid_to")
        if o.get("organization_uid") and o["organization_uid"] not in known["orgs"]:
            errs.append(f"{where}: organization_uid {o['organization_uid']} is not a known organisation")
    return errs


def check_company(path: str, doc: dict, known: dict) -> list[str]:
    errs = []
    org = doc["organization"]
    uid = org["uid"]
    for name in (org.get("aliases") or []) + (org.get("former_names") or []):
        if name.strip().lower() == org["name"].strip().lower():
            errs.append(f"{path}: alias {name!r} is the name itself")
    if org.get("parent_uid") == uid:
        errs.append(f"{path}: parent_uid points at the organisation itself")
    if org.get("parent_uid") and org["parent_uid"] not in known["orgs"]:
        errs.append(f"{path}: parent_uid {org['parent_uid']} is not a known organisation")
    for i, r in enumerate(doc.get("relations") or []):
        where = f"{path}: relations[{i}] ({r.get('relation')})"
        errs += ordered(where, r.get("valid_from"), r.get("valid_to"), "valid_from", "valid_to")
        if r.get("organization_uid") == uid:
            errs.append(f"{where}: relates the organisation to itself")
        if r.get("organization_uid") and r["organization_uid"] not in known["orgs"]:
            errs.append(f"{where}: organization_uid {r['organization_uid']} is not a known organisation; "
                        f"name it with `organization:` instead")
        if r.get("relation") in ("joint_venture_of", "minority_stake_in") and r.get("share_pct") is None:
            errs.append(f"{where}: a joint venture or a minority stake states its share")
    return errs


def check_market(path: str, doc: dict, known: dict) -> list[str]:
    errs = []
    src = doc["source"]
    priced = (doc.get("commodity_prices") or []) + (doc.get("price_indices") or []) \
        + (doc.get("market_volumes") or [])
    if priced and not src.get("data_redistributable"):
        errs.append(f"{path}: {len(priced)} price/index/volume row(s) from a source whose data "
                    f"may not be redistributed. Remove the rows and list the provider under "
                    f"`providers` so a consumer knows what to join.")
    for key in ("commodity_prices", "price_indices", "market_volumes", "trade_flows"):
        for i, r in enumerate(doc.get(key) or []):
            errs += ordered(f"{path}: {key}[{i}]", r.get("period_start"), r.get("period_end"),
                            "period_start", "period_end")
    for i, r in enumerate(doc.get("market_volumes") or []):
        if r.get("organization_uid") and r["organization_uid"] not in known["orgs"]:
            errs.append(f"{path}: market_volumes[{i}]: organization_uid {r['organization_uid']} "
                        f"is not a known organisation")
    for i, a in enumerate(doc.get("supply_agreements") or []):
        where = f"{path}: supply_agreements[{i}] ({a.get('uid')})"
        errs += ordered(where, a.get("valid_from"), a.get("valid_to"), "valid_from", "valid_to")
        sup = a.get("supplier_uid") or a.get("supplier")
        buy = a.get("buyer_uid") or a.get("buyer")
        if sup == buy:
            errs.append(f"{where}: supplier and buyer are the same organisation")
        for k in ("supplier_uid", "buyer_uid"):
            if a.get(k) and a[k] not in known["orgs"]:
                errs.append(f"{where}: {k} {a[k]} is not a known organisation")
        if a.get("site_uid") and a["site_uid"] not in known["sites"]:
            errs.append(f"{where}: site {a['site_uid']} is not in contrib/sites")
        if a.get("volume") is not None and not a.get("volume_unit"):
            errs.append(f"{where}: volume needs a unit")
    for i, d in enumerate(doc.get("distributions") or []):
        where = f"{path}: distributions[{i}]"
        errs += ordered(where, d.get("valid_from"), d.get("valid_to"), "valid_from", "valid_to")
        for k in ("distributor_uid", "manufacturer_uid"):
            if d.get(k) and d[k] not in known["orgs"]:
                errs.append(f"{where}: {k} {d[k]} is not a known organisation")
    return errs


def check_patent(path: str, doc: dict, known: dict) -> list[str]:
    errs = []
    fam = doc["family"]
    if fam["uid"] != f"patent/{fam['docdb_family_id']}":
        errs.append(f"{path}: family uid {fam['uid']} must be patent/{fam['docdb_family_id']}")
    numbers = set()
    for i, p in enumerate(doc["publications"]):
        where = f"{path}: publications[{i}] ({p.get('publication_number')})"
        num = p["publication_number"]
        if num in numbers:
            errs.append(f"{where}: publication number repeated in the file")
        numbers.add(num)
        if num[:2] != p["jurisdiction"]:
            errs.append(f"{where}: jurisdiction {p['jurisdiction']} does not match the number")
        if p.get("legal_status") and not (p.get("legal_status_jurisdiction") and p.get("legal_status_as_of")):
            errs.append(f"{where}: a legal status carries the jurisdiction it was observed in and the date")
        primaries = [c for c in (p.get("categories") or []) if c.get("primary")]
        if len(primaries) > 1:
            errs.append(f"{where}: more than one primary category")
        for a, b, la, lb in ((p.get("priority_date"), p.get("filing_date"), "priority_date", "filing_date"),
                             (p.get("filing_date"), p.get("publication_date"), "filing_date", "publication_date"),
                             (p.get("filing_date"), p.get("grant_date"), "filing_date", "grant_date")):
            errs += ordered(where, a, b, la, lb)
    for i, l in enumerate(doc.get("links") or []):
        where = f"{path}: links[{i}] ({l.get('relation')})"
        if l.get("organization_uid") and l["organization_uid"] not in known["orgs"]:
            errs.append(f"{where}: organization_uid {l['organization_uid']} is not a known organisation")
        if l.get("product_uid") and l["product_uid"] not in known["products"]:
            errs.append(f"{where}: product {l['product_uid']} is not in contrib/cells")
        wants_org = l["relation"] in ("assigned_to", "licensed_to")
        has_org = bool(l.get("organization") or l.get("organization_uid"))
        if wants_org and not has_org:
            errs.append(f"{where}: {l['relation']} names an organisation")
        if l["relation"] in ("covers_product", "cites_product") and not l.get("product_uid"):
            errs.append(f"{where}: {l['relation']} names a product_uid")
        if l["relation"] in ("covers_material", "uses_material") and not l.get("material_uid"):
            errs.append(f"{where}: {l['relation']} names a material_uid")
    return errs


CHECKS = {"sites": check_site, "companies": check_company, "market": check_market, "patents": check_patent}


# ---------------------------------------------------------------------
def validate_files(files: list[str], expect_dir: bool = True) -> tuple[list[str], dict]:
    """Validate a list of files; returns (errors, counts by layer)."""
    schemas = {name: json.load(open(os.path.join(SCHEMAS, spec["schema"]), encoding="utf-8"))
               for name, spec in LAYERS.items()}
    known = known_uids()
    errs: list[str] = []
    counts = {name: 0 for name in LAYERS}
    seen: dict[str, str] = {}
    parsed: list[tuple[str, str, object]] = []
    for f in files:
        rel = os.path.relpath(f, ROOT)
        try:
            doc = plain(yaml.safe_load(open(f, encoding="utf-8")))
        except yaml.YAMLError as e:
            errs.append(f"{rel}: not valid YAML: {e}")
            continue
        parsed.append((f, rel, doc))
        # what this batch defines is known to the rest of the batch
        if isinstance(doc, dict):
            if isinstance(doc.get("site"), dict) and doc["site"].get("uid"):
                known["sites"].add(doc["site"]["uid"])
            if isinstance(doc.get("organization"), dict) and doc["organization"].get("uid"):
                known["orgs"].add(doc["organization"]["uid"])
    for f, rel, doc in parsed:
        layer = layer_of(doc)
        if layer == "products":
            errs.append(f"{rel}: a product contribution; it belongs under contrib/cells and "
                        f"tools/validate_contrib.py checks it")
            continue
        if layer is None:
            errs.append(f"{rel}: cannot tell which layer this is (no site, organization, family "
                        f"or market series key)")
            continue
        if expect_dir:
            parts = rel.split(os.sep)
            if len(parts) > 1 and parts[0] == "contrib" and parts[1] != LAYERS[layer]["dir"]:
                errs.append(f"{rel}: a {layer} file under contrib/{parts[1]}; move it to "
                            f"contrib/{LAYERS[layer]['dir']}/")
        try:
            jsonschema.validate(doc, schemas[layer])
        except jsonschema.ValidationError as e:
            errs.append(f"{rel}: structural: {'/'.join(str(p) for p in e.absolute_path)}: {e.message}")
            continue
        counts[layer] += 1
        # one identity per uid across the whole layer
        ident = {"sites": lambda d: d["site"]["uid"], "companies": lambda d: d["organization"]["uid"],
                 "patents": lambda d: d["family"]["uid"], "market": lambda d: None}[layer](doc)
        if ident:
            if ident in seen:
                errs.append(f"{rel}: {ident} is already defined in {seen[ident]}")
            seen[ident] = rel
        if layer == "patents":
            for p in doc["publications"]:
                key = "pub:" + p["publication_number"]
                if key in seen:
                    errs.append(f"{rel}: publication {p['publication_number']} is already in {seen[key]}")
                seen[key] = rel
        errs += CHECKS[layer](rel, doc, known)
    return errs, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files or directories; default contrib/{sites,companies,market,patents}")
    ap.add_argument("--examples", action="store_true", help="also validate docs/examples (fictional, never loaded)")
    a = ap.parse_args()
    files: list[str] = []
    if a.paths:
        for p in a.paths:
            if os.path.isdir(p):
                files += sorted(glob.glob(os.path.join(p, "**", "*.y*ml"), recursive=True))
            else:
                files.append(p)
    else:
        for spec in LAYERS.values():
            files += sorted(glob.glob(os.path.join(ROOT, "contrib", spec["dir"], "**", "*.y*ml"), recursive=True))
    errs, counts = validate_files(files)
    if a.examples:
        ex = sorted(glob.glob(os.path.join(ROOT, "docs", "examples", "*.y*ml")))
        e2, c2 = validate_files(ex, expect_dir=False)
        errs += e2
        for k, v in c2.items():
            counts[k] += v
    for e in errs:
        print("  " + e, file=sys.stderr)
    print(", ".join(f"{v} {k}" for k, v in counts.items()) + f", {len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
