#!/usr/bin/env python3
"""Validate the candidate sets under review/layers: names of cell, cathode
and anode makers and of factories, recalled without a document.

A candidate is a work order. It says who or what to look for, where, and
which page to verify it against. It carries no source, no page and no
quote, and this validator refuses one that does: provenance is added by
tools/verify_layer_candidates.py from the page itself, never typed into a
candidate. Beyond the schema:

  * uids are unique across every set;
  * a site's uid sits under its operator's slug (site/<operator>/<site>)
    and its operator and partners are candidates or organisations the
    library already holds;
  * a company's parent is likewise known;
  * verify_at and website are https URLs;
  * every stage a role or a kind implies exists in schema/184_companies.sql.

    python tools/validate_layer_candidates.py            # review/layers/*.yaml
    python tools/validate_layer_candidates.py --stats    # and the counts by set, stage, country
"""
from __future__ import annotations

import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys

import jsonschema
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "json-schema", "layer-candidate.schema.json")
DIR = os.path.join(ROOT, "review", "layers")
FORBIDDEN = {"quote", "page", "locator", "source", "sha256", "document_date", "section", "evidence"}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_layers import known_uids, plain  # noqa: E402


def stage_map() -> tuple[dict, dict]:
    """role -> stage and site kind -> stage, read from the schema file so
    there is one copy of the map."""
    text = open(os.path.join(ROOT, "schema", "184_companies.sql"), encoding="utf-8").read()
    block = re.search(r"INSERT INTO supply_chain_stage \(.*?\) VALUES(.*?'\)\s*;)", text, re.S).group(1)
    kinds, roles = {}, {}
    for code, k_arr, r_arr in re.findall(r"\('([a-z_]+)',\s*\d+,[^']*'[^']*',\s*'(?:[^']|'')*',\s*'\{([a-z_,]*)\}',\s*'\{([a-z_,]*)\}'\)", block):
        for k in filter(None, k_arr.split(",")):
            kinds[k] = code
        for r in filter(None, r_arr.split(",")):
            roles[r] = code
    return roles, kinds


def forbidden_keys(obj, path="") -> list[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN:
                out.append(f"{path}/{k}")
            out += forbidden_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += forbidden_keys(v, f"{path}[{i}]")
    return out


def load_sets(files: list[str]) -> tuple[list[tuple[str, dict]], list[str]]:
    schema = json.load(open(SCHEMA, encoding="utf-8"))
    docs, errs = [], []
    for f in files:
        rel = os.path.relpath(f, ROOT)
        try:
            doc = plain(yaml.safe_load(open(f, encoding="utf-8")))
        except yaml.YAMLError as e:
            errs.append(f"{rel}: not valid YAML: {e}")
            continue
        try:
            jsonschema.validate(doc, schema)
        except jsonschema.ValidationError as e:
            errs.append(f"{rel}: structural: {'/'.join(str(p) for p in e.absolute_path)}: {e.message}")
            continue
        for bad in forbidden_keys(doc):
            errs.append(f"{rel}: {bad}: a candidate carries no provenance; verification adds it")
        docs.append((rel, doc))
    return docs, errs


def validate(files: list[str]) -> tuple[list[str], dict]:
    docs, errs = load_sets(files)
    roles_stage, kinds_stage = stage_map()
    known = known_uids()
    cand_orgs = {c["uid"] for _, d in docs for c in d.get("companies") or []}
    all_orgs = cand_orgs | known["orgs"]
    seen: dict[str, str] = {}
    stats = {"sets": {}, "companies": 0, "sites": 0, "stage": collections.Counter(),
             "country": collections.Counter(), "confidence": collections.Counter(),
             "in_library": 0}
    for rel, doc in docs:
        name = doc["candidate_set"]
        n_c, n_s = len(doc.get("companies") or []), len(doc.get("sites") or [])
        stats["sets"][name] = {"companies": n_c, "sites": n_s, "recalled_on": doc["recalled_on"]}
        stats["companies"] += n_c
        stats["sites"] += n_s
        for i, c in enumerate(doc.get("companies") or []):
            where = f"{rel}: companies[{i}] ({c['uid']})"
            if c["uid"] in seen:
                errs.append(f"{where}: uid already used in {seen[c['uid']]}")
            seen[c["uid"]] = rel
            if c.get("website") and not c["website"].startswith("https://"):
                errs.append(f"{where}: website must be https")
            if c.get("parent_uid") and c["parent_uid"] not in all_orgs:
                errs.append(f"{where}: parent_uid {c['parent_uid']} is neither a candidate nor in the library")
            if c.get("parent_uid") == c["uid"]:
                errs.append(f"{where}: parent_uid is the company itself")
            for r in c["roles"]:
                if r in roles_stage:
                    stats["stage"][roles_stage[r]] += 1
            stats["country"][c["country"]] += 1
            stats["confidence"][c["confidence"]] += 1
            if c["uid"] in known["orgs"]:
                stats["in_library"] += 1
        for i, s in enumerate(doc.get("sites") or []):
            where = f"{rel}: sites[{i}] ({s['uid']})"
            if s["uid"] in seen:
                errs.append(f"{where}: uid already used in {seen[s['uid']]}")
            seen[s["uid"]] = rel
            op_slug = s["operator_uid"][4:]
            if s["uid"].split("/")[1] != op_slug:
                errs.append(f"{where}: uid must sit under its operator: site/{op_slug}/<site>")
            if s["operator_uid"] not in all_orgs:
                errs.append(f"{where}: operator_uid {s['operator_uid']} is neither a candidate nor in the library")
            for p in s.get("partners") or []:
                if p not in all_orgs:
                    errs.append(f"{where}: partner {p} is neither a candidate nor in the library")
                if p == s["operator_uid"]:
                    errs.append(f"{where}: partner {p} is the operator")
            if s["kind"] in kinds_stage:
                stats["stage"][kinds_stage[s["kind"]]] += 1
            elif s["kind"] != "other":
                errs.append(f"{where}: kind {s['kind']} has no stage in schema/184_companies.sql")
            stats["country"][s["country"]] += 1
            stats["confidence"][s["confidence"]] += 1
            if s["uid"] in known["sites"]:
                stats["in_library"] += 1
    return errs, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    files = a.paths or sorted(glob.glob(os.path.join(DIR, "*.y*ml")))
    errs, stats = validate(files)
    for e in errs:
        print("  " + e, file=sys.stderr)
    print(f"{len(stats['sets'])} candidate set(s), {stats['companies']} companies, {stats['sites']} sites, "
          f"{len(errs)} error(s)")
    if a.stats:
        print("\n  by set:")
        for name, s in stats["sets"].items():
            print(f"    {name:<24} {s['companies']:>4} companies {s['sites']:>4} sites   recalled {s['recalled_on']}")
        print("  by stage:")
        for stage, n in sorted(stats["stage"].items(), key=lambda t: -t[1]):
            print(f"    {stage:<20} {n:>4}")
        print("  by country (top 12):")
        for cc, n in stats["country"].most_common(12):
            print(f"    {cc:<4} {n:>4}")
        print("  by confidence: " + ", ".join(f"{k} {v}" for k, v in sorted(stats["confidence"].items())))
        print(f"  already in the library (by uid): {stats['in_library']}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
