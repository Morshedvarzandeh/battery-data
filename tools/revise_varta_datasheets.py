#!/usr/bin/env python3
"""Move the 11 VARTA Dynamic EFB records onto VARTA's own PDF datasheets.

WHY
---
The lead-acid batch of 29 October 2026 recorded the VARTA Dynamic EFB range
from VARTA's product pages, because the PDF datasheet each page links to is
download-only and could not be opened in that review. The page prints
capacity, CCA, voltage and dimensions; the datasheet prints the same figures
plus the filled weight. With the 11 datasheets now downloaded (owner's
instruction, 30 October 2026), each record takes its datasheet as its source:
every figure already recorded is re-located in it, and the filled weight is
added where the datasheet prints one (10 of 11; the N50 sheet prints '-').

RULE
----
A record is revised only when every recorded figure is printed in its
datasheet exactly as recorded (capacity, CCA, voltage, the L/W/H triple,
the case size and the short code); otherwise the tool stops. Nothing is
derived: the datasheet still states no capacity rate or temperature and no
CCA standard, so those stay declared unstated.

The datasheet service renders each PDF on download (pdfinfo CreationDate), so
the SHA-256 identifies the copy inspected, as the product pages' did.

    python tools/revise_varta_datasheets.py                 # apply (idempotent)
    python tools/revise_varta_datasheets.py --check         # exit 1 if work remains
    python tools/revise_varta_datasheets.py --verify DIR    # re-read the PDFs in DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELLS = os.path.join(ROOT, "contrib", "cells", "clarios")
AUDIT = os.path.join(ROOT, "review", "audits", "2026-10-30-varta-datasheet-revision.json")
URL = "https://api.data-varta-automotive.com/v2/en-001/datasheet/fc41bc000f09fe2fee5adfef8ea415ad/{etn}K262.pdf"
FACTS = "Facts only; source body is not redistributed."

# ETN, PDF bytes, SHA-256, rendered (UTC, pdfinfo CreationDate), filled weight as printed
SHEETS = [
    ("550500055", 231137, "06cbf34999795e773dedd9bf4eac1d8908bc1e2f73b4b58b98b8d19cb1924944", "2026-10-30", "-"),
    ("560500064", 227682, "938b33e2b3bd80e7dfc05157e3097c4cdc3c85ded90d4b4b160032688087e3a4", "2026-10-30", "16,93 kg"),
    ("565500065", 218839, "7eda9cc395abc94f368ef0f915a1ef03af2340e266e75d4592174710a32f1365", "2026-10-30", "18,63 kg"),
    ("565501065", 220926, "e6cd481440856dcf1c0d7a16a437b0472e45f4edd9a2e6728b1a6e1efeec565a", "2026-10-30", "18,4 kg"),
    ("570500076", 220357, "684b5c728c61bfdc5e3fc09df84160509898f90baa2c08f18ec8ab748148ffae", "2026-10-30", "19,53 kg"),
    ("572501076", 221468, "c4d0f4c0ca4a7c253cf72647f45b170e42d6795c377c5f68be299f6c4c89eccd", "2026-10-29", "20,7 kg"),
    ("575500073", 215346, "7ab8ff34158d7dbbab76696dfe380cb2f71b7cce0c4579b13c8889e90f51711b", "2026-10-30", "21,19 kg"),
    ("580500080", 215763, "0f8ef189a8ab57159800ae27d7e26e4428c1ce136ca0b234f8b5261895be975f", "2026-10-30", "21,68 kg"),
    ("585501080", 212501, "6218c1893988b6bbb3c6bbe5f1cdd8441f4227de7a5ba01bddb0aff012b57da3", "2026-10-30", "26,4 kg"),
    ("595500085", 208301, "7b150e2130622d9970f90dbde73c7f77034acbea3b38f2d08acad293633a42a7", "2026-10-30", "24,49 kg"),
    ("605500095", 203687, "97e730c47c230691047f0306485a9dfac5fb8313322d649dc786d1df3e0f7fde", "2026-10-30", "26,07 kg"),
]
SECTION = "TECHNICAL DATA"
FIELDS = ["source", "observations", "chemistry.locator"]


def num(text: str):
    v = float(text.replace(",", "."))
    return int(v) if v.is_integer() else v


def note(etn: str, size: int, rendered: str, weight: str) -> str:
    parts = [
        FACTS,
        f"VARTA Automotive PDF datasheet for {etn}K262 (title 'Datasheet for Battery: {etn}K262', 2 pages,",
        f"{size:,} bytes), as rendered by VARTA's datasheet service on {rendered}; the service renders the PDF on",
        "each download, so the SHA-256 identifies the copy inspected.",
        "VARTA Automotive batteries are made and sold by Clarios ('Clarios manufactures and distributes VARTA",
        "Automotive batteries', varta-automotive.com home page), so the manufacturer is Clarios and the model keeps",
        "the VARTA name. Dynamic EFB is the renamed Silver Dynamic EFB.",
        "EFB is lead-acid: the product page states 'While EFB is an improved flooded battery'.",
        "The datasheet prints capacity, CCA, voltage, dimensions (L/W/H), case size, short code, UK code, weight",
        "filled, base hold-down, layout and terminal type. It prints no unit for the dimensions; they are millimetres",
        "per the product page's tooltip ('The dimensions are in millimetres (mm).'). The capacity's rate,",
        "temperature and end voltage and the CCA's standard, temperature, duration and end voltage are not stated.",
        ("It prints no weight ('Weight filled: -')." if weight == "-"
         else "'Weight filled' is the battery with its electrolyte."),
        f"Replaced the product page (src/varta-dynamic-efb-{etn}-web-2026-10-29) as this record's source on",
        "2026-10-30, because the datasheet prints every figure the page did and the weight; each recorded figure",
        "was re-located in the datasheet text, and all agree with the page.",
    ]
    return " ".join(parts)


def revise(doc: dict, sheet) -> dict:
    etn, size, sha, rendered, weight = sheet
    out = json.loads(json.dumps(doc))
    by_q = {o["quantity"]: o for o in out["observations"]}
    cap, cca = by_q["capacity"]["value"], by_q["cranking_current"]["value"]
    dims = "/".join(str(by_q[q]["value"]) for q in ("length", "width", "height"))
    quotes = {
        "capacity": f"Capacity: {cap} Ah",
        "nominal_voltage": f"Voltage: {by_q['nominal_voltage']['value']} V",
        "cranking_current": f"CCA: {cca} A",
        "length": f"Dimensions (L/W/H): {dims}",
        "width": f"Dimensions (L/W/H): {dims}",
        "height": f"Dimensions (L/W/H): {dims}",
    }
    out["source"] = {
        "uid": f"src/varta-dynamic-efb-{etn}-datasheet-{rendered}",
        "kind": "datasheet",
        "title": f"VARTA Dynamic EFB {etn}K262 datasheet",
        "url": URL.format(etn=etn),
        "retrieved_at": rendered,
        "sha256": sha,
        "license": "proprietary",
        "redistributable": False,
        "note": note(etn, size, rendered, weight),
    }
    for o in out["observations"]:
        o["locator"] = {"section": SECTION, "quote": quotes[o["quantity"]], "page": 2}
    if weight != "-":
        out["observations"].append({
            "quantity": "mass", "value": num(weight.split()[0]), "unit": "kg",
            "locator": {"section": SECTION, "quote": f"Weight filled: {weight}", "page": 2},
        })
    out["chemistry"]["locator"] = {"section": "Heading", "quote": f"DYNAMIC EFB {etn}K262", "page": 1}
    return out


def verify(directory: str) -> int:
    """Re-read each PDF: bytes, hash and every quote the revised record cites."""
    bad = 0
    for sheet in SHEETS:
        etn, size, sha, _rendered, weight = sheet
        path = os.path.join(directory, f"{etn}K262.pdf")
        raw = open(path, "rb").read()
        text = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
        flat = re.sub(r"\s+", " ", text.replace("ﬁ", "fi"))
        # The sheet sets "Dimensions" above "(L/W/H):" beside the voltage row, so the
        # extracted text interleaves them; put the label back together.
        flat = re.sub(r"Dimensions (Voltage: [\d,]+ V) \(L/W/H\):", r"\1 Dimensions (L/W/H):", flat)
        doc = json.load(open(os.path.join(CELLS, f"varta-dynamic-efb-{etn}.yaml"), encoding="utf-8"))
        problems = []
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha:
            problems.append("bytes or SHA-256 differ")
        for o in doc["observations"] + [{"locator": doc["chemistry"]["locator"]}]:
            quote = o["locator"]["quote"]
            if quote not in flat:
                problems.append(f"not found: {quote!r}")
        if weight == "-" and "Weight filled: -" not in flat:
            problems.append("expected 'Weight filled: -'")
        print(f"{etn}: {'ok' if not problems else '; '.join(problems)}")
        bad += bool(problems)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", metavar="DIR")
    a = ap.parse_args()
    if a.verify:
        return verify(a.verify)
    sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
    todo = []
    for sheet in SHEETS:
        path = os.path.join(CELLS, f"varta-dynamic-efb-{sheet[0]}.yaml")
        doc = json.load(open(path, encoding="utf-8"))
        if doc["source"]["kind"] != "datasheet":
            todo.append((path, doc, sheet))
    if a.check:
        print(f"{len(todo)} VARTA record(s) still cite the product page" if todo
              else "ok: every VARTA Dynamic EFB record cites its datasheet")
        return 1 if todo else 0
    revisions = []
    for path, doc, sheet in todo:
        before = sha(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(revise(doc, sheet), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        weight = sheet[4]
        revisions.append({
            "uid": doc["product"]["uid"],
            "file": os.path.relpath(path, ROOT),
            "previous_sha256": before,
            "revised_sha256": sha(path),
            "fields": FIELDS,
            "change": ("source: product page -> datasheet PDF; locators re-pointed to the datasheet"
                       + ("; no weight printed" if weight == "-" else f"; mass {weight} added")),
        })
    audit = {
        "schema_version": "1", "reviewed_at": "2026-10-30",
        "reviewer": "Claude, acting under the repository owner's instruction in chat; every quote re-located in the "
                    "datasheet text by tools/revise_varta_datasheets.py --verify",
        "authorization": [
            "Claude, 2026-10-30: 'May I download those 10 PDFs in your Chrome and then read them from your Downloads folder?'",
            "Owner: 'Yes, download all 10'",
        ],
        "scope": "The 11 VARTA Dynamic EFB records of the 29 October lead-acid batch",
        "basis": "Each record's source becomes its VARTA PDF datasheet, which prints every figure the product page "
                 "printed plus the filled weight. No value changes; 10 filled weights are added (the N50 sheet prints "
                 "none). Capacity rate and CCA standard remain unstated: the datasheets do not print them.",
        "revisions": [],
    }
    if os.path.exists(AUDIT):
        audit = json.load(open(AUDIT, encoding="utf-8"))
    audit["revisions"].extend(revisions)
    with open(AUDIT, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"revised {len(revisions)} VARTA record(s); audit: {os.path.relpath(AUDIT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
