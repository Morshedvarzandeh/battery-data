#!/usr/bin/env python3
"""
literature-miner : discovery -> triage -> acquire -> classify -> extract
                   -> validate -> review queue

Runnable skeleton. The discovery and parsing stages are real; the model
calls are behind a single `LLM` protocol so you can plug in whichever
provider you use without touching the pipeline logic.

The design commitment worth preserving if you rewrite this: every stage
is a separate, narrowly-scoped decision. A single prompt that "reads the
paper and returns the data" confabulates. A chain where each step can
answer "no" does so far less.

    python pipeline.py discover --query "HPPC lithium-ion aging" --limit 50
    python pipeline.py run --doi 10.1016/j.jpowsour.2020.228566
    python pipeline.py ingest-dataset --url https://zenodo.org/records/1234
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import os
import re
import sys
import time
from typing import Any, Iterable, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

log = logging.getLogger("literature-miner")

AGENT_NAME = "literature-miner"
AGENT_VERSION = "0.3.0"
USER_AGENT = "battery-data/0.1 (+https://github.com/Morshedvarzandeh/battery-data)"

# =====================================================================
# Model interface
# =====================================================================


class LLM(Protocol):
    def complete(self, prompt: str, *, schema: dict | None = None,
                 images: list[bytes] | None = None) -> Any: ...


class NullLLM:
    """Placeholder so the pipeline is importable and testable without keys."""

    def complete(self, prompt, *, schema=None, images=None):
        raise NotImplementedError(
            "Wire up a model provider. Every call site passes a JSON Schema; "
            "constrain the model to it rather than parsing free text."
        )


def make_llm(stage: str = "triage") -> LLM:
    """AnthropicLLM when a key is present, NullLLM otherwise - so importing
    and offline commands (discover, selftest) never require credentials."""
    if os.getenv("ANTHROPIC_API_KEY"):
        from llm_anthropic import get_llm
        return get_llm(stage)
    return NullLLM()


# =====================================================================
# 1. DISCOVER
# =====================================================================

# Multi-modal query set. A single phrasing misses most of the corpus, so
# each family is run independently and the results unioned.
QUERY_FAMILIES: dict[str, list[str]] = {
    "test_method": [
        "hybrid pulse power characterization lithium ion",
        "electrochemical impedance spectroscopy lithium-ion aging",
        "galvanostatic intermittent titration technique diffusion",
        "incremental capacity analysis degradation",
        "differential voltage analysis lithium-ion",
        "accelerating rate calorimetry 18650",
        "high precision coulometry lithium ion",
        "entropic coefficient measurement lithium cell",
    ],
    "cell_identity": [
        "INR21700 characterization", "18650 NMC cycling dataset",
        "LG M50 parameterisation", "A123 ANR26650 LFP",
        "LFP prismatic 280Ah cycle life", "4680 cell characterization",
    ],
    "quantity": [
        "specific heat capacity lithium-ion cell measurement",
        "anisotropic thermal conductivity pouch cell",
        "self-discharge rate lithium-ion measurement",
        "open circuit voltage hysteresis LFP",
    ],
    "dataset_intent": [
        "battery cycling dataset open data",
        "data descriptor lithium-ion battery degradation",
        "battery aging dataset calendar cyclic",
    ],
    "degradation": [
        "loss of lithium inventory quantification",
        "knee point battery degradation prediction",
        "calendar aging Arrhenius lithium ion",
        "lithium plating onset detection",
    ],
}


def _get_json(url: str, params: dict | None = None, retries: int = 3) -> dict:
    if params:
        url = f"{url}?{urlencode(params)}"
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT,
                                        "Accept": "application/json"})
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as exc:                      # noqa: BLE001
            if attempt == retries - 1:
                log.warning("GET failed %s: %s", url, exc)
                return {}
            time.sleep(2 ** attempt)
    return {}


@dataclasses.dataclass
class Candidate:
    """A discovered work, before we know whether it holds usable data."""
    source: str
    doi: str | None = None
    title: str = ""
    abstract: str = ""
    year: int | None = None
    url: str | None = None
    pdf_url: str | None = None
    license: str | None = None
    repository_links: list[str] = dataclasses.field(default_factory=list)
    raw: dict = dataclasses.field(default_factory=dict)

    def key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower()}"
        return "title:" + re.sub(r"\W+", "", self.title.lower())[:120]


def discover_openalex(query: str, limit: int = 50) -> list[Candidate]:
    data = _get_json("https://api.openalex.org/works", {
        "search": query, "per-page": min(limit, 200),
        "filter": "type:article", "mailto": os.getenv("CONTACT_EMAIL", ""),
    })
    out = []
    for w in data.get("results", [])[:limit]:
        inv = w.get("abstract_inverted_index") or {}
        abstract = " ".join(inv.keys()) if inv else ""
        loc = (w.get("best_oa_location") or {})
        out.append(Candidate(
            source="openalex",
            doi=(w.get("doi") or "").replace("https://doi.org/", "") or None,
            title=w.get("title") or "",
            abstract=abstract[:4000],
            year=w.get("publication_year"),
            url=w.get("id"),
            pdf_url=loc.get("pdf_url"),
            license=loc.get("license"),
            raw={"cited_by": w.get("cited_by_count")},
        ))
    return out


def discover_zenodo(query: str, limit: int = 50) -> list[Candidate]:
    """Datasets are the highest-yield target: raw time series, not prose."""
    data = _get_json("https://zenodo.org/api/records", {
        "q": query, "size": min(limit, 100), "type": "dataset",
    })
    out = []
    for rec in data.get("hits", {}).get("hits", [])[:limit]:
        md = rec.get("metadata", {})
        out.append(Candidate(
            source="zenodo",
            doi=md.get("doi"),
            title=md.get("title", ""),
            abstract=re.sub(r"<[^>]+>", "", md.get("description", ""))[:4000],
            year=int((md.get("publication_date") or "0")[:4]) or None,
            url=rec.get("links", {}).get("self_html"),
            license=(md.get("license") or {}).get("id"),
            repository_links=[f.get("links", {}).get("self", "")
                              for f in rec.get("files", [])],
            raw={"n_files": len(rec.get("files", []))},
        ))
    return out


def discover_arxiv(query: str, limit: int = 50) -> list[Candidate]:
    url = ("http://export.arxiv.org/api/query?"
           + urlencode({"search_query": f"all:{query}", "max_results": limit}))
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}),
                     timeout=30) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as exc:                          # noqa: BLE001
        log.warning("arxiv failed: %s", exc)
        return []
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S)[:limit]:
        def tag(t):
            m = re.search(rf"<{t}>(.*?)</{t}>", entry, re.S)
            return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        aid = tag("id")
        out.append(Candidate(
            source="arxiv", title=tag("title"), abstract=tag("summary")[:4000],
            url=aid, pdf_url=aid.replace("/abs/", "/pdf/"),
            year=int(tag("published")[:4] or 0) or None, license="arxiv",
        ))
    return out


def discover_osti(query: str, limit: int = 50) -> list[Candidate]:
    """US national labs: INL, NREL, SNL, ANL. Test manuals and abuse data."""
    data = _get_json("https://www.osti.gov/api/v1/records",
                     {"q": query, "rows": min(limit, 100)})
    rows = data if isinstance(data, list) else data.get("records", [])
    return [Candidate(
        source="osti", doi=r.get("doi"), title=r.get("title", ""),
        abstract=(r.get("description") or "")[:4000],
        year=int((r.get("publication_date") or "0")[:4] or 0) or None,
        url=r.get("links", [{}])[0].get("href") if r.get("links") else None,
    ) for r in rows[:limit]]


DISCOVERERS = {
    "openalex": discover_openalex,
    "zenodo": discover_zenodo,
    "arxiv": discover_arxiv,
    "osti": discover_osti,
}


def discover(queries: Iterable[str], limit: int = 50,
             backends: Iterable[str] = ("openalex", "zenodo", "arxiv")) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for q in queries:
        for b in backends:
            try:
                for c in DISCOVERERS[b](q, limit):
                    if c.key() not in seen:
                        seen[c.key()] = c
            except Exception as exc:                  # noqa: BLE001
                log.warning("%s/%s failed: %s", b, q, exc)
    log.info("discovered %d unique works", len(seen))
    return list(seen.values())


# =====================================================================
# 2. TRIAGE
# =====================================================================

TRIAGE_SCHEMA = {
    "type": "object",
    "required": ["has_data", "data_kinds", "data_availability", "priority", "reason"],
    "properties": {
        "has_data": {"type": "boolean"},
        "data_kinds": {"type": "array", "items": {"type": "string"}},
        "cell_identified": {"type": "boolean"},
        "cell_hint": {"type": ["string", "null"]},
        "n_cells_hint": {"type": ["integer", "null"]},
        "data_availability": {
            "enum": ["repository", "supplementary", "tables", "figures_only", "none"]},
        "priority": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "additionalProperties": False,
}

TRIAGE_PROMPT = """\
You are triaging a scientific work for a battery database. Decide only whether
it contains battery data that could be extracted into structured records, and
of what kind. Do NOT extract any values.

Answer "has_data": false for review articles, pure modelling papers with no
new measurements, and papers that only cite others' data.

Rank data_availability by how the data can actually be obtained:
  repository    - links a dataset (Zenodo, Figshare, GitHub, data.matr.io)
  supplementary - SI files attached to the paper
  tables        - numbers in the paper's own tables
  figures_only  - data exists only as plotted curves
  none          - no extractable data

Be conservative. A false "yes" costs an expensive full-text pass; a false "no"
costs one paper out of thousands.

TITLE: {title}

ABSTRACT: {abstract}
"""


def triage(llm: LLM, c: Candidate) -> dict:
    return llm.complete(
        TRIAGE_PROMPT.format(title=c.title, abstract=c.abstract[:3000]),
        schema=TRIAGE_SCHEMA,
    )


def triage_file(llm: LLM, in_path: str, out_path: str,
                min_priority: float = 0.0) -> dict:
    """Triage every candidate in a discover-output JSON file.

    Failures on individual papers are recorded and skipped, never fatal:
    a sweep over 300 abstracts must not die on abstract 217.
    """
    cands = json.load(open(in_path))
    results, errors = [], 0
    for i, raw in enumerate(cands):
        c = Candidate(**{k: v for k, v in raw.items()
                         if k in Candidate.__dataclass_fields__})
        try:
            verdict = triage(llm, c)
        except Exception as exc:                      # noqa: BLE001
            log.warning("triage failed on %s: %s", c.key(), exc)
            errors += 1
            continue
        if verdict.get("has_data") and verdict.get("priority", 0) >= min_priority:
            results.append({**raw, "triage": verdict})
        if (i + 1) % 25 == 0:
            log.info("triaged %d/%d (%d kept)", i + 1, len(cands), len(results))

    results.sort(key=lambda r: -r["triage"]["priority"])
    summary = {
        "n_in": len(cands), "n_kept": len(results), "n_errors": errors,
        "by_availability": {},
    }
    for r in results:
        k = r["triage"]["data_availability"]
        summary["by_availability"][k] = summary["by_availability"].get(k, 0) + 1

    json.dump({"summary": summary, "candidates": results},
              open(out_path, "w"), indent=2)
    return summary


# =====================================================================
# 5. EXTRACT — schema the model is constrained to
# =====================================================================

OBSERVATION_SCHEMA = {
    "type": "object",
    "required": ["records"],
    "properties": {
        "records": {"type": "array", "items": {
            "type": "object",
            "required": ["quantity_code", "value", "unit", "conditions",
                         "locator", "confidence"],
            "properties": {
                "quantity_code": {"type": "string"},
                "statistic": {"enum": ["rated", "nominal", "standard", "minimum",
                                       "typical", "maximum", "initial", "design",
                                       "guaranteed", "mean", "median", "measured"]},
                "value": {"type": "number"},
                "unit": {"type": "string"},
                "tol_plus": {"type": ["number", "null"]},
                "tol_minus": {"type": ["number", "null"]},
                "is_lower_bound": {"type": "boolean"},
                "conditions": {
                    "type": "object",
                    "description": "condition_set columns. Anything the source "
                                   "does not state goes in 'unstated', never omitted.",
                    "properties": {
                        "temperature_c": {"type": ["number", "null"]},
                        "temperature_reference": {"type": ["string", "null"]},
                        "rate_value": {"type": ["number", "null"]},
                        "rate_unit": {"type": ["string", "null"]},
                        "rate_reference_capacity_ah": {"type": ["number", "null"]},
                        "voltage_upper_v": {"type": ["number", "null"]},
                        "voltage_lower_v": {"type": ["number", "null"]},
                        "soc_pct": {"type": ["number", "null"]},
                        "pulse_duration_s": {"type": ["number", "null"]},
                        "frequency_hz": {"type": ["number", "null"]},
                        "cycle_index": {"type": ["integer", "null"]},
                        "direction": {"type": ["string", "null"]},
                        "unstated": {"type": "array", "items": {"type": "string"}},
                        "verbatim": {"type": ["string", "null"]},
                    },
                },
                "locator": {
                    "type": "object",
                    "required": ["quote"],
                    "properties": {
                        "page": {"type": ["integer", "null"]},
                        "section": {"type": ["string", "null"]},
                        "quote": {"type": "string", "minLength": 10},
                        "bbox": {"type": ["array", "null"],
                                 "items": {"type": "number"}},
                    },
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "additionalProperties": False,
        }},
    },
}

EXTRACT_PROMPT = """\
Extract battery measurements from the region below into structured records.

RULES — these are enforced downstream and violations are rejected:

1. Every record needs a `quote`: the verbatim text from the source that
   supports the value. If you cannot quote it, do not emit it.

2. Every record needs its CONDITIONS. A capacity without rate, temperature and
   cutoff voltage is not a fact. Conditions are usually NOT in the table - look
   in the caption, the methods section, and footnotes.

3. If the source genuinely does not state a condition, list that column name in
   `unstated`. Do NOT infer it, do NOT default it to 25 C, do NOT omit it.
   "The paper never says" is itself valuable information.

4. Never convert between units that are not interconvertible. A 0.5P constant-
   power rating is not a C-rate. An AC impedance is not a DC resistance. A
   mV/day self-discharge is not a leakage current.

5. Emit one record per stated value. "Rated", "typical" and "minimum" capacity
   are three separate claims, not three estimates of one.

6. Prefer omission to guessing.

Valid quantity_code values: {quantities}

REGION ({region_kind}, page {page}):
{content}

SURROUNDING CONTEXT (caption, methods):
{context}
"""


def extract_region(llm: LLM, region: dict, context: str,
                   quantities: list[str]) -> dict:
    return llm.complete(
        EXTRACT_PROMPT.format(
            quantities=", ".join(quantities),
            region_kind=region.get("kind"), page=region.get("page"),
            content=region.get("content", ""), context=context[:4000],
        ),
        schema=OBSERVATION_SCHEMA,
    )


# =====================================================================
# 5b. Cycler file parsing
# =====================================================================

CYCLER_PARSERS = {
    ".res":    ("galvani",    "MPRfile/ArbinFile"),
    ".mpr":    ("galvani",    "MPRfile"),
    ".mpt":    ("eclabfiles", "process"),
    ".nda":    ("NewareNDA",  "read"),
    ".ndax":   ("NewareNDA",  "read"),
    ".bdf":    ("batterydf",  "read"),
    ".txt":    ("beep",       "MaccorDatapath"),
    ".csv":    ("pandas",     "read_csv"),
    ".parquet": ("pandas",    "read_parquet"),
    ".h5":     ("battdat",    "BatteryDataset.from_hdf"),
}


def infer_current_sign(df) -> str:
    """
    Never trust the column name. battdat / VDF / battery-data-standard are
    charge-positive; ionworksdata is discharge-positive. Infer from whether
    charge capacity accumulates while current is positive.
    """
    try:
        import numpy as np
        cur = df["current_ampere"].to_numpy()
        cap = df.get("charging_capacity_ah")
        if cap is None:
            return "unspecified"
        dcap = np.diff(cap.to_numpy())
        pos = cur[1:] > 0
        if pos.sum() < 10:
            return "unspecified"
        return "charge_positive" if np.nanmean(dcap[pos]) > 0 else "discharge_positive"
    except Exception:                                 # noqa: BLE001
        return "unspecified"


def detect_rpt_segments(cycle_summary) -> list[dict]:
    """
    Split an aging run into [aging, RPT, aging, RPT, ...].

    RPTs are the low-rate, longer cycles recurring at a fixed interval.
    Cluster on (mean rate, duration); the minority cluster that appears
    periodically is the RPT. This is the structure every aging dataset has
    and no published schema records, which is why the literature is
    perennially confused about whether a plotted capacity came from the
    RPT or from the cycling itself.
    """
    import numpy as np
    if not len(cycle_summary):
        return []
    dur = np.asarray([c["duration_s"] for c in cycle_summary], float)
    med = np.nanmedian(dur)
    is_rpt = dur > 1.8 * med                          # markedly longer than typical

    segments, start, cur = [], 0, bool(is_rpt[0])
    for i, flag in enumerate(is_rpt):
        if bool(flag) != cur:
            segments.append({"role": "periodic_rpt" if cur else "aging_cycling",
                             "start_cycle": int(cycle_summary[start]["cycle_index"]),
                             "end_cycle": int(cycle_summary[i - 1]["cycle_index"])})
            start, cur = i, bool(flag)
    segments.append({"role": "periodic_rpt" if cur else "aging_cycling",
                     "start_cycle": int(cycle_summary[start]["cycle_index"]),
                     "end_cycle": int(cycle_summary[-1]["cycle_index"])})
    if segments and segments[0]["role"] == "periodic_rpt":
        segments[0]["role"] = "baseline_rpt"
    if segments and segments[-1]["role"] == "periodic_rpt":
        segments[-1]["role"] = "final_rpt"
    return segments


# =====================================================================
# 6/7. Stage into the review queue
# =====================================================================

def stage_candidates(conn, job_id: int, records: list[dict],
                     product_hint: str | None) -> int:
    """Write extracted records to bd_stage, then validate them mechanically."""
    n = 0
    with conn.cursor() as cur:
        for r in records:
            loc = r.get("locator", {})
            cur.execute("""
                INSERT INTO bd_stage.candidate
                  (job_id, target_table, payload, product_hint, quantity_code,
                   value_native, unit_native, condition_json,
                   page, section, quote, bbox, confidence)
                VALUES (%s,'observation',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (job_id, json.dumps(r), product_hint, r.get("quantity_code"),
                  r.get("value"), r.get("unit"),
                  json.dumps(r.get("conditions") or {}),
                  loc.get("page"), loc.get("section"), loc.get("quote"),
                  loc.get("bbox"), r.get("confidence")))
            cid = cur.fetchone()[0]
            cur.execute("SELECT bd_stage.validate_candidate(%s)", (cid,))
            cur.execute("SELECT bd_stage.detect_conflicts(%s)", (cid,))
            n += 1
    conn.commit()
    return n


def open_agent_run(conn, prompt_files: list[str], model_id: str) -> int:
    h = hashlib.sha256()
    for p in sorted(prompt_files):
        if os.path.exists(p):
            h.update(open(p, "rb").read())
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO bd.agent_run
              (uid, agent_name, agent_version, model_id, prompt_sha256, toolchain)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
        """, (f"run/{AGENT_NAME}/{int(time.time())}", AGENT_NAME, AGENT_VERSION,
              model_id, h.hexdigest(), json.dumps({"parsers": CYCLER_PARSERS})))
        rid = cur.fetchone()[0]
    conn.commit()
    return rid


# =====================================================================
# CLI
# =====================================================================

def main(argv=None):
    ap = argparse.ArgumentParser(prog="literature-miner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="search for candidate works")
    d.add_argument("--query", action="append",
                   help="repeatable; omit to use the built-in query families")
    d.add_argument("--family", action="append", choices=list(QUERY_FAMILIES))
    d.add_argument("--limit", type=int, default=50)
    d.add_argument("--backend", action="append", choices=list(DISCOVERERS))
    d.add_argument("--out", default="-")

    t = sub.add_parser("triage", help="LLM-triage a discover output file")
    t.add_argument("input", help="JSON file written by `discover --out`")
    t.add_argument("--out", default="triaged.json")
    t.add_argument("--min-priority", type=float, default=0.5)

    for name, helptext in [("run", "full pipeline on one work"),
                           ("ingest-dataset", "parse a dataset archive")]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("--doi")
        s.add_argument("--url")
        s.add_argument("--dsn", default=os.getenv("BATTERY_DSN",
                                                  "dbname=batterydb"))

    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s %(message)s")

    if a.cmd == "discover":
        queries = list(a.query or [])
        for f in (a.family or ([] if queries else list(QUERY_FAMILIES))):
            queries += QUERY_FAMILIES[f]
        cands = discover(queries, a.limit,
                         a.backend or ("openalex", "zenodo", "arxiv"))
        payload = [dataclasses.asdict(c) for c in cands]
        out = json.dumps(payload, indent=2)
        if a.out == "-":
            print(out)
        else:
            open(a.out, "w").write(out)
            log.info("wrote %d candidates to %s", len(payload), a.out)
        return 0

    if a.cmd == "triage":
        llm = make_llm("triage")
        if isinstance(llm, NullLLM):
            log.error("triage needs ANTHROPIC_API_KEY; see AGENT.md")
            return 1
        summary = triage_file(llm, a.input, a.out, a.min_priority)
        print(json.dumps(summary, indent=2))
        log.info("wrote %s", a.out)
        return 0

    log.error("stage '%s' needs a configured LLM provider and database; "
              "see AGENT.md", a.cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
