#!/usr/bin/env python3
"""Validate an immutable EU battery-research release.

JSON Schema is the structural half of the contract.  This module implements
the parts that JSON Schema cannot express: deterministic identities, source
snapshot and JSON-pointer provenance, cross-record references, file integrity,
rights-to-asset linkage, and safe release-local paths.

The public API deliberately returns a list of errors rather than raising for
bad input.  A malformed or hostile release must fail closed and still provide
useful diagnostics to CI and to a curator running the command locally.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


ROOT = Path(__file__).resolve().parents[1]
RECORD_SCHEMA_PATH = ROOT / "json-schema" / "eu-research-record.schema.json"
RELEASE_SCHEMA_PATH = ROOT / "json-schema" / "eu-research-release.schema.json"
OBSERVATION_SCHEMA_PATH = (
    ROOT / "json-schema" / "eu-research-observation.schema.json"
)

SUMMARY_KEYS = {
    "PROJECT": "projects",
    "RESULT": "results",
    "PROJECT_RESULT": "project_result_links",
    "PARTICIPATION": "participations",
    "RESULT_ASSET": "result_assets",
    "REVIEW_CANDIDATE": "review_candidates",
    "EXCLUDED_MATCH": "excluded_matches",
}

RECORD_SET_POLICY = {
    "PROJECT": ("PUBLIC", True),
    "RESULT": ("PUBLIC", True),
    "PROJECT_RESULT": ("PUBLIC", True),
    "PARTICIPATION": ("PUBLIC", True),
    "RESULT_ASSET": ("PUBLIC", True),
    "REVIEW_CANDIDATE": ("INTERNAL", False),
    "EXCLUDED_MATCH": ("INTERNAL", False),
}

APPROVED_GATES = {
    "MANIFEST_SCHEMA",
    "SOURCE_PROVENANCE",
    "CANONICAL_IDENTIFIERS",
    "COUNT_RECONCILIATION",
    "REFERENTIAL_INTEGRITY",
    "SCOPE_CLASSIFICATION",
    "ACCESS_VERIFICATION",
    "RIGHTS_REVIEW",
    "DETERMINISTIC_BUILD",
    "SANITIZED_EXPORT",
}

APPROVED_RECORD_SETS = {
    "PROJECT",
    "RESULT",
    "PROJECT_RESULT",
    "PARTICIPATION",
    "REVIEW_CANDIDATE",
    "EXCLUDED_MATCH",
}

RESULT_URN = "urn:battery-data:eu-research:result:v1"
PROJECT_RESULT_URN = "urn:battery-data:eu-research:project-result:v1"
PARTICIPATION_URN = "urn:battery-data:eu-research:participation:v1"
CLAIM_URN = "urn:battery-data:eu-research:claim:v1"
REVIEW_URN = "urn:battery-data:eu-research:review:v1"
EXCLUSION_URN = "urn:battery-data:eu-research:exclusion:v1"

_PROGRAMME_NAMESPACE = re.compile(
    r"^eu-[a-z0-9]+(?:[._-][a-z0-9]+)*$"
)
_SHA256 = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_DOI = re.compile(r"^10\.[0-9]{4,9}/\S+$")
_RELEASE_DATE = re.compile(
    r"^snapshot/eu-battery/(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})\.[1-9][0-9]*$"
)
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_POINTER_ESCAPE = re.compile(r"~(?![01])")
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
_PHONE = re.compile(
    r"(?i)\b(?:phone|mobile|telephone|tel|fax)\s*[:=]?\s*"
    r"\+?[0-9][0-9 ().-]{5,}[0-9]"
)
_SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,255}"),
    re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)

PROGRAMME_LABELS = {
    "eu-cef2027": "CEF2027",
    "eu-digital": "DIGITAL",
    "eu-ecsc": "ECSC",
    "eu-edf": "EDF",
    "eu-emff": "EMFF",
    "eu-eng": "ENG",
    "eu-env": "ENV",
    "eu-erasmus-plus": "Erasmus+",
    "eu-fp1": "FP1",
    "eu-fp2": "FP2",
    "eu-fp3": "FP3",
    "eu-fp4": "FP4",
    "eu-fp5": "FP5",
    "eu-fp6": "FP6",
    "eu-fp7": "FP7",
    "eu-h2020": "H2020",
    "eu-horizon": "HORIZON",
    "eu-i3": "Interregional Innovation Investments (I3)",
    "eu-ic": "IC",
    "eu-innovation-fund": "Innovation Fund",
    "eu-life": "LIFE",
    "eu-pre-fwp": "PRE_FWP",
    "eu-rfcs2027": "RFCS2027",
    "eu-single-market-programme": "Single Market Programme",
    "eu-socpl": "SOCPL",
}

# Dataset IDs are identity components, so adding or changing one is a reviewed
# contract change. The value is the only source system allowed to declare it.
DATASET_REGISTRY = {
    "battery-data/eu-battery-excluded-matches": "CURATOR",
    "battery-data/eu-battery-participations": "CURATOR",
    "battery-data/eu-battery-projects": "CURATOR",
    "battery-data/eu-battery-public-results": "CURATOR",
    "battery-data/eu-battery-review-candidates": "CURATOR",
    "cordis/archived-search": "CORDIS_LIVE",
    "cordis/fp7-projects": "CORDIS_BULK",
    "cordis/h2020-organisations": "CORDIS_BULK",
    "cordis/h2020-project-publications": "CORDIS_BULK",
    "cordis/h2020-projects": "CORDIS_BULK",
    "cordis/project-deliverables": "CORDIS_BULK",
    "cordis/project-publications": "CORDIS_BULK",
    "cordis/project-report-summaries": "CORDIS_BULK",
    "cordis/projects": "CORDIS_BULK",
    "curator/eu-battery-scope/1.0.0": "CURATOR",
    "eurio/project-organisation": "EURIO",
    "eurio/project-result": "EURIO",
    "eurio/project-topic": "EURIO",
    "funding-tenders/projects": "FUNDING_TENDERS",
    "funding-tenders/results": "FUNDING_TENDERS",
    "openaire/results": "OPENAIRE",
    "project-repository/results": "PROJECT_REPOSITORY",
}

FROZEN_BASELINES = {
    "baseline/eu-battery/2026-08-21.1": {
        "release_id": "snapshot/eu-battery/2026-08-21.1",
        "as_of_date": "2026-08-21",
        "sha256": "884cb26bb2110fcc9bfc0784e1184b4603367b8b5f1ef1d0ba914f0537dcb035",
    }
}

# Provenance hosts are deliberately narrow for the official aggregators.  A
# project repository may live on a beneficiary's public host, so that source
# class is constrained to public HTTPS rather than to a fixed domain.
SOURCE_HOSTS = {
    "CORDIS_BULK": {"cordis.europa.eu", "data.europa.eu"},
    "CORDIS_LIVE": {"cordis.europa.eu"},
    "FUNDING_TENDERS": {
        "ec.europa.eu",
        "api.tech.ec.europa.eu",
    },
    "EURIO": {"cordis.europa.eu", "data.europa.eu"},
    "OPENAIRE": {"openaire.eu"},
    "CURATOR": {"github.com", "raw.githubusercontent.com"},
}


class StrictJsonError(ValueError):
    """Input is not unambiguous standards-compliant JSON."""


def _reject_constant(value: str) -> None:
    raise StrictJsonError(f"non-finite JSON number is forbidden: {value}")


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _strict_json_loads(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_object_without_duplicate_keys,
        parse_constant=_reject_constant,
    )


def _load_json_file(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise StrictJsonError("UTF-8 BOM is forbidden")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise StrictJsonError(f"invalid UTF-8: {exc}") from exc
    return _strict_json_loads(text)


def _normalise_nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalise_seed_value(value: Any) -> Any:
    if isinstance(value, str):
        return _normalise_nfc(value)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, (list, tuple)):
        return [_normalise_seed_value(item) for item in value]
    raise ValueError(f"unsupported deterministic-ID component: {type(value).__name__}")


def canonical_seed(parts: Sequence[Any]) -> str:
    """Return an unambiguous UTF-8 JSON-array UUIDv5 name.

    Delimiter concatenation is intentionally avoided: DOI suffixes, titles and
    source-local identifiers may themselves contain common delimiters.
    """

    payload = [_normalise_seed_value(part) for part in parts]
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _uuid_record_id(prefix: str, parts: Sequence[Any]) -> str:
    return f"{prefix}/{uuid5(NAMESPACE_URL, canonical_seed(parts))}"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalised = _normalise_nfc(value).strip()
    if not normalised:
        raise ValueError(f"{field_name} must not be empty")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in normalised):
        raise ValueError(f"{field_name} contains a control character")
    return normalised


def _normalise_programme_namespace(value: Any) -> str:
    namespace = _require_text(value, "programme_namespace").casefold()
    if not _PROGRAMME_NAMESPACE.fullmatch(namespace):
        raise ValueError(
            "programme_namespace must be a canonical 'eu-' lowercase namespace"
        )
    return namespace


def canonical_project_id(
    programme_namespace: Any, official_project_id: Any
) -> str:
    """Build the exact project ID from its programme and official ID."""

    namespace = _normalise_programme_namespace(programme_namespace)
    official = _require_text(official_project_id, "official_project_id")
    encoded = quote(official, safe="-._~", encoding="utf-8", errors="strict")
    return f"research_project/{namespace}/{encoded}"


def normalize_doi(value: Any) -> str:
    doi = _require_text(value, "DOI")
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        doi,
        flags=re.IGNORECASE,
    )
    if _BAD_PERCENT.search(doi):
        raise ValueError("DOI contains malformed percent encoding")
    doi = _normalise_nfc(unquote(doi, encoding="utf-8", errors="strict"))
    doi = doi.strip().casefold()
    if not _DOI.fullmatch(doi):
        raise ValueError(f"invalid DOI identity: {doi!r}")
    return doi


def _normalise_percent_encoding(value: str) -> str:
    if _BAD_PERCENT.search(value):
        raise ValueError("URI contains malformed percent encoding")

    def replace(match: re.Match[str]) -> str:
        byte = int(match.group(1), 16)
        character = chr(byte)
        if character in _UNRESERVED:
            return character
        return f"%{byte:02X}"

    return re.sub(r"%([0-9A-Fa-f]{2})", replace, value)


def normalize_uri(value: Any) -> str:
    """Normalize a persistent HTTP(S) or URN identity conservatively."""

    uri = _require_text(value, "official URI")
    try:
        split = urlsplit(uri)
    except ValueError as exc:
        raise ValueError(f"invalid official URI: {exc}") from exc
    scheme = split.scheme.casefold()
    if scheme not in {"http", "https", "urn"}:
        raise ValueError("official URI must use http, https or urn")
    if split.fragment:
        # Fragments identify a sub-resource rather than the published result.
        split = split._replace(fragment="")

    if scheme in {"http", "https"}:
        if split.username is not None or split.password is not None:
            raise ValueError("official URI must not contain user information")
        host = split.hostname
        if not host:
            raise ValueError("official URI has no host")
        try:
            host = host.encode("idna").decode("ascii").casefold()
            port = split.port
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f"invalid official URI authority: {exc}") from exc
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        default_port = (scheme == "http" and port == 80) or (
            scheme == "https" and port == 443
        )
        netloc = host if port is None or default_port else f"{host}:{port}"
        path = quote(
            _normalise_nfc(split.path),
            safe="/%:@-._~!$&'()*+,;=",
            encoding="utf-8",
            errors="strict",
        )
        query = quote(
            _normalise_nfc(split.query),
            safe="/?@-._~!$&'()*+,;=:%",
            encoding="utf-8",
            errors="strict",
        )
        path = _normalise_percent_encoding(path)
        query = _normalise_percent_encoding(query)
        return urlunsplit((scheme, netloc, path, query, ""))

    # urlsplit stores the scheme-specific part of a URN in ``path``.
    if split.netloc or not split.path:
        raise ValueError("URN identity must be an opaque, non-empty URI")
    urn_path = quote(
        _normalise_nfc(split.path),
        safe=":@-._~!$&'()*+,;=/%",
        encoding="utf-8",
        errors="strict",
    )
    urn_path = _normalise_percent_encoding(urn_path)
    urn_query = quote(
        _normalise_nfc(split.query),
        safe="/?@-._~!$&'()*+,;=:%",
        encoding="utf-8",
        errors="strict",
    )
    urn_query = _normalise_percent_encoding(urn_query)
    return urlunsplit(("urn", "", urn_path, urn_query, ""))


def normalize_fingerprint_title(value: Any) -> str:
    title = _require_text(value, "fingerprint title")
    title = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(title.split())


def deterministic_result_id(data: Mapping[str, Any]) -> str:
    """Recompute a result ID from the declared identity basis and components."""

    basis = data.get("identity_basis")
    if basis == "DOI":
        identity = normalize_doi(data.get("identity_value"))
        if data.get("identity_value") != identity:
            raise ValueError("DOI identity_value is not in canonical form")
        doi = normalize_doi(data.get("doi"))
        if identity != doi:
            raise ValueError("DOI identity_value does not match doi")
        parts = [RESULT_URN, "doi", identity]
    elif basis == "OFFICIAL_URI":
        identity = normalize_uri(data.get("identity_value"))
        if data.get("identity_value") != identity:
            raise ValueError("OFFICIAL_URI identity_value is not in canonical form")
        official_uri = normalize_uri(data.get("official_result_uri"))
        if identity != official_uri:
            raise ValueError(
                "OFFICIAL_URI identity_value does not match official_result_uri"
            )
        parts = [RESULT_URN, "official-uri", identity]
    elif basis == "SOURCE_RECORD":
        project_id = _require_text(
            data.get("identity_project_id"), "identity_project_id"
        )
        source_system = _require_text(
            data.get("identity_source_system"), "identity_source_system"
        )
        source_dataset = _require_text(
            data.get("identity_source_dataset"), "identity_source_dataset"
        )
        source_record = _require_text(data.get("identity_value"), "identity_value")
        if data.get("identity_source_dataset") != source_dataset:
            raise ValueError("identity_source_dataset is not in canonical form")
        if data.get("identity_value") != source_record:
            raise ValueError("SOURCE_RECORD identity_value is not in canonical form")
        source_result_ids = data.get("source_result_ids")
        if not isinstance(source_result_ids, list) or source_record not in source_result_ids:
            raise ValueError("SOURCE_RECORD identity_value is absent from source_result_ids")
        parts = [
            RESULT_URN,
            "source-record",
            project_id,
            source_system,
            source_dataset,
            source_record,
        ]
    elif basis == "FINGERPRINT":
        project_id = _require_text(
            data.get("identity_project_id"), "identity_project_id"
        )
        result_type = _require_text(data.get("result_type"), "result_type")
        published_year = data.get("published_year")
        if published_year is not None and (
            isinstance(published_year, bool) or not isinstance(published_year, int)
        ):
            raise ValueError("published_year must be an integer or null")
        title = normalize_fingerprint_title(data.get("title"))
        stored = _require_text(data.get("identity_value"), "identity_value")
        if stored != title:
            raise ValueError(
                "FINGERPRINT identity_value does not match normalized title"
            )
        parts = [
            RESULT_URN,
            "fingerprint",
            project_id,
            result_type,
            published_year,
            title,
        ]
    else:
        raise ValueError(f"unsupported result identity_basis: {basis!r}")
    return _uuid_record_id("research_result", parts)


def deterministic_project_result_id(project_id: Any, result_id: Any) -> str:
    project = _require_text(project_id, "project_id")
    result = _require_text(result_id, "result_id")
    return _uuid_record_id(
        "project_result", [PROJECT_RESULT_URN, project, result]
    )


def deterministic_participation_id(project_id: Any, organization_id: Any) -> str:
    project = _require_text(project_id, "project_id")
    organization = _require_text(organization_id, "organization_id")
    return _uuid_record_id(
        "project_participation",
        [PARTICIPATION_URN, project, organization],
    )


def deterministic_claim_id(record_id: Any, claim: Mapping[str, Any]) -> str:
    record = _require_text(record_id, "record_id")
    asserted_fields = claim.get("asserted_fields")
    if not isinstance(asserted_fields, list) or not asserted_fields:
        raise ValueError("asserted_fields must be a non-empty list")
    pointers = sorted(
        _require_text(pointer, "asserted_fields item") for pointer in asserted_fields
    )
    parts = [
        CLAIM_URN,
        record,
        _require_text(claim.get("source_snapshot_id"), "source_snapshot_id"),
        _require_text(claim.get("source_artifact_id"), "source_artifact_id"),
        _require_text(claim.get("source_system"), "source_system"),
        _require_text(claim.get("source_dataset"), "source_dataset"),
        _normalise_optional_text(claim.get("source_record_id")),
        _normalise_optional_text(claim.get("evidence_locator")),
        pointers,
    ]
    return _uuid_record_id("claim", parts)


def deterministic_review_id(candidate_project_id: Any) -> str:
    project = _require_text(candidate_project_id, "candidate_project_id")
    return _uuid_record_id("research_review", [REVIEW_URN, project])


def deterministic_exclusion_id(candidate_project_id: Any) -> str:
    project = _require_text(candidate_project_id, "candidate_project_id")
    return _uuid_record_id("research_exclusion", [EXCLUSION_URN, project])


def deterministic_result_asset_id(asset_sha256: Any) -> str:
    digest = _sha256_digest(asset_sha256, "asset_sha256")
    return f"result_asset/sha256/{digest}"


def _normalise_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return _require_text(value, "identity component")


def _sha256_digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a SHA-256 string")
    match = _SHA256.fullmatch(value)
    if not match:
        raise ValueError(f"{field_name} is not a lowercase SHA-256 digest")
    return match.group(1)


def _nfc_tree(value: Any) -> Any:
    if isinstance(value, str):
        return _normalise_nfc(value)
    if isinstance(value, list):
        return [_nfc_tree(item) for item in value]
    if isinstance(value, dict):
        return {_normalise_nfc(key): _nfc_tree(item) for key, item in value.items()}
    return value


def canonical_record_hash(record: Mapping[str, Any]) -> str:
    """Hash stable record content, excluding snapshot-observation fields."""

    payload = _nfc_tree({
        key: value
        for key, value in record.items()
        if key
        not in {"release_id", "first_seen_on", "last_seen_on", "content_hash"}
    })
    provenance = payload.get("provenance")
    if isinstance(provenance, list):
        for claim in provenance:
            if not isinstance(claim, dict):
                continue
            claim.pop("retrieved_at", None)
            review = claim.get("review")
            if isinstance(review, dict):
                review.pop("reviewed_at", None)
    data = payload.get("data")
    if isinstance(data, dict):
        data.pop("access_verified_at", None)
        if payload.get("record_type") == "RESULT_ASSET":
            data.pop("retrieved_at", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def canonical_source_snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    """Hash the exact component manifest represented by a source snapshot."""

    payload = _nfc_tree(
        {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def deterministic_source_observation_id(observation: Mapping[str, Any]) -> str:
    payload = _nfc_tree(
        {
            key: value
            for key, value in observation.items()
            if key != "observation_id"
        }
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "source_observation/sha256/" + hashlib.sha256(encoded).hexdigest()


def _diagnostic_text(value: Any, limit: int = 500) -> str:
    """Make untrusted diagnostic text single-line and terminal-safe."""

    rendered = "".join(
        character
        if ord(character) >= 0x20 and ord(character) != 0x7F
        else f"\\u{ord(character):04x}"
        for character in str(value)
    )
    if len(rendered) > limit:
        return rendered[: limit - 3] + "..."
    return rendered


def _schema_error(prefix: str, error: Any) -> str:
    location = "/".join(
        _diagnostic_text(str(part).replace("~", "~0").replace("/", "~1"), 100)
        for part in error.absolute_path
    )
    message = _diagnostic_text(error.message)
    if location:
        return f"{prefix} at /{location}: {message}"
    return f"{prefix}: {message}"


def _safe_relative_file(base: Path, relative: Any) -> tuple[Path | None, str | None]:
    if not isinstance(relative, str) or not relative:
        return None, f"unsafe release path: {relative!r}"
    if "\x00" in relative or "\\" in relative:
        return None, f"unsafe release path: {relative!r}"
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        return None, f"unsafe release path: {relative!r}"
    candidate = base.joinpath(*posix.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, f"release file is missing or unresolvable: {relative}: {exc}"
    if resolved == base or base not in resolved.parents or not resolved.is_file():
        return None, f"release file is missing or escapes the release: {relative}"
    return resolved, None


def _public_https_host(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        split = urlsplit(value)
        if split.scheme.casefold() != "https" or not split.hostname:
            return None
        if split.username is not None or split.password is not None:
            return None
        if split.port not in (None, 443):
            return None
        host = split.hostname.encode("idna").decode("ascii").casefold().rstrip(".")
    except (UnicodeError, ValueError):
        return None
    if not host or host == "localhost" or host.endswith(".localhost"):
        return None
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        labels = host.split(".")
        if len(labels) < 2 or all(label.isdigit() for label in labels):
            return None
        hostname_label = re.compile(
            r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
        )
        if any(not hostname_label.fullmatch(label) for label in labels):
            return None
        return host
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_reserved
    ):
        return None
    return host


def _host_matches(host: str, allowed: set[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in allowed)


def _source_url_allowed(source_system: Any, value: Any) -> bool:
    host = _public_https_host(value)
    if host is None or not isinstance(source_system, str):
        return False
    if source_system == "PROJECT_REPOSITORY":
        return True
    allowed = SOURCE_HOSTS.get(source_system)
    return bool(allowed and _host_matches(host, allowed))


def _pointer_tokens(pointer: Any) -> list[str]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON pointer must start with '/'")
    if _POINTER_ESCAPE.search(pointer):
        raise ValueError("JSON pointer contains an invalid '~' escape")
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]


def _pointer_resolves(document: Any, pointer: Any) -> bool:
    try:
        tokens = _pointer_tokens(pointer)
    except ValueError:
        return False
    value = document
    for token in tokens:
        if isinstance(value, dict):
            if token not in value:
                return False
            value = value[token]
        elif isinstance(value, list):
            if not token.isdigit():
                return False
            index = int(token)
            if index >= len(value):
                return False
            value = value[index]
        else:
            return False
    return True


def _walk_strings(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(item, path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, path + (str(index),))


def _looks_machine_local(path: tuple[str, ...], value: str) -> bool:
    # JSON pointers intentionally begin with '/', so do not confuse them with
    # filesystem paths.
    if any(part in {"asserted_fields", "applies_to"} for part in path):
        return False
    text = value.strip()
    lowered = text.casefold()
    if lowered.startswith(("file:", "vscode:", "smb:")):
        return True
    if text.startswith(("/", "~/", "\\\\", "//")) or _WINDOWS_PATH.match(text):
        return True
    if lowered.startswith(("http://", "https://")):
        try:
            split = urlsplit(text)
        except ValueError:
            return True
        if split.username is not None or split.password is not None:
            return True
        host = split.hostname
        if host and _public_https_host(
            "https://" + host + (split.path or "/")
        ) is None:
            return True
    return False


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _looks_personal_contact(value: str) -> bool:
    return bool(
        value.casefold().startswith("mailto:")
        or _EMAIL.search(value)
        or _PHONE.search(value)
    )


def _sensitive_scan_exempt(
    record: Mapping[str, Any], path: tuple[str, ...]
) -> bool:
    if not path:
        return False
    if path[-1] in {"doi", "grant_doi"}:
        return True
    data = record.get("data")
    return bool(
        path[-1] == "identity_value"
        and isinstance(data, dict)
        and data.get("identity_basis") == "DOI"
    )


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an RFC 3339 date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _media_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    media_type = value.split(";", 1)[0].strip().casefold()
    return media_type or None


def _pointer_covers(pointer: Any, protected: str) -> bool:
    """Return true when a claim pointer asserts a protected node or an ancestor."""

    try:
        pointer_tokens = _pointer_tokens(pointer)
        protected_tokens = _pointer_tokens(protected)
    except ValueError:
        return False
    return (
        protected_tokens[: len(pointer_tokens)] == pointer_tokens
        or pointer_tokens[: len(protected_tokens)] == protected_tokens
    )


def _record_dates_valid(record: Mapping[str, Any], as_of: date) -> str | None:
    try:
        first = date.fromisoformat(str(record.get("first_seen_on")))
        last = date.fromisoformat(str(record.get("last_seen_on")))
    except ValueError:
        return "first_seen_on and last_seen_on must be ISO dates"
    if first > last:
        return "first_seen_on is after last_seen_on"
    if last > as_of:
        return "last_seen_on is after the release as_of_date"
    return None


@dataclass
class _Index:
    counts: Counter[str] = field(default_factory=Counter)
    projects: set[str] = field(default_factory=set)
    project_data: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    results: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    project_results: list[tuple[str, str, str]] = field(default_factory=list)
    participations: list[tuple[str, str, str, tuple[str, ...]]] = field(
        default_factory=list
    )
    project_coordinators: dict[str, str | None] = field(default_factory=dict)
    assets: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = field(
        default_factory=dict
    )
    identity_project_refs: list[tuple[str, str]] = field(default_factory=list)
    result_external_identities: dict[tuple[str, str], str] = field(
        default_factory=dict
    )
    exclusions: set[str] = field(default_factory=set)
    scope_counts: Counter[str] = field(default_factory=Counter)
    programme_counts: Counter[str] = field(default_factory=Counter)
    primary_project_source_counts: Counter[str] = field(default_factory=Counter)
    record_artifact_refs: dict[str, set[str]] = field(default_factory=dict)
    result_identity_artifact_refs: dict[str, set[str]] = field(default_factory=dict)
    result_source_tuples: dict[tuple[str, str, str], str] = field(
        default_factory=dict
    )


def _validate_provenance(
    record: Mapping[str, Any],
    source_snapshots: Mapping[str, Mapping[str, Any]],
    seen_claim_ids: set[str],
    methodology_version: Any,
    generated_at: datetime,
    errors: list[str],
) -> set[str]:
    record_id = str(record.get("record_id", "<missing>"))
    claims = record.get("provenance")
    if not isinstance(claims, list):
        return set()
    referenced_artifacts: set[str] = set()
    for claim_index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        where = f"{record_id} provenance[{claim_index}]"
        claim_id = claim.get("claim_id")
        if isinstance(claim_id, str):
            if claim_id in seen_claim_ids:
                errors.append(f"duplicate claim ID: {claim_id}")
            else:
                seen_claim_ids.add(claim_id)
        snapshot_id = claim.get("source_snapshot_id")
        snapshot = source_snapshots.get(snapshot_id) if isinstance(snapshot_id, str) else None
        artifact: Mapping[str, Any] | None = None
        if snapshot is None:
            errors.append(f"unknown source_snapshot_id in {where}: {snapshot_id!r}")
        else:
            artifact_id = claim.get("source_artifact_id")
            snapshot_artifacts = snapshot.get("artifacts")
            known_artifacts = (
                {
                    item.get("artifact_id"): item
                    for item in snapshot_artifacts
                    if isinstance(item, dict)
                }
                if isinstance(snapshot_artifacts, list)
                else {}
            )
            artifact = known_artifacts.get(artifact_id)
            if artifact is None:
                errors.append(
                    f"unknown source_artifact_id in {where}: {artifact_id!r}"
                )
            else:
                if isinstance(artifact_id, str):
                    referenced_artifacts.add(artifact_id)
                dataset_ids = artifact.get("dataset_ids")
                if not isinstance(dataset_ids, list) or claim.get(
                    "source_dataset"
                ) not in dataset_ids:
                    errors.append(
                        f"source dataset is not declared by artifact in {where}"
                    )
                data = record.get("data")
                if (
                    record.get("record_type") == "RESULT"
                    and isinstance(data, dict)
                    and data.get("identity_basis") == "SOURCE_RECORD"
                    and claim.get("source_system")
                    == data.get("identity_source_system")
                    and claim.get("source_dataset")
                    == data.get("identity_source_dataset")
                    and claim.get("source_record_id") == data.get("identity_value")
                    and dataset_ids != [data.get("identity_source_dataset")]
                ):
                    errors.append(
                        f"SOURCE_RECORD identity artifact is not single-dataset in "
                        f"{where}"
                    )
        source_system = claim.get("source_system")
        if snapshot is not None and snapshot.get("source_system") != source_system:
            errors.append(f"source system does not match snapshot in {where}")
        if not _source_url_allowed(source_system, claim.get("source_url")):
            errors.append(f"source host is not allowed for {source_system!r}: {where}")
        if snapshot is not None and not _source_url_allowed(
            source_system, snapshot.get("official_url")
        ):
            errors.append(
                f"source snapshot host is not allowed for {source_system!r}: {where}"
            )
        try:
            claim_retrieved_at = _parse_datetime(
                claim.get("retrieved_at"), "claim retrieved_at"
            )
        except ValueError as exc:
            errors.append(f"claim timestamp error in {where}: {exc}")
            claim_retrieved_at = None
        else:
            if claim_retrieved_at > generated_at:
                errors.append(f"claim retrieval is after generated_at in {where}")
        pointers = claim.get("asserted_fields")
        if isinstance(pointers, list):
            for pointer in pointers:
                if not _pointer_resolves(record, pointer):
                    errors.append(f"asserted field does not resolve in {where}: {pointer!r}")
            classification_fields: set[str] = set()
            if record.get("record_type") == "PROJECT":
                classification_fields = {
                    "/data/scope_class",
                    "/data/battery_domains",
                }
            elif record.get("record_type") == "PROJECT_RESULT":
                classification_fields = {
                    "/data/battery_relevance",
                    "/data/battery_domains",
                }
            if source_system != "CURATOR" and any(
                _pointer_covers(pointer, protected)
                for pointer in pointers
                for protected in classification_fields
            ):
                errors.append(
                    f"non-curator source asserts battery classification in {where}"
                )
        try:
            expected = deterministic_claim_id(record_id, claim)
        except (TypeError, ValueError) as exc:
            errors.append(f"cannot recompute claim ID in {where}: {exc}")
        else:
            if claim.get("claim_id") != expected:
                errors.append(f"claim ID is not deterministic in {where}")

        review = claim.get("review")
        if isinstance(review, dict):
            if review.get("methodology_version") != methodology_version:
                errors.append(f"claim review methodology does not match release in {where}")
            try:
                reviewed_at = _parse_datetime(
                    review.get("reviewed_at"), "reviewed_at"
                )
            except ValueError as exc:
                errors.append(f"claim review timestamp error in {where}: {exc}")
            else:
                if reviewed_at > generated_at:
                    errors.append(f"claim review is after generated_at in {where}")
                if claim_retrieved_at is not None and reviewed_at < claim_retrieved_at:
                    errors.append(f"claim review predates retrieval in {where}")

    if record.get("record_type") == "RESULT" and isinstance(record.get("data"), dict):
        data = record["data"]
        if data.get("identity_basis") == "SOURCE_RECORD":
            match = any(
                isinstance(claim, dict)
                and claim.get("source_system") == data.get("identity_source_system")
                and claim.get("source_dataset") == data.get("identity_source_dataset")
                and claim.get("source_record_id") == data.get("identity_value")
                for claim in claims
            )
            if not match:
                errors.append(
                    f"SOURCE_RECORD identity has no matching provenance claim: {record_id}"
                )

    record_type = record.get("record_type")
    curation_state = record.get("curation_state")
    required_classification_fields: set[str] | None = None
    if curation_state == "ACCEPTED" and record_type == "PROJECT":
        required_classification_fields = {
            "/data/scope_class",
            "/data/battery_domains",
        }
    elif curation_state == "ACCEPTED" and record_type == "PROJECT_RESULT":
        required_classification_fields = {
            "/data/battery_relevance",
            "/data/battery_domains",
        }
    if required_classification_fields is not None:
        reviewed = any(
            isinstance(claim, dict)
            and claim.get("source_system") == "CURATOR"
            and claim.get("extraction_method") == "MANUAL_REVIEW"
            and isinstance(claim.get("review"), dict)
            and claim["review"].get("decision") == "ACCEPT"
            and required_classification_fields.issubset(
                set(claim.get("asserted_fields") or [])
            )
            for claim in claims
        )
        if not reviewed:
            errors.append(
                f"accepted {record_type} lacks an ACCEPT curator claim for "
                f"classification fields: {record_id}"
            )

    if record_type == "EXCLUDED_MATCH":
        rejected = any(
            isinstance(claim, dict)
            and claim.get("source_system") == "CURATOR"
            and claim.get("extraction_method") == "MANUAL_REVIEW"
            and isinstance(claim.get("review"), dict)
            and claim["review"].get("decision") == "REJECT"
            for claim in claims
        )
        if not rejected:
            errors.append(
                f"excluded match lacks a manual curator REJECT claim: {record_id}"
            )
    return referenced_artifacts


def _validate_rights_pointers(
    record: Mapping[str, Any], public: bool, errors: list[str]
) -> None:
    record_id = str(record.get("record_id", "<missing>"))
    rights = record.get("rights")
    if not isinstance(rights, dict):
        return
    assertions = rights.get("field_assertions")
    if not isinstance(assertions, list):
        if record.get("record_type") == "RESULT_ASSET":
            errors.append(f"result asset has no field-level rights assertions: {record_id}")
        return
    for assertion_index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            continue
        pointers = assertion.get("applies_to")
        if not isinstance(pointers, list):
            continue
        for pointer in pointers:
            if not _pointer_resolves(record, pointer):
                errors.append(
                    f"rights pointer does not resolve in {record_id} "
                    f"assertion[{assertion_index}]: {pointer!r}"
                )
    data = record.get("data")
    if not isinstance(data, dict):
        return
    for key in data:
        escaped = str(key).replace("~", "~0").replace("/", "~1")
        pointer = f"/data/{escaped}"
        assertion = _effective_rights_assertion(record, pointer, errors)
        if assertion is None:
            errors.append(f"data field lacks a rights assertion: {record_id}: {pointer}")
        elif public and assertion.get("metadata_redistribution") != "ALLOWED":
            errors.append(
                f"public data field is not redistributable: {record_id}: {pointer}"
            )


def _effective_rights_assertion(
    record: Mapping[str, Any], target: str, errors: list[str] | None = None
) -> Mapping[str, Any] | None:
    """Resolve overlapping rights assertions by the most-specific pointer.

    Equal-specificity assertions must agree on the fields that affect reuse;
    otherwise the release is ambiguous and therefore fails closed.
    """

    rights = record.get("rights")
    if not isinstance(rights, dict):
        return None
    assertions = rights.get("field_assertions")
    if not isinstance(assertions, list):
        return None
    try:
        target_tokens = _pointer_tokens(target)
    except ValueError:
        return None
    matches: list[tuple[int, Mapping[str, Any]]] = []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        applies_to = assertion.get("applies_to")
        if not isinstance(applies_to, list):
            continue
        best_for_assertion = -1
        for pointer in applies_to:
            try:
                tokens = _pointer_tokens(pointer)
            except ValueError:
                continue
            if target_tokens[: len(tokens)] == tokens:
                best_for_assertion = max(best_for_assertion, len(tokens))
        if best_for_assertion >= 0:
            matches.append((best_for_assertion, assertion))
    if not matches:
        return None
    specificity = max(score for score, _assertion in matches)
    winners = [assertion for score, assertion in matches if score == specificity]
    decision_fields = {
        (
            assertion.get("metadata_redistribution"),
            assertion.get("source_content_licence_status"),
            assertion.get("source_asset_redistribution"),
            assertion.get("licence"),
            assertion.get("licence_url"),
            assertion.get("evidence_url"),
        )
        for assertion in winners
    }
    if len(decision_fields) > 1:
        if errors is not None:
            errors.append(
                f"conflicting equally specific rights assertions for "
                f"{record.get('record_id', '<missing>')} at {target}"
            )
        return None
    return winners[0]


def _asset_has_redistribution_rights(
    record: Mapping[str, Any], errors: list[str]
) -> bool:
    assertion = _effective_rights_assertion(
        record, "/data/archive_path", errors
    )
    if assertion is None:
        return False
    return bool(
        assertion.get("source_asset_redistribution") == "ALLOWED"
        and assertion.get("source_content_licence_status")
        in {
            "OPEN_LICENSE_VERIFIED",
            "PUBLIC_DOMAIN_VERIFIED",
            "EXPLICIT_REUSE_PERMISSION",
        }
        and isinstance(assertion.get("licence"), str)
        and assertion["licence"].strip()
        and _public_https_host(assertion.get("licence_url")) is not None
        and _public_https_host(assertion.get("evidence_url")) is not None
    )


def _validate_record_semantics(
    record: Mapping[str, Any],
    manifest: Mapping[str, Any],
    record_set: Mapping[str, Any],
    source_snapshots: Mapping[str, Mapping[str, Any]],
    as_of: date,
    generated_at: datetime,
    index: _Index,
    seen_ids: set[str],
    seen_claim_ids: set[str],
    errors: list[str],
) -> None:
    record_type = record.get("record_type")
    record_id = record.get("record_id")
    if not isinstance(record_type, str) or not isinstance(record_id, str):
        return

    if record_type != record_set.get("record_type"):
        errors.append(f"record type does not match manifest: {record_id}")
    if record.get("release_id") != manifest.get("release_id"):
        errors.append(f"record release does not match manifest: {record_id}")
    if record_id in seen_ids:
        errors.append(f"duplicate canonical record ID: {record_id}")
    else:
        seen_ids.add(record_id)

    if record_set.get("visibility") == "PUBLIC" and record.get(
        "curation_state"
    ) != "ACCEPTED":
        errors.append(f"unaccepted record exposed publicly: {record_id}")

    date_error = _record_dates_valid(record, as_of)
    if date_error:
        errors.append(f"record date error for {record_id}: {date_error}")

    try:
        expected_hash = canonical_record_hash(record)
    except (TypeError, ValueError) as exc:
        errors.append(f"cannot compute content hash for {record_id}: {exc}")
    else:
        if record.get("content_hash") != expected_hash:
            errors.append(f"record content hash mismatch: {record_id}")

    for value_path, value in _walk_strings(record):
        if _looks_machine_local(value_path, value):
            errors.append(
                f"machine-local path or URL leaked into record: {record_id} "
                f"at /{'/'.join(value_path)}"
            )
            break
        if _looks_secret(value) or (
            not _sensitive_scan_exempt(record, value_path)
            and _looks_personal_contact(value)
        ):
            errors.append(
                f"credential or personal contact leaked into record: {record_id} "
                f"at /{'/'.join(value_path)}"
            )
            break

    referenced_artifacts = _validate_provenance(
        record,
        source_snapshots,
        seen_claim_ids,
        manifest.get("methodology_version"),
        generated_at,
        errors,
    )
    index.record_artifact_refs[record_id] = referenced_artifacts
    _validate_rights_pointers(
        record, record_set.get("visibility") == "PUBLIC", errors
    )

    data = record.get("data")
    if not isinstance(data, dict):
        return
    try:
        if record_type == "PROJECT":
            official_project_id = _require_text(
                data.get("official_project_id"), "official_project_id"
            )
            expected_id = canonical_project_id(
                data.get("programme_namespace"), data.get("official_project_id")
            )
            if data.get("official_project_id") != official_project_id:
                errors.append(f"official project ID is not canonical: {record_id}")
            if data.get("programme_namespace") != _normalise_programme_namespace(
                data.get("programme_namespace")
            ):
                errors.append(f"project programme namespace is not canonical: {record_id}")
            expected_label = PROGRAMME_LABELS.get(data.get("programme_namespace"))
            if data.get("framework_programme") != expected_label:
                errors.append(
                    f"project programme label does not match namespace: {record_id}"
                )
            if record_id != expected_id:
                errors.append(f"project ID does not match project data: {record_id}")
            index.projects.add(record_id)
            index.project_data[record_id] = data
            scope_class = data.get("scope_class")
            if isinstance(scope_class, str):
                index.scope_counts[scope_class] += 1
            programme_label = data.get("framework_programme")
            if isinstance(programme_label, str):
                index.programme_counts[programme_label] += 1
            project_claims = [
                claim
                for claim in record.get("provenance", [])
                if isinstance(claim, dict) and claim.get("source_system") != "CURATOR"
            ]
            if any(
                claim.get("source_system") == "FUNDING_TENDERS"
                for claim in project_claims
            ):
                index.primary_project_source_counts[
                    "FUNDING_TENDERS_PORTAL"
                ] += 1
            elif any(
                claim.get("source_dataset") == "cordis/archived-search"
                for claim in project_claims
            ):
                index.primary_project_source_counts["CORDIS_ARCHIVED_SEARCH"] += 1
            elif any(
                claim.get("source_system") in {"CORDIS_BULK", "CORDIS_LIVE"}
                for claim in project_claims
            ):
                index.primary_project_source_counts[
                    "CORDIS_MODERN_BULK_OR_LIVE"
                ] += 1
            coordinator_id = data.get("coordinator_org_id")
            index.project_coordinators[record_id] = (
                coordinator_id if isinstance(coordinator_id, str) else None
            )
        elif record_type == "RESULT":
            basis = data.get("identity_basis")
            complete_source_claim = any(
                isinstance(claim, dict)
                and claim.get("source_system") not in {None, "CURATOR"}
                and isinstance(claim.get("source_dataset"), str)
                and bool(claim["source_dataset"].strip())
                and isinstance(claim.get("source_record_id"), str)
                and bool(claim["source_record_id"].strip())
                for claim in record.get("provenance", [])
            )
            expected_basis = (
                "DOI"
                if data.get("doi") is not None
                else "OFFICIAL_URI"
                if data.get("official_result_uri") is not None
                else "SOURCE_RECORD"
                if complete_source_claim
                else "FINGERPRINT"
            )
            if basis != expected_basis:
                errors.append(
                    f"result identity precedence requires {expected_basis}: {record_id}"
                )
            expected_id = deterministic_result_id(data)
            if record_id != expected_id:
                errors.append(f"result ID is not deterministic: {record_id}")
            matching_identity_artifacts: set[str] = set()
            for claim in record.get("provenance", []):
                if not isinstance(claim, dict) or claim.get("source_system") == "CURATOR":
                    continue
                source_record_id = claim.get("source_record_id")
                source_dataset = claim.get("source_dataset")
                source_system = claim.get("source_system")
                if (
                    isinstance(source_system, str)
                    and isinstance(source_dataset, str)
                    and isinstance(source_record_id, str)
                    and source_record_id.strip()
                ):
                    source_tuple = (source_system, source_dataset, source_record_id)
                    prior_result = index.result_source_tuples.get(source_tuple)
                    if prior_result is not None and prior_result != record_id:
                        errors.append(
                            f"source result tuple is reused by distinct results: "
                            f"{record_id}"
                        )
                    else:
                        index.result_source_tuples[source_tuple] = record_id
                    if (
                        basis == "SOURCE_RECORD"
                        and source_system == data.get("identity_source_system")
                        and source_dataset == data.get("identity_source_dataset")
                        and source_record_id == data.get("identity_value")
                        and isinstance(claim.get("source_artifact_id"), str)
                    ):
                        matching_identity_artifacts.add(claim["source_artifact_id"])
            if matching_identity_artifacts:
                index.result_identity_artifact_refs[record_id] = (
                    matching_identity_artifacts
                )
            for kind, raw_value, normalizer in (
                ("DOI", data.get("doi"), normalize_doi),
                ("OFFICIAL_URI", data.get("official_result_uri"), normalize_uri),
            ):
                if raw_value is None:
                    continue
                normalized = normalizer(raw_value)
                if raw_value != normalized:
                    errors.append(
                        f"stored global result identity is not canonical {kind}: "
                        f"{record_id}"
                    )
                identity_key = (kind, normalized)
                prior = index.result_external_identities.get(identity_key)
                if prior is not None and prior != record_id:
                    errors.append(
                        f"duplicate global result identity {kind}: {record_id}"
                    )
                else:
                    index.result_external_identities[identity_key] = record_id
            access_status = data.get("access_status")
            if access_status != "METADATA_ONLY" and _public_https_host(
                data.get("direct_url")
            ) is None:
                errors.append(f"checked result URL is not public HTTPS: {record_id}")
            if access_status in {
                "OPEN_FULL_CONTENT",
                "OPEN_REPOSITORY_LANDING_PAGE",
            }:
                status = data.get("access_http_status")
                allowed_statuses = (
                    {200, 206}
                    if access_status == "OPEN_FULL_CONTENT"
                    else {200}
                )
                if isinstance(status, bool) or status not in allowed_statuses:
                    errors.append(
                        f"open result has an incompatible HTTP status: {record_id}"
                    )
                if _public_https_host(data.get("access_final_url")) is None:
                    errors.append(
                        f"open result final URL is not public HTTPS: {record_id}"
                    )
                expected_evidence_kind = (
                    {"SUBSTANTIVE_FILE", "OFFICIAL_FULL_NARRATIVE"}
                    if access_status == "OPEN_FULL_CONTENT"
                    else {"LANDING_PAGE"}
                )
                if data.get("access_check_method") != "GET":
                    errors.append(f"open result was not verified with GET: {record_id}")
                if data.get("access_evidence_kind") not in expected_evidence_kind:
                    errors.append(f"open result evidence kind is incompatible: {record_id}")
                media_type = _media_type(data.get("access_content_type"))
                if media_type in {
                    "application/problem+json",
                    "application/problem+xml",
                }:
                    errors.append(f"open result returned an error media type: {record_id}")
                if (
                    access_status == "OPEN_FULL_CONTENT"
                    and data.get("access_evidence_kind") == "SUBSTANTIVE_FILE"
                    and media_type in {"text/html", "application/xhtml+xml"}
                ):
                    errors.append(
                        f"substantive-file result has a landing-page content type: {record_id}"
                    )
                if (
                    access_status == "OPEN_FULL_CONTENT"
                    and data.get("access_evidence_kind") == "OFFICIAL_FULL_NARRATIVE"
                    and media_type not in {"text/html", "application/xhtml+xml"}
                ):
                    errors.append(
                        f"official full narrative has a non-HTML content type: {record_id}"
                    )
                if access_status == "OPEN_REPOSITORY_LANDING_PAGE" and not (
                    isinstance(data.get("availability_note"), str)
                    and data["availability_note"].strip()
                ):
                    errors.append(f"landing-page result lacks an outcome note: {record_id}")
            if data.get("access_verified_at") is not None:
                try:
                    verified_at = _parse_datetime(
                        data.get("access_verified_at"), "access_verified_at"
                    )
                except ValueError as exc:
                    errors.append(f"result access timestamp error for {record_id}: {exc}")
                else:
                    if verified_at > generated_at:
                        errors.append(
                            f"result access verification is after generated_at: {record_id}"
                        )
            index.results[record_id] = data
            if data.get("identity_basis") in {"SOURCE_RECORD", "FINGERPRINT"}:
                project_ref = data.get("identity_project_id")
                if isinstance(project_ref, str):
                    index.identity_project_refs.append((record_id, project_ref))
        elif record_type == "PROJECT_RESULT":
            project_id = data.get("project_id")
            result_id = data.get("result_id")
            expected_id = deterministic_project_result_id(project_id, result_id)
            if record_id != expected_id:
                errors.append(f"project-result ID is not deterministic: {record_id}")
            if isinstance(project_id, str) and isinstance(result_id, str):
                index.project_results.append((record_id, project_id, result_id))
        elif record_type == "PARTICIPATION":
            project_id = data.get("project_id")
            organization_id = data.get("organization_id")
            expected_id = deterministic_participation_id(project_id, organization_id)
            if record_id != expected_id:
                errors.append(f"participation ID is not deterministic: {record_id}")
            source_organization_id = data.get("source_organization_id")
            if (
                not isinstance(source_organization_id, str)
                or re.fullmatch(r"[0-9]{9}", source_organization_id) is None
                or organization_id != f"org/eu-pic/{source_organization_id}"
            ):
                errors.append(
                    f"participation organization is not the declared EU PIC: {record_id}"
                )
            official_pic_claim = any(
                isinstance(claim, dict)
                and claim.get("source_system") != "CURATOR"
                and isinstance(claim.get("asserted_fields"), list)
                and "/data/source_organization_id" in claim["asserted_fields"]
                and "/data/organization_id" in claim["asserted_fields"]
                and isinstance(claim.get("source_record_id"), str)
                and isinstance(source_organization_id, str)
                and source_organization_id in claim["source_record_id"]
                and isinstance(claim.get("evidence_locator"), str)
                and source_organization_id in claim["evidence_locator"]
                for claim in record.get("provenance", [])
            )
            if not official_pic_claim:
                errors.append(
                    f"participation PIC lacks a bound official-source claim: "
                    f"{record_id}"
                )
            roles = data.get("roles")
            if (
                isinstance(project_id, str)
                and isinstance(organization_id, str)
                and isinstance(roles, list)
            ):
                index.participations.append(
                    (
                        record_id,
                        project_id,
                        organization_id,
                        tuple(role for role in roles if isinstance(role, str)),
                    )
                )
        elif record_type == "RESULT_ASSET":
            expected_id = deterministic_result_asset_id(data.get("asset_sha256"))
            if record_id != expected_id:
                errors.append(f"result-asset ID does not match asset digest: {record_id}")
            if not _asset_has_redistribution_rights(record, errors):
                errors.append(
                    f"result asset lacks explicit redistribution rights: {record_id}"
                )
            try:
                asset_retrieved_at = _parse_datetime(
                    data.get("retrieved_at"), "result asset retrieved_at"
                )
            except ValueError as exc:
                errors.append(f"result asset timestamp error for {record_id}: {exc}")
            else:
                if asset_retrieved_at > generated_at:
                    errors.append(
                        f"result asset retrieval is after generated_at: {record_id}"
                    )
            index.assets[record_id] = (data, record.get("rights", {}))
        elif record_type == "REVIEW_CANDIDATE":
            expected_id = deterministic_review_id(data.get("candidate_project_id"))
            if record_id != expected_id:
                errors.append(f"review ID is not deterministic: {record_id}")
        elif record_type == "EXCLUDED_MATCH":
            expected_id = deterministic_exclusion_id(data.get("candidate_project_id"))
            if record_id != expected_id:
                errors.append(f"exclusion ID is not deterministic: {record_id}")
            candidate_project_id = data.get("candidate_project_id")
            if isinstance(candidate_project_id, str):
                index.exclusions.add(candidate_project_id)
    except (TypeError, ValueError) as exc:
        errors.append(f"cannot recompute {record_type} ID for {record_id}: {exc}")

    if record_type in SUMMARY_KEYS:
        index.counts[record_type] += 1


def _validate_record_set(
    base: Path,
    record_set: Mapping[str, Any],
    manifest: Mapping[str, Any],
    validator: Draft202012Validator,
    source_snapshots: Mapping[str, Mapping[str, Any]],
    as_of: date,
    generated_at: datetime,
    index: _Index,
    seen_ids: set[str],
    seen_claim_ids: set[str],
    seen_paths: set[str],
    record_schema_id: Any,
    record_schema_sha256: str,
    errors: list[str],
) -> None:
    relative = record_set.get("path")
    if not isinstance(relative, str):
        errors.append(f"unsafe record-set path: {relative!r}")
        return
    if relative in seen_paths:
        errors.append(f"duplicate record-set path: {relative}")
        return
    seen_paths.add(relative)

    if record_set.get("record_schema") != record_schema_id:
        errors.append(f"record schema ID does not match the local schema: {relative}")
    if record_set.get("record_schema_sha256") != record_schema_sha256:
        errors.append(f"record schema SHA-256 mismatch: {relative}")

    record_type = record_set.get("record_type")
    expected_policy = RECORD_SET_POLICY.get(record_type)
    if expected_policy is not None:
        expected_visibility, expected_canonical = expected_policy
        if record_set.get("visibility") != expected_visibility:
            errors.append(
                f"record-set visibility for {record_type} must be {expected_visibility}"
            )
        if record_set.get("canonical") is not expected_canonical:
            errors.append(
                f"record-set canonical flag for {record_type} must be "
                f"{str(expected_canonical).lower()}"
            )

    path, path_error = _safe_relative_file(base, relative)
    if path_error:
        errors.append(path_error.replace("release path", "record-set path"))
        return
    assert path is not None

    hasher = hashlib.sha256()
    byte_size = 0
    record_count = 0
    file_ids: list[str] = []
    saw_line = False
    last_byte = b""

    try:
        handle = path.open("rb")
    except OSError as exc:
        errors.append(f"cannot open record-set file {relative}: {exc}")
        return

    with handle:
        for line_number, raw_line in enumerate(handle, start=1):
            saw_line = True
            last_byte = raw_line[-1:]
            byte_size += len(raw_line)
            hasher.update(raw_line)
            if line_number == 1 and raw_line.startswith(b"\xef\xbb\xbf"):
                errors.append(f"UTF-8 BOM is forbidden: {relative}:1")
            if b"\r" in raw_line:
                errors.append(f"CR is forbidden in LF NDJSON: {relative}:{line_number}")
            try:
                text = raw_line.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                errors.append(f"invalid UTF-8: {relative}:{line_number}: {exc}")
                continue
            content = text[:-1] if text.endswith("\n") else text
            if not content.strip():
                errors.append(f"blank NDJSON line is forbidden: {relative}:{line_number}")
                continue
            record_count += 1
            try:
                record = _strict_json_loads(content)
            except (json.JSONDecodeError, StrictJsonError) as exc:
                errors.append(f"invalid JSON: {relative}:{line_number}: {exc}")
                continue
            if not isinstance(record, dict):
                errors.append(
                    f"record schema: {relative}:{line_number}: record must be an object"
                )
                continue

            schema_errors = sorted(
                validator.iter_errors(record),
                key=lambda item: tuple(str(part) for part in item.absolute_path),
            )
            if schema_errors:
                errors.extend(
                    _schema_error(f"record schema: {relative}:{line_number}", error)
                    for error in schema_errors
                )
                # Do not run semantic code against a structurally invalid shape.
                continue

            record_id = record.get("record_id")
            if isinstance(record_id, str):
                file_ids.append(record_id)
            _validate_record_semantics(
                record,
                manifest,
                record_set,
                source_snapshots,
                as_of,
                generated_at,
                index,
                seen_ids,
                seen_claim_ids,
                errors,
            )

    if saw_line and last_byte != b"\n":
        errors.append(f"record-set file lacks final LF: {relative}")
    actual_sha = hasher.hexdigest()
    if actual_sha != record_set.get("sha256"):
        errors.append(f"file SHA-256 mismatch: {relative}")
    if byte_size != record_set.get("byte_size"):
        errors.append(f"byte-size mismatch: {relative}")
    if record_count != record_set.get("record_count"):
        errors.append(f"record-count mismatch: {relative}")
    if file_ids != sorted(file_ids):
        errors.append(f"records are not sorted by record_id: {relative}")


def _file_digest_and_size(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _validate_source_observation_ledger(
    base: Path,
    manifest: Mapping[str, Any],
    validator: Draft202012Validator,
    source_snapshots: Mapping[str, Mapping[str, Any]],
    index: _Index,
    schema_id: Any,
    schema_sha256: str,
    errors: list[str],
) -> Mapping[str, Any] | None:
    ledger = manifest.get("source_observation_ledger")
    if manifest.get("release_kind") == "TEST_FIXTURE":
        if ledger is not None:
            errors.append("TEST_FIXTURE source observation ledger must be null")
        return None
    if not isinstance(ledger, dict):
        errors.append("FULL_SNAPSHOT requires a source observation ledger")
        return None
    if ledger.get("observation_schema") != schema_id:
        errors.append("source observation schema ID does not match the local schema")
    if ledger.get("observation_schema_sha256") != schema_sha256:
        errors.append("source observation schema SHA-256 mismatch")

    relative = ledger.get("path")
    reserved = {"manifest.json"}
    baseline = manifest.get("baseline")
    if isinstance(baseline, dict) and isinstance(baseline.get("path"), str):
        reserved.add(baseline["path"])
    record_sets = manifest.get("record_sets")
    if isinstance(record_sets, list):
        reserved.update(
            record_set["path"]
            for record_set in record_sets
            if isinstance(record_set, dict) and isinstance(record_set.get("path"), str)
        )
    if relative in reserved:
        errors.append("source observation ledger aliases generated release data")
    path, path_error = _safe_relative_file(base, relative)
    if path_error:
        errors.append(path_error.replace("release path", "source observation path"))
        return None
    assert path is not None

    artifacts: dict[str, tuple[Any, Mapping[str, Any]]] = {}
    for snapshot in source_snapshots.values():
        source_system = snapshot.get("source_system")
        snapshot_artifacts = snapshot.get("artifacts")
        if not isinstance(snapshot_artifacts, list):
            continue
        for artifact in snapshot_artifacts:
            if isinstance(artifact, dict) and isinstance(
                artifact.get("artifact_id"), str
            ):
                artifacts[artifact["artifact_id"]] = (source_system, artifact)

    relation_ids = {relation_id for relation_id, _project, _result in index.project_results}
    hasher = hashlib.sha256()
    byte_size = 0
    record_count = 0
    ids: list[str] = []
    seen_ids: set[str] = set()
    seen_rows: set[tuple[str, int]] = set()
    access_counts: Counter[str] = Counter()
    relevance_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    project_counts: Counter[str] = Counter()
    referenced_artifacts: set[str] = set()
    saw_line = False
    last_byte = b""

    try:
        handle = path.open("rb")
    except OSError as exc:
        errors.append(f"cannot open source observation ledger {relative}: {exc}")
        return None
    with handle:
        for line_number, raw_line in enumerate(handle, start=1):
            saw_line = True
            last_byte = raw_line[-1:]
            byte_size += len(raw_line)
            hasher.update(raw_line)
            if line_number == 1 and raw_line.startswith(b"\xef\xbb\xbf"):
                errors.append(f"UTF-8 BOM is forbidden: {relative}:1")
            if b"\r" in raw_line:
                errors.append(f"CR is forbidden in LF NDJSON: {relative}:{line_number}")
            try:
                text = raw_line.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                errors.append(f"invalid UTF-8: {relative}:{line_number}: {exc}")
                continue
            content = text[:-1] if text.endswith("\n") else text
            if not content.strip():
                errors.append(
                    f"blank NDJSON line is forbidden: {relative}:{line_number}"
                )
                continue
            record_count += 1
            try:
                observation = _strict_json_loads(content)
            except (json.JSONDecodeError, StrictJsonError) as exc:
                errors.append(f"invalid JSON: {relative}:{line_number}: {exc}")
                continue
            if not isinstance(observation, dict):
                errors.append(
                    f"observation schema: {relative}:{line_number}: row must be an object"
                )
                continue
            schema_errors = sorted(
                validator.iter_errors(observation),
                key=lambda item: tuple(str(part) for part in item.absolute_path),
            )
            if schema_errors:
                errors.extend(
                    _schema_error(
                        f"observation schema: {relative}:{line_number}", error
                    )
                    for error in schema_errors
                )
                continue

            observation_id = observation["observation_id"]
            ids.append(observation_id)
            if observation_id in seen_ids:
                errors.append(f"duplicate source observation ID: {observation_id}")
            else:
                seen_ids.add(observation_id)
            try:
                expected_id = deterministic_source_observation_id(observation)
            except (TypeError, ValueError) as exc:
                errors.append(
                    f"cannot hash source observation {observation_id}: "
                    f"{_diagnostic_text(exc)}"
                )
            else:
                if observation_id != expected_id:
                    errors.append(
                        f"source observation ID is not deterministic: {observation_id}"
                    )
            if observation.get("release_id") != manifest.get("release_id"):
                errors.append(f"source observation release mismatch: {observation_id}")

            artifact_id = observation["source_artifact_id"]
            artifact_entry = artifacts.get(artifact_id)
            if artifact_entry is None:
                errors.append(
                    f"source observation references an unknown artifact: {observation_id}"
                )
            else:
                source_system, artifact = artifact_entry
                if observation.get("source_system") != source_system:
                    errors.append(
                        f"source observation system does not match artifact: "
                        f"{observation_id}"
                    )
                if observation.get("source_dataset") not in artifact.get(
                    "dataset_ids", []
                ):
                    errors.append(
                        f"source observation dataset does not match artifact: "
                        f"{observation_id}"
                    )
                referenced_artifacts.add(artifact_id)
            row_key = (artifact_id, observation["source_row_number"])
            if row_key in seen_rows:
                errors.append(
                    f"duplicate source artifact row in observation ledger: {observation_id}"
                )
            else:
                seen_rows.add(row_key)
            project_id = observation["project_id"]
            if project_id not in index.projects:
                errors.append(f"source observation project is unknown: {observation_id}")
            disposition = observation["disposition"]
            if disposition in {"CANONICAL_LINK", "DUPLICATE_LINK"} and observation.get(
                "project_result_id"
            ) not in relation_ids:
                errors.append(
                    f"source observation link is unknown: {observation_id}"
                )
            access_counts[observation["access_status"]] += 1
            relevance_counts[observation["battery_relevance"]] += 1
            type_counts[observation["result_type"]] += 1
            project_counts[project_id] += 1

    if saw_line and last_byte != b"\n":
        errors.append(f"source observation ledger lacks final LF: {relative}")
    if hasher.hexdigest() != ledger.get("sha256"):
        errors.append(f"source observation ledger SHA-256 mismatch: {relative}")
    if byte_size != ledger.get("byte_size"):
        errors.append(f"source observation ledger byte-size mismatch: {relative}")
    if record_count != ledger.get("record_count"):
        errors.append(f"source observation ledger record-count mismatch: {relative}")
    if ids != sorted(ids):
        errors.append("source observation ledger is not sorted by observation_id")
    for value in (
        "OPEN_FULL_CONTENT",
        "OPEN_REPOSITORY_LANDING_PAGE",
        "METADATA_ONLY",
        "PAYWALLED",
        "RESTRICTED_OR_CONFIDENTIAL",
        "BROKEN_OR_MISSING",
    ):
        access_counts.setdefault(value, 0)
    for value in (
        "DIRECT_BATTERY_RESULT",
        "RESULT_FROM_BATTERY_PROJECT",
        "UNCLASSIFIED",
    ):
        relevance_counts.setdefault(value, 0)
    for value in (
        "COMMUNICATION_DISSEMINATION",
        "CONFERENCE_PUBLICATION",
        "DATASET_DATABASE",
        "PROJECT_REPORT_SUMMARY",
        "HARDWARE_PROTOTYPE_DESIGN",
        "JOURNAL_PUBLICATION",
        "LCA_TEA_COST_MARKET",
        "MODEL_SIMULATOR_DIGITAL_TWIN",
        "OTHER_PUBLIC_RESULT",
        "PATENT_IP",
        "PROJECT_ADMINISTRATION",
        "SOFTWARE_SOURCE_CODE",
        "STANDARD_ROADMAP_POLICY",
        "TECHNICAL_DELIVERABLE",
        "TEST_METHOD_PROTOCOL",
        "TRAINING_EDUCATION",
    ):
        type_counts.setdefault(value, 0)
    return {
        "source_result_rows": len(ids),
        "source_row_access_counts": dict(access_counts),
        "source_row_result_relevance_counts": dict(relevance_counts),
        "source_row_result_type_counts": dict(type_counts),
        "project_counts": dict(project_counts),
        "referenced_artifact_ids": referenced_artifacts,
        "input_artifact_id": ledger.get("input_artifact_id"),
    }


def _validate_cross_references(
    base: Path,
    index: _Index,
    source_snapshots: Mapping[str, Mapping[str, Any]],
    retained_source_digests: set[str],
    errors: list[str],
) -> None:
    source_retained_paths = {
        artifact.get("retained_path")
        for snapshot in source_snapshots.values()
        for artifact in (
            snapshot.get("artifacts")
            if isinstance(snapshot.get("artifacts"), list)
            else []
        )
        if isinstance(artifact, dict) and isinstance(artifact.get("retained_path"), str)
    }
    linked_results: set[str] = set()
    relation_pairs: set[tuple[str, str]] = set()
    linked_projects: set[str] = set()
    for relation_id, project_id, result_id in index.project_results:
        if project_id not in index.projects:
            errors.append(f"orphan project-result project: {relation_id}")
        if result_id not in index.results:
            errors.append(f"orphan project-result result: {relation_id}")
        linked_results.add(result_id)
        linked_projects.add(project_id)
        relation_pairs.add((project_id, result_id))

    participation_roles: dict[tuple[str, str], set[str]] = {}
    for participation_id, project_id, organization_id, roles in index.participations:
        if project_id not in index.projects:
            errors.append(f"orphan participation: {participation_id}")
        participation_roles.setdefault((project_id, organization_id), set()).update(
            roles
        )

    coordinator_roles: dict[str, set[str]] = {}
    for (project_id, organization_id), roles in participation_roles.items():
        if "COORDINATOR" in roles:
            coordinator_roles.setdefault(project_id, set()).add(organization_id)

    for project_id, organization_id in index.project_coordinators.items():
        expected = {organization_id} if organization_id is not None else set()
        actual = coordinator_roles.get(project_id, set())
        if actual != expected:
            errors.append(
                f"project coordinator contradicts COORDINATOR participations: "
                f"{project_id}"
            )

    for result_id, project_id in index.identity_project_refs:
        if project_id not in index.projects:
            errors.append(f"result identity references an unknown project: {result_id}")
        if (project_id, result_id) not in relation_pairs:
            errors.append(
                f"project-scoped result identity lacks its project-result link: "
                f"{result_id}"
            )

    for result_id in sorted(set(index.results) - linked_results):
        errors.append(f"result has no project attribution: {result_id}")

    for asset_id, (data, _rights) in index.assets.items():
        result_id = data.get("result_id")
        if result_id not in index.results:
            errors.append(f"orphan result asset: {asset_id}")
        else:
            listed = index.results[result_id].get("asset_ids")
            if not isinstance(listed, list) or asset_id not in listed:
                errors.append(f"result does not list its bundled asset: {asset_id}")

        relative = data.get("archive_path")
        if relative in source_retained_paths:
            errors.append(f"result asset aliases retained source bytes: {asset_id}")
        path, path_error = _safe_relative_file(base, relative)
        if path_error:
            errors.append(
                path_error.replace("release path", "result-asset archive_path")
            )
            continue
        assert path is not None
        try:
            actual_sha, actual_size = _file_digest_and_size(path)
            expected_sha = _sha256_digest(data.get("asset_sha256"), "asset_sha256")
        except (OSError, ValueError) as exc:
            errors.append(f"cannot verify result asset {asset_id}: {exc}")
            continue
        if actual_sha != expected_sha:
            errors.append(f"result-asset file SHA-256 mismatch: {asset_id}")
        if actual_sha in retained_source_digests:
            errors.append(f"result asset aliases retained source bytes: {asset_id}")
        if actual_size != data.get("byte_size"):
            errors.append(f"result-asset byte-size mismatch: {asset_id}")

    for result_id, data in index.results.items():
        asset_ids = data.get("asset_ids")
        if not isinstance(asset_ids, list):
            continue
        if data.get("access_status") == "METADATA_ONLY" and asset_ids:
            errors.append(f"metadata-only result claims a bundled asset: {result_id}")
        for asset_id in asset_ids:
            asset = index.assets.get(asset_id)
            if asset is None:
                errors.append(f"result references a missing asset: {result_id}: {asset_id}")
            elif asset[0].get("result_id") != result_id:
                errors.append(f"result asset points at a different result: {asset_id}")


def _validate_release_dates(
    manifest: Mapping[str, Any], errors: list[str]
) -> tuple[date, datetime]:
    as_of_text = manifest.get("as_of_date")
    try:
        as_of = date.fromisoformat(str(as_of_text))
    except ValueError:
        # The manifest schema normally catches this; retain a safe fallback.
        errors.append("manifest as_of_date is not an ISO date")
        as_of = date.min
    release_id = manifest.get("release_id")
    match = _RELEASE_DATE.fullmatch(release_id) if isinstance(release_id, str) else None
    if not match or match.group("date") != as_of_text:
        errors.append("release_id date does not match as_of_date")
    try:
        generated_at = _parse_datetime(manifest.get("generated_at"), "generated_at")
    except ValueError as exc:
        errors.append(f"manifest generated_at error: {exc}")
        generated_at = datetime.min.replace(tzinfo=timezone.utc)
    else:
        if generated_at.date() < as_of:
            errors.append("generated_at is before as_of_date")
    return as_of, generated_at


def _validate_sources(
    base: Path,
    manifest: Mapping[str, Any],
    generated_at: datetime,
    errors: list[str],
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    snapshots: dict[str, Mapping[str, Any]] = {}
    artifact_ids: set[str] = set()
    retained_paths: set[str] = set()
    retained_source_digests: set[str] = set()
    reserved_paths = {"manifest.json"}
    reserved_digests: set[str] = set()
    baseline = manifest.get("baseline")
    if isinstance(baseline, dict) and isinstance(baseline.get("path"), str):
        reserved_paths.add(baseline["path"])
        if isinstance(baseline.get("sha256"), str):
            reserved_digests.add(baseline["sha256"])
    ledger = manifest.get("source_observation_ledger")
    if isinstance(ledger, dict) and isinstance(ledger.get("path"), str):
        reserved_paths.add(ledger["path"])
        if isinstance(ledger.get("sha256"), str):
            reserved_digests.add(ledger["sha256"])
    record_sets = manifest.get("record_sets")
    if isinstance(record_sets, list):
        reserved_paths.update(
            record_set["path"]
            for record_set in record_sets
            if isinstance(record_set, dict) and isinstance(record_set.get("path"), str)
        )
        reserved_digests.update(
            record_set["sha256"]
            for record_set in record_sets
            if isinstance(record_set, dict) and isinstance(record_set.get("sha256"), str)
        )
    raw_snapshots = manifest.get("source_snapshots")
    if not isinstance(raw_snapshots, list):
        return snapshots
    for snapshot in raw_snapshots:
        if not isinstance(snapshot, dict):
            continue
        source_id = snapshot.get("source_id")
        if not isinstance(source_id, str):
            continue
        if source_id in snapshots:
            errors.append(f"duplicate source snapshot ID: {source_id}")
        else:
            snapshots[source_id] = snapshot
        source_system = snapshot.get("source_system")
        if not _source_url_allowed(source_system, snapshot.get("official_url")):
            errors.append(
                f"source snapshot host is not allowed for {source_system!r}: "
                f"{source_id}"
            )
        try:
            snapshot_retrieved_at = _parse_datetime(
                snapshot.get("retrieved_at"), "source snapshot retrieved_at"
            )
        except ValueError as exc:
            errors.append(f"source snapshot timestamp error for {source_id}: {exc}")
        else:
            if snapshot_retrieved_at > generated_at:
                errors.append(
                    f"source snapshot retrieval is after generated_at: {source_id}"
                )
        declared_snapshot_hash = snapshot.get("snapshot_sha256")
        if declared_snapshot_hash is not None:
            try:
                expected_snapshot_hash = canonical_source_snapshot_hash(snapshot)
            except (TypeError, ValueError) as exc:
                errors.append(
                    f"cannot hash source snapshot {source_id}: "
                    f"{_diagnostic_text(exc)}"
                )
            else:
                if declared_snapshot_hash != expected_snapshot_hash:
                    errors.append(f"source snapshot SHA-256 mismatch: {source_id}")
        artifacts = snapshot.get("artifacts")
        if not isinstance(artifacts, list):
            continue
        for artifact_index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                continue
            where = f"{source_id} artifact[{artifact_index}]"
            artifact_id = artifact.get("artifact_id")
            if isinstance(artifact_id, str):
                if artifact_id in artifact_ids:
                    errors.append(f"duplicate source artifact ID: {artifact_id}")
                else:
                    artifact_ids.add(artifact_id)
            if not _source_url_allowed(source_system, artifact.get("official_url")):
                errors.append(
                    f"source artifact host is not allowed for {source_system!r}: "
                    f"{where}"
                )
            dataset_ids = artifact.get("dataset_ids")
            if isinstance(dataset_ids, list):
                for dataset_id in dataset_ids:
                    if DATASET_REGISTRY.get(dataset_id) != source_system:
                        errors.append(
                            f"source artifact dataset is not in the v1 registry for "
                            f"{source_system!r}: {where}"
                        )
            try:
                artifact_retrieved_at = _parse_datetime(
                    artifact.get("retrieved_at"), "source artifact retrieved_at"
                )
            except ValueError as exc:
                errors.append(f"source artifact timestamp error for {where}: {exc}")
            else:
                if artifact_retrieved_at > generated_at:
                    errors.append(
                        f"source artifact retrieval is after generated_at: {where}"
                    )

            retained_path = artifact.get("retained_path")
            if retained_path is None:
                if manifest.get("status") == "APPROVED":
                    errors.append(
                        f"approved release source artifact lacks retained bytes: "
                        f"{artifact_id or where}"
                    )
                continue
            if not retained_path.startswith("source_artifacts/"):
                errors.append(
                    f"source artifact retained_path is outside source_artifacts/: "
                    f"{artifact_id or where}"
                )
            if PurePosixPath(retained_path).as_posix() != retained_path:
                errors.append(
                    f"source artifact retained_path is not canonical: "
                    f"{artifact_id or where}"
                )
            if retained_path in reserved_paths:
                errors.append(
                    f"source artifact retained_path aliases generated release data: "
                    f"{artifact_id or where}"
                )
            if retained_path in retained_paths:
                errors.append(
                    f"duplicate source artifact retained_path: {retained_path}"
                )
            else:
                retained_paths.add(retained_path)
            path, path_error = _safe_relative_file(base, retained_path)
            if path_error:
                errors.append(
                    path_error.replace("release path", "source artifact retained_path")
                )
                continue
            assert path is not None
            source_artifacts_path = base / "source_artifacts"
            try:
                source_artifacts_root = source_artifacts_path.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                errors.append(
                    f"cannot resolve source_artifacts/ for "
                    f"{artifact_id or where}: {_diagnostic_text(exc)}"
                )
                continue
            if source_artifacts_root != source_artifacts_path:
                errors.append(
                    f"source_artifacts/ itself resolves through a symlink: "
                    f"{artifact_id or where}"
                )
            if (
                path == source_artifacts_root
                or source_artifacts_root not in path.parents
            ):
                errors.append(
                    f"source artifact retained_path resolves outside "
                    f"source_artifacts/: {artifact_id or where}"
                )
            try:
                actual_sha, actual_size = _file_digest_and_size(path)
                expected_sha = _sha256_digest(
                    artifact.get("sha256"), "source artifact sha256"
                )
            except (OSError, ValueError) as exc:
                errors.append(
                    f"cannot verify retained source artifact {artifact_id or where}: "
                    f"{_diagnostic_text(exc)}"
                )
                continue
            if actual_sha != expected_sha:
                errors.append(
                    f"source artifact file SHA-256 mismatch: {artifact_id or where}"
                )
            else:
                retained_source_digests.add(actual_sha)
            if actual_sha in reserved_digests:
                errors.append(
                    f"source artifact bytes alias generated release data: "
                    f"{artifact_id or where}"
                )
            if actual_size != artifact.get("byte_size"):
                errors.append(
                    f"source artifact byte-size mismatch: {artifact_id or where}"
                )
    return snapshots, retained_source_digests


def _validate_baseline(
    base: Path, manifest: Mapping[str, Any], errors: list[str]
) -> Mapping[str, Any] | None:
    baseline = manifest.get("baseline")
    release_kind = manifest.get("release_kind")
    if release_kind == "TEST_FIXTURE":
        if baseline is not None:
            errors.append("TEST_FIXTURE release baseline must be null")
        return None
    if release_kind != "FULL_SNAPSHOT":
        return None
    if not isinstance(baseline, dict):
        errors.append("FULL_SNAPSHOT release requires a baseline object")
        return None

    relative = baseline.get("path")
    path, path_error = _safe_relative_file(base, relative)
    if path_error:
        errors.append(path_error.replace("release path", "baseline path"))
        return None
    assert path is not None
    try:
        actual_sha, _actual_size = _file_digest_and_size(path)
    except OSError as exc:
        errors.append(f"cannot verify baseline file {relative}: {exc}")
        return None
    if actual_sha != baseline.get("sha256"):
        errors.append(f"baseline file SHA-256 mismatch: {relative}")
    baseline_id = baseline.get("baseline_id")
    frozen = FROZEN_BASELINES.get(baseline_id)
    if frozen is None:
        errors.append(f"baseline ID is not registered as immutable: {baseline_id!r}")
    elif actual_sha != frozen["sha256"]:
        errors.append(f"baseline digest is not the registered immutable value: {relative}")
    try:
        baseline_document = _load_json_file(path)
    except (OSError, json.JSONDecodeError, StrictJsonError) as exc:
        errors.append(f"invalid baseline JSON {relative}: {exc}")
        return None
    if not isinstance(baseline_document, dict):
        errors.append(f"baseline JSON must be an object: {relative}")
        return None
    if baseline_document.get("baseline_id") != baseline.get("baseline_id"):
        errors.append(f"baseline ID does not match baseline file: {relative}")
    if baseline_document.get("contract_version") != manifest.get("contract_version"):
        errors.append(f"baseline contract version does not match release: {relative}")
    if baseline_document.get("release_id") != manifest.get("release_id"):
        errors.append(f"baseline release ID does not match release: {relative}")
    if baseline_document.get("as_of_date") != manifest.get("as_of_date"):
        errors.append(f"baseline as-of date does not match release: {relative}")
    if frozen is not None:
        if manifest.get("release_id") != frozen["release_id"]:
            errors.append(f"release ID does not match registered baseline: {relative}")
        if manifest.get("as_of_date") != frozen["as_of_date"]:
            errors.append(f"release date does not match registered baseline: {relative}")
    return baseline_document


def _validate_baseline_reconciliation(
    manifest: Mapping[str, Any],
    baseline: Mapping[str, Any] | None,
    source_snapshots: Mapping[str, Mapping[str, Any]],
    index: _Index,
    ledger_summary: Mapping[str, Any] | None,
    errors: list[str],
) -> None:
    if manifest.get("release_kind") != "FULL_SNAPSHOT" or baseline is None:
        return
    counts = baseline.get("counts")
    summary = manifest.get("summary")
    if not isinstance(counts, dict) or not isinstance(summary, dict):
        errors.append("baseline counts or manifest summary is not an object")
        return

    exact_summary_mapping = {
        "projects": "project_records",
        "participations": "participation_records",
        "review_candidates": "review_candidates",
        "excluded_matches": "excluded_matches",
    }
    for summary_key, baseline_key in exact_summary_mapping.items():
        if summary.get(summary_key) != counts.get(baseline_key):
            errors.append(
                f"baseline count mismatch: summary.{summary_key} != "
                f"counts.{baseline_key}"
            )

    scope_counts = baseline.get("scope_counts")
    if not isinstance(scope_counts, dict) or dict(index.scope_counts) != scope_counts:
        errors.append("emitted project scope counts do not match baseline")
    programme_counts = baseline.get("framework_programme_counts")
    if (
        not isinstance(programme_counts, dict)
        or dict(index.programme_counts) != programme_counts
    ):
        errors.append("emitted programme counts do not match baseline")
    primary_counts = baseline.get("primary_project_source_counts")
    if (
        not isinstance(primary_counts, dict)
        or dict(index.primary_project_source_counts) != primary_counts
    ):
        errors.append("emitted primary project source counts do not match baseline")
    if isinstance(scope_counts, dict):
        strict_count = scope_counts.get("BATTERY_CORE", 0) + scope_counts.get(
            "BATTERY_ECOSYSTEM", 0
        )
        if strict_count != counts.get("strict_core_and_ecosystem_projects"):
            errors.append("baseline strict project partition does not reconcile")
        if scope_counts.get("BATTERY_INTEGRATED") != counts.get(
            "integrated_projects"
        ):
            errors.append("baseline integrated project partition does not reconcile")

    linked_projects = {
        project_id
        for _relation_id, project_id, _result_id in index.project_results
        if project_id in index.projects
    }
    if len(linked_projects) != counts.get("projects_with_indexed_results"):
        errors.append("projects-with-results count does not match baseline")
    if len(index.projects - linked_projects) != counts.get(
        "projects_without_indexed_results"
    ):
        errors.append("projects-without-results count does not match baseline")

    seeds = baseline.get("seed_projects")
    if isinstance(seeds, list):
        for seed in seeds:
            if not isinstance(seed, dict):
                errors.append("baseline seed project is malformed")
                continue
            project_id = seed.get("project_id")
            data = index.project_data.get(project_id)
            if data is None or data.get("acronym") != seed.get("acronym"):
                errors.append(f"baseline seed project is missing or changed: {project_id}")

    observation = manifest.get("source_observation_summary")
    observed_fields = (
        "source_row_access_counts",
        "source_row_result_relevance_counts",
        "source_row_result_type_counts",
        "primary_project_source_counts",
        "seed_project_result_rows",
    )
    if not isinstance(observation, dict):
        errors.append("FULL_SNAPSHOT lacks source observation summary")
    else:
        if observation.get("source_result_rows") != counts.get("source_result_rows"):
            errors.append("source result row count does not match baseline")
        for field_name in observed_fields:
            if observation.get(field_name) != baseline.get(field_name):
                errors.append(
                    f"source observation partition does not match baseline: {field_name}"
                )
        for field_name in (
            "source_row_access_counts",
            "source_row_result_relevance_counts",
            "source_row_result_type_counts",
        ):
            partition = observation.get(field_name)
            if isinstance(partition, dict) and sum(partition.values()) != observation.get(
                "source_result_rows"
            ):
                errors.append(f"source observation partition does not sum: {field_name}")

        if ledger_summary is None:
            errors.append("source observation summary has no verified ledger")
        else:
            for field_name in (
                "source_result_rows",
                "source_row_access_counts",
                "source_row_result_relevance_counts",
                "source_row_result_type_counts",
            ):
                if observation.get(field_name) != ledger_summary.get(field_name):
                    errors.append(
                        f"source observation summary is not derived from ledger: "
                        f"{field_name}"
                    )
            seed_counts: dict[str, int] = {}
            project_counts = ledger_summary.get("project_counts")
            if isinstance(project_counts, dict) and isinstance(seeds, list):
                for seed in seeds:
                    if isinstance(seed, dict) and isinstance(seed.get("acronym"), str):
                        seed_counts[seed["acronym"]] = project_counts.get(
                            seed.get("project_id"), 0
                        )
            if observation.get("seed_project_result_rows") != seed_counts:
                errors.append(
                    "seed project source-result counts are not derived from ledger"
                )
            if observation.get("primary_project_source_counts") != dict(
                index.primary_project_source_counts
            ):
                errors.append(
                    "primary project source summary is not derived from projects"
                )

    coverage = baseline.get("coverage_assertions")
    if isinstance(coverage, dict):
        for assertion in coverage.values():
            if not isinstance(assertion, dict):
                continue
            exception = assertion.get("documented_exception")
            if isinstance(exception, str) and exception not in index.exclusions:
                errors.append(f"baseline coverage exception is not excluded: {exception}")

    if manifest.get("status") == "APPROVED":
        canonical_counts = baseline.get("canonical_counts")
        if not isinstance(canonical_counts, dict):
            errors.append(
                "baseline canonical result/link counts are not frozen; "
                "FULL_SNAPSHOT cannot be APPROVED"
            )
        else:
            for summary_key, baseline_key in (
                ("results", "result_records"),
                ("project_result_links", "project_result_links"),
            ):
                if summary.get(summary_key) != canonical_counts.get(baseline_key):
                    errors.append(
                        f"canonical baseline count mismatch: {summary_key}"
                    )

        artifacts_by_id: dict[str, Mapping[str, Any]] = {}
        for snapshot in source_snapshots.values():
            artifacts = snapshot.get("artifacts")
            if not isinstance(artifacts, list):
                continue
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                artifact_id = artifact.get("artifact_id")
                if isinstance(artifact_id, str):
                    artifacts_by_id[artifact_id] = artifact
        input_digests = baseline.get("input_snapshot_sha256")
        input_datasets = baseline.get("input_snapshot_dataset_ids")
        baseline_artifacts: dict[str, str] = {}
        if not isinstance(input_digests, dict) or not isinstance(input_datasets, dict):
            errors.append("baseline input snapshot digest/dataset registry is missing")
        else:
            for filename, digest in input_digests.items():
                expected_dataset = input_datasets.get(filename)
                matches: list[str] = []
                for artifact_id, artifact in artifacts_by_id.items():
                    try:
                        artifact_digest = _sha256_digest(
                            artifact.get("sha256"), "artifact sha256"
                        )
                    except ValueError:
                        continue
                    if (
                        artifact_digest == digest
                        and expected_dataset in artifact.get("dataset_ids", [])
                    ):
                        matches.append(artifact_id)
                if len(matches) != 1:
                    errors.append(
                        f"approved release does not bind exactly one baseline input: "
                        f"{filename}"
                    )
                else:
                    baseline_artifacts[filename] = matches[0]

        if ledger_summary is not None and ledger_summary.get(
            "input_artifact_id"
        ) != baseline_artifacts.get("final_public_results.json"):
            errors.append(
                "source observation ledger is not bound to final_public_results.json"
            )

        baseline_artifact_ids = set(baseline_artifacts.values())
        required_record_types = {
            "PROJECT",
            "RESULT",
            "PROJECT_RESULT",
            "PARTICIPATION",
            "REVIEW_CANDIDATE",
            "EXCLUDED_MATCH",
        }
        for record_id in sorted(index.record_artifact_refs):
            record_type = next(
                (
                    kind
                    for kind, prefix in (
                        ("PROJECT", "research_project/"),
                        ("RESULT", "research_result/"),
                        ("PROJECT_RESULT", "project_result/"),
                        ("PARTICIPATION", "project_participation/"),
                        ("REVIEW_CANDIDATE", "research_review/"),
                        ("EXCLUDED_MATCH", "research_exclusion/"),
                    )
                    if record_id.startswith(prefix)
                ),
                None,
            )
            if record_type in required_record_types and not (
                index.record_artifact_refs[record_id] & baseline_artifact_ids
            ):
                errors.append(
                    f"approved record is not linked to a frozen baseline input: "
                    f"{record_id}"
                )
        for result_id, artifact_ids in index.result_identity_artifact_refs.items():
            if not artifact_ids & baseline_artifact_ids:
                errors.append(
                    f"SOURCE_RECORD identity is not bound to a frozen input: "
                    f"{result_id}"
                )

        referenced_baseline_artifacts = set().union(
            *index.record_artifact_refs.values()
        ) if index.record_artifact_refs else set()
        if ledger_summary is not None:
            ledger_refs = ledger_summary.get("referenced_artifact_ids")
            if isinstance(ledger_refs, set):
                referenced_baseline_artifacts.update(ledger_refs)
            input_artifact_id = ledger_summary.get("input_artifact_id")
            if isinstance(input_artifact_id, str):
                referenced_baseline_artifacts.add(input_artifact_id)
        for filename, artifact_id in baseline_artifacts.items():
            if artifact_id not in referenced_baseline_artifacts:
                errors.append(
                    f"frozen baseline input is unused by records or ledger: {filename}"
                )


def _validate_gates_and_approval(
    manifest: Mapping[str, Any],
    source_snapshots: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    gates = manifest.get("quality_gates")
    gate_map: dict[str, Mapping[str, Any]] = {}
    if isinstance(gates, list):
        for gate in gates:
            if not isinstance(gate, dict) or not isinstance(gate.get("gate"), str):
                continue
            gate_name = gate["gate"]
            if gate_name in gate_map:
                errors.append(f"duplicate quality gate: {gate_name}")
            else:
                gate_map[gate_name] = gate

    if manifest.get("status") != "APPROVED":
        return
    record_sets = manifest.get("record_sets")
    present_record_types = {
        record_set.get("record_type")
        for record_set in record_sets
        if isinstance(record_set, dict)
    } if isinstance(record_sets, list) else set()
    missing_record_types = APPROVED_RECORD_SETS - present_record_types
    if missing_record_types:
        errors.append(
            "approved release is missing record sets: "
            + ", ".join(sorted(missing_record_types))
        )
    missing = APPROVED_GATES - set(gate_map)
    extra = set(gate_map) - APPROVED_GATES
    if missing:
        errors.append("approved release is missing gates: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("approved release has unknown gates: " + ", ".join(sorted(extra)))
    for gate_name in sorted(APPROVED_GATES & set(gate_map)):
        if gate_map[gate_name].get("status") != "PASSED":
            errors.append(f"approved release has an unpassed gate: {gate_name}")
    for source_id, snapshot in source_snapshots.items():
        try:
            _sha256_digest(snapshot.get("snapshot_sha256"), "snapshot_sha256")
        except ValueError:
            errors.append(f"approved release source lacks a hash: {source_id}")
        artifacts = snapshot.get("artifacts")
        if not isinstance(artifacts, list):
            continue
        for artifact_index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                continue
            try:
                _sha256_digest(artifact.get("sha256"), "artifact sha256")
            except ValueError:
                artifact_id = artifact.get("artifact_id", artifact_index)
                errors.append(
                    f"approved release source artifact lacks a hash: {artifact_id}"
                )
            if not isinstance(artifact.get("byte_size"), int) or isinstance(
                artifact.get("byte_size"), bool
            ):
                artifact_id = artifact.get("artifact_id", artifact_index)
                errors.append(
                    f"approved release source artifact lacks a byte size: "
                    f"{artifact_id}"
                )


def _validate_snapshot(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    if not manifest_path.is_file():
        return [f"manifest does not exist or is not a file: {manifest_path}"]

    try:
        manifest = _load_json_file(manifest_path)
    except (OSError, json.JSONDecodeError, StrictJsonError) as exc:
        return [f"invalid manifest JSON: {exc}"]
    if not isinstance(manifest, dict):
        return ["manifest schema: manifest must be an object"]

    try:
        release_schema = _load_json_file(RELEASE_SCHEMA_PATH)
        record_schema = _load_json_file(RECORD_SCHEMA_PATH)
        observation_schema = _load_json_file(OBSERVATION_SCHEMA_PATH)
        record_schema_sha256, _schema_size = _file_digest_and_size(RECORD_SCHEMA_PATH)
        observation_schema_sha256, _observation_schema_size = _file_digest_and_size(
            OBSERVATION_SCHEMA_PATH
        )
        Draft202012Validator.check_schema(release_schema)
        Draft202012Validator.check_schema(record_schema)
        Draft202012Validator.check_schema(observation_schema)
    except (OSError, json.JSONDecodeError, StrictJsonError, SchemaError) as exc:
        return [f"validator schema error: {exc}"]

    format_checker = FormatChecker()
    manifest_validator = Draft202012Validator(
        release_schema, format_checker=format_checker
    )
    manifest_errors = sorted(
        manifest_validator.iter_errors(manifest),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if manifest_errors:
        return [_schema_error("manifest schema", error) for error in manifest_errors]

    for value_path, value in _walk_strings(manifest):
        if _looks_secret(value) or _looks_personal_contact(value):
            errors.append(
                "credential or personal contact leaked into manifest at /"
                + "/".join(value_path)
            )
            break

    base = manifest_path.parent.resolve()
    as_of, generated_at = _validate_release_dates(manifest, errors)
    baseline_document = _validate_baseline(base, manifest, errors)
    source_snapshots, retained_source_digests = _validate_sources(
        base, manifest, generated_at, errors
    )
    _validate_gates_and_approval(manifest, source_snapshots, errors)

    record_validator = Draft202012Validator(
        record_schema, format_checker=format_checker
    )
    index = _Index()
    seen_ids: set[str] = set()
    seen_claim_ids: set[str] = set()
    seen_paths: set[str] = set()
    record_sets = manifest.get("record_sets")
    assert isinstance(record_sets, list)  # established by the release schema
    for record_set in record_sets:
        assert isinstance(record_set, dict)
        _validate_record_set(
            base,
            record_set,
            manifest,
            record_validator,
            source_snapshots,
            as_of,
            generated_at,
            index,
            seen_ids,
            seen_claim_ids,
            seen_paths,
            record_schema.get("$id"),
            record_schema_sha256,
            errors,
        )

    _validate_cross_references(
        base, index, source_snapshots, retained_source_digests, errors
    )
    observation_validator = Draft202012Validator(
        observation_schema, format_checker=format_checker
    )
    ledger_summary = _validate_source_observation_ledger(
        base,
        manifest,
        observation_validator,
        source_snapshots,
        index,
        observation_schema.get("$id"),
        observation_schema_sha256,
        errors,
    )
    summary = manifest.get("summary")
    assert isinstance(summary, dict)
    for record_type, summary_key in SUMMARY_KEYS.items():
        if summary.get(summary_key) != index.counts[record_type]:
            errors.append(f"summary count mismatch: {summary_key}")
    _validate_baseline_reconciliation(
        manifest,
        baseline_document,
        source_snapshots,
        index,
        ledger_summary,
        errors,
    )
    return errors


def validate_snapshot(path: str | Path) -> list[str]:
    """Validate ``path`` and return deterministic, user-facing errors.

    The broad final exception guard is intentional.  Input must never turn a
    release gate into a traceback and an accidental success; unexpected
    validator failures are reported as fatal errors instead.
    """

    try:
        return _validate_snapshot(Path(path))
    except Exception as exc:  # pragma: no cover - defensive fail-closed boundary
        return [
            f"validator failed closed: {type(exc).__name__}: "
            f"{_diagnostic_text(exc)}"
        ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate EU battery-research release manifests and files."
    )
    parser.add_argument("manifest", nargs="+", help="release manifest.json path")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit one JSON result object per manifest",
    )
    args = parser.parse_args(argv)

    failed = False
    for raw_path in args.manifest:
        errors = validate_snapshot(raw_path)
        failed = failed or bool(errors)
        if args.json:
            print(
                json.dumps(
                    {"manifest": raw_path, "valid": not errors, "errors": errors},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        elif errors:
            print(f"FAIL {raw_path}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"ok   {raw_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
