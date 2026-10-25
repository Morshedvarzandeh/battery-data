#!/usr/bin/env python3
"""Resolve the audited byte hash of an accepted record.

Acceptance audits in review/audits/ record the SHA-256 of every file they
accept. Tests pin those bytes so an accepted record cannot change quietly.
A later, documented change to an accepted record is a *revision*: an audit
with a `revisions` list recording, per file, the bytes it started from and the
bytes it produced, the fields it touched and why.

This module walks the audits in date order (their filenames are date-prefixed)
and answers two questions the tests need:

    accepted_sha256(path)  -> the hash the file is currently expected to have
    revised_fields(path)   -> dotted field paths a revision has changed since
                              the file was first accepted (e.g. "product.form_factor")

A revision whose `previous_sha256` does not match the hash the ledger holds at
that point is a gap in the chain and raises, so an undocumented edit between
two audits cannot be papered over by the next one.
"""
from __future__ import annotations
import glob, json, os
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDITS = os.path.join(ROOT, "review", "audits")


@lru_cache(maxsize=1)
def _ledger() -> tuple[dict[str, str], dict[str, list[str]]]:
    current: dict[str, str] = {}
    fields: dict[str, list[str]] = {}
    for f in sorted(glob.glob(os.path.join(AUDITS, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            audit = json.load(fh)
        for d in audit.get("decisions", []):
            if d.get("decision") == "accept" and d.get("accepted_file"):
                current[d["accepted_file"]] = d["accepted_document_sha256"]
        for r in audit.get("revisions", []):
            path = r["file"]
            held = current.get(path)
            if held is not None and held != r["previous_sha256"]:
                raise ValueError(
                    f"{os.path.basename(f)}: revision of {path} starts from "
                    f"{r['previous_sha256'][:12]} but the ledger holds {held[:12]}")
            current[path] = r["revised_sha256"]
            fields.setdefault(path, []).extend(r.get("fields", []))
    return current, fields


def accepted_sha256(path: str, fallback: str | None = None) -> str | None:
    """Current audited hash for a repo-relative path; `fallback` if unknown."""
    return _ledger()[0].get(path, fallback)


def revised_fields(path: str) -> list[str]:
    return list(_ledger()[1].get(path, []))


def without_fields(doc: dict, dotted: list[str]) -> dict:
    """Copy of `doc` with the given dotted paths removed (for comparisons)."""
    out = json.loads(json.dumps(doc))
    for d in dotted:
        node = out
        parts = d.split(".")
        for p in parts[:-1]:
            node = node.get(p) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict):
            node.pop(parts[-1], None)
    return out
