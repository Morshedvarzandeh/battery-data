#!/usr/bin/env python3
"""Re-derive candidate declarations from review issues that outlived their files.

The research process that opens `[candidate]` issues keeps opening them without
committing their `review/candidates/*.yaml`. Approving such an issue cannot
work: the promotion script resolves the path the issue names and finds nothing
to promote.

The rendered issue body is the only surviving copy of those extractions. It is
also the exact text the owner reads before checking the approval box, so
re-deriving the candidate from it accepts precisely what was reviewed -- the
table in the issue is the record, and this turns it back into a file.

Two fields the renderer never emitted cannot come back:

  * `statistic` -- whether a value was the rated, typical, minimum or maximum
    figure. Two rows of the same quantity that differed only by statistic are
    indistinguishable once rendered.
  * `locator.page` -- which page of the source the quote came from. The quote
    itself survives, so the claim is still checkable, just not page-addressed.

Recovered records say so in `source.note` rather than inventing either.

    GITHUB_TOKEN=... python tools/recover_issue_candidates.py

Writes review/batches/<batch>.json and updates review/issue-map.json. Run
tools/build_review_batch.py afterwards to emit the candidate files themselves.

`.github/workflows/adopt-candidate.yml` runs this on every newly opened
candidate issue, which sets the trust boundary: anyone can open an issue, so an
issue that fails any check here is skipped with a warning rather than allowed
to poison the batch or abort the adoption of the well-formed ones. Nothing this
script writes is accepted data -- everything stays pending until the owner
checks the approval box, and the promotion script re-validates from scratch.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "review" / "batches" / "2026-08-09-issue-recovery.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "Morshedvarzandeh/battery-data")

TITLE_PREFIX = "[candidate] "
MARKER = re.compile(r"<!--\s*battery-candidate:\s*(\S+?)\s*-->")
UID_MARKER = re.compile(r"<!--\s*battery-uid:\s*(\S+?)\s*-->")
# The same shape promote_candidate.py enforces. Both markers are attacker
# writable -- anyone can open an issue -- and the uid's segments become file
# system paths in build_review_batch.py, so the charset is a security check,
# not a formality: no slash can survive into a single segment, and every
# emitted file stays under review/candidates/.
UID_SHAPE = re.compile(
    r"^(cell|module|pack|system|primary_cell|component)/([a-z0-9-]+)/([a-z0-9._-]+)$")
HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)
KIND = re.compile(r"^\*\*Product type:\*\*\s*`([^`]+)`", re.M)
SOURCE = re.compile(r"^\*\*Source:\*\*\s*\[(.*)\]\((\S*)\)", re.M)
REVISION = re.compile(r"^\*\*Source revision/date:\*\*\s*(.*?)\s*$", re.M)
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|(.*?)\|(.*?)\|(.*)\|\s*$", re.M)
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

NOTE = ("Recovered from the review issue that outlived its candidate file. The "
        "rendered issue carried no per-value statistic label and no page "
        "number, so neither is asserted here.")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")


def fetch_issues() -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("set GITHUB_TOKEN (or GH_TOKEN) to read the review issues")
    issues, page = [], 1
    while True:
        url = f"https://api.github.com/repos/{REPO}/issues?state=open&per_page=100&page={page}"
        request = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "battery-data-issue-recovery",
        })
        with urllib.request.urlopen(request) as response:
            batch = json.load(response)
        if not batch:
            return issues
        issues += [i for i in batch
                   if "pull_request" not in i and i["title"].startswith(TITLE_PREFIX)]
        page += 1


def split_heading(heading: str, uid: str) -> tuple[str, str]:
    """Recover manufacturer and model number using the model slug in the uid.

    The heading is `{manufacturer} {model_number}` with no separator, and
    manufacturer names run to several words ("EVE Energy", "LG Energy
    Solution"), so the split has to come from somewhere other than whitespace.
    The uid's third segment is the slugged model, so the model is whichever
    trailing run of words slugs to it.

    Exact slugging comes first. The token-subsequence fallback exists because
    issue creators abbreviate when they slug -- "REPT BATTERO 392Ah ESS"
    becomes `392ah`, "CATL Naxtra passenger EV sodium-ion cell" drops the
    "EV" -- so the model is the trailing run that starts on the slug's first
    token and contains all its tokens in order.
    """
    model_slug = uid.split("/", 2)[2]
    bare = lambda text: slug(text).replace("-", "")
    tokens = lambda text: [t for t in slug(text).replace(".", "-").split("-") if t]
    model_tokens = tokens(model_slug)

    def subsequence(tail):
        had = tokens(tail)
        if not had or not model_tokens or had[0] != model_tokens[0]:
            return False
        position = 0
        for token in had:
            if position < len(model_tokens) and token == model_tokens[position]:
                position += 1
        return position == len(model_tokens)

    words = heading.split(" ")
    for match in (lambda tail: slug(tail) == model_slug,
                  lambda tail: bare(tail) == model_slug.replace("-", ""),
                  subsequence):
        for start in range(len(words)):
            tail = " ".join(words[start:])
            if start and match(tail):
                return " ".join(words[:start]), tail
    raise ValueError(f"cannot split {heading!r} against uid {uid}")


def condition_specs() -> dict[str, tuple[str, list | None]]:
    """Declared type and enum per condition, so a rendered cell comes back typed.

    Every cell in the markdown table is text. A voltage_lower_v left as the
    string "2.5" passes the review validator and then fails the contribution
    schema at the moment of approval -- which is the failure this whole script
    exists to clear, arriving one step later.
    """
    schema = json.loads((ROOT / "json-schema" / "cell-contribution.schema.json").read_text())
    return {name: (spec.get("type", "string"), spec.get("enum"))
            for name, spec in schema["$defs"]["conditions"]["properties"].items()}


SPECS = condition_specs()


def parse_conditions(text: str) -> dict | None:
    """Invert tools/render_review_issues.py:conditions_text.

    A value the schema cannot hold -- "temperature_c=room temperature" where a
    number is required, "temperature_reference=cell" where 'cell' is not in
    the vocabulary -- is an issue author asserting something its own quote
    does not support in schema terms. The literal wording is kept in
    `verbatim` and the key is declared unstated: per the quote, it is.
    """
    text = text.strip()
    if not text or text == "not required":
        return None
    conditions: dict = {}
    unstated: list = []
    kept_verbatim: list = []
    for part in text.split(";"):
        part = part.strip()
        if part.startswith("not stated:"):
            unstated += [c.strip() for c in part[len("not stated:"):].split(",")
                         if c.strip() and c.strip() not in unstated]
        elif "=" in part:
            key, _, value = part.partition("=")
            key, value = key.strip(), value.strip()
            declared, allowed = SPECS.get(key, ("string", None))
            try:
                if declared == "integer":
                    value = int(value)
                elif declared == "number":
                    value = float(value)
                    value = int(value) if value.is_integer() else value
                elif allowed and value not in allowed:
                    raise ValueError(f"{value!r} is not in the {key} vocabulary")
            except ValueError:
                kept_verbatim.append(f"{key}={value}")
                if key not in unstated:
                    unstated.append(key)
                continue
            conditions[key] = value
    if unstated:
        conditions["unstated"] = unstated
    if kept_verbatim:
        conditions["verbatim"] = "; ".join(kept_verbatim)
    return conditions or None


def source_of(title: str, url: str, revision: str, maker: str) -> dict:
    """Build the provenance record the contribution schema requires.

    `uid` and `kind` are mandatory and the renderer emitted neither, so both
    are derived from the URL -- the same document always yields the same uid,
    and products sharing a datasheet share its provenance.
    """
    tail = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
    stem = re.sub(r"\.(pdf|html?|aspx)$", "", tail[-1], flags=re.I) if tail else "index"
    source = {
        "uid": f"src/{maker}-{slug(stem)}",
        "kind": "datasheet" if url.lower().endswith(".pdf") else "manufacturer_web",
        "title": title,
        "url": url,
    }
    if ISO_DATE.fullmatch(revision):
        source["document_date"] = revision
    elif revision and revision != "not stated":
        source["revision"] = revision
    source["license"] = "proprietary"
    source["redistributable"] = False
    source["note"] = NOTE
    return source


def recover(issue: dict) -> dict:
    body = issue["body"] or ""
    uid_match = UID_MARKER.search(body)
    if not uid_match:
        raise ValueError("battery-uid marker is missing")
    uid = uid_match.group(1)
    shape = UID_SHAPE.fullmatch(uid)
    if not shape:
        raise ValueError(f"uid {uid!r} is not shaped kind/maker/model")
    kind, maker, model_slug = shape.groups()
    stated = MARKER.search(body).group(1)
    derived = f"review/candidates/{maker}/{model_slug}.yaml"
    if stated != derived:
        raise ValueError(f"issue names {stated} but its uid implies {derived}")
    heading = HEADING.search(body)
    source_line = SOURCE.search(body)
    revision_line = REVISION.search(body)
    if not heading or not source_line or not revision_line:
        raise ValueError("issue body is missing its heading, source or revision line")
    manufacturer, model_number = split_heading(heading.group(1), uid)
    title, url = source_line.groups()
    if not url.startswith("https://"):
        raise ValueError(f"source url is not https: {url!r}")

    observations = []
    for quantity, value_cell, condition_cell, quote_cell in ROW.findall(body):
        number, _, unit = value_cell.strip().partition(" ")
        observation = {
            "quantity": quantity,
            "value": float(number) if re.search(r"[.eE]", number) else int(number),
            "unit": unit.strip(),
        }
        conditions = parse_conditions(condition_cell)
        if conditions:
            observation["conditions"] = conditions
        observation["locator"] = {"quote": quote_cell.strip().replace("\\|", "|")}
        observations.append(observation)

    return {
        "issue_number": issue["number"],
        "issue_url": issue["html_url"],
        "candidate_file": MARKER.search(body).group(1),
        "document": {
            "schema_version": "1",
            "product": {
                "uid": uid,
                "kind": kind,
                "manufacturer": manufacturer,
                "model_number": model_number,
                "is_rechargeable": kind != "primary_cell",
            },
            "source": source_of(title, url, revision_line.group(1), maker),
            "observations": observations,
        },
    }


def registry_problems(document: dict, registry: dict) -> str | None:
    """The checks tools/validate_review.py would fail this document on later.

    Running them per issue means one malformed issue is skipped here with its
    reason, instead of failing the validators after the batch is written and
    blocking the adoption of every well-formed candidate beside it.
    """
    observations = document.get("observations") or []
    if not observations:
        return "no observations"
    for observation in observations:
        quantity = observation["quantity"]
        if quantity not in registry:
            return f"unknown quantity {quantity!r}"
        if not observation["unit"]:
            return f"{quantity} has no unit"
        if len(observation["locator"]["quote"]) < 8:
            return f"{quantity} has no evidence quote"
        conditions = observation.get("conditions") or {}
        unstated = set(conditions.get("unstated") or [])
        for required in registry[quantity]:
            if conditions.get(required) in (None, "unspecified") and required not in unstated:
                return f"{quantity} is missing condition {required}"
    return None


def main() -> int:
    # A candidate file on disk normally means the issue is fine and needs no
    # recovery -- except for the ones this script wrote last time, which are on
    # disk precisely because it ran. Re-deriving those keeps the run idempotent
    # and lets a fix to the parser reach records already recovered.
    previous = json.loads(BATCH.read_text())["candidates"] if BATCH.exists() else []
    mine = {entry["candidate_file"] for entry in previous}
    committed = {str(path.relative_to(ROOT))
                 for path in (ROOT / "review" / "candidates").rglob("*.yaml")} - mine
    registry = json.loads((ROOT / "json-schema" / "quantity-registry.json").read_text())
    index = json.loads((ROOT / "review" / "index.json").read_text())
    indexed_files = {item["uid"]: item["candidate_file"] for item in index["candidates"]}
    accepted_uids = {item["uid"] for item in index["candidates"]
                     if item["state"] == "accepted"}

    # An accepted candidate's issue is closed, so it can no longer be fetched
    # and re-derived -- but its entry is the checked-in record behind an
    # accepted index row, and dropping it would erase that row on the next
    # rebuild. Entries whose issue is merely gone (rejected, deleted) drop out
    # here, which is the correct way to leave the queue.
    recovered = [entry for entry in previous
                 if entry["document"]["product"]["uid"] in accepted_uids]
    taken_files = {entry["candidate_file"] for entry in recovered}
    taken_sources = {entry["document"]["source"]["uid"]: entry["document"]["source"]["url"]
                     for entry in recovered}
    skipped = 0

    def skip(issue: dict, reason: str) -> None:
        nonlocal skipped
        skipped += 1
        print(f"WARN #{issue['number']}: {reason} -- skipped", file=sys.stderr)

    for issue in fetch_issues():
        marker = MARKER.search(issue["body"] or "")
        if not marker or marker.group(1) in committed:
            continue
        try:
            entry = recover(issue)
        except ValueError as error:
            skip(issue, str(error))
            continue
        document = entry["document"]
        uid, source = document["product"]["uid"], document["source"]
        if entry["candidate_file"] in taken_files:
            skip(issue, f"{entry['candidate_file']} already claimed by another issue")
            continue
        if indexed_files.get(uid) not in (None, entry["candidate_file"]):
            skip(issue, f"uid {uid} already belongs to {indexed_files[uid]}")
            continue
        if taken_sources.setdefault(source["uid"], source["url"]) != source["url"]:
            skip(issue, f"source uid {source['uid']} already covers a different document")
            continue
        problem = registry_problems(document, registry)
        if problem:
            skip(issue, problem)
            continue
        taken_files.add(entry["candidate_file"])
        recovered.append(entry)
    recovered.sort(key=lambda entry: entry["candidate_file"])

    BATCH.parent.mkdir(parents=True, exist_ok=True)
    BATCH.write_text(json.dumps({
        "schema_version": 1,
        "batch": BATCH.stem,
        "origin": "review issues whose candidate files were never committed",
        "unrecoverable_fields": ["observations[].statistic", "observations[].locator.page"],
        "candidate_count": len(recovered),
        "candidates": recovered,
    }, indent=2, ensure_ascii=False) + "\n")

    issue_map = json.loads((ROOT / "review" / "issue-map.json").read_text())
    for entry in recovered:
        issue_map[entry["document"]["product"]["uid"]] = {
            "issue_number": entry["issue_number"],
            "issue_url": entry["issue_url"],
        }
    (ROOT / "review" / "issue-map.json").write_text(
        json.dumps(issue_map, indent=2, ensure_ascii=False) + "\n")

    observations = sum(len(e["document"]["observations"]) for e in recovered)
    print(f"recovered {len(recovered)} candidate(s), {observations} observation(s), "
          f"{len(taken_sources)} source(s), {skipped} issue(s) skipped "
          f"-> {BATCH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
