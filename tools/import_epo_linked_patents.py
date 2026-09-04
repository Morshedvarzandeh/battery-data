#!/usr/bin/env python3
"""Build a deterministic patent/company review batch from EPO Linked Open EP Data.

The input files are immutable SPARQL result snapshots.  This importer never
calls the network, never claims DOCDB-family resolution and never promotes a
record.  It deduplicates publication numbers across query shards and against
all previously checked-in patent publication candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.1.0"
COMPANY_SCHEMA_VERSION = "1.0.0"
SNAPSHOT_DATE = "2026-09-04"
SOURCE_ENDPOINT = "https://data.epo.org/linked-data/query"
SOURCE_LANDING = "https://data.epo.org/linked-data/"
SOURCE_LICENSE = "CC-BY-4.0"

SOURCE_SPECS = {
    "g01r31-367.json": {
        "seed_ipc": "G01R31-367",
        "seed_categories": ["software_control", "electronics_hardware"],
        "purpose": "battery diagnostics, SOC/SOH estimation and computer-implemented monitoring",
    },
    "h01m10-0525.json": {
        "seed_ipc": "H01M10-0525",
        "seed_categories": ["electrochemistry_materials"],
        "purpose": "rechargeable lithium-ion cells and materials",
    },
    "h01m10-44.json": {
        "seed_ipc": "H01M10-44",
        "seed_categories": ["electrical_power"],
        "purpose": "battery charge/discharge control and electrical management",
    },
    "h01m10-48.json": {
        "seed_ipc": "H01M10-48",
        "seed_categories": ["electronics_hardware"],
        "purpose": "battery monitoring, sensing and test hardware",
    },
    "h01m10-613.json": {
        "seed_ipc": "H01M10-613",
        "seed_categories": ["thermal_safety"],
        "purpose": "battery thermal management",
    },
    "h01m50-20.json": {
        "seed_ipc": "H01M50-20",
        "seed_categories": ["mechanical_structures"],
        "purpose": "battery modules, packs, housings and structural arrangements",
    },
}

COMPANY_WORDS = {
    "ag", "aktiengesellschaft", "as", "bv", "company", "co", "corp", "corporation",
    "gmbh", "group", "inc", "incorporated", "kabushiki", "kaisha", "kgaa", "limited",
    "llc", "ltd", "nv", "oy", "plc", "pte", "sa", "sas", "se", "spa", "srl",
    "technology", "technologies", "industries", "industrial", "holdings",
}
RESEARCH_WORDS = {
    "academy", "centre", "center", "college", "ecole", "institute", "institut",
    "laboratory", "laboratories", "research", "universidad", "universita", "universite",
    "university", "schule", "hochschule",
}
GOVERNMENT_WORDS = {"agency", "authority", "commission", "government", "ministry"}

VALUE_CHAIN_RULES = {
    "cell_battery_manufacturer": [
        "battery", "batteries", "accumulator", "catl", "sdi", "saft", "sanyo",
        "yuasa", "varta", "energy solution", "sk on", "svolt", "eve power",
    ],
    "materials_supplier": [
        "chemical", "chemicals", "chemie", "material", "materials", "mining", "metal",
        "umicore", "basf", "evonik", "nexeon", "electrolyte", "separator", "graphite",
    ],
    "automotive_oem": [
        "automobile", "automotive", "motor", "motors", "toyota", "nissan", "tesla",
        "volkswagen", "bmw", "daimler", "mercedes", "hyundai", "kia", "honda", "renault",
    ],
    "electronics_power_systems": [
        "electric", "electronics", "semiconductor", "bosch", "huawei", "siemens",
        "power systems", "automation", "controls", "instrument",
    ],
    "energy_storage_integrator": ["energy storage", "storage systems", "grid storage"],
    "charging_grid": ["charging", "charger", "electric power", "utility", "grid"],
    "recycling_circularity": ["recycling", "recycle", "circular", "recovery"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: object, length: int = 12) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", normalized_text(value)).strip("-")
    return result[:70] or "unnamed"


def binding_value(binding: dict, key: str, default: str = "") -> str:
    return str((binding.get(key) or {}).get("value") or default).strip()


def kind_code(binding: dict) -> str:
    return binding_value(binding, "kind").rsplit("_", 1)[-1]


def publication_number(binding: dict) -> str:
    return f"EP{binding_value(binding, 'number')}{kind_code(binding)}"


def ipc_code(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def application_id(uri: str) -> str:
    marker = "/application/"
    return uri.split(marker, 1)[-1].strip("/") if marker in uri else uri


def parse_applicants(raw: str) -> list[dict]:
    applicants = []
    seen = set()
    for item in raw.split("||"):
        item = item.strip()
        if not item:
            continue
        if "@@" in item:
            name, country = item.rsplit("@@", 1)
        else:
            name, country = item, ""
        name = " ".join(name.split()).strip()
        country = country.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", country):
            country = ""
        key = (name, country)
        if name and key not in seen:
            applicants.append({"raw_name": name, "country": country or None})
            seen.add(key)
    return applicants


def looks_like_person(name: str) -> bool:
    words = set(normalized_text(name).split())
    if words & (COMPANY_WORDS | RESEARCH_WORDS | GOVERNMENT_WORDS):
        return False
    return bool(re.fullmatch(r"[^,]{2,50},\s*[^,]{2,50}", name))


def organization_type(name: str) -> str:
    words = set(normalized_text(name).split())
    if words & RESEARCH_WORDS:
        return "research_institution"
    if words & GOVERNMENT_WORDS:
        return "government"
    if words & COMPANY_WORDS:
        return "company"
    return "unknown_organization"


def value_chain_classification(name: str, entity_type: str, registry: dict | None) -> dict:
    if registry:
        categories = registry["value_chain_categories"]
        return {
            "categories": categories,
            "primary_category": categories[0],
            "classification_method": "curated_registry",
            "confidence": 0.9,
            "basis": [f"company-registry:{registry['uid']}"],
            "review_state": "provisional",
        }
    if entity_type == "research_institution":
        return {
            "categories": ["research_academic"],
            "primary_category": "research_academic",
            "classification_method": "name_heuristic",
            "confidence": 0.75,
            "basis": ["institution-name marker"],
            "review_state": "provisional",
        }
    text = normalized_text(name)
    matches = {
        code: sorted(term for term in terms if term in text)
        for code, terms in VALUE_CHAIN_RULES.items()
    }
    matches = {code: terms for code, terms in matches.items() if terms}
    if matches:
        categories = sorted(matches, key=lambda code: (-len(matches[code]), code))
        return {
            "categories": categories,
            "primary_category": categories[0],
            "classification_method": "name_heuristic",
            "confidence": min(0.8, 0.55 + 0.05 * len(matches[categories[0]])),
            "basis": [f"name:{term}" for term in matches[categories[0]]],
            "review_state": "provisional",
        }
    if entity_type == "company":
        return {
            "categories": ["other_industrial"],
            "primary_category": "other_industrial",
            "classification_method": "name_heuristic",
            "confidence": 0.5,
            "basis": ["corporate-name marker only"],
            "review_state": "provisional",
        }
    return {
        "categories": ["unresolved"],
        "primary_category": "unresolved",
        "classification_method": "unresolved",
        "confidence": None,
        "basis": [],
        "review_state": "provisional",
    }


def load_registry(path: Path) -> tuple[dict, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    by_alias = {}
    for company in document["companies"]:
        for name in [company["canonical_name"], *company.get("aliases", [])]:
            key = (normalized_text(name), company["country"])
            if key in by_alias and by_alias[key]["uid"] != company["uid"]:
                raise ValueError(f"ambiguous company registry alias: {key}")
            by_alias[key] = company
    return document, by_alias


def technical_classification(title: str, seed_categories: set[str], taxonomy: dict) -> dict:
    from import_cordis_patents import classification

    result = classification(title, "", [], taxonomy)
    categories = set(result["categories"]) | seed_categories
    scores = Counter(result["keyword_scores"])
    for category in seed_categories:
        scores[category] = max(scores[category], 2)
    priority = {code: index for index, code in enumerate(taxonomy["primary_priority"])}
    primary = sorted(categories, key=lambda code: (-scores[code], priority.get(code, 999), code))[0]
    requested = sorted({
        taxonomy["categories"][code]["requested_category"]
        for code in categories
        if taxonomy["categories"][code].get("requested_category")
    })
    return {
        "taxonomy_version": taxonomy["version"],
        "primary_category": primary,
        "categories": sorted(categories),
        "requested_categories": requested,
        "keyword_scores": dict(sorted(scores.items())),
        "matched_terms": result["matched_terms"],
        "seed_classification_evidence": sorted(seed_categories),
        "confidence": 0.7 if seed_categories else result["confidence"],
        "review_state": "provisional",
    }


def read_existing_publications(import_root: Path, output: Path) -> set[str]:
    publications = set()
    for path in import_root.glob("*/publication-candidates/part-*.jsonl"):
        if output in path.parents:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            publications.add(json.loads(line)["publication_number"])
    return publications


def write_jsonl_shards(directory: Path, rows: list[dict], size: int) -> list[tuple[Path, int]]:
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("part-*.jsonl"):
        old.unlink()
    written = []
    for offset in range(0, len(rows), size):
        path = directory / f"part-{offset // size + 1:04d}.jsonl"
        block = rows[offset:offset + size]
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in block),
            encoding="utf-8",
        )
        written.append((path, len(block)))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Directory containing immutable EPO SPARQL JSON responses")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, default=ROOT / "patents" / "taxonomy.json")
    parser.add_argument("--company-taxonomy", type=Path, default=ROOT / "patents" / "company-taxonomy.json")
    parser.add_argument("--company-registry", type=Path, default=ROOT / "patents" / "company-registry.json")
    args = parser.parse_args()

    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    company_taxonomy = json.loads(args.company_taxonomy.read_text(encoding="utf-8"))
    registry_document, registry_by_alias = load_registry(args.company_registry)
    existing = read_existing_publications(args.output.parent, args.output)

    raw_by_publication: dict[str, list[dict]] = defaultdict(list)
    raw_row_count = 0
    source_files = {}
    for filename, spec in sorted(SOURCE_SPECS.items()):
        path = args.input / filename
        response = json.loads(path.read_text(encoding="utf-8"))
        bindings = response["results"]["bindings"]
        source_files[f"source/{filename}"] = {
            "sha256": sha256(path),
            "records": len(bindings),
            **spec,
        }
        for binding in bindings:
            number = publication_number(binding)
            record = {
                "publication_number": number,
                "publication_uri": binding_value(binding, "pub"),
                "number": binding_value(binding, "number"),
                "kind_code": kind_code(binding),
                "publication_date": binding_value(binding, "date") or None,
                "title": binding_value(binding, "title"),
                "ipc_classifications": sorted({ipc_code(item) for item in binding_value(binding, "ipcs").split("|") if item}),
                "applicants": parse_applicants(binding_value(binding, "applicants")),
                "application_ids": sorted({application_id(item) for item in binding_value(binding, "applications").split("|") if item}),
                "priority_application_ids": sorted({application_id(item) for item in binding_value(binding, "priorities").split("|") if item}),
                "international_application_ids": sorted({application_id(item) for item in binding_value(binding, "internationalApplications").split("|") if item}),
                "seed_ipc": spec["seed_ipc"],
                "seed_categories": spec["seed_categories"],
                "source_file": filename,
            }
            record["source_record_uid"] = f"epo-linked-data/{number.lower()}/{spec['seed_ipc'].lower()}/{stable_hash(record)}"
            raw_by_publication[number].append(record)
            raw_row_count += 1

    cross_import_duplicates = sorted(set(raw_by_publication) & existing)
    candidate_groups = {
        number: rows for number, rows in raw_by_publication.items() if number not in existing
    }

    registry_hits = Counter()
    company_accumulator: dict[str, dict] = {}
    publication_company_links = []
    candidates = []
    for number, rows in sorted(candidate_groups.items()):
        canonical = sorted(rows, key=lambda row: (row["source_file"], row["source_record_uid"]))[0]
        titles = sorted({row["title"] for row in rows if row["title"]})
        seed_categories = {category for row in rows for category in row["seed_categories"]}
        seed_ipcs = sorted({row["seed_ipc"] for row in rows})
        all_ipcs = sorted({code for row in rows for code in row["ipc_classifications"]})
        application_ids = sorted({item for row in rows for item in row["application_ids"]})
        priority_application_ids = sorted({item for row in rows for item in row["priority_application_ids"]})
        international_application_ids = sorted({item for row in rows for item in row["international_application_ids"]})
        raw_applicants = []
        seen_applicants = set()
        for row in rows:
            for applicant in row["applicants"]:
                key = (applicant["raw_name"], applicant["country"])
                if key not in seen_applicants:
                    raw_applicants.append(applicant)
                    seen_applicants.add(key)

        resolved_applicants = []
        for applicant in sorted(raw_applicants, key=lambda item: (normalized_text(item["raw_name"]), item["country"] or "")):
            name = applicant["raw_name"]
            country = applicant["country"]
            if looks_like_person(name):
                resolved_applicants.append({
                    **applicant,
                    "entity_type": "natural_person",
                    "company_uid": None,
                    "resolution_state": "excluded_from_company_index",
                })
                continue
            registry = registry_by_alias.get((normalized_text(name), country))
            if registry:
                company_uid = registry["uid"]
                registry_hits[company_uid] += 1
                canonical_name = registry["canonical_name"]
                entity_type = registry["organization_type"]
            else:
                entity_type = organization_type(name)
                company_uid = f"company-candidate/{slug(name)}-{(country or 'xx').lower()}-{stable_hash([normalized_text(name), country], 8)}"
                canonical_name = name

            company = company_accumulator.setdefault(company_uid, {
                "company_uid": company_uid,
                "canonical_name": canonical_name,
                "country": country,
                "organization_type": entity_type,
                "registry": registry,
                "aliases": set(),
                "publications": set(),
                "primary_categories": Counter(),
                "technical_categories": Counter(),
                "publication_dates": [],
            })
            company["aliases"].add(name)
            company["publications"].add(number)
            if canonical["publication_date"]:
                company["publication_dates"].append(canonical["publication_date"])
            resolved_applicants.append({
                **applicant,
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "company_uid": company_uid,
                "resolution_state": "registry_match" if registry else "normalized_name_country_candidate",
            })
            publication_company_links.append({
                "publication_uid": f"patent-publication/{number.lower()}",
                "publication_number": number,
                "company_uid": company_uid,
                "relation": "applicant",
                "raw_name": name,
                "country": country,
                "review_state": "pending_review",
            })

        classification = technical_classification(canonical["title"], seed_categories, taxonomy)
        for applicant in resolved_applicants:
            if applicant["company_uid"]:
                company = company_accumulator[applicant["company_uid"]]
                company["primary_categories"][classification["primary_category"]] += 1
                company["technical_categories"].update(classification["categories"])

        candidates.append({
            "schema_version": SCHEMA_VERSION,
            "record_type": "patent_publication_candidate",
            "publication_uid": f"patent-publication/{number.lower()}",
            "publication_number": number,
            "jurisdiction": "EP",
            "kind_code": canonical["kind_code"],
            "publication_date": canonical["publication_date"],
            "title": canonical["title"],
            "title_variants": titles,
            "abstract": None,
            "applicants": resolved_applicants,
            "assignees": [],
            "ipc_classifications": all_ipcs,
            "cpc_classifications": [],
            "application_ids": application_ids,
            "priority_application_ids": priority_application_ids,
            "international_application_ids": international_application_ids,
            "seed_ipc_queries": seed_ipcs,
            "source_records": sorted(row["source_record_uid"] for row in rows),
            "source_observation_ids": sorted(row["source_record_uid"] for row in rows),
            "source_record_count": len(rows),
            "projects": [],
            "battery_relevance": "DIRECT_BATTERY_CLASSIFICATION",
            "classification": classification,
            "family": {
                "docdb_family_id": None,
                "status": "needs_docdb_resolution",
                "provisional_cluster_keys": international_application_ids or priority_application_ids,
                "cluster_basis": "international_application" if international_application_ids else ("shared_priority_set" if priority_application_ids else None),
            },
            "legal_status": {"status": "unknown", "jurisdiction": None, "as_of": None},
            "publication_url": canonical["publication_uri"].replace("http://", "https://"),
            "provenance": {
                "source": "EPO Linked Open EP Data",
                "source_endpoint": SOURCE_ENDPOINT,
                "snapshot_date": SNAPSHOT_DATE,
                "license": SOURCE_LICENSE,
                "source_files": sorted({row["source_file"] for row in rows}),
            },
            "review_flags": [
                "needs_docdb_family", "needs_claims_review", "needs_abstract_enrichment",
                "legal_status_unverified", "applicant_identity_pending",
            ],
            "review_state": "pending_review",
        })

    companies = []
    for company_uid, value in sorted(company_accumulator.items()):
        registry = value["registry"]
        value_chain = value_chain_classification(
            value["canonical_name"], value["organization_type"], registry
        )
        dates = sorted(value["publication_dates"])
        aliases = sorted(value["aliases"], key=lambda item: (normalized_text(item), item))
        if registry:
            aliases = sorted(set(aliases) | set(registry.get("aliases", [])) | {registry["canonical_name"]})
        review_flags = ["needs_entity_curator_approval", "current_patent_owner_not_asserted"]
        if not registry:
            review_flags.extend([
                "needs_legal_name_validation", "needs_website_validation",
                "needs_external_identifier_resolution", "needs_value_chain_category_review",
            ])
        companies.append({
            "schema_version": COMPANY_SCHEMA_VERSION,
            "record_type": "patent_company_candidate",
            "company_uid": company_uid,
            "canonical_name": value["canonical_name"],
            "legal_name": registry.get("legal_name") if registry else None,
            "country": value["country"],
            "organization_type": value["organization_type"],
            "aliases": aliases,
            "value_chain": value_chain,
            "patent_portfolio": {
                "publication_count": len(value["publications"]),
                "publication_numbers": sorted(value["publications"]),
                "earliest_publication_date": dates[0] if dates else None,
                "latest_publication_date": dates[-1] if dates else None,
                "jurisdictions": ["EP"],
                "primary_technical_category_counts": dict(sorted(value["primary_categories"].items())),
                "technical_category_counts": dict(sorted(value["technical_categories"].items())),
                "taxonomy_version": taxonomy["version"],
            },
            "identifiers": {
                "ror_id": None,
                "gleif_lei": None,
                "epo_applicant_name_country_key": stable_hash([normalized_text(value["canonical_name"]), value["country"]], 20),
            },
            "corporate_profile": {
                "website": registry.get("website") if registry else None,
                "parent_company_uid": None,
                "ownership_as_of": None,
                "headquarters_country": value["country"],
            },
            "provenance": {
                "patent_source": "EPO Linked Open EP Data",
                "snapshot_date": SNAPSHOT_DATE,
                "license": SOURCE_LICENSE,
                "registry_version": registry_document["version"] if registry else None,
            },
            "review_flags": sorted(review_flags),
            "review_state": "pending_review",
        })

    candidates.sort(key=lambda row: row["publication_number"])
    companies.sort(key=lambda row: (-row["patent_portfolio"]["publication_count"], row["canonical_name"], row["company_uid"]))
    publication_company_links.sort(key=lambda row: (row["publication_number"], row["company_uid"], row["raw_name"]))

    args.output.mkdir(parents=True, exist_ok=True)
    generated = []
    generated += write_jsonl_shards(args.output / "publication-candidates", candidates, 100)
    generated += write_jsonl_shards(args.output / "companies", companies, 100)
    generated += write_jsonl_shards(args.output / "publication-company-links", publication_company_links, 150)

    title_groups = defaultdict(list)
    for row in candidates:
        title_groups[normalized_text(row["title"])].append(row["publication_number"])
    normalized_entity_groups = defaultdict(set)
    for row in companies:
        normalized_entity_groups[normalized_text(row["canonical_name"])].add(row["country"])
    by_application = defaultdict(list)
    by_family_hint = defaultdict(list)
    for row in candidates:
        for application in row["application_ids"]:
            by_application[application].append(row["publication_number"])
        keys = row["family"]["provisional_cluster_keys"]
        if keys:
            by_family_hint["|".join(keys)].append(row["publication_number"])
    duplicate_report = {
        "raw_publication_observations": raw_row_count,
        "unique_publications_before_existing_filter": len(raw_by_publication),
        "repeated_query_hit_groups": [
            {"publication_number": number, "source_record_count": len(rows), "seed_ipcs": sorted({row["seed_ipc"] for row in rows})}
            for number, rows in sorted(raw_by_publication.items()) if len(rows) > 1
        ],
        "cross_import_publication_duplicates_excluded": cross_import_duplicates,
        "normalized_title_collision_groups": [
            {"normalized_title": title, "publication_numbers": numbers}
            for title, numbers in sorted(title_groups.items()) if len(numbers) > 1
        ],
        "company_name_country_conflicts": [
            {"normalized_name": name, "countries": sorted(countries)}
            for name, countries in sorted(normalized_entity_groups.items()) if len(countries) > 1
        ],
        "same_application_publication_groups": [
            {"application_id": application, "publication_numbers": sorted(set(numbers))}
            for application, numbers in sorted(by_application.items()) if len(set(numbers)) > 1
        ],
        "provisional_family_hint_groups": [
            {"cluster_key": key, "publication_numbers": sorted(set(numbers))}
            for key, numbers in sorted(by_family_hint.items()) if len(set(numbers)) > 1
        ],
        "family_duplicate_status": "provisional_hints_computed;_docdb_resolution_required",
    }
    duplicate_path = args.output / "duplicate-report.json"
    duplicate_path.write_text(json.dumps(duplicate_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    generated.append((duplicate_path, 1))

    category_index = []
    for code, spec in company_taxonomy["categories"].items():
        members = [row for row in companies if code in row["value_chain"]["categories"]]
        category_index.append({
            "code": code,
            "label": spec["label"],
            "definition": spec["definition"],
            "company_count": len(members),
            "publication_count": sum(row["patent_portfolio"]["publication_count"] for row in members),
            "companies": [
                {"company_uid": row["company_uid"], "name": row["canonical_name"], "country": row["country"], "publication_count": row["patent_portfolio"]["publication_count"]}
                for row in members
            ],
        })
    company_index = {
        "schema_version": "1.0.0",
        "taxonomy_version": company_taxonomy["version"],
        "generated_from": "epo-linked-data-2026-09-04",
        "categories": category_index,
        "companies": [
            {
                "company_uid": row["company_uid"],
                "name": row["canonical_name"],
                "legal_name": row["legal_name"],
                "country": row["country"],
                "organization_type": row["organization_type"],
                "value_chain_categories": row["value_chain"]["categories"],
                "publication_count": row["patent_portfolio"]["publication_count"],
                "earliest_publication_date": row["patent_portfolio"]["earliest_publication_date"],
                "latest_publication_date": row["patent_portfolio"]["latest_publication_date"],
                "website": row["corporate_profile"]["website"],
                "review_state": row["review_state"],
            }
            for row in companies
        ],
    }
    index_path = args.output / "company-index.json"
    index_path.write_text(json.dumps(company_index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    generated.append((index_path, 1))

    primary_counts = Counter(row["classification"]["primary_category"] for row in candidates)
    requested_counts = Counter(
        requested for row in candidates for requested in row["classification"]["requested_categories"]
    )
    entity_type_counts = Counter(row["organization_type"] for row in companies)
    company_category_counts = Counter(
        category for row in companies for category in row["value_chain"]["categories"]
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "import_id": "epo-linked-data-battery-patents-2026-09-04",
        "created_at": SNAPSHOT_DATE,
        "source": {
            "publisher": "European Patent Office",
            "landing_url": SOURCE_LANDING,
            "endpoint": SOURCE_ENDPOINT,
            "snapshot_date": SNAPSHOT_DATE,
            "license": SOURCE_LICENSE,
            "query_scope": SOURCE_SPECS,
        },
        "counts": {
            "raw_publication_observations": raw_row_count,
            "unique_publications_before_existing_filter": len(raw_by_publication),
            "cross_import_duplicates_excluded": len(cross_import_duplicates),
            "new_publication_candidates": len(candidates),
            "repeated_query_rows_collapsed": raw_row_count - len(raw_by_publication),
            "company_candidates": len(companies),
            "publication_company_links": len(publication_company_links),
            "natural_person_applicant_mentions": sum(
                applicant["entity_type"] == "natural_person"
                for row in candidates for applicant in row["applicants"]
            ),
            "registry_resolved_company_mentions": sum(registry_hits.values()),
        },
        "classification": {
            "technical_taxonomy_version": taxonomy["version"],
            "company_taxonomy_version": company_taxonomy["version"],
            "publication_primary_category_counts": dict(sorted(primary_counts.items())),
            "publication_requested_category_counts": dict(sorted(requested_counts.items())),
            "company_entity_type_counts": dict(sorted(entity_type_counts.items())),
            "company_value_chain_category_counts": dict(sorted(company_category_counts.items())),
            "labels_are_provisional": True,
        },
        "files": {
            **source_files,
            **{
                str(path.relative_to(args.output)): {"sha256": sha256(path), "records": count}
                for path, count in generated
            },
        },
        "acceptance_boundary": {
            "publication_candidates_are_accepted_patents": False,
            "company_candidates_are_accepted_organizations": False,
            "requires_human_review": True,
            "requires_docdb_family_resolution": True,
            "applicant_is_not_current_owner": True,
            "legal_status_is_not_freedom_to_operate_advice": True,
        },
    }
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
