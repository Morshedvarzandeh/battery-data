#!/usr/bin/env python3
"""Find duplicate product records across accepted and review data.

The product name alone is deliberately not enough to declare a duplicate.
Battery catalogues use punctuation to distinguish some terminal, tab, or other
hardware variants.  Conversely, punctuation also drifts between PDFs, web
pages, and distributor listings.  This checker therefore collects identity
signals and compares the identifying specifications before classifying a pair:

* ``exact_duplicate``: the same product UID occurs in more than one file.
* ``probable_duplicate``: manufacturer/model, alias, or source/model identity
  agrees and the shared identifying specifications do not conflict.
* ``identity_collision``: the normalized identity agrees, but an identifying
  specification conflicts (or there is not enough evidence to merge safely).

By default, exact and probable duplicates make the command fail.  Review-only
collisions are printed but do not fail, so legitimate punctuation/connector
variants can remain separate while still receiving human attention.

Examples::

    python tools/check_duplicates.py
    python tools/check_duplicates.py --format json --fail-on review
    python tools/check_duplicates.py contrib/cells review/candidates
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = (ROOT / "contrib/cells", ROOT / "review/candidates")

# Only legal/corporate suffixes belong here.  Productive words such as
# "Energy", "Battery", and "SDI" are intentionally retained.
CORPORATE_SUFFIXES = {
    "ag",
    "bv",
    "co",
    "company",
    "corp",
    "corporation",
    "gmbh",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "nv",
    "plc",
    "sa",
}

# Curated manufacturer-name aliases used only when two labels are known to
# represent the same catalogue identity. Keep this deliberately narrow: broad
# brand/group collapsing would create false positives across distinct makers.
MANUFACTURER_ALIASES = {
    "panasonicenergy": "panasonic",
}

# Specifications useful for deciding whether two normalized names actually
# describe the same physical product.  Tolerances absorb ordinary rounding,
# not distinct capacity grades or package variants.
SPEC_TOLERANCES: Mapping[str, float] = {
    "capacity": 0.05,
    "nominal_voltage": 0.02,
    "nominal_energy": 0.05,
    "energy": 0.05,
    "mass": 0.05,
    "diameter": 0.01,
    "height": 0.01,
}

UNIT_CONVERSIONS: Mapping[str, Mapping[str, tuple[float, str]]] = {
    "capacity": {
        "ah": (1.0, "Ah"),
        "mah": (0.001, "Ah"),
    },
    "nominal_voltage": {
        "v": (1.0, "V"),
        "mv": (0.001, "V"),
    },
    "nominal_energy": {
        "wh": (1.0, "Wh"),
        "kwh": (1000.0, "Wh"),
    },
    "energy": {
        "wh": (1.0, "Wh"),
        "kwh": (1000.0, "Wh"),
    },
    "mass": {
        "kg": (1.0, "kg"),
        "g": (0.001, "kg"),
        "mg": (0.000001, "kg"),
    },
    "diameter": {
        "m": (1000.0, "mm"),
        "cm": (10.0, "mm"),
        "mm": (1.0, "mm"),
    },
    "height": {
        "m": (1000.0, "mm"),
        "cm": (10.0, "mm"),
        "mm": (1.0, "mm"),
    },
    "length": {
        "m": (1000.0, "mm"),
        "cm": (10.0, "mm"),
        "mm": (1.0, "mm"),
    },
    "width": {
        "m": (1000.0, "mm"),
        "cm": (10.0, "mm"),
        "mm": (1.0, "mm"),
    },
}


class InputError(ValueError):
    """An input record could not be read as a contribution document."""


@dataclass(frozen=True)
class SpecValue:
    value: float
    unit: str


@dataclass(frozen=True)
class Record:
    path: str
    uid: str
    kind: str
    manufacturer: str
    model: str
    aliases: tuple[str, ...]
    source_keys: frozenset[str]
    specs: Mapping[str, tuple[SpecValue, ...]]
    box_dimensions_mm: tuple[float, ...] | None
    form_factor: str = ""
    rechargeable: bool | None = None

    @property
    def manufacturer_key(self) -> str:
        return normalize_manufacturer(self.manufacturer)

    @property
    def model_key(self) -> str:
        return compact_identifier(self.model)


@dataclass(frozen=True)
class SpecComparison:
    agreements: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    classification: str
    signals: tuple[str, ...]
    left: Record
    right: Record
    agreements: tuple[str, ...]
    conflicts: tuple[str, ...]
    rationale: str

    @property
    def rank(self) -> int:
        return {"exact_duplicate": 0, "probable_duplicate": 1}.get(
            self.classification, 2
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "signals": list(self.signals),
            "left": record_summary(self.left),
            "right": record_summary(self.right),
            "specification_agreements": list(self.agreements),
            "specification_conflicts": list(self.conflicts),
            "rationale": self.rationale,
        }


def _fold(value: str) -> str:
    """Unicode/case normalization with combining marks removed."""

    decomposed = unicodedata.normalize("NFKD", str(value)).casefold()
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def identifier_words(value: str) -> tuple[str, ...]:
    """Return Unicode alphanumeric runs without discarding variant suffixes."""

    return tuple(re.findall(r"[^\W_]+", _fold(value), flags=re.UNICODE))


def compact_identifier(value: str) -> str:
    """Normalize case and punctuation while preserving every alphanumeric."""

    return "".join(identifier_words(value))


def normalize_manufacturer(value: str) -> str:
    words = list(identifier_words(value))
    while words and words[-1] in CORPORATE_SUFFIXES:
        words.pop()
    normalized = "".join(words)
    return MANUFACTURER_ALIASES.get(normalized, normalized)


def literal_identifier(value: str) -> str:
    """Case/space normalization that deliberately preserves punctuation."""

    return " ".join(_fold(value).split())


def normalize_url(value: str) -> str:
    if not value:
        return ""
    try:
        split = urlsplit(value.strip())
    except ValueError:
        return value.strip().casefold()
    host = (split.hostname or "").casefold()
    port = split.port
    if port and not ((split.scheme == "http" and port == 80) or (split.scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", split.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, val)
            for key, val in parse_qsl(split.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
        )
    )
    # http/https drift is common for a single manufacturer document.  The
    # authority, path, and non-tracking query identify it more reliably.
    return urlunsplit(("", host, path, query, ""))


def source_keys(source: Mapping[str, Any]) -> frozenset[str]:
    keys: set[str] = set()
    if source.get("sha256"):
        keys.add(f"sha256:{str(source['sha256']).casefold()}")
    if source.get("doi"):
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(source["doi"]), flags=re.I)
        keys.add(f"doi:{doi.strip().casefold()}")
    if source.get("uid"):
        keys.add(f"uid:{compact_identifier(str(source['uid']))}")
    if source.get("url"):
        keys.add(f"url:{normalize_url(str(source['url']))}")
    return frozenset(key for key in keys if not key.endswith(":") and not key.endswith(":/"))


def _normalized_unit(unit: Any) -> str:
    return re.sub(r"[\s._-]+", "", str(unit or "")).casefold()


def _spec_value(quantity: str, value: Any, unit: Any) -> SpecValue | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    normalized_unit = _normalized_unit(unit)
    conversion = UNIT_CONVERSIONS.get(quantity, {}).get(normalized_unit)
    if conversion:
        scale, canonical_unit = conversion
        return SpecValue(number * scale, canonical_unit)
    if not normalized_unit:
        return None
    return SpecValue(number, normalized_unit)


def extract_specs(doc: Mapping[str, Any]) -> tuple[dict[str, tuple[SpecValue, ...]], tuple[float, ...] | None]:
    collected: dict[str, list[SpecValue]] = defaultdict(list)
    for observation in doc.get("observations") or []:
        if not isinstance(observation, Mapping):
            continue
        quantity = str(observation.get("quantity") or "")
        if quantity not in SPEC_TOLERANCES and quantity not in {"length", "width"}:
            continue
        value = _spec_value(quantity, observation.get("value"), observation.get("unit"))
        if value is not None and value not in collected[quantity]:
            collected[quantity].append(value)

    dimensions: list[float] = []
    for quantity in ("length", "width", "height"):
        values = collected.get(quantity, [])
        mm_values = [item.value for item in values if item.unit == "mm"]
        if len(mm_values) == 1:
            dimensions.append(mm_values[0])
    # Sorting avoids a false conflict when two datasheets reverse their
    # published length/width/height order.
    box_dimensions = tuple(sorted(dimensions)) if len(dimensions) >= 2 else None
    return ({key: tuple(values) for key, values in collected.items()}, box_dimensions)


def _load_yaml(text: str, path: Path) -> Mapping[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only in minimal installs
        raise InputError(f"{path}: non-JSON YAML needs PyYAML (pip install pyyaml)") from exc
    try:
        doc = yaml.safe_load(text)
    except Exception as exc:
        raise InputError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(doc, Mapping):
        raise InputError(f"{path}: document root must be an object")
    return doc


def load_record(path: Path, root: Path = ROOT) -> Record:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"{path}: cannot read: {exc}") from exc
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = _load_yaml(text, path)
    if not isinstance(doc, Mapping):
        raise InputError(f"{path}: document root must be an object")
    product = doc.get("product")
    source = doc.get("source")
    if not isinstance(product, Mapping) or not isinstance(source, Mapping):
        raise InputError(f"{path}: product and source objects are required")
    required = ("uid", "manufacturer", "model_number")
    missing = [key for key in required if not str(product.get(key) or "").strip()]
    if missing:
        raise InputError(f"{path}: product missing {', '.join(missing)}")
    aliases = product.get("aliases") or []
    if not isinstance(aliases, Sequence) or isinstance(aliases, (str, bytes)):
        raise InputError(f"{path}: product.aliases must be an array")
    specs, dimensions = extract_specs(doc)
    try:
        display_path = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        display_path = str(path)
    return Record(
        path=display_path,
        uid=str(product["uid"]).strip(),
        kind=str(product.get("kind") or ""),
        manufacturer=str(product["manufacturer"]).strip(),
        model=str(product["model_number"]).strip(),
        aliases=tuple(str(alias).strip() for alias in aliases if str(alias).strip()),
        source_keys=source_keys(source),
        specs=specs,
        box_dimensions_mm=dimensions,
        form_factor=str(product.get("form_factor") or ""),
        rechargeable=(product.get("is_rechargeable")
                      if isinstance(product.get("is_rechargeable"), bool)
                      else None),
    )


def collect_files(paths: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix.casefold() in {".yaml", ".yml"}:
            files.add(path.resolve())
        elif path.is_dir():
            for pattern in ("**/*.yaml", "**/*.yml"):
                files.update(candidate.resolve() for candidate in path.glob(pattern) if candidate.is_file())
        else:
            raise InputError(f"{path}: no YAML file or directory found")
    return sorted(files)


def load_records(paths: Iterable[Path], root: Path = ROOT) -> list[Record]:
    return [load_record(path, root=root) for path in collect_files(paths)]


def _pairs(indices: Iterable[int]) -> Iterator[tuple[int, int]]:
    ordered = sorted(set(indices))
    for offset, left in enumerate(ordered):
        for right in ordered[offset + 1 :]:
            yield left, right


def _add_group_signals(
    groups: Mapping[Any, Iterable[int]], signal: str, pair_signals: dict[tuple[int, int], set[str]]
) -> None:
    for indices in groups.values():
        for pair in _pairs(indices):
            pair_signals[pair].add(signal)


def _close(left: float, right: float, tolerance: float) -> bool:
    scale = max(abs(left), abs(right), 1e-12)
    return abs(left - right) <= tolerance * scale


def _format_values(values: Sequence[SpecValue]) -> str:
    return "/".join(f"{item.value:g} {item.unit}" for item in values)


def compare_specs(left: Record, right: Record) -> SpecComparison:
    agreements: list[str] = []
    conflicts: list[str] = []
    for label, left_value, right_value in (
        ("kind", left.kind, right.kind),
        ("form_factor", left.form_factor, right.form_factor),
    ):
        if left_value and right_value and left_value != right_value:
            conflicts.append(f"{label}: {left_value} vs {right_value}")
    if (left.rechargeable is not None and right.rechargeable is not None
            and left.rechargeable != right.rechargeable):
        conflicts.append(
            f"is_rechargeable: {left.rechargeable} vs {right.rechargeable}"
        )
    for quantity, tolerance in SPEC_TOLERANCES.items():
        left_values = left.specs.get(quantity, ())
        right_values = right.specs.get(quantity, ())
        if not left_values or not right_values:
            continue
        comparable = [
            (a, b)
            for a in left_values
            for b in right_values
            if a.unit == b.unit
        ]
        if not comparable:
            continue
        label = f"{quantity}: {_format_values(left_values)} vs {_format_values(right_values)}"
        if any(_close(a.value, b.value, tolerance) for a, b in comparable):
            agreements.append(label)
        else:
            conflicts.append(label)

    if left.box_dimensions_mm and right.box_dimensions_mm:
        if len(left.box_dimensions_mm) == len(right.box_dimensions_mm):
            label = (
                "box_dimensions: "
                f"{'x'.join(f'{v:g}' for v in left.box_dimensions_mm)} mm vs "
                f"{'x'.join(f'{v:g}' for v in right.box_dimensions_mm)} mm"
            )
            if all(
                _close(a, b, 0.01)
                for a, b in zip(left.box_dimensions_mm, right.box_dimensions_mm)
            ):
                agreements.append(label)
            else:
                conflicts.append(label)
    return SpecComparison(tuple(agreements), tuple(conflicts))


def _same_source(left: Record, right: Record) -> bool:
    return bool(left.source_keys & right.source_keys)


def _manufacturer_names_related(left: Record, right: Record) -> bool:
    """Conservatively recognize a short/long spelling of one manufacturer."""

    first, second = left.manufacturer_key, right.manufacturer_key
    if not first or not second:
        return False
    if first == second:
        return True
    return min(len(first), len(second)) >= 3 and (
        first.startswith(second) or second.startswith(first)
    )


def classify_pair(left: Record, right: Record, signals: Iterable[str]) -> Finding:
    ordered_signals = tuple(sorted(set(signals)))
    comparison = compare_specs(left, right)

    if "exact_uid" in ordered_signals:
        classification = "exact_duplicate"
        rationale = "The exact product UID occurs in both files; one identity must not be defined twice."
    elif comparison.conflicts:
        classification = "identity_collision"
        rationale = (
            "The names collapse to the same identity, but identifying specifications conflict. "
            "Keep separate pending review; punctuation may encode an official variant."
        )
    else:
        normalized_identity = "normalized_manufacturer_model" in ordered_signals
        same_source_model = "same_source_model" in ordered_signals
        alias_model_match = "alias_model_match" in ordered_signals
        literal_model_match = literal_identifier(left.model) == literal_identifier(right.model)
        identity_signal = normalized_identity or alias_model_match
        enough_support = (
            identity_signal
            and (bool(comparison.agreements) or same_source_model or literal_model_match)
        ) or (
            same_source_model
            and _manufacturer_names_related(left, right)
            and (bool(comparison.agreements) or literal_model_match)
        )

        if enough_support:
            classification = "probable_duplicate"
            rationale = (
                "Identity signals agree and no identifying specification conflicts; merge or "
                "retain one canonical product record after review."
            )
        else:
            classification = "identity_collision"
            rationale = (
                "A normalized or alias identity collides, but there is not enough shared "
                "specification evidence to merge automatically."
            )

    return Finding(
        classification=classification,
        signals=ordered_signals,
        left=left,
        right=right,
        agreements=comparison.agreements,
        conflicts=comparison.conflicts,
        rationale=rationale,
    )


def find_duplicates(records: Sequence[Record]) -> list[Finding]:
    pair_signals: dict[tuple[int, int], set[str]] = defaultdict(set)

    by_uid: dict[str, list[int]] = defaultdict(list)
    by_identity: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_source_model: dict[tuple[str, str], list[int]] = defaultdict(list)
    alias_index: dict[tuple[str, str], dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))

    for index, record in enumerate(records):
        by_uid[record.uid].append(index)
        if record.manufacturer_key and record.model_key:
            by_identity[(record.manufacturer_key, record.model_key)].append(index)
            alias_index[(record.manufacturer_key, record.model_key)][index].add("model")
        for alias in record.aliases:
            alias_key = compact_identifier(alias)
            if alias_key:
                alias_index[(record.manufacturer_key, alias_key)][index].add("alias")
        for source_key in record.source_keys:
            if record.model_key:
                by_source_model[(source_key, record.model_key)].append(index)

    _add_group_signals(by_uid, "exact_uid", pair_signals)
    _add_group_signals(by_identity, "normalized_manufacturer_model", pair_signals)
    _add_group_signals(by_source_model, "same_source_model", pair_signals)

    for indexed in alias_index.values():
        if len(indexed) < 2 or not any("alias" in roles for roles in indexed.values()):
            continue
        for pair in _pairs(indexed):
            pair_signals[pair].add("alias_model_match")

    findings = [
        classify_pair(records[left], records[right], signals)
        for (left, right), signals in pair_signals.items()
    ]
    return sorted(
        findings,
        key=lambda item: (item.rank, item.left.path, item.right.path, item.signals),
    )


def record_summary(record: Record) -> dict[str, str]:
    return {
        "path": record.path,
        "uid": record.uid,
        "manufacturer": record.manufacturer,
        "model_number": record.model,
    }


def print_text(records: Sequence[Record], findings: Sequence[Finding]) -> None:
    print(f"{len(records)} product record(s) scanned")
    for finding in findings:
        label = {
            "exact_duplicate": "BLOCK exact duplicate",
            "probable_duplicate": "BLOCK probable duplicate",
            "identity_collision": "REVIEW identity collision",
        }[finding.classification]
        print(f"\n{label}")
        print(
            f"  {finding.left.path}: {finding.left.manufacturer} {finding.left.model} "
            f"[{finding.left.uid}]"
        )
        print(
            f"  {finding.right.path}: {finding.right.manufacturer} {finding.right.model} "
            f"[{finding.right.uid}]"
        )
        print(f"  signals: {', '.join(finding.signals)}")
        for conflict in finding.conflicts:
            print(f"  conflicts: {conflict}")
        for agreement in finding.agreements:
            print(f"  agrees: {agreement}")
        print(f"  {finding.rationale}")

    counts = {
        name: sum(item.classification == name for item in findings)
        for name in ("exact_duplicate", "probable_duplicate", "identity_collision")
    }
    print(
        "\n"
        f"{counts['exact_duplicate']} exact duplicate(s), "
        f"{counts['probable_duplicate']} probable duplicate(s), "
        f"{counts['identity_collision']} review collision(s)"
    )


def should_fail(findings: Sequence[Finding], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    if fail_on == "exact":
        return any(item.classification == "exact_duplicate" for item in findings)
    if fail_on == "duplicate":
        return any(item.classification in {"exact_duplicate", "probable_duplicate"} for item in findings)
    return bool(findings)  # review: every finding requires a clean result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="YAML files/directories (default: contrib/cells and review/candidates)",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--fail-on",
        choices=("exact", "duplicate", "review", "never"),
        default="duplicate",
        help="minimum finding class that exits non-zero (default: duplicate)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = args.paths or list(DEFAULT_PATHS)
    try:
        records = load_records(paths)
    except InputError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    findings = find_duplicates(records)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "records_scanned": len(records),
                    "findings": [finding.as_dict() for finding in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print_text(records, findings)
    return 1 if should_fail(findings, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
