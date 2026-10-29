"""Technology and chemistry, as two separate classifications of a record.

A record states one chemistry designation ("LFP", "Sodium-ion", "Lithium
polymer", "Li/MnO2"), sometimes a cathode ("NFPP") and an electrolyte
("Semi-Solid"). Those labels mix two levels: "Sodium-ion" names a battery
technology, "LFP" names an electrode chemistry, "Lithium polymer" names a
lithium-ion construction. The finder needs them apart -- a Technology filter
(lithium-ion, sodium-ion, lead-acid, AGM...) and a Chemistry filter (LFP, NMC,
NFPP...) -- so web/data/technologies-and-chemistries.json files every
designation under exactly one technology and, where the record supports it,
one chemistry. Nothing here is written back into a record.

    classify(tax, designation, cathode, electrolyte)
        -> {"tech": ..., "variant": ..., "chem": ...}   (None where unstated)
    check(tax, records) -> list of problems; empty means every label is filed
"""
from __future__ import annotations

import json
import re
from collections import Counter

SEP = " › "  # "Lead-acid › AGM": how a variant is keyed and displayed


def normalize(text: str) -> str:
    """Case- and punctuation-folded form used for aliases and search."""
    return re.sub(r"\s+", " ", re.sub(r"[-_/]+", " ", str(text).lower())).strip()


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _tech_index(tax: dict) -> dict[str, tuple[str, str | None]]:
    out: dict[str, tuple[str, str | None]] = {}
    for t in tax["technologies"]:
        for d in t.get("designations", []):
            out.setdefault(d, (t["name"], None))
        for v in t.get("variants", []):
            for d in v.get("designations", []):
                out[d] = (t["name"], v["name"])
    return out


def classify(tax: dict, designation: str | None, cathode: str | None = None,
             electrolyte: str | None = None) -> dict:
    tech = variant = chem = None
    if designation:
        tech, variant = _tech_index(tax).get(designation, (None, None))
    if tech and variant is None and electrolyte:
        for t in tax["technologies"]:
            if t["name"] == tech:
                for v in t.get("variants", []):
                    if electrolyte in v.get("electrolytes", []):
                        variant = v["name"]
    for c in tax["chemistries"]:
        if designation and designation in c.get("designations", []):
            chem = c["name"]
            break
    if chem is None and cathode:
        for c in tax["chemistries"]:
            if cathode in c.get("cathodes", []):
                chem = c["name"]
                break
    return {"tech": tech, "variant": variant, "chem": chem}


def check(tax: dict, records: list[tuple[str | None, str | None, str | None]]) -> list[str]:
    """records: (designation, cathode, electrolyte) for every non-component product."""
    errs: list[str] = []
    names = [t["name"] for t in tax["technologies"]]
    for n, k in Counter(names).items():
        if k > 1:
            errs.append(f"technology {n!r} is listed {k} times")
    for t in tax["technologies"]:
        vnames = [v["name"] for v in t.get("variants", [])]
        if len(vnames) != len(set(vnames)):
            errs.append(f"technology {t['name']!r} repeats a variant")
    cnames = [c["name"] for c in tax["chemistries"]]
    for n, k in Counter(cnames).items():
        if k > 1:
            errs.append(f"chemistry {n!r} is listed {k} times")
    for kind, entries in (("technology", tax["technologies"]), ("chemistry", tax["chemistries"])):
        for e in entries:
            if not e.get("aliases"):
                errs.append(f"{kind} {e['name']!r} has no search aliases")

    # A designation belongs to one technology (directly or through one variant)
    # and to at most one chemistry.
    seen_tech: Counter = Counter()
    for t in tax["technologies"]:
        for d in t.get("designations", []):
            seen_tech[d] += 1
        for v in t.get("variants", []):
            for d in v.get("designations", []):
                seen_tech[d] += 1
    for d, k in seen_tech.items():
        if k > 1:
            errs.append(f"designation {d!r} is filed under {k} technologies or variants")
    seen_chem = Counter(d for c in tax["chemistries"] for d in c.get("designations", []))
    for d, k in seen_chem.items():
        if k > 1:
            errs.append(f"designation {d!r} is filed under {k} chemistries")

    counts = Counter(records)
    unfiled: Counter = Counter()
    unfiled_cathode: Counter = Counter()
    for (designation, cathode, electrolyte), n in counts.items():
        if not designation:
            continue
        got = classify(tax, designation, cathode, electrolyte)
        if got["tech"] is None:
            unfiled[designation] += n
        elif got["chem"] is None and cathode and designation not in seen_chem:
            # A technology-level label ("Sodium-ion") that prints a cathode: the
            # cathode is the chemistry, so it must be filed, not dropped.
            if not any(cathode in c.get("cathodes", []) for c in tax["chemistries"]):
                unfiled_cathode[(designation, cathode)] += n
    for d, n in sorted(unfiled.items()):
        errs.append(f"designation {d!r} ({n} record(s)) belongs to no technology; file it in "
                    f"web/data/technologies-and-chemistries.json")
    for (d, c), n in sorted(unfiled_cathode.items()):
        errs.append(f"cathode {c!r} on {d!r} ({n} record(s)) is filed under no chemistry")
    return errs
