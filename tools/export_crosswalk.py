#!/usr/bin/env python3
"""
Emit the standards crosswalk as publishable artefacts.

Generated from bd.v_crosswalk so it cannot drift from the schema:

    crosswalk.json   machine-readable, for tooling
    crosswalk.csv    for spreadsheets and review
    CROSSWALK.md     human-readable, for the repo and a preprint

Run:  python tools/export_crosswalk.py [dbname] [outdir]
"""
import csv, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = sys.argv[1] if len(sys.argv) > 1 else "batterydb"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "crosswalk")
os.makedirs(OUT, exist_ok=True)

def q(sql):
    r = subprocess.run(["psql", "-tAq", "-d", DB, "-c", sql],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout.strip() or "[]")

vocabs = q("SELECT coalesce(json_agg(row_to_json(v)),'[]') FROM bd.vocabulary v;")
rows   = q("SELECT coalesce(json_agg(row_to_json(c)),'[]') FROM bd.v_crosswalk c;")

payload = {
    "title": "battery-data standards crosswalk",
    "description": ("Mapping between this schema's quantities and the four "
                    "external vocabularies describing overlapping parts of the "
                    "battery data landscape. Rows with relation='no_equivalent' "
                    "record deliberate absences - what a standard cannot express "
                    "is as important as what it can."),
    "repository": "https://github.com/Morshedvarzandeh/battery-data",
    "license": "CC-BY-4.0",
    "vocabularies": vocabs,
    "mappings": rows,
}
json.dump(payload, open(os.path.join(OUT, "crosswalk.json"), "w"), indent=2)

if rows:
    with open(os.path.join(OUT, "crosswalk.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

# ---- Markdown -------------------------------------------------------
by_vocab = {}
for r in rows:
    by_vocab.setdefault(r["vocabulary"], []).append(r)

REL_NOTE = {
    "exact": "round-trips losslessly",
    "close": "same quantity, minor definitional differences",
    "broader": "the external term is more general - information is lost going out",
    "narrower": "the external term is more specific",
    "related": "associated but not substitutable",
    "no_equivalent": "**the external vocabulary has no term for this**",
}

md = ["# battery-data standards crosswalk", "",
      "Generated from `bd.v_crosswalk`. Do not edit by hand.", "",
      "Four vocabularies describe overlapping parts of the battery data",
      "landscape and no published crosswalk connects them. This is that",
      "crosswalk. The `relation` column records mapping **fidelity**, which",
      "is the part a naive mapping omits and the part that matters: an",
      "`exact` mapping can be relied on for round-tripping, a `broader` one",
      "cannot.", "",
      "Rows marked `no_equivalent` are deliberate content, not omissions.", "",
      "## Vocabularies", "",
      "| Code | Name | Version | Licence |", "|---|---|---|---|"]
for v in vocabs:
    md.append(f"| `{v['code']}` | {v['name']} | {v.get('version') or ''} "
              f"| {v.get('license') or ''} |")
md.append("")
for v in vocabs:
    if v.get("notes"):
        md.append(f"**{v['code']}** — {v['notes']}\n")

for vocab, rs in sorted(by_vocab.items()):
    md += ["", f"## {vocab}", "",
           "| Quantity | SI unit | External term | Relation | Verified | Note |",
           "|---|---|---|---|---|---|"]
    for r in sorted(rs, key=lambda x: (x["relation"] != "no_equivalent", x["quantity"])):
        term = f"`{r['external_term']}`" if r["external_term"] else "— *(none)*"
        note = (r.get("note") or "").replace("\n", " ").replace("|", "\\|")
        md.append(f"| `{r['quantity']}` | {r['si_unit']} | {term} | "
                  f"{r['relation']} | {'yes' if r['verified'] else 'pending'} | {note} |")

md += ["", "## Reading the relation column", ""]
for k, vtext in REL_NOTE.items():
    md.append(f"- **`{k}`** — {vtext}")
md += ["", "## Unverified rows", "",
       "EMMO class IRIs are opaque UUIDs (`BatteryCell` = ",
       "`battery_68ed592a_7924_45d0_a108_94d6275d57f0`). Rows marked *pending*",
       "carry a label but no IRI: `tools/sync_vocabularies.py` resolves them by",
       "parsing `battery.ttl` and `electrochemistry.ttl` at build time.",
       "Hand-copying UUIDs from documentation is how crosswalks silently rot.", ""]

open(os.path.join(OUT, "CROSSWALK.md"), "w").write("\n".join(md))

verified = sum(1 for r in rows if r["verified"])
print(f"wrote {OUT}/crosswalk.json, crosswalk.csv, CROSSWALK.md")
print(f"  {len(rows)} mappings across {len(by_vocab)} vocabularies "
      f"({verified} verified, {len(rows)-verified} pending IRI resolution)")
print(f"  {sum(1 for r in rows if r['relation']=='no_equivalent')} explicit absences recorded")
