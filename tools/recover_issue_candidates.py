#!/usr/bin/env python3
"""Re-derive candidate declarations from review issues that outlived their files.

Most `[candidate]` issues were opened without their `review/candidates/*.yaml`
ever being committed. Approving one could therefore never work: the promotion
script resolves the path named in the issue and finds nothing to promote.

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
    """
    model_slug = uid.split("/", 2)[2]
    bare = lambda text: slug(text).replace("-", "")
    words = heading.split(" ")
    for match in (lambda tail: slug(tail) == model_slug,
                  lambda tail: bare(tail) == model_slug.replace("-", "")):
        for start in range(len(words)):
            tail = " ".join(words[start:])
            if start and match(tail):
                return " ".join(words[:start]), tail
    raise SystemExit(f"cannot split {heading!r} against uid {uid}")


def parse_conditions(text: str) -> dict | None:
    """Invert tools/render_review_issues.py:conditions_text."""
    text = text.strip()
    if not text or text == "not required":
        return None
    conditions: dict = {}
    for part in text.split(";"):
        part = part.strip()
        if part.startswith("not stated:"):
            conditions["unstated"] = [c.strip() for c
                                      in part[len("not stated:"):].split(",") if c.strip()]
        elif "=" in part:
            key, _, value = part.partition("=")
            conditions[key.strip()] = value.strip()
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
    uid = UID_MARKER.search(body).group(1)
    kind, maker, model_slug = uid.split("/", 2)
    manufacturer, model_number = split_heading(HEADING.search(body).group(1), uid)
    title, url = SOURCE.search(body).groups()

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
            "source": source_of(title, url, REVISION.search(body).group(1), maker),
            "observations": observations,
        },
    }


def main() -> int:
    committed = {str(path.relative_to(ROOT))
                 for path in (ROOT / "review" / "candidates").rglob("*.yaml")}
    recovered = []
    for issue in fetch_issues():
        marker = MARKER.search(issue["body"] or "")
        if not marker or marker.group(1) in committed:
            continue
        recovered.append(recover(issue))
    recovered.sort(key=lambda entry: entry["candidate_file"])

    expected = {entry["candidate_file"]:
                "review/candidates/{1}/{2}.yaml".format(*entry["document"]["product"]["uid"].split("/"))
                for entry in recovered}
    for stated, derived in expected.items():
        if stated != derived:
            sys.exit(f"issue names {stated} but its uid implies {derived}")
    sources = {}
    for entry in recovered:
        source = entry["document"]["source"]
        if sources.setdefault(source["uid"], source["url"]) != source["url"]:
            sys.exit(f"source uid {source['uid']} covers two documents")

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
          f"{len(sources)} source(s) -> {BATCH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
