#!/usr/bin/env python3
"""Fetch the bounded EPO Linked Open EP Data query shards used by the importer.

This script is intentionally separate from the deterministic importer. Network
refreshes create a new dated snapshot; they never rewrite a released snapshot.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from import_epo_linked_patents import SOURCE_ENDPOINT, SOURCE_SPECS


QUERY = """PREFIX patent: <http://data.epo.org/linked-data/def/patent/>
PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>
SELECT ?pub ?number ?kind ?date
       (SAMPLE(?title0) AS ?title)
       (GROUP_CONCAT(DISTINCT STR(?ipc2); separator="|") AS ?ipcs)
       (GROUP_CONCAT(DISTINCT CONCAT(STR(?appname), "@@", COALESCE(STR(?country), "")); separator="||") AS ?applicants)
       (GROUP_CONCAT(DISTINCT STR(?application); separator="|") AS ?applications)
       (GROUP_CONCAT(DISTINCT STR(?priority); separator="|") AS ?priorities)
       (GROUP_CONCAT(DISTINCT STR(?international); separator="|") AS ?internationalApplications)
WHERE {
  ?pub patent:classificationIPCInventive <http://data.epo.org/linked-data/def/ipc/%(seed_ipc)s> ;
       patent:publicationNumber ?number ;
       patent:publicationKind ?kind ;
       patent:publicationDate ?date ;
       patent:titleOfInvention ?title0 .
  FILTER(STRSTARTS(STR(?pub), "http://data.epo.org/linked-data/data/publication/EP/"))
  FILTER(REGEX(STR(?kind), "_A[12]$"))
  FILTER(LANG(?title0) = "en" || LANG(?title0) = "")
  OPTIONAL { ?pub patent:classificationIPCInventive ?ipc2 . }
  OPTIONAL {
    ?pub patent:applicantVC ?app .
    ?app vcard:fn ?appname .
    OPTIONAL { ?app vcard:hasAddress/patent:countryCode ?country }
  }
  OPTIONAL { ?pub patent:application ?application . }
  OPTIONAL { ?pub patent:priority ?priority . }
  OPTIONAL { ?pub patent:internationalApplication ?international . }
}
GROUP BY ?pub ?number ?kind ?date
LIMIT %(limit)d
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace", action="store_true", help="replace files inside a new/unreleased snapshot directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    for index, (filename, spec) in enumerate(sorted(SOURCE_SPECS.items())):
        path = args.output / filename
        if path.exists() and not args.replace:
            raise SystemExit(f"refusing to replace immutable snapshot file: {path}")
        limit = 350 if filename == "h01m10-0525.json" else 100
        query = QUERY % {"seed_ipc": spec["seed_ipc"], "limit": limit}
        url = SOURCE_ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
        request = urllib.request.Request(url, headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "battery-data-patent-import/1.0 (+https://github.com/Morshedvarzandeh/battery-data)",
        })
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read()
        document = json.loads(payload)
        if "results" not in document or "bindings" not in document["results"]:
            raise SystemExit(f"invalid SPARQL response for {filename}")
        path.write_bytes(payload)
        print(f"{filename}: {len(document['results']['bindings'])} result(s)")
        if index + 1 < len(SOURCE_SPECS):
            time.sleep(1.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
