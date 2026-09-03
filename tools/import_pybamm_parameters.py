#!/usr/bin/env python3
"""Import a published PyBaMM parameter set as a model contribution.

PyBaMM ships parameter sets that are transcriptions of peer-reviewed
parameterisation papers (Chen 2020 for the LG M50, Marquis 2019 and Ecker
2015 for Kokam pouch cells), each file citing the paper it came from. That
is exactly the model layer this schema has a table for and nothing in it:
bd.model_parameterisation, with fit provenance.

This reads one such file at a pinned PyBaMM tag, records where the bytes
came from (URL, tag, sha256) and which article they cite (DOI from PyBaMM's
own CITATIONS.bib), and writes a contribution under contrib/models/ that
tools/load_models.py loads. Scalar parameters are kept as numbers;
function-valued parameters carry their source code, because a fitted OCP
curve is the function, not a number.

With --write-product it also writes the cell's contribution file from the
handful of cell-level values the set states (nominal capacity, cut-offs),
each quoting the line of the file it was read from. That file is a starting
point for review, not a datasheet: it says so in source.note.

    python tools/import_pybamm_parameters.py --set Chen2020 --tag v24.1 \\
        --product cell/lg-energy-solution/inr21700-m50 \\
        --manufacturer "LG Energy Solution" --model INR21700-M50 --write-product
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import sys
import types
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = "https://raw.githubusercontent.com/pybamm-team/PyBaMM/{tag}/pybamm/{path}"
CACHE = os.path.join(ROOT, "vocab", "cache", "pybamm")


def fetch(tag: str, path: str) -> tuple[bytes, str]:
    os.makedirs(CACHE, exist_ok=True)
    dest = os.path.join(CACHE, f"{tag}-{path.replace('/', '_')}")
    url = RAW.format(tag=tag, path=path)
    if not os.path.exists(dest):
        with urllib.request.urlopen(url, timeout=120) as resp:
            open(dest, "wb").write(resp.read())
    data = open(dest, "rb").read()
    return data, url


def bib_entries(text: str) -> dict:
    out = {}
    for m in re.finditer(r"@\w+\{([^,]+),(.*?)\n\}", text, re.S):
        key, body = m.group(1).strip(), m.group(2)
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\")", body):
            fields[f.group(1).lower()] = f.group(2)[1:-1].strip()
        out[key] = fields
    return out


class _Any:
    """Stands in for any pybamm runtime object a parameter file touches at
    import time (data loaders, processed tables). It is never evaluated; the
    payload records that the value is a runtime object, not a number."""
    def __getattr__(self, name):
        return _Any()

    def __call__(self, *args, **kwargs):
        return _Any()

    def __iter__(self):
        return iter(())


class _Module(types.ModuleType):
    def __getattr__(self, name):
        return _Any()


def stub_pybamm() -> types.ModuleType:
    """Enough of pybamm for a parameter file to import without pybamm."""
    import numpy as np
    m = _Module("pybamm")
    for name in ("exp", "tanh", "cosh", "sinh", "sqrt", "log", "log10", "maximum", "minimum",
                 "sigmoid", "arctan", "power"):
        setattr(m, name, getattr(np, name, None) or (lambda *a, **k: None))
    m.Parameter = lambda name: name
    m.Scalar = lambda v, *a, **k: v
    m.FunctionParameter = lambda name, inputs=None, **k: name
    m.constants = types.SimpleNamespace(R=8.314462618, F=96485.33212, k_b=1.380649e-23, q_e=1.602176634e-19)
    m.Interpolant = lambda *a, **k: None
    m.t = "t"
    return m


def serialise(value):
    import numpy as np
    if isinstance(value, _Any):
        return {"unresolved": "pybamm runtime object (a data file or processed table), not transcribed"}
    if callable(value):
        try:
            src = inspect.getsource(value)
        except (OSError, TypeError):
            src = None
        return {"function": getattr(value, "__name__", "function"), "source": src}
    if isinstance(value, tuple):
        return {"tuple": [serialise(v) for v in value]}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {k: serialise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialise(v) for v in value]
    return value


def load_set(data: bytes, name: str) -> tuple[dict, str, list[str]]:
    sys.modules["pybamm"] = stub_pybamm()
    module = types.ModuleType(name)
    module.__file__ = f"<pybamm {name}>"
    exec(compile(data.decode("utf-8"), f"<pybamm {name}>", "exec"), module.__dict__)
    values = module.get_parameter_values()
    doc = inspect.getdoc(module.get_parameter_values) or ""
    cited = sorted(set(re.findall(r":footcite:t:`([^`]+)`", data.decode("utf-8"))))
    return values, doc, cited


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", s.lower()).strip("-")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, help="parameter set name, e.g. Chen2020")
    ap.add_argument("--tag", default="v24.1", help="PyBaMM git tag the file is read at")
    ap.add_argument("--product", required=True, help="library uid of the cell the set describes")
    ap.add_argument("--manufacturer")
    ap.add_argument("--model")
    ap.add_argument("--chemistry-designation")
    ap.add_argument("--write-product", action="store_true")
    a = ap.parse_args()

    path = f"input/parameters/lithium_ion/{a.set}.py"
    data, url = fetch(a.tag, path)
    digest = hashlib.sha256(data).hexdigest()
    bib, _ = fetch(a.tag, "CITATIONS.bib")
    entries = bib_entries(bib.decode("utf-8"))
    values, doc, cited = load_set(data, a.set)
    primary = (a.set if a.set in cited
               else next((k for k in cited if k.startswith(a.set)), cited[0] if cited else a.set))
    citations = []
    for key in cited or [a.set]:
        e = entries.get(key, {})
        citations.append({"key": key, "doi": e.get("doi"), "title": e.get("title"),
                          "journal": e.get("journal"), "year": e.get("year"),
                          "author": e.get("author")})
    lead = next((c for c in citations if c["key"] == primary), citations[0])

    _, maker, model = a.product.split("/", 2)
    model_uid = f"model/{maker}/{model}/{slug(a.set)}"
    source_uid = f"src/pybamm-{a.tag}-{slug(a.set)}"
    ref_t = values.get("Reference temperature [K]")
    payload = {k: serialise(v) for k, v in values.items()}
    contribution = {
        "schema_version": "1",
        "model": {
            "uid": model_uid,
            "name": f"{a.set} parameter set for the {a.model or model} (PyBaMM {a.tag})",
            "kind": "dfn_parameter_set",
            "format_name": "pybamm_dict",
            "format_version": f"PyBaMM {a.tag}",
            "product_uid": a.product,
            "reference_temperature_c": round(ref_t - 273.15, 2) if isinstance(ref_t, (int, float)) else None,
            "notes": doc,
        },
        "source": {
            "uid": source_uid,
            "kind": "journal_article",
            "title": lead.get("title") or f"PyBaMM parameter set {a.set}",
            "doi": lead.get("doi"),
            "url": url,
            "sha256": digest,
            "license": "BSD-3-Clause (PyBaMM); parameter values as published in the cited articles",
            "note": (f"Values read from PyBaMM's {a.set}.py at tag {a.tag}, which cites the "
                     f"articles listed under citations. Function-valued parameters carry the "
                     f"source code of the fitted expression. The set's own note applies: "
                     f"these are values used to fit models in the cited papers, not "
                     f"guaranteed cell parameters."),
        },
        "citations": citations,
        "payload": payload,
    }
    out = os.path.join(ROOT, "contrib", "models", maker, f"{model}-{slug(a.set)}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(contribution, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    n_fn = sum(1 for v in payload.values() if isinstance(v, dict) and "function" in v)
    print(f"  wrote {os.path.relpath(out, ROOT)}: {len(payload)} parameters, {n_fn} functions, "
          f"cites {', '.join(c['key'] for c in citations)}")

    if a.write_product:
        text = data.decode("utf-8")
        def line_for(key):
            m = re.search(r'^\s*"' + re.escape(key) + r'".*$', text, re.M)
            return m.group(0).strip() if m else None
        obs = []
        cap, lower, upper = (values.get("Nominal cell capacity [A.h]"),
                             values.get("Lower voltage cut-off [V]"),
                             values.get("Upper voltage cut-off [V]"))
        if cap is not None:
            cond = {"unstated": ["rate_value", "rate_unit", "temperature_c"]}
            if lower is not None:
                cond["voltage_lower_v"] = lower
            else:
                cond["unstated"].append("voltage_lower_v")
            obs.append({"quantity": "capacity", "statistic": "nominal", "value": cap, "unit": "Ah",
                        "conditions": cond,
                        "locator": {"section": "get_parameter_values()",
                                    "quote": line_for("Nominal cell capacity [A.h]")}})
        if upper is not None:
            obs.append({"quantity": "charge_cutoff_voltage", "statistic": "nominal", "value": upper,
                        "unit": "V", "locator": {"section": "get_parameter_values()",
                                                  "quote": line_for("Upper voltage cut-off [V]")}})
        if lower is not None:
            obs.append({"quantity": "discharge_cutoff_voltage", "statistic": "nominal", "value": lower,
                        "unit": "V", "locator": {"section": "get_parameter_values()",
                                                  "quote": line_for("Lower voltage cut-off [V]")}})
        product = {
            "schema_version": "1",
            "product": {"uid": a.product, "kind": "cell", "manufacturer": a.manufacturer or maker,
                        "model_number": a.model or model, "is_rechargeable": True},
            "source": {**contribution["source"],
                       "note": (f"Cell-level values read from PyBaMM's {a.set}.py at tag {a.tag}, "
                                f"a transcription of the cited parameterisation article. A "
                                f"starting point for a datasheet-backed record, not a datasheet: "
                                f"rate and temperature for the nominal capacity are not stated "
                                f"in the parameter file.")},
            "observations": obs,
        }
        if a.chemistry_designation:
            product["chemistry"] = {"designation": a.chemistry_designation}
        pout = os.path.join(ROOT, "contrib", "cells", maker, f"{model}.yaml")
        os.makedirs(os.path.dirname(pout), exist_ok=True)
        if os.path.exists(pout):
            print(f"  product file exists, not overwritten: {os.path.relpath(pout, ROOT)}")
        else:
            with open(pout, "w", encoding="utf-8") as fh:
                json.dump(product, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            print(f"  wrote {os.path.relpath(pout, ROOT)}: {len(obs)} observations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
