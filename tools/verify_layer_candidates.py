#!/usr/bin/env python3
"""Turn a recalled candidate into a contribution by reading the page it names.

For every candidate under review/layers the tool fetches `verify_at`, finds
the company's or site's name on the page (name, legal name, then aliases)
and, when found, writes a contribution file in the company or site format
whose source is that page (URL, retrieval date, sha256 of the bytes) and
whose locator quotes the sentence the name appears in. Fields the page did
not confirm are kept from the candidate and said to be recalled in the
record's note, so the reviewer who promotes the file sees exactly what
rests on the quote and what does not.

Nothing is promoted by this tool. Verified files land under
review/layers/verified/ and a person moves them into contrib/ (or runs
with --promote to write them there directly). A candidate whose page could
not be fetched, or whose name is not on the page, is logged and stays in
the queue.

Needs network access to the companies' sites. Offline, --offline-dir maps
a candidate uid to a saved HTML file (uid with / replaced by __, plus
.html), which is how the tests run.

    python tools/verify_layer_candidates.py --set cell-makers --limit 20
    python tools/verify_layer_candidates.py --promote
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import html as html_mod
import json
import os
import re
import sys
import urllib.error
import urllib.request

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "review", "layers")
OUT = os.path.join(DIR, "verified")
LOG = os.path.join(DIR, "verification-log.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_layers import known_uids, plain  # noqa: E402

UA = "battery-data/1.1 (+https://github.com/Morshedvarzandeh/battery-data; verification of a recalled name)"


def fetch(url: str, timeout: int = 25) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


BLOCK = ("p", "div", "br", "li", "tr", "td", "th", "section", "article", "nav", "header",
         "footer", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "figcaption", "title")
# glyphs a page uses to separate menu items; without them a navigation bar runs
# into the first paragraph and the two become one sentence
SEPARATORS = "|•·›»‣▪"


def strip_html(html: str) -> str:
    """Rendered text, with block boundaries kept as sentence boundaries.

    A quote is only useful if it is the sentence a human would point at. Left
    as one undifferentiated run of words, a page's <title> and menu glue
    themselves to the first paragraph and the quote becomes nonsense, so every
    block-level tag and every menu separator becomes a full stop here.
    """
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    html = re.sub(rf"(?i)</?({'|'.join(BLOCK)})\b[^>]*>", " . ", html)
    text = html_mod.unescape(re.sub(r"(?s)<[^>]+>", " ", html))
    text = re.sub(rf"[{re.escape(SEPARATORS)}]", " . ", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"(\s*\.\s*)+", ". ", text).strip()


def sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]


def score(chunk: str) -> float:
    """Prefer a sentence over a menu item: prose has lower-case words, verbs
    and length; a navigation fragment has none of them."""
    words = chunk.split()
    if not words:
        return -1.0
    lower = sum(1 for w in words if w[:1].islower())
    return min(len(words), 60) + 2 * lower


def find_quote(text: str, needles: list[str], min_len: int = 40, max_len: int = 300):
    """A needle found on the page, and the sentence that carries it.

    Every sentence naming the needle is scored and the most prose-like wins,
    because the first occurrence is almost always the page title or the menu.
    A short winning sentence takes the next one with it, so the quote reads.
    """
    parts = sentences(text)
    for needle in needles:
        if not needle or len(needle) < 2:
            continue
        low = needle.lower()
        hits = [i for i, p in enumerate(parts) if low in p.lower()]
        if not hits:
            continue
        i = max(hits, key=lambda j: score(parts[j]))
        quote = parts[i]
        j = i + 1
        while len(quote) < min_len and j < len(parts) and len(quote) + len(parts[j]) + 1 <= max_len:
            quote += " " + parts[j]
            j += 1
        return needle, quote[:max_len].strip()
    return None


def needles_for(cand: dict) -> list[str]:
    out = [cand.get("name"), cand.get("legal_name")] + list(cand.get("aliases") or [])
    seen, uniq = set(), []
    for n in out:
        if n and n.lower() not in seen:
            seen.add(n.lower())
            uniq.append(n)
    return uniq


def source_for(cand: dict, url: str, raw: bytes, date: str) -> dict:
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0])
    # the page, not just the host: two pages on one site read on one day are
    # two sources, and a shared uid would attach one page's quote to the other
    tail = hashlib.sha256(url.encode()).hexdigest()[:8]
    return {"uid": "src/" + re.sub(r"[^a-z0-9.-]+", "-", host.lower()).strip("-") + "-" + date + "-" + tail,
            "kind": "manufacturer_web",
            "title": f"{cand['name']}: web page read to verify a recalled name",
            "url": url, "document_date": date, "sha256": hashlib.sha256(raw).hexdigest(),
            "note": (f"Retrieved {date} by tools/verify_layer_candidates.py. The name was found on the page "
                     f"and quoted; every other field came from the candidate recalled on "
                     f"{cand.get('_recalled_on', 'an unrecorded date')} and needs the document that states it.")}


def verify_text(cand: dict, entity: str, text: str, url: str, raw: bytes, date: str,
                known_orgs: set[str]) -> dict | None:
    """The contribution for a candidate when its name is on the page, else None."""
    hit = find_quote(text, needles_for(cand))
    if not hit:
        return None
    needle, quote = hit
    locator = {"section": url, "quote": quote}
    recalled = f"Recalled, not yet confirmed by a document (verify_at found only the name '{needle}')"
    if entity == "company":
        org = {k: cand[k] for k in ("uid", "name", "legal_name", "aliases", "former_names", "country",
                                    "hq_region", "hq_locality", "founded_year", "website", "roles",
                                    "ticker", "exchange", "parent_uid") if cand.get(k) is not None}
        detail = []
        if cand.get("makes"):
            detail.append("makes " + ", ".join(cand["makes"]))
        if cand.get("chemistries"):
            detail.append("chemistries " + ", ".join(cand["chemistries"]))
        org["description"] = f"{recalled}: " + ("; ".join(detail) if detail else "profile fields") + "."
        return {"schema_version": "1", "organization": org,
                "source": source_for(cand, url, raw, date), "locator": locator}
    site = {k: cand[k] for k in ("uid", "kind", "name", "country", "region", "locality", "status")
            if cand.get(k) is not None}
    if cand["operator_uid"] in known_orgs:
        site["operator_uid"] = cand["operator_uid"]
    elif cand.get("_operator_name"):
        site["operator"] = cand["_operator_name"]
    else:
        # neither in the library nor named by a candidate: say so rather than
        # inventing a company name out of the slug
        site["operator"] = cand["operator_uid"].split("/", 1)[1].replace("-", " ").title()
        site.setdefault("notes", "")
    if cand.get("makes"):
        site["products"] = list(cand["makes"])
    if cand.get("status"):
        site["notes"] = f"{recalled}: status '{cand['status']}' as recalled; the page decides."
    else:
        site["notes"] = f"{recalled}: location and products as recalled."
    return {"schema_version": "1", "site": site, "source": source_for(cand, url, raw, date), "locator": locator}


def out_path(base: str, entity: str, uid: str) -> str:
    if entity == "company":
        return os.path.join(base, "companies", uid.split("/", 1)[1] + ".yaml")
    _, op, name = uid.split("/", 2)
    return os.path.join(base, "sites", op, name.replace("/", "-") + ".yaml")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default=None, help="only this candidate set")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--promote", action="store_true", help="write into contrib/ instead of review/layers/verified")
    ap.add_argument("--offline-dir", default=None, help="saved pages, <uid with / as __>.html, instead of the network")
    a = ap.parse_args()
    base = os.path.join(ROOT, "contrib") if a.promote else a.out
    known = known_uids()["orgs"]
    date = datetime.date.today().isoformat()
    log = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else []
    done, found, failed = 0, 0, 0
    files = sorted(glob.glob(os.path.join(DIR, "*.y*ml")))
    docs = [plain(yaml.safe_load(open(f, encoding="utf-8"))) for f in files]
    # a plant's operator is usually named in a different set from the plant, so
    # the name index spans every set before anything is verified
    names = {c["uid"]: c["name"] for d in docs for c in d.get("companies") or []}
    for doc in docs:
        if a.set and doc["candidate_set"] != a.set:
            continue
        items = [("company", c) for c in doc.get("companies") or []] + [("site", s) for s in doc.get("sites") or []]
        for entity, cand in items:
            if a.limit and done >= a.limit:
                break
            done += 1
            cand = dict(cand, _recalled_on=doc["recalled_on"], _operator_name=names.get(cand.get("operator_uid")))
            entry = {"uid": cand["uid"], "url": cand["verify_at"], "date": date}
            try:
                if a.offline_dir:
                    p = os.path.join(a.offline_dir, cand["uid"].replace("/", "__") + ".html")
                    raw, url = open(p, "rb").read(), cand["verify_at"]
                else:
                    raw, url = fetch(cand["verify_at"])
            except (OSError, urllib.error.URLError, ValueError) as e:
                entry["result"] = f"fetch failed: {str(e)[:120]}"
                log.append(entry)
                failed += 1
                print(f"  --    {cand['uid']}: {entry['result']}")
                continue
            contribution = verify_text(cand, entity, strip_html(raw.decode("utf-8", "replace")), url, raw, date, known)
            if contribution is None:
                entry["result"] = "name not found on the page"
                log.append(entry)
                failed += 1
                print(f"  --    {cand['uid']}: name not on the page")
                continue
            path = out_path(base, entity, cand["uid"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(f"# Written by tools/verify_layer_candidates.py on {date}; review before promotion.\n")
                yaml.safe_dump(contribution, fh, sort_keys=False, allow_unicode=True, width=100)
            entry["result"] = "verified"
            entry["file"] = os.path.relpath(path, ROOT)
            entry["quote"] = contribution["locator"]["quote"]
            log.append(entry)
            found += 1
            print(f"  ok    {cand['uid']} -> {entry['file']}")
    os.makedirs(DIR, exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"\n{done} candidate(s) tried, {found} verified, {failed} left in the queue; log in {os.path.relpath(LOG, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
