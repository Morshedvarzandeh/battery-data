#!/usr/bin/env python3
"""Load accepted contributions from contrib/ into the relational library.

`contrib/` is the accepted end of the review flow, and nothing carried it into
Postgres. `tools/build_db.sh` loads the schema, the seed files load four
reference cells and the valuation layer, and `tools/build_web_data.py` reads
the YAML straight into the catalog page. So an approved battery appeared on the
site and in no query -- which is the gap this closes.

Everything lands in `bd_stage` first, because docs/04-ingestion.md says no
inbound path writes `bd.*` directly and this one is not special. Staging earns
its place here rather than merely obeying the rule: it is where the unit table,
the quantity registry, the required-conditions rule and the plausibility bounds
get applied, and where a value that contradicts an already-accepted one is
flagged before it lands rather than after.

Promotion runs by default because `contrib/` is post-review by construction --
a file is only there because the owner approved its issue or merged its pull
request. `--stage-only` stops after validation and leaves the review queue
populated instead.

    python tools/load_contrib.py --dsn dbname=batterydb
    python tools/load_contrib.py --dsn dbname=batterydb --stage-only
    python tools/load_contrib.py --dsn dbname=batterydb contrib/cells/byd

Re-running is safe. A file whose bytes were loaded before is skipped, and a
file that has changed since supersedes its previous load rather than asserting
the same claim twice.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import sys

try:
    import psycopg2
    import psycopg2.extras
    import yaml
except ImportError:
    sys.exit("pip install psycopg2-binary pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# How a source's kind bears on what its numbers are worth. A datasheet is the
# maker asserting something about its own product; a third-party lab is someone
# else measuring it. The database keeps that distinction and so must this.
EVIDENCE_BY_SOURCE_KIND = {
    "datasheet": "manufacturer_claim",
    "manufacturer_web": "manufacturer_claim",
    "distributor_listing": "manufacturer_claim",
    "regulatory_filing": "manufacturer_claim",
    "third_party_test": "measured",
    "internal_measurement": "measured",
    "teardown_report": "measured",
    "journal_article": "literature_reported",
    "preprint": "literature_reported",
    "conference_paper": "literature_reported",
    "thesis": "literature_reported",
    "dataset": "measured",
}

# Conditions travel as a jsonb payload for bd.intern_conditions. `verbatim` is
# the contributor's own wording of the test setup and has no column.
CONDITION_DROP = {"verbatim"}


def document_date(source: dict) -> tuple[str | None, int | None, dict]:
    """Split a stated document date into the precision the columns can hold.

    Datasheets are dated "2020-10" and "2022" as often as they are dated in
    full. `source.document_date` is a DATE, so storing those means inventing a
    day the document does not carry. The year goes to `published_year`, the
    literal to `raw_metadata`, and the date column stays empty rather than
    precise and wrong.
    """
    stated = str(source.get("document_date") or "").strip()
    if not stated:
        return None, None, {}
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stated):
        return stated, int(stated[:4]), {}
    if re.fullmatch(r"\d{4}(-\d{2})?", stated):
        return None, int(stated[:4]), {"document_date_stated": stated}
    return None, None, {"document_date_stated": stated}


def sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def scalar(cur, sql: str, params: tuple = ()) -> int | None:
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def ensure_organization(cur, slug: str, name: str) -> int:
    uid = f"org/{slug}"
    cur.execute(
        """INSERT INTO bd.organization (uid, name, roles) VALUES (%s, %s, '{manufacturer}')
           ON CONFLICT (uid) DO NOTHING""", (uid, name))
    return scalar(cur, "SELECT id FROM bd.organization WHERE uid = %s", (uid,))


def ensure_source(cur, source: dict, org_id: int) -> int:
    dated, year, extra = document_date(source)
    cur.execute(
        """INSERT INTO bd.source (uid, kind, title, publisher_org_id, url, revision,
                                  document_date, published_year, is_final, license,
                                  redistributable, content_sha256, scope_note,
                                  region_scope, raw_metadata, retrieved_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
           ON CONFLICT (uid) DO NOTHING""",
        (source["uid"], source["kind"], source.get("title"), org_id, source.get("url"),
         source.get("revision"), dated, year, source.get("is_final"),
         source.get("license"), bool(source.get("redistributable", False)),
         source.get("sha256"), source.get("note"), source.get("region_scope"),
         psycopg2.extras.Json(extra)))
    return scalar(cur, "SELECT id FROM bd.source WHERE uid = %s", (source["uid"],))


def ensure_product(cur, product: dict, org_id: int) -> int:
    cur.execute(
        """INSERT INTO bd.product (uid, kind, manufacturer_id, model_number, form_factor,
                                   form_factor_code, iec_designation, ansi_neda,
                                   is_rechargeable)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (uid) DO NOTHING""",
        (product["uid"], product["kind"], org_id, product["model_number"],
         product.get("form_factor"), product.get("form_factor_code"),
         product.get("iec_designation"), product.get("ansi_neda"),
         product.get("is_rechargeable")))
    product_id = scalar(cur, "SELECT id FROM bd.product WHERE uid = %s", (product["uid"],))
    for alias in product.get("aliases") or []:
        cur.execute(
            """INSERT INTO bd.product_alias (product_id, alias, kind)
               VALUES (%s, %s, 'oem_code') ON CONFLICT DO NOTHING""", (product_id, alias))
    return product_id


def ensure_revision(cur, product: dict, source: dict, product_id: int, source_id: int) -> int:
    """One revision per (product, source): a spec is a document, not a product.

    The uid carries the revision label so two documents for the same product
    stay legible in a query result, which is the whole reason the model splits
    product from product_revision.
    """
    label = source.get("revision") or source.get("document_date") or "unversioned"
    _, maker, model = product["uid"].split("/", 2)
    uid = f"rev/{maker}/{model}/{label}"
    dated, _, _ = document_date(source)
    cur.execute(
        """INSERT INTO bd.product_revision (uid, product_id, source_id, revision_label,
                                            effective_date, is_preliminary, region_scope,
                                            review)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'accepted')
           ON CONFLICT (product_id, source_id) DO NOTHING""",
        (uid, product_id, source_id, source.get("revision"), dated,
         source.get("is_final") is False, source.get("region_scope")))
    return scalar(cur,
                  "SELECT id FROM bd.product_revision WHERE product_id=%s AND source_id=%s",
                  (product_id, source_id))


def ensure_contributor(cur, uid: str, name: str) -> int:
    cur.execute(
        """INSERT INTO bd.contributor (uid, display_name, is_bot) VALUES (%s, %s, true)
           ON CONFLICT (uid) DO NOTHING""", (uid, name))
    return scalar(cur, "SELECT id FROM bd.contributor WHERE uid = %s", (uid,))


def condition_payload(observation: dict) -> dict | None:
    conditions = {k: v for k, v in (observation.get("conditions") or {}).items()
                  if k not in CONDITION_DROP}
    return conditions or None


def stage(cur, job_id: int, product_uid: str, observation: dict) -> int:
    locator = observation.get("locator") or {}
    return scalar(cur,
        """INSERT INTO bd_stage.candidate
             (job_id, target_table, payload, product_hint, quantity_code, value_native,
              unit_native, condition_json, page, section, quote, bbox)
           VALUES (%s, 'observation', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (job_id, psycopg2.extras.Json(observation), product_uid, observation["quantity"],
         observation.get("value"), observation.get("unit"),
         psycopg2.extras.Json(condition_payload(observation)),
         locator.get("page"), locator.get("section"), locator.get("quote"),
         locator.get("bbox")))


def promote_observation(cur, candidate_id: int, revision_id: int, source_id: int,
                        observation: dict, evidence: str, extraction: str,
                        reviewer_id: int, note: str) -> int:
    locator = observation.get("locator") or {}
    location_id = scalar(cur,
        """INSERT INTO bd.source_location (source_id, page, section, quote, bbox)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (source_id, locator.get("page"), locator.get("section"), locator.get("quote"),
         locator.get("bbox")))
    provenance_id = scalar(cur,
        """INSERT INTO bd.provenance (source_location_id, evidence, extraction, review,
                                      contributor_id, reviewed_by, reviewed_at, review_note)
           VALUES (%s, %s, %s, 'accepted', %s, %s, now(), %s) RETURNING id""",
        (location_id, evidence, extraction, reviewer_id, reviewer_id, note))
    conditions = condition_payload(observation)
    observation_id = scalar(cur,
        """INSERT INTO bd.observation
             (product_revision_id, quantity_id, statistic, value_native, unit_native,
              tol_plus, tol_minus, value_min, value_max, is_lower_bound, is_upper_bound,
              n_samples, condition_set_id, provenance_id)
           SELECT %s, q.id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  CASE WHEN %s::jsonb IS NULL THEN NULL
                       ELSE bd.intern_conditions(%s::jsonb) END,
                  %s
             FROM bd.quantity q WHERE q.code = %s
           RETURNING id""",
        (revision_id, observation.get("statistic") or "nominal", observation.get("value"),
         observation["unit"], observation.get("tol_plus"), observation.get("tol_minus"),
         observation.get("value_min"), observation.get("value_max"),
         bool(observation.get("is_lower_bound", False)),
         bool(observation.get("is_upper_bound", False)), observation.get("n_samples"),
         psycopg2.extras.Json(conditions) if conditions else None,
         psycopg2.extras.Json(conditions) if conditions else None,
         provenance_id, observation["quantity"]))
    cur.execute(
        """UPDATE bd_stage.candidate SET state='merged', promoted_id=%s, reviewed_by=%s,
                  reviewed_at=now() WHERE id=%s""",
        (observation_id, reviewer_id, candidate_id))
    cur.execute(
        """INSERT INTO bd_stage.review_action (candidate_id, reviewer_id, action, reason)
           VALUES (%s, %s, 'accept', %s)""", (candidate_id, reviewer_id, note))
    return observation_id


def promote_application(cur, application: dict, revision_id: int, source_id: int,
                        evidence: str, extraction: str, reviewer_id: int, note: str) -> None:
    locator = application.get("locator") or {}
    location_id = scalar(cur,
        """INSERT INTO bd.source_location (source_id, page, section, quote)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (source_id, locator.get("page"), locator.get("section"), locator.get("quote")))
    provenance_id = scalar(cur,
        """INSERT INTO bd.provenance (source_location_id, evidence, extraction, confidence,
                                      review, contributor_id, reviewed_by, reviewed_at,
                                      review_note)
           VALUES (%s, %s, %s, %s, 'accepted', %s, %s, now(), %s) RETURNING id""",
        (location_id, evidence, extraction, application.get("confidence"), reviewer_id,
         reviewer_id, note))
    cur.execute(
        """INSERT INTO bd.application (uid, name, sector, operator_text, programme, region,
                                       in_service_from, in_service_to, system_energy_kwh,
                                       system_power_kw, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (uid) DO NOTHING""",
        (application["uid"], application["name"], application["sector"],
         application.get("operator"), application.get("programme"), application.get("region"),
         application.get("in_service_from"), application.get("in_service_to"),
         application.get("system_energy_kwh"), application.get("system_power_kw"),
         application.get("notes")))
    application_id = scalar(cur, "SELECT id FROM bd.application WHERE uid = %s",
                            (application["uid"],))
    cur.execute(
        """INSERT INTO bd.product_application
             (application_id, product_revision_id, role, quantity_per_unit, topology_string,
              basis, confidence, provenance_id, is_exclusive, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT DO NOTHING""",
        (application_id, revision_id, application.get("role"),
         application.get("quantity_per_unit"), application.get("topology_string"),
         application["basis"], application.get("confidence"), provenance_id,
         bool(application.get("is_exclusive", False)), application.get("notes")))


def supersede_previous(cur, relative_path: str, digest: str) -> int:
    """Retire what an earlier load of this same file asserted.

    Editing a contribution and reloading must not leave the old claim standing
    beside the new one. The old provenance is marked superseded rather than
    deleted, because what the file used to say is part of its history.
    """
    cur.execute(
        """UPDATE bd.provenance p SET review = 'superseded'
             FROM bd_stage.candidate c
             JOIN bd_stage.ingest_job j ON j.id = c.job_id
             JOIN bd.observation o ON o.id = c.promoted_id
            WHERE j.input_uri = %s AND j.input_sha256 <> %s
              AND c.state = 'merged' AND p.id = o.provenance_id
              AND p.review <> 'superseded'""", (relative_path, digest))
    return cur.rowcount


def load_file(cur, path: str, args, reviewer_id: int) -> dict:
    relative = os.path.relpath(path, ROOT)
    digest = sha256(path)
    document = yaml.safe_load(open(path))
    product, source = document["product"], document["source"]

    if scalar(cur, "SELECT id FROM bd_stage.ingest_job WHERE input_sha256 = %s", (digest,)):
        return {"path": relative, "skipped": "already loaded, unchanged"}

    superseded = supersede_previous(cur, relative, digest)
    _, maker_slug, _ = product["uid"].split("/", 2)
    org_id = ensure_organization(cur, maker_slug, product["manufacturer"])
    source_id = ensure_source(cur, source, org_id)

    job_id = scalar(cur,
        """INSERT INTO bd_stage.ingest_job (uid, input_kind, input_uri, input_sha256,
                                            source_id, state)
           VALUES (%s, 'contrib_yaml', %s, %s, %s, 'validating') RETURNING id""",
        (f"job/contrib/{digest[:16]}", relative, digest, source_id))

    staged = []
    for observation in document["observations"]:
        candidate_id = stage(cur, job_id, product["uid"], observation)
        cur.execute("SELECT bd_stage.validate_candidate(%s)", (candidate_id,))
        verdict = cur.fetchone()[0]
        cur.execute("SELECT bd_stage.detect_conflicts(%s)", (candidate_id,))
        staged.append((candidate_id, observation, verdict, cur.fetchone()[0]))

    invalid = [(o["quantity"], v["errors"]) for _, o, v, _ in staged if v["errors"]]
    conflicts = sum(1 for *_, n in staged if n)
    result = {"path": relative, "staged": len(staged), "invalid": invalid,
              "conflicts": conflicts, "superseded": superseded, "promoted": 0}

    if args.stage_only:
        cur.execute("UPDATE bd_stage.ingest_job SET state='staged', finished_at=now(), "
                    "stats=%s WHERE id=%s",
                    (psycopg2.extras.Json({"candidates": len(staged),
                                           "invalid": len(invalid)}), job_id))
        return result
    if invalid:
        # Refusing the whole file rather than half of it: a spec sheet loaded
        # with its bad rows dropped reads in a query as a complete spec sheet.
        cur.execute("UPDATE bd_stage.ingest_job SET state='invalid', finished_at=now(), "
                    "error=%s WHERE id=%s",
                    (f"{len(invalid)} candidate(s) failed validation", job_id))
        return result

    # Staging cannot restate every constraint bd.* enforces, and should not try
    # to. Promotion runs inside a savepoint so a constraint the staging pass did
    # not anticipate lands in the report as a validation error against the file,
    # rather than as a traceback that abandons the whole run.
    cur.execute("SAVEPOINT promotion")
    try:
        result["promoted"] = promote_file(cur, document, org_id, source_id, staged,
                                          relative, args, reviewer_id)
    except psycopg2.Error as error:
        cur.execute("ROLLBACK TO SAVEPOINT promotion")
        message = str(getattr(error, "diag", None) and error.diag.message_primary or error)
        result["invalid"] = [("promotion", [message.strip()])]
        result["promoted"] = 0
        cur.execute("UPDATE bd_stage.ingest_job SET state='invalid', finished_at=now(), "
                    "error=%s WHERE id=%s", (message.strip()[:500], job_id))
        return result
    cur.execute("RELEASE SAVEPOINT promotion")

    cur.execute("UPDATE bd_stage.ingest_job SET state='merged', finished_at=now(), "
                "stats=%s WHERE id=%s",
                (psycopg2.extras.Json({"candidates": len(staged),
                                       "promoted": result["promoted"],
                                       "conflicts": conflicts}), job_id))
    return result


def promote_file(cur, document: dict, org_id: int, source_id: int, staged: list,
                 relative: str, args, reviewer_id: int) -> int:
    product, source = document["product"], document["source"]
    product_id = ensure_product(cur, product, org_id)
    revision_id = ensure_revision(cur, product, source, product_id, source_id)
    evidence = EVIDENCE_BY_SOURCE_KIND.get(source["kind"], "manufacturer_claim")
    note = f"accepted into contrib/ as {relative}"
    if document.get("chemistry"):
        chemistry = document["chemistry"]
        # A contribution states chemistry for the document as a whole and gives
        # it no locator of its own, so it is attributed to the whole source
        # rather than to a page it never named.
        chemistry_provenance = scalar(cur,
            """INSERT INTO bd.provenance (source_location_id, evidence, extraction, review,
                                          contributor_id, reviewed_by, reviewed_at,
                                          review_note)
               VALUES (bd.whole_source(%s), %s, %s, 'accepted', %s, %s, now(), %s)
               RETURNING id""",
            (source_id, evidence, args.extraction, reviewer_id, reviewer_id, note))
        cur.execute(
            """INSERT INTO bd.product_chemistry (product_revision_id, designation,
                                                 cathode_text, anode_text, system_string,
                                                 provenance_id)
               SELECT %s, %s, %s, %s, %s, %s WHERE NOT EXISTS (
                 SELECT 1 FROM bd.product_chemistry WHERE product_revision_id = %s)""",
            (revision_id, chemistry.get("designation"), chemistry.get("cathode_text"),
             chemistry.get("anode_text"), chemistry.get("system_string"),
             chemistry_provenance, revision_id))
    promoted = 0
    for candidate_id, observation, _, _ in staged:
        promote_observation(cur, candidate_id, revision_id, source_id, observation,
                            evidence, args.extraction, reviewer_id, note)
        promoted += 1
    for application in document.get("applications") or []:
        promote_application(cur, application, revision_id, source_id, evidence,
                            args.extraction, reviewer_id, note)
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=os.path.join(ROOT, "contrib"))
    parser.add_argument("--dsn", default=os.environ.get("BATTERY_DSN", "dbname=batterydb"))
    parser.add_argument("--stage-only", action="store_true",
                        help="validate into bd_stage and stop before promotion")
    parser.add_argument("--extraction", default="manual_entry",
                        help="extraction_method to record. A contribution file does not "
                             "say how it was produced, and a human accepted it before it "
                             "got here, so manual_entry is the honest default.")
    parser.add_argument("--reviewer", default="user/contrib-review")
    args = parser.parse_args()

    files = ([args.path] if args.path.endswith((".yaml", ".yml"))
             else sorted(glob.glob(os.path.join(args.path, "**", "*.y*ml"), recursive=True)))
    if not files:
        print(f"no contribution files under {args.path}")
        return 0

    connection = psycopg2.connect(args.dsn)
    results, failed = [], 0
    with connection:
        with connection.cursor() as cur:
            reviewer_id = ensure_contributor(cur, args.reviewer,
                                             "contrib review (owner-approved)")
            for path in files:
                result = load_file(cur, path, args, reviewer_id)
                results.append(result)
                if result.get("invalid"):
                    failed += 1
    connection.close()

    for result in results:
        if result.get("skipped"):
            print(f"  --    {result['path']}  ({result['skipped']})")
            continue
        flags = []
        if result["conflicts"]:
            flags.append(f"{result['conflicts']} conflicting with accepted data")
        if result["superseded"]:
            flags.append(f"{result['superseded']} superseded")
        status = "FAIL" if result["invalid"] else "ok  "
        print(f"  {status}  {result['path']}  {result['staged']} staged, "
              f"{result['promoted']} promoted"
              + (f"  [{'; '.join(flags)}]" if flags else ""))
        for quantity, errors in result["invalid"]:
            print(f"          {quantity}: {'; '.join(errors)}", file=sys.stderr)

    loaded = sum(1 for r in results if not r.get("skipped"))
    print(f"\n{loaded} file(s) loaded, {sum(r.get('promoted', 0) for r in results)} "
          f"observation(s) promoted, {failed} file(s) rejected")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
