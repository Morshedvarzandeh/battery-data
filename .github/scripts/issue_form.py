#!/usr/bin/env python3
"""
Parse a GitHub issue-form body into JSON.

Issue forms render as `### Field label` followed by the value, and `_No
response_` where a field was left blank. That is the whole format.

This exists as a file rather than a shell one-liner because the issue body
is attacker-controlled text: anyone who can open an issue writes it. It is
read from an environment variable and never touches a shell, so a body
containing backticks, `$(...)` or a newline followed by `rm -rf /` is a
string and stays a string.

    ISSUE_BODY="$BODY" python .github/scripts/issue_form.py > request.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from urllib.parse import urlparse

BLANK = {"_no response_", "_none_", ""}


def parse(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    key = None
    buf: list[str] = []
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.*?)\s*$", line)
        if m:
            if key is not None:
                out[key] = "\n".join(buf).strip()
            key = m.group(1).strip().lower()
            buf = []
        elif key is not None:
            buf.append(line)
    if key is not None:
        out[key] = "\n".join(buf).strip()
    return {k: ("" if v.strip().lower() in BLANK else v.strip())
            for k, v in out.items()}


def main() -> int:
    fields = parse(os.environ.get("ISSUE_BODY", ""))

    url = fields.get("datasheet url", "")
    scheme = urlparse(url).scheme
    if scheme not in ("http", "https"):
        # A file:// or gopher:// URL here would make the runner fetch
        # something it was never meant to reach.
        print(f"datasheet url must be http or https, got {scheme or 'nothing'!r}",
              file=sys.stderr)
        return 2

    kind = fields.get("product kind", "cell").strip() or "cell"
    if kind not in ("cell", "module", "pack", "system", "primary_cell",
                    "component"):
        print(f"unknown product kind {kind!r}", file=sys.stderr)
        return 2

    req = {
        "url": url,
        "manufacturer": fields.get("manufacturer", ""),
        "model": fields.get("model number", ""),
        "kind": kind,
        "source_url": fields.get("landing page", ""),
        # A ticked checkbox renders as '- [X] label'.
        "redistributable": bool(
            re.search(r"^\s*-\s*\[[xX]\]", fields.get("licence", ""), re.M)),
        "notes": fields.get("anything the extractor should know", "")[:2000],
    }
    missing = [k for k in ("manufacturer", "model") if not req[k]]
    if missing:
        print(f"missing required field(s): {', '.join(missing)}", file=sys.stderr)
        return 2

    json.dump(req, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
