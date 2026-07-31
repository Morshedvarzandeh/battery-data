#!/usr/bin/env python3
"""
Bulk ingestion of published open cycling datasets.

tools/cyclers.py handles one file: sniff the vendor dialect, normalise to
BDF, work out the sign and cycle conventions, load it. What it will not do
is invent the rows that file has to hang from. A test run needs a
product_unit, a product_unit needs a product_revision, and every one of
them needs a provenance chain back to something citable.

This script is that missing layer. It takes a published dataset, builds the
organization -> product -> revision -> unit spine once, records where the
bytes came from with a hash and a retrieval date, and then walks the files
through cyclers.py.

Why datasets and not a web crawler: a cycling dataset already carries the
conditions the schema demands. A scraped HTML table does not, and the
schema will refuse it - correctly. One published dataset is worth more than
any amount of crawling, because the rate, the temperature and the cutoff
came with it.

    python tools/ingest_open_dataset.py list
    python tools/ingest_open_dataset.py plan severson-2019 ~/data/severson/
    python tools/ingest_open_dataset.py ingest oxford-2017 ~/data/oxford/ \
        --emit-sql out.sql
    python tools/ingest_open_dataset.py demo --emit-sql -    # no files needed

The demo path synthesises an aging campaign through cyclers' own generator
and runs the entire pipeline offline, so the wiring can be proved before
any download.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cyclers  # noqa: E402

log = logging.getLogger("ingest")

# =====================================================================
# Dataset registry.
#
# Landing pages, not file URLs: published datasets move their files and a
# hardcoded path rots. Fetch by hand or with your own mirror, then point
# this script at the directory.
#
# LICENCE FIELDS ARE A STARTING POINT, NOT A RULING. Verify at the landing
# page before redistributing anything. Several of these permit research use
# but not republication of the raw files, which is why this script stores a
# URL, a hash and a retrieval date rather than copying data into the repo.
# =====================================================================
DATASETS: dict[str, dict] = {
    "severson-2019": {
        "name": "Severson et al. fast-charging LFP cycling",
        "publisher": "Toyota Research Institute / MIT / Stanford",
        "landing": "https://data.matr.io/1/",
        "citation": ("Severson, K.A. et al. Data-driven prediction of battery "
                     "cycle life before capacity degradation. "
                     "Nature Energy 4, 383-391 (2019)."),
        "doi": "10.1038/s41560-019-0356-8",
        "license": "CC BY 4.0 - verify at landing page",
        "cells": "124 x A123 APR18650M1A, LFP/graphite, 1.1 Ah",
        "chemistry": "LFP", "form_factor": "cylindrical", "ff_code": "18650",
        "nominal_ah": 1.1, "nominal_v": 3.3,
        "manufacturer": "A123 Systems", "model": "APR18650M1A",
        "file_glob": "*.csv",
        "test_kind": "cycle_life",
        "notes": ("Distributed as MATLAB .mat; export per-cell CSV first. "
                  "Fast-charge policies vary per cell - that is the point of "
                  "the dataset, so keep the policy in the run notes."),
    },
    "oxford-2017": {
        "name": "Oxford Battery Degradation Dataset 1",
        "publisher": "University of Oxford",
        "landing": "https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac",
        "citation": ("Birkl, C. Oxford Battery Degradation Dataset 1. "
                     "University of Oxford (2017)."),
        "license": "CC BY - verify at landing page",
        "cells": "8 x Kokam SLPB533459H4, LCO/NCO pouch, 0.74 Ah",
        "chemistry": "LCO-NCO", "form_factor": "pouch", "ff_code": None,
        "nominal_ah": 0.74, "nominal_v": 3.7,
        "manufacturer": "Kokam", "model": "SLPB533459H4",
        "file_glob": "*.csv",
        "test_kind": "cycle_life",
        "notes": ("Drive-cycle ageing at 40 C with periodic characterisation. "
                  "The characterisation blocks are exactly the periodic_rpt "
                  "segments detect_rpt_segments looks for."),
    },
    "nasa-pcoe": {
        "name": "NASA PCoE battery data sets",
        "publisher": "NASA Ames Prognostics Center of Excellence",
        "landing": "https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/",
        "citation": ("Saha, B. and Goebel, K. Battery Data Set, NASA Prognostics "
                     "Data Repository, NASA Ames Research Center."),
        "license": "US Government work, public domain - verify at landing page",
        "cells": "18650 LCO, ~2 Ah, charge/discharge/impedance at several temperatures",
        "chemistry": "LCO", "form_factor": "cylindrical", "ff_code": "18650",
        "nominal_ah": 2.0, "nominal_v": 3.7,
        "manufacturer": "unstated", "model": "unstated",
        "file_glob": "*.csv",
        "test_kind": "cycle_life",
        "notes": ("Includes EIS sweeps alongside cycling. Those belong in "
                  "eis_spectrum, not timeseries_record - this script skips "
                  "them rather than flattening them into a time series."),
    },
    "calce": {
        "name": "CALCE battery cycling data",
        "publisher": "Center for Advanced Life Cycle Engineering, U. Maryland",
        "landing": "https://calce.umd.edu/battery-data",
        "citation": "CALCE Battery Research Group, University of Maryland.",
        "license": "research use - verify at landing page",
        "cells": ("5 cell types: INR18650-20R 2.0Ah NMC/graphite, A123 1.1Ah LFP, "
                  "CS2 1.1Ah prismatic LCO, CX2 1.35Ah prismatic LCO, PL 1.5Ah pouch LCO"),
        "chemistry": "LCO", "form_factor": "prismatic_hardcase", "ff_code": None,
        "nominal_ah": 1.1, "nominal_v": 3.7,
        "manufacturer": "unstated", "model": "CS2",
        "file_glob": "*.xlsx",
        "test_kind": "cycle_life",
        "notes": ("Set --nominal-ah per cell type; they differ (1.1 / 1.35 / 1.5 / 2.0 Ah). "
                  "Arbin exports as Excel, so convert to CSV for the sniffer. CS2_8 and "
                  "CS2_21 came off a CADEX tester and ship as .txt instead. Campaigns go "
                  "well beyond plain cycling: low-current and incremental OCV at 0/25/45 C, "
                  "DST/US06/FUDS drive cycles, pulsed-discharge profiles, temperature "
                  "cycling 25-55 C, and partial-SOC ageing with periodic full "
                  "characterisation. Cite the CALCE article for the experiment, not just "
                  "the page."),
    },
    "batteryarchive": {
        "name": "Battery Archive (aggregator)",
        "publisher": "Battery Archive contributors",
        "landing": "https://www.batteryarchive.org/",
        "citation": "Cite the originating laboratory, not the aggregator.",
        "license": "per contributing dataset - verify per file",
        "cells": "Sandia, CALCE, Oxford, HNEI, UL-PUR and others, re-served uniformly",
        "chemistry": None, "form_factor": None, "ff_code": None,
        "nominal_ah": None, "nominal_v": None,
        "manufacturer": None, "model": None,
        "file_glob": "*.csv",
        "test_kind": "cycle_life",
        "notes": ("Best first target: already normalised to one CSV layout "
                  "across laboratories, with per-cell metadata. Set --chemistry "
                  "and --nominal-ah per batch, since they vary by cell."),
    },
}


def sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def lit(v) -> str:
    """SQL literal. Kept identical in spirit to cyclers._lit."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def spine_sql(ds: dict, key: str, retrieved: str, files: list[tuple[str, str]],
              chemistry: str | None, nominal_ah: float | None) -> str:
    """
    Organization -> source -> source_location -> provenance, then
    product -> product_revision -> product_unit, one unit per file.

    Everything is idempotent on uid so re-running a dataset does not
    duplicate it.
    """
    chem = chemistry or ds.get("chemistry")
    ah = nominal_ah if nominal_ah is not None else ds.get("nominal_ah")
    manu = ds.get("manufacturer") or "unstated"
    model = ds.get("model") or key
    prod_uid = f"cell/{manu.lower().replace(' ', '-')}/{str(model).lower()}"
    src_uid = f"src/dataset/{key}"

    org_uid = "org/" + ds["publisher"].lower().replace(" ", "-").replace("/", "-")[:60]

    o = ["BEGIN;",
         "-- ---------------------------------------------------------------",
         f"-- {ds['name']}",
         f"-- {ds['publisher']}",
         f"-- {ds['citation']}",
         f"-- licence: {ds['license']}",
         f"-- chemistry {chem}, nominal {ah} Ah",
         "-- ---------------------------------------------------------------",
         "SET search_path = bd, public;",
         "",
         "INSERT INTO organization (uid, name, roles)",
         f"VALUES ({lit(org_uid)}, {lit(ds['publisher'])}, ARRAY['test_lab']::text[])",
         "  ON CONFLICT (uid) DO NOTHING;",
         "",
         "-- url is set as well as landing_url: source_has_locator requires a",
         "-- citable handle, and a dataset landing page is the only stable one",
         "-- these publishers offer.",
         "INSERT INTO source (uid, kind, title, url, landing_url, doi, repository,",
         "                    retrieved_at, retrieved_from, license, scope_note,",
         "                    redistributable, publisher_org_id)",
         f"SELECT {lit(src_uid)}, 'dataset', {lit(ds['name'])},",
         f"       {lit(ds['landing'])}, {lit(ds['landing'])}, {lit(ds.get('doi'))}, {lit(key)},",
         f"       {lit(retrieved)}, {lit(ds['landing'])}, {lit(ds['license'])},",
         f"       {lit(ds['citation'])}, FALSE, o.id",
         f"  FROM organization o WHERE o.uid = {lit(org_uid)}",
         "  ON CONFLICT (uid) DO NOTHING;",
         "",
         "-- manufacturer is its own organization: the lab that ran the test",
         "-- and the vendor that built the cell are rarely the same body.",
         "INSERT INTO organization (uid, name, roles)",
         f"VALUES ({lit('org/' + manu.lower().replace(' ', '-'))}, {lit(manu)},",
         "        ARRAY['manufacturer']::text[])",
         "  ON CONFLICT (uid) DO NOTHING;",
         "",
         "INSERT INTO product (uid, kind, manufacturer_id, model_number,",
         "                     form_factor, form_factor_code, is_rechargeable)",
         f"SELECT {lit(prod_uid)}, 'cell', o.id, {lit(model)},",
         f"       {lit(ds.get('form_factor'))}::form_factor, {lit(ds.get('ff_code'))}, TRUE",
         f"  FROM organization o WHERE o.uid = {lit('org/' + manu.lower().replace(' ', '-'))}",
         "  ON CONFLICT (uid) DO NOTHING;",
         "",
         "INSERT INTO product_revision (uid, product_id, source_id, effective_date)",
         f"SELECT {lit(prod_uid + '/rev/' + key)}, p.id, s.id, {lit(retrieved)}",
         "  FROM product p, source s",
         f" WHERE p.uid = {lit(prod_uid)} AND s.uid = {lit(src_uid)}",
         "  ON CONFLICT (uid) DO NOTHING;",
         ""]

    for path, digest in files:
        stem = os.path.splitext(os.path.basename(path))[0]
        unit_uid = f"{prod_uid}/unit/{key}/{stem}"
        base = os.path.basename(path)
        o += [f"-- {base}  sha256={digest[:16]}...",
              "INSERT INTO source_location (source_id, locator_kind, file_path, quote)",
              f"SELECT s.id, 'file', {lit(base)},",
              f"       {lit('cycler file ' + base + ' sha256:' + digest)}",
              f"  FROM source s WHERE s.uid = {lit(src_uid)};",
              "",
              "-- prior_cycle_count left NULL deliberately. Published datasets",
              "-- almost never state whether a cell was fresh, and a guessed",
              "-- zero is the most common defect in reused cycling data.",
              "INSERT INTO product_unit (uid, product_revision_id, serial_number, notes)",
              f"SELECT {lit(unit_uid)}, r.id, {lit(stem)},",
              f"       {lit('prior history not stated by the dataset')}",
              f"  FROM product_revision r WHERE r.uid = {lit(prod_uid + '/rev/' + key)}",
              "  ON CONFLICT (uid) DO NOTHING;",
              ""]

    o += ["COMMIT;", ""]
    return "\n".join(o)


def provenance_sql(key: str) -> str:
    """
    One provenance row the runs hang from. evidence 'measured' and
    extraction 'file_parse' are the honest pair here: somebody put a cell on
    a cycler and this is that file, parsed - not a vendor claim, and not an
    LLM reading a PDF.
    """
    return "\n".join([
        "BEGIN;",
        "SET search_path = bd, public;",
        "INSERT INTO provenance (source_location_id, evidence, extraction, review, confidence)",
        "SELECT sl.id, 'measured', 'file_parse', 'pending_review', 1.000",
        "  FROM source_location sl JOIN source s ON s.id = sl.source_id",
        f" WHERE s.uid = {lit('src/dataset/' + key)}",
        " ORDER BY sl.id LIMIT 1;",
        "COMMIT;",
        "",
    ])


def discover(root: str, glob_pat: str) -> list[str]:
    import glob as _g
    if os.path.isfile(root):
        return [root]
    hits = sorted(_g.glob(os.path.join(root, "**", glob_pat), recursive=True))
    return hits


def cmd_list(_a) -> int:
    print(f"{'key':18} {'cells':52} licence")
    print("-" * 100)
    for k, d in DATASETS.items():
        print(f"{k:18} {str(d['cells'])[:52]:52} {d['license']}")
    print("\nLanding pages (fetch by hand, then point this script at the directory):")
    for k, d in DATASETS.items():
        print(f"  {k:18} {d['landing']}")
    print("\nLicences are a starting point. Verify before redistributing.")
    return 0


def cmd_fetch(a) -> int:
    """
    Download the files of a dataset, verifying and recording hashes.

    Deliberately not clever: no crawling, no link discovery. You give it
    URLs, it stores the bytes with a manifest of what arrived and when.
    That manifest is what the ingest step turns into provenance rows.

    Many of these publishers sit behind a click-through or a login, and
    several corporate networks block them outright. If that is your
    situation, download by hand and skip straight to 'plan'.
    """
    import urllib.request
    import urllib.error

    ds = DATASETS[a.dataset]
    urls = a.url or []
    if not urls:
        print(f"{ds['name']}\n  landing: {ds['landing']}\n  licence: {ds['license']}")
        if ds.get("notes"):
            print(f"  note: {ds['notes']}")
        print("\nNo --url given. These publishers do not offer a stable file API,")
        print("so fetch from the landing page and re-run, or pass --url explicitly:")
        print(f"  python tools/ingest_open_dataset.py fetch {a.dataset} \\")
        print("      --url https://.../cell01.csv --url https://.../cell02.csv --dest ./data")
        return 2

    os.makedirs(a.dest, exist_ok=True)
    manifest_path = os.path.join(a.dest, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        manifest = json.load(open(manifest_path))

    ok = 0
    for u in urls:
        name = os.path.basename(u.split("?")[0]) or "download.bin"
        dest = os.path.join(a.dest, name)
        if os.path.exists(dest) and not a.force:
            log.info("%s already present, skipping (--force to refetch)", name)
            ok += 1
            continue
        try:
            log.info("fetching %s", u)
            with urllib.request.urlopen(u, timeout=a.timeout) as r, open(dest, "wb") as fh:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
        except Exception as exc:                                  # noqa: BLE001
            log.error("%s FAILED: %s", u, exc)
            log.error("  if this is a 403 or a timeout, the host is probably blocked "
                      "by your network policy - download by hand and use 'plan'")
            continue
        digest = sha256(dest)
        manifest[name] = {"url": u, "sha256": digest,
                          "retrieved": _dt.date.today().isoformat(),
                          "bytes": os.path.getsize(dest)}
        log.info("  %s  %s bytes  sha256=%s...", name,
                 manifest[name]["bytes"], digest[:16])
        ok += 1

    json.dump(manifest, open(manifest_path, "w"), indent=2, sort_keys=True)
    print(f"\n{ok}/{len(urls)} file(s) in {a.dest}; manifest at {manifest_path}")
    print(f"next:  python tools/ingest_open_dataset.py plan {a.dataset} {a.dest}")
    return 0 if ok else 1


def cmd_plan(a) -> int:
    ds = DATASETS[a.dataset]
    files = discover(a.path, a.glob or ds["file_glob"])
    print(f"{ds['name']}\n  {ds['publisher']}\n  {ds['citation']}")
    print(f"  licence: {ds['license']}")
    if ds.get("notes"):
        print(f"  note: {ds['notes']}")
    print(f"\n{len(files)} file(s) under {a.path}")
    ok = 0
    for p in files[: a.limit]:
        try:
            header, _sep = cyclers.read_header(p)
            dialect, conf = cyclers.sniff(header)
            print(f"  {os.path.basename(p):48} {dialect:10} confidence {conf:.2f}")
            ok += 1
        except Exception as exc:                                  # noqa: BLE001
            print(f"  {os.path.basename(p):48} UNREADABLE  {exc}")
    if len(files) > a.limit:
        print(f"  ... {len(files) - a.limit} more not shown (--limit)")
    print(f"\n{ok}/{min(len(files), a.limit)} readable. "
          f"Nothing has been written; run 'ingest' to emit SQL.")
    return 0


def run_pipeline(key: str, ds: dict, files: list[str], out, *,
                 chemistry=None, nominal_ah=None, test_kind=None,
                 provenance_id: int = 1) -> dict:
    retrieved = _dt.date.today().isoformat()
    hashed = [(p, sha256(p)) for p in files]
    out.write(spine_sql(ds, key, retrieved, hashed, chemistry, nominal_ah))
    out.write(provenance_sql(key))

    manu = (ds.get("manufacturer") or "unstated").lower().replace(" ", "-")
    model = str(ds.get("model") or key).lower()
    prod_uid = f"cell/{manu}/{model}"

    stats = {"files": 0, "cycles": 0, "segments": 0, "failed": [], "warnings": []}
    for path, digest in hashed:
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            nz = cyclers.normalise(path)
            sql, meta = cyclers.emit_sql(
                nz,
                unit_uid=f"{prod_uid}/unit/{key}/{stem}",
                run_uid=f"run/{key}/{stem}",
                provenance_id=provenance_id,
                test_kind=test_kind or ds["test_kind"],
                c_rate_ref_ah=nominal_ah if nominal_ah is not None else ds.get("nominal_ah"),
                c_rate_ref_src="dataset_nominal" if ds.get("nominal_ah") else None,
            )
            out.write(f"\n-- {os.path.basename(path)}  sha256={digest[:16]}...\n")
            out.write(sql)
            stats["files"] += 1
            stats["cycles"] += meta.get("n_cycles", 0)
            stats["segments"] += len(meta.get("segments", []))
            for w in meta.get("warnings", []):
                stats["warnings"].append(f"{stem}: {w}")
            log.info("%s -> %s cycles, %s segments (%s)", os.path.basename(path),
                     meta.get("n_cycles"), len(meta.get("segments", [])), nz.dialect)
        except Exception as exc:                                  # noqa: BLE001
            stats["failed"].append((os.path.basename(path), str(exc)))
            log.warning("%s FAILED: %s", os.path.basename(path), exc)
    return stats


def cmd_ingest(a) -> int:
    ds = DATASETS[a.dataset]
    files = discover(a.path, a.glob or ds["file_glob"])
    if not files:
        log.error("no files matching %s under %s", a.glob or ds["file_glob"], a.path)
        return 1
    if a.limit:
        files = files[: a.limit]

    out = sys.stdout if a.emit_sql == "-" else open(a.emit_sql, "w")
    try:
        stats = run_pipeline(a.dataset, ds, files, out,
                             chemistry=a.chemistry, nominal_ah=a.nominal_ah,
                             test_kind=a.test_kind)
    finally:
        if out is not sys.stdout:
            out.close()

    tgt = "stdout" if a.emit_sql == "-" else a.emit_sql
    sys.stderr.write(
        f"\n{stats['files']}/{len(files)} files, {stats['cycles']} cycles, "
        f"{stats['segments']} segments -> {tgt}\n")
    if stats["warnings"]:
        sys.stderr.write(f"{len(stats['warnings'])} convention warning(s):\n")
        for w in stats["warnings"][:10]:
            sys.stderr.write(f"  {w}\n")
    if stats["failed"]:
        sys.stderr.write(f"{len(stats['failed'])} file(s) failed:\n")
        for name, err in stats["failed"][:10]:
            sys.stderr.write(f"  {name}: {err}\n")
    sys.stderr.write(
        "\nNothing has touched the database. Review, then:\n"
        f"  psql -v ON_ERROR_STOP=1 -d batterydb -f {tgt}\n"
        "  psql -d batterydb -c \"SELECT bd_graph.refresh();\"\n")
    return 0 if stats["files"] else 1


def cmd_demo(a) -> int:
    """
    Prove the pipeline offline. Synthesises an aging campaign with cyclers'
    own generator, then runs the real code path over it - so a failure here
    is a real failure, not a mock passing itself.
    """
    import tempfile
    ds = dict(DATASETS["oxford-2017"])
    ds["name"] += " (SYNTHETIC DEMO - not real data)"
    ds["license"] = "n/a - synthetic"
    tmp = tempfile.mkdtemp(prefix="bd-demo-")
    files = []
    for i, dialect in enumerate(["arbin", "maccor", "neware"], 1):
        csv = cyclers._synth(dialect, n_cycles=90, rpt_every=25)
        p = os.path.join(tmp, f"demo_cell_{i:02d}_{dialect}.csv")
        with open(p, "w") as fh:
            fh.write(csv)
        files.append(p)
    out = sys.stdout if a.emit_sql == "-" else open(a.emit_sql, "w")
    try:
        stats = run_pipeline("demo-synthetic", ds, files, out, nominal_ah=0.74)
    finally:
        if out is not sys.stdout:
            out.close()
    sys.stderr.write(
        f"\ndemo: {stats['files']}/{len(files)} files, {stats['cycles']} cycles, "
        f"{stats['segments']} segments across {len(files)} vendor dialects\n"
        f"synthetic files left in {tmp}\n")
    return 0 if stats["files"] == len(files) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ingest_open_dataset")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="show the dataset registry")

    f = sub.add_parser("fetch", help="download dataset files and record hashes")
    f.add_argument("dataset", choices=sorted(DATASETS))
    f.add_argument("--url", action="append", help="repeatable")
    f.add_argument("--dest", default="./data")
    f.add_argument("--timeout", type=int, default=120)
    f.add_argument("--force", action="store_true")

    p = sub.add_parser("plan", help="scan files and report what would be ingested")
    p.add_argument("dataset", choices=sorted(DATASETS))
    p.add_argument("path")
    p.add_argument("--glob")
    p.add_argument("--limit", type=int, default=20)

    i = sub.add_parser("ingest", help="emit the SQL transaction for a dataset")
    i.add_argument("dataset", choices=sorted(DATASETS))
    i.add_argument("path")
    i.add_argument("--glob")
    i.add_argument("--limit", type=int)
    i.add_argument("--chemistry")
    i.add_argument("--nominal-ah", type=float, dest="nominal_ah")
    i.add_argument("--test-kind", dest="test_kind")
    i.add_argument("--emit-sql", default="-",
                   help="path to write SQL to, or '-' for stdout")

    d = sub.add_parser("demo", help="run the pipeline on synthetic files, offline")
    d.add_argument("--emit-sql", default="-")

    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return {"list": cmd_list, "fetch": cmd_fetch, "plan": cmd_plan,
            "ingest": cmd_ingest, "demo": cmd_demo}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
