#!/usr/bin/env python3
"""
Turn a datasheet PDF into a reviewable contribution.

    python tools/extract_datasheet.py --pdf lfp-302ah.pdf \
        --manufacturer CATL --model 302Ah --kind cell

    python tools/extract_datasheet.py --url https://example.com/cell.pdf \
        --manufacturer "Samsung SDI" --model INR21700-50E

Output is a YAML file under contrib/cells/<manufacturer>/<model>.yaml in the
same format a human contributor would write by hand, validated against
json-schema/cell-contribution.schema.json before it is written.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not write to the database. Extraction produces a *proposal*; a human
accepts, edits or rejects it. In CI that review is a pull request, which is
why this writes a file rather than an INSERT.

It also does not fill gaps. Half the quantities in this schema are
meaningless without their conditions -- a capacity with no rate and no cutoff
is not a fact -- so the extraction prompt forbids inferring them and requires
the model to name what the document leaves unstated. A datasheet that omits
the discharge rate produces `unstated: [rate_value, rate_unit]`, not a
plausible 0.2C. The validator then enforces the same rule independently, so
a model that ignores the instruction fails the run rather than filing a
confident guess.

The whole PDF goes to the model, not extracted text. Datasheet tables
interleave when flattened: four cell names followed by four masses arrive as
eight numbers in a row and pairing them back up is guesswork. Layout is data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "agents", "literature-miner"))

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml jsonschema")

MAX_PDF_BYTES = 30 * 1024 * 1024          # API limit is 32MB; leave headroom


# ---------------------------------------------------------------- prompt ----
INSTRUCTIONS = """\
You are extracting facts from a battery product datasheet into a strict
schema. You are not summarising it and you are not helping a reader; you are
producing a record that other people will cite.

THE ONE RULE THAT MATTERS

A value without its measurement conditions is not a fact. Capacity depends on
discharge rate, temperature and cutoff voltage; the same cell can differ by
several percent between 0.2C and 1C. Internal resistance depends entirely on
the method used to measure it. So:

  * If the document states a condition, record it.
  * If the document does NOT state a condition that the quantity requires,
    put that condition's name in `conditions.unstated`. Never guess it, never
    fill in a "typical" value, never leave it silently absent.

An extraction that says `unstated: [rate_value, rate_unit, temperature_c]` is
correct and useful. One that quietly assumes 25 C is a fabrication, and will
be rejected.

EVIDENCE

Every observation needs a locator: the page number it came from and a
verbatim quote from the document that contains the value. Quote what is
printed, not a paraphrase. If you cannot point at the text, do not emit the
observation.

WHAT TO EXTRACT

Only what the document states about THIS product. Do not carry over a number
from a different model in a comparison table. Do not derive values -- if the
sheet gives mass and energy but not specific energy, emit mass and energy and
let the reader divide. Derived numbers lose their conditions.

Prefer the quantity codes listed below. If a value has no matching code, skip
it rather than inventing a code.

AVAILABLE QUANTITIES (code -- required conditions)
%(registry)s

STATISTICS

`statistic` says which number in a range this is: `nominal`, `typical`,
`minimum`, `maximum`, `rated`, `guaranteed`. Datasheets usually give a
"typical" and a "minimum" capacity; both are worth having, as separate
observations.

APPLICATIONS

If, and only if, the document names specific end uses -- a named vehicle, a
named operator, a named installation -- record them under `applications`.
`basis` is `manufacturer_stated` when the manufacturer's own document says
it. Do not record generic marketing categories ("suitable for EVs") as
applications; that is not a deployment, it is a sales pitch.

PRODUCT IDENTITY

The manufacturer is who MADE the cell, which is not necessarily who published
the document: a test laboratory's report is not evidence that the laboratory
built the cell. If the document does not name the maker, leave `manufacturer`
as given to you and say so in a note rather than assuming.
"""


def build_schema(registry: dict) -> dict:
    """The extraction schema is the contribution schema, narrowed.

    Reusing the file the validator checks against means the model is aiming
    at exactly the target the validator enforces, rather than at a second
    description of it that can drift.
    """
    contrib = json.load(open(os.path.join(ROOT, "json-schema",
                                          "cell-contribution.schema.json")))
    defs = contrib["$defs"]

    def inline(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return inline(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {k: inline(v) for k, v in node.items()}
        if isinstance(node, list):
            return [inline(v) for v in node]
        return node

    props = inline(contrib["properties"])
    props["observations"]["items"]["properties"]["quantity"] = {
        "type": "string", "enum": sorted(registry),
        "description": "Quantity code. Must be one of these exactly.",
    }
    # curves are a separate job: digitising a plotted line is not something to
    # do blind from a page image, and a wrong curve is harder to spot than a
    # wrong scalar.
    props.pop("curves", None)
    props.pop("schema_version", None)
    return {
        "type": "object",
        "required": ["product", "source", "observations"],
        "properties": props,
    }


def registry_block(registry: dict) -> str:
    lines = []
    for code in sorted(registry):
        req = registry[code]
        lines.append(f"  {code}" + (f" -- requires {', '.join(req)}" if req
                                    else " -- no required conditions"))
    return "\n".join(lines)


# ------------------------------------------------------------------ io ------
def read_pdf(path: str | None, url: str | None) -> tuple[bytes, str]:
    if path:
        data = open(path, "rb").read()
        origin = os.path.basename(path)
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "battery-data"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        origin = url
    if not data.startswith(b"%PDF"):
        sys.exit(f"{origin} is not a PDF (starts {data[:8]!r})")
    if len(data) > MAX_PDF_BYTES:
        sys.exit(f"{origin} is {len(data)/1e6:.1f} MB; the API accepts 32 MB. "
                 f"Split it and extract the relevant pages.")
    return data, origin


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "unknown"


def dump_yaml(doc: dict) -> str:
    """YAML with the block ordering a reviewer expects to read.

    Default-flow-style off and sort_keys off, because a diff that reorders
    every key on re-extraction is a diff nobody reviews.
    """
    order = ["schema_version", "product", "source", "chemistry",
             "observations", "applications", "notes"]
    ordered = {k: doc[k] for k in order if k in doc}
    ordered.update({k: v for k, v in doc.items() if k not in ordered})
    return yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True,
                          width=88, default_flow_style=False)


# ---------------------------------------------------------------- main ------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", help="local PDF path")
    src.add_argument("--url", help="URL of the PDF")
    src.add_argument("--request", help="JSON file with url/manufacturer/model/"
                                       "kind/source_url/redistributable, as "
                                       "written by .github/scripts/issue_form.py")
    ap.add_argument("--manufacturer")
    ap.add_argument("--model", help="model number as printed")
    ap.add_argument("--kind", default="cell",
                    choices=["cell", "module", "pack", "system",
                             "primary_cell", "component"])
    ap.add_argument("--source-url", help="page the PDF was published on, "
                                         "if different from --url")
    ap.add_argument("--redistributable", action="store_true",
                    help="the licence permits storing the document body; "
                         "off by default, which is the safe default")
    ap.add_argument("--out", help="output path (default: contrib/cells/...)")
    ap.add_argument("--model-id", help="override the extraction model")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the YAML instead of writing it")
    a = ap.parse_args(argv)

    # A request file carries values that came from an issue body. Reading them
    # here rather than splicing them onto a command line keeps them a single
    # argv element each, with no shell and no second quote-parser in between.
    if a.request:
        r = json.load(open(a.request))
        a.url = r["url"]
        a.manufacturer = r["manufacturer"]
        a.model = r["model"]
        a.kind = r.get("kind") or "cell"
        a.source_url = r.get("source_url") or None
        a.redistributable = bool(r.get("redistributable"))
    if not (a.manufacturer and a.model):
        ap.error("--manufacturer and --model are required unless --request is used")

    registry_path = os.path.join(ROOT, "json-schema", "quantity-registry.json")
    if not os.path.exists(registry_path):
        sys.exit("no quantity registry; run tools/dump_quantities.py first")
    registry = json.load(open(registry_path))

    pdf, origin = read_pdf(a.pdf, a.url)

    from llm_anthropic import AnthropicLLM, EXTRACT_MODEL, LLMError
    llm = AnthropicLLM(model=a.model_id or EXTRACT_MODEL, max_tokens=16000)

    prompt = (INSTRUCTIONS % {"registry": registry_block(registry)}
              + f"\n\nTHIS DOCUMENT\n\nManufacturer as submitted: {a.manufacturer}"
                f"\nModel as submitted: {a.model}\nProduct kind: {a.kind}\n"
                f"Source: {a.source_url or a.url or origin}\n")

    try:
        doc = llm.complete(prompt, schema=build_schema(registry), pdfs=[pdf])
    except LLMError as e:
        sys.exit(f"extraction failed: {e}")

    doc["schema_version"] = "1"
    doc.setdefault("product", {})
    doc["product"].setdefault("kind", a.kind)
    doc["product"].setdefault("manufacturer", a.manufacturer)
    doc["product"].setdefault("model_number", a.model)
    doc["product"]["uid"] = f"{a.kind}/{slug(a.manufacturer)}/{slug(a.model)}"
    doc.setdefault("source", {})
    doc["source"].setdefault("kind", "datasheet")
    doc["source"].setdefault("uid", f"src/{slug(a.manufacturer)}-{slug(a.model)}")
    doc["source"]["redistributable"] = bool(a.redistributable)
    if a.source_url or a.url:
        doc["source"]["url"] = a.source_url or a.url

    text = dump_yaml(doc)
    header = (
        "# battery-data contribution -- extracted from a source document by\n"
        "# tools/extract_datasheet.py. NOT YET REVIEWED.\n"
        "#\n"
        "# Check before accepting: does every observation's quote actually say\n"
        "# what the value claims, and is anything in `unstated` in fact stated\n"
        "# somewhere on the page? Those are the two ways this goes wrong.\n"
    )

    out = a.out or os.path.join(ROOT, "contrib", "cells",
                                slug(a.manufacturer), f"{slug(a.model)}.yaml")

    if a.dry_run:
        print(header + text)
    else:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").write(header + text)
        print(f"wrote {os.path.relpath(out, ROOT)}")

    # Validate exactly as CI will, so a bad extraction fails here and not in
    # somebody's review.
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import validate_contrib as vc
    schema = json.load(open(vc.SCHEMA))
    tmp = out if not a.dry_run else None
    if tmp:
        errs = vc.check(tmp, schema, registry)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        n_obs = len(doc.get("observations", []))
        n_uns = sum(1 for o in doc.get("observations", [])
                    if (o.get("conditions") or {}).get("unstated"))
        print(f"{n_obs} observation(s), {n_uns} with conditions the document "
              f"does not state, {len(doc.get('applications', []))} application(s), "
              f"{len(errs)} validation error(s)")
        return 1 if errs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
