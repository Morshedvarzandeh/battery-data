#!/usr/bin/env python3
"""Load the contributions that are not products into the library.

contrib/sites/      -> bd.site, site_alias, resource_estimate, site_metric, site_ownership
contrib/companies/  -> bd.organization (profile columns), organization_alias, organization_relation
contrib/market/     -> bd.commodity_price, price_index, market_volume, trade_flow,
                       supply_agreement, distribution
contrib/patents/    -> bd.patent_family, patent_publication, patent_classification,
                       patent_entity_link, all as review = accepted

A file says which layer it is by its shape (tools/validate_layers.py decides
the same way). Organisations named in a file are created when absent, with
the role the context implies; an *_uid pins to an existing one instead.
Every row carries provenance to the source and the quote. Price, index and
volume rows are refused unless the source says its data may be
redistributed, the rule the validator enforces.

A reload replaces what a file asserted before: the rows whose provenance
note names the file are deleted and written again.

    python tools/load_layers.py --dsn dbname=batterydb
    python tools/load_layers.py contrib/sites/some-operator/some-mine.yaml
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

try:
    import psycopg2
    import psycopg2.extras
    import yaml
except ImportError:
    sys.exit("pip install psycopg2-binary pyyaml")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_layers import LAYERS, layer_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVIDENCE_BY_KIND = {"dataset": "measured", "journal_article": "literature_reported",
                    "preprint": "literature_reported", "regulatory_filing": "literature_reported",
                    "third_party_test": "measured", "patent": "literature_reported",
                    "manufacturer_web": "manufacturer_claim", "datasheet": "manufacturer_claim",
                    "distributor_listing": "manufacturer_claim"}


def scalar(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def ensure_org(cur, name: str | None, uid: str | None, role: str | None) -> int | None:
    """An organisation by uid (must exist) or by name (created, role merged)."""
    if uid:
        org_id = scalar(cur, "SELECT id FROM bd.organization WHERE uid = %s", (uid,))
        if org_id is None:
            raise ValueError(f"organisation {uid} is not in the library")
        return org_id
    if not name:
        return None
    # the same company under one uid: a name that matches an existing
    # organisation's name, legal name or alias resolves to it before a new
    # slug is minted, so "Example Lithium Ltd" in a site file is the
    # org/example-lithium the company file defined
    org_id = scalar(cur, """SELECT o.id FROM bd.organization o
                             WHERE lower(o.name) = lower(%s) OR lower(o.legal_name) = lower(%s)
                             UNION
                            SELECT a.org_id FROM bd.organization_alias a WHERE lower(a.alias) = lower(%s)
                             LIMIT 1""", (name, name, name))
    if org_id is not None:
        if role:
            cur.execute("""UPDATE bd.organization
                              SET roles = (SELECT COALESCE(array_agg(DISTINCT r ORDER BY r), '{}')
                                             FROM unnest(roles || %s::text[]) r)
                            WHERE id = %s""", ([role], org_id))
        return org_id
    uid = f"org/{slug(name)}"
    cur.execute("""INSERT INTO bd.organization (uid, name, roles) VALUES (%s, %s, %s)
                   ON CONFLICT (uid) DO UPDATE
                     SET roles = (SELECT COALESCE(array_agg(DISTINCT r ORDER BY r), '{}')
                                    FROM unnest(bd.organization.roles || EXCLUDED.roles) r)""",
                (uid, name, [role] if role else []))
    return scalar(cur, "SELECT id FROM bd.organization WHERE uid = %s", (uid,))


def ensure_source(cur, src: dict, evidence_default: str) -> tuple[int, str]:
    date = str(src.get("document_date") or "")
    cur.execute(
        """INSERT INTO bd.source (uid, kind, title, doi, url, revision, license, redistributable,
                                  content_sha256, scope_note, published_year, raw_metadata, retrieved_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
           ON CONFLICT (uid) DO NOTHING""",
        (src["uid"], src["kind"], src.get("title"), src.get("doi"), src.get("url"),
         src.get("revision"), src.get("license"), bool(src.get("redistributable", False)),
         src.get("sha256"), src.get("note"), int(date[:4]) if date[:4].isdigit() else None,
         psycopg2.extras.Json({"data_redistributable": src.get("data_redistributable"),
                               "document_date_stated": src.get("document_date")})))
    evidence = EVIDENCE_BY_KIND.get(src["kind"], evidence_default)
    return scalar(cur, "SELECT id FROM bd.source WHERE uid = %s", (src["uid"],)), evidence


def locate(cur, source_id: int, locator: dict | None, evidence: str, reviewer_id: int, note: str) -> int:
    locator = locator or {}
    location_id = scalar(cur,
        """INSERT INTO bd.source_location (source_id, page, section, quote)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (source_id, locator.get("page"), locator.get("section"), locator.get("quote")))
    return scalar(cur,
        """INSERT INTO bd.provenance (source_location_id, evidence, extraction, review,
                                      contributor_id, reviewed_by, reviewed_at, review_note)
           VALUES (%s, %s, 'manual_entry', 'accepted', %s, %s, now(), %s) RETURNING id""",
        (location_id, evidence, reviewer_id, reviewer_id, note))


def forget(cur, table: str, note: str, extra_sql: str = "", extra: tuple = ()):
    """Delete the rows a previous load of this file wrote to a table."""
    cur.execute(f"""DELETE FROM bd.{table} t USING bd.provenance p
                     WHERE p.id = t.provenance_id AND p.review_note = %s {extra_sql}""",
                (note, *extra))


# ---------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------
def load_site(cur, doc: dict, rel: str, reviewer_id: int) -> str:
    note = f"accepted into contrib/ as {rel}"
    site, src = doc["site"], doc["source"]
    source_id, evidence = ensure_source(cur, src, "manufacturer_claim")
    operator_id = ensure_org(cur, site.get("operator"), site.get("operator_uid"), "site_operator")
    provenance_id = locate(cur, source_id, doc.get("locator"), evidence, reviewer_id, note)
    cur.execute(
        """INSERT INTO bd.site (uid, kind, name, operator_org_id, country, region, locality,
                                latitude, longitude, status, status_as_of, commodities, products,
                                deposit_type, opened_year, notes, provenance_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (uid) DO UPDATE SET
             kind = EXCLUDED.kind, name = EXCLUDED.name, operator_org_id = EXCLUDED.operator_org_id,
             country = EXCLUDED.country, region = EXCLUDED.region, locality = EXCLUDED.locality,
             latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude, status = EXCLUDED.status,
             status_as_of = EXCLUDED.status_as_of, commodities = EXCLUDED.commodities,
             products = EXCLUDED.products, deposit_type = EXCLUDED.deposit_type,
             opened_year = EXCLUDED.opened_year, notes = EXCLUDED.notes,
             provenance_id = EXCLUDED.provenance_id, updated_at = now()""",
        (site["uid"], site["kind"], site["name"], operator_id, site["country"], site.get("region"),
         site.get("locality"), site.get("latitude"), site.get("longitude"),
         site.get("status") or "unknown", site.get("status_as_of"), site.get("commodities") or [],
         site.get("products") or [], site.get("deposit_type"), site.get("opened_year"),
         site.get("notes"), provenance_id))
    site_id = scalar(cur, "SELECT id FROM bd.site WHERE uid = %s", (site["uid"],))
    for alias in site.get("aliases") or []:
        cur.execute("INSERT INTO bd.site_alias (site_id, alias) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (site_id, alias))
    for table in ("resource_estimate", "site_metric", "site_ownership"):
        forget(cur, table, note, "AND t.site_id = %s", (site_id,))
    n = 0
    for r in doc.get("resources") or []:
        pid = locate(cur, source_id, r.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.resource_estimate (site_id, commodity, category, reporting_code, tonnage,
                 tonnage_unit, grade, grade_unit, cutoff_grade, cutoff_unit, contained_metal,
                 contained_unit, as_of, unstated, notes, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (site_id, r["commodity"], r.get("category") or "unspecified",
             r.get("reporting_code") or "unspecified", r.get("tonnage"), r.get("tonnage_unit"),
             r.get("grade"), r.get("grade_unit"), r.get("cutoff_grade"), r.get("cutoff_unit"),
             r.get("contained_metal"), r.get("contained_unit"), r.get("as_of"),
             r.get("unstated") or [], r.get("notes"), pid))
        n += 1
    for m in doc.get("metrics") or []:
        pid = locate(cur, source_id, m.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.site_metric (site_id, metric, subject, status, value, unit, period_start,
                 period_end, as_of, notes, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (site_id, m["metric"], m.get("subject"), m.get("status") or "unspecified", m["value"],
             m["unit"], m["period_start"], m.get("period_end"), m.get("as_of"), m.get("notes"), pid))
        n += 1
    for o in doc.get("ownership") or []:
        org_id = ensure_org(cur, o.get("organization"), o.get("organization_uid"), "owner")
        pid = locate(cur, source_id, o.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.site_ownership (site_id, org_id, share_pct, role, valid_from, valid_to, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            (site_id, org_id, o.get("share_pct"), o.get("role") or "owner", o.get("valid_from"),
             o.get("valid_to"), pid))
        n += 1
    return f"ok    {rel}: {site['uid']} + {n} row(s)"


# ---------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------
def load_company(cur, doc: dict, rel: str, reviewer_id: int) -> str:
    note = f"accepted into contrib/ as {rel}"
    org, src = doc["organization"], doc["source"]
    source_id, evidence = ensure_source(cur, src, "manufacturer_claim")
    provenance_id = locate(cur, source_id, doc.get("locator"), evidence, reviewer_id, note)
    parent_id = None
    if org.get("parent_uid"):
        parent_id = ensure_org(cur, None, org["parent_uid"], None)
    cur.execute(
        """INSERT INTO bd.organization (uid, name, legal_name, country, roles, website, ror_id, gleif_lei,
                 founded_year, hq_region, hq_locality, ticker, exchange, description, parent_id, provenance_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (uid) DO UPDATE SET
             name = EXCLUDED.name,
             legal_name   = COALESCE(EXCLUDED.legal_name, bd.organization.legal_name),
             country      = COALESCE(EXCLUDED.country, bd.organization.country),
             roles        = (SELECT COALESCE(array_agg(DISTINCT r ORDER BY r), '{}')
                               FROM unnest(bd.organization.roles || EXCLUDED.roles) r),
             website      = COALESCE(EXCLUDED.website, bd.organization.website),
             ror_id       = COALESCE(EXCLUDED.ror_id, bd.organization.ror_id),
             gleif_lei    = COALESCE(EXCLUDED.gleif_lei, bd.organization.gleif_lei),
             founded_year = COALESCE(EXCLUDED.founded_year, bd.organization.founded_year),
             hq_region    = COALESCE(EXCLUDED.hq_region, bd.organization.hq_region),
             hq_locality  = COALESCE(EXCLUDED.hq_locality, bd.organization.hq_locality),
             ticker       = COALESCE(EXCLUDED.ticker, bd.organization.ticker),
             exchange     = COALESCE(EXCLUDED.exchange, bd.organization.exchange),
             description  = COALESCE(EXCLUDED.description, bd.organization.description),
             parent_id    = COALESCE(EXCLUDED.parent_id, bd.organization.parent_id),
             provenance_id = EXCLUDED.provenance_id, updated_at = now()""",
        (org["uid"], org["name"], org.get("legal_name"), org.get("country"), org["roles"],
         org.get("website"), org.get("ror_id"), org.get("lei"), org.get("founded_year"),
         org.get("hq_region"), org.get("hq_locality"), org.get("ticker"), org.get("exchange"),
         org.get("description"), parent_id, provenance_id))
    org_id = scalar(cur, "SELECT id FROM bd.organization WHERE uid = %s", (org["uid"],))
    for alias, kind in [(a, "trade_name") for a in org.get("aliases") or []] + \
                       [(a, "former_name") for a in org.get("former_names") or []]:
        cur.execute("""INSERT INTO bd.organization_alias (org_id, alias, kind) VALUES (%s, %s, %s)
                       ON CONFLICT (org_id, alias) DO UPDATE SET kind = EXCLUDED.kind""",
                    (org_id, alias, kind))
    forget(cur, "organization_relation", note)
    n = 0
    for r in doc.get("relations") or []:
        other = ensure_org(cur, r.get("organization"), r.get("organization_uid"), None)
        pid = locate(cur, source_id, r.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.organization_relation (org_id, related_org_id, relation, share_pct,
                 valid_from, valid_to, notes, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            (org_id, other, r["relation"], r.get("share_pct"), r.get("valid_from"), r.get("valid_to"),
             r.get("notes"), pid))
        n += 1
    return f"ok    {rel}: {org['uid']} + {n} relation(s)"


# ---------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------
def load_market(cur, doc: dict, rel: str, reviewer_id: int) -> str:
    note = f"accepted into contrib/ as {rel}"
    src = doc["source"]
    priced = (doc.get("commodity_prices") or []) + (doc.get("price_indices") or []) \
        + (doc.get("market_volumes") or [])
    if priced and not src.get("data_redistributable"):
        return f"FAIL  {rel}: price rows from a source whose data may not be redistributed"
    source_id, evidence = ensure_source(cur, src, "literature_reported")
    for table in ("commodity_price", "price_index", "market_volume", "trade_flow",
                  "supply_agreement", "distribution"):
        forget(cur, table, note)
    n = 0
    for r in doc.get("commodity_prices") or []:
        pid = locate(cur, source_id, r.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.commodity_price (commodity, traded_form_id, grade, basis, market, currency,
                 value, per_unit, period_start, period_end, provider, provenance_id)
               VALUES (%s, (SELECT id FROM bd.traded_form WHERE code = %s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            (r["commodity"], r.get("traded_form"), r.get("grade"), r.get("basis") or "unspecified",
             r["market"], r["currency"], r["value"], r["per_unit"], r["period_start"], r["period_end"],
             r.get("provider"), pid))
        n += 1
    for r in doc.get("price_indices") or []:
        pid = locate(cur, source_id, r.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.price_index (segment, chemistry_family, chemistry, sector, region, currency, value,
                 per_unit, basis, period_start, period_end, provider, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (r["segment"], r.get("chemistry_family"), r.get("chemistry"), r.get("sector"), r["region"], r["currency"],
             r["value"], r.get("per_unit") or "kWh", r.get("basis") or "unspecified",
             r["period_start"], r["period_end"], r.get("provider"), pid))
        n += 1
    for r in doc.get("market_volumes") or []:
        org_id = ensure_org(cur, r.get("organization"), r.get("organization_uid"), "manufacturer")
        pid = locate(cur, source_id, r.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.market_volume (metric, org_id, region, country, sector, chemistry_family,
                 chemistry, value, unit, share_pct, rank, period_start, period_end, provider, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (r["metric"], org_id, r.get("region"), r.get("country"), r.get("sector"),
             r.get("chemistry_family"), r.get("chemistry"), r["value"], r["unit"], r.get("share_pct"), r.get("rank"),
             r["period_start"], r["period_end"], r.get("provider"), pid))
        n += 1
    for r in doc.get("trade_flows") or []:
        pid = locate(cur, source_id, r.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.trade_flow (reporter_country, partner_country, hs_code, commodity, direction,
                 period_start, period_end, value_usd, quantity, quantity_unit, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            (r["reporter_country"], r["partner_country"], r["hs_code"], r.get("commodity"),
             r["direction"], r["period_start"], r["period_end"], r.get("value_usd"),
             r.get("quantity"), r.get("quantity_unit"), pid))
        n += 1
    for a in doc.get("supply_agreements") or []:
        sup = ensure_org(cur, a.get("supplier"), a.get("supplier_uid"), "supplier")
        buy = ensure_org(cur, a.get("buyer"), a.get("buyer_uid"), "buyer")
        pid = locate(cur, source_id, a.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.supply_agreement (uid, supplier_org_id, buyer_org_id, kind, subject, site_id,
                 traded_form_id, volume, volume_unit, volume_period, valid_from, valid_to, announced_on,
                 notes, provenance_id)
               VALUES (%s, %s, %s, %s, %s, (SELECT id FROM bd.site WHERE uid = %s),
                       (SELECT id FROM bd.traded_form WHERE code = %s), %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (uid) DO UPDATE SET
                 supplier_org_id = EXCLUDED.supplier_org_id, buyer_org_id = EXCLUDED.buyer_org_id,
                 kind = EXCLUDED.kind, subject = EXCLUDED.subject, site_id = EXCLUDED.site_id,
                 traded_form_id = EXCLUDED.traded_form_id, volume = EXCLUDED.volume,
                 volume_unit = EXCLUDED.volume_unit, volume_period = EXCLUDED.volume_period,
                 valid_from = EXCLUDED.valid_from, valid_to = EXCLUDED.valid_to,
                 announced_on = EXCLUDED.announced_on, notes = EXCLUDED.notes,
                 provenance_id = EXCLUDED.provenance_id""",
            (a["uid"], sup, buy, a.get("kind") or "unspecified", a["subject"], a.get("site_uid"),
             a.get("traded_form"), a.get("volume"), a.get("volume_unit"), a.get("volume_period"),
             a.get("valid_from"), a.get("valid_to"), a.get("announced_on"), a.get("notes"), pid))
        n += 1
    for d in doc.get("distributions") or []:
        dist = ensure_org(cur, d.get("distributor"), d.get("distributor_uid"), "distributor")
        mfr = ensure_org(cur, d.get("manufacturer"), d.get("manufacturer_uid"), "manufacturer")
        pid = locate(cur, source_id, d.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.distribution (distributor_org_id, manufacturer_org_id, status, regions,
                 product_families, url, valid_from, valid_to, provenance_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            (dist, mfr, d.get("status") or "unspecified", d.get("regions") or [],
             d.get("product_families") or [], d.get("url"), d.get("valid_from"), d.get("valid_to"), pid))
        n += 1
    return f"ok    {rel}: {n} row(s)"


# ---------------------------------------------------------------------
# Patents: the accepted end of docs/08-patents.md
# ---------------------------------------------------------------------
def load_patent(cur, doc: dict, rel: str, reviewer_id: int) -> str:
    note = f"accepted into contrib/ as {rel}"
    fam, src = doc["family"], doc["source"]
    taxonomy = fam.get("taxonomy_version") or "battery-patent-taxonomy-1.0.0"
    source_id, evidence = ensure_source(cur, src, "literature_reported")
    pid = locate(cur, source_id, doc.get("locator"), evidence, reviewer_id, note)
    cur.execute(
        """INSERT INTO bd.patent_family (uid, docdb_family_id, title, abstract, earliest_priority_date,
                 primary_category, taxonomy_version, provenance_id, review)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'accepted')
           ON CONFLICT (uid) DO UPDATE SET
             docdb_family_id = EXCLUDED.docdb_family_id, title = EXCLUDED.title,
             abstract = EXCLUDED.abstract, earliest_priority_date = EXCLUDED.earliest_priority_date,
             primary_category = EXCLUDED.primary_category, taxonomy_version = EXCLUDED.taxonomy_version,
             provenance_id = EXCLUDED.provenance_id, review = 'accepted'""",
        (fam["uid"], fam["docdb_family_id"], fam["title"], fam.get("abstract"),
         fam.get("earliest_priority_date"), fam["primary_category"], taxonomy, pid))
    family_id = scalar(cur, "SELECT id FROM bd.patent_family WHERE uid = %s", (fam["uid"],))
    n = 0
    for p in doc["publications"]:
        ppid = locate(cur, source_id, p.get("locator"), evidence, reviewer_id, note)
        uid = f"{fam['uid']}/{p['publication_number']}"
        cur.execute(
            """INSERT INTO bd.patent_publication (uid, family_id, publication_number, application_number,
                 jurisdiction, kind_code, title, abstract, priority_date, filing_date, publication_date,
                 grant_date, applicants, assignees, inventors, source_id, provenance_id, publication_url,
                 legal_status, legal_status_jurisdiction, legal_status_as_of, review)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       'accepted')
               ON CONFLICT (uid) DO UPDATE SET
                 family_id = EXCLUDED.family_id, publication_number = EXCLUDED.publication_number,
                 application_number = EXCLUDED.application_number, jurisdiction = EXCLUDED.jurisdiction,
                 kind_code = EXCLUDED.kind_code, title = EXCLUDED.title, abstract = EXCLUDED.abstract,
                 priority_date = EXCLUDED.priority_date, filing_date = EXCLUDED.filing_date,
                 publication_date = EXCLUDED.publication_date, grant_date = EXCLUDED.grant_date,
                 applicants = EXCLUDED.applicants, assignees = EXCLUDED.assignees,
                 inventors = EXCLUDED.inventors, source_id = EXCLUDED.source_id,
                 provenance_id = EXCLUDED.provenance_id, publication_url = EXCLUDED.publication_url,
                 legal_status = EXCLUDED.legal_status,
                 legal_status_jurisdiction = EXCLUDED.legal_status_jurisdiction,
                 legal_status_as_of = EXCLUDED.legal_status_as_of, review = 'accepted'""",
            (uid, family_id, p["publication_number"], p.get("application_number"), p["jurisdiction"],
             p.get("kind_code"), p["title"], p.get("abstract"), p.get("priority_date"),
             p.get("filing_date"), p.get("publication_date"), p.get("grant_date"),
             psycopg2.extras.Json(p.get("applicants") or []), psycopg2.extras.Json(p.get("assignees") or []),
             psycopg2.extras.Json(p.get("inventors") or []), source_id, ppid, p["publication_url"],
             p.get("legal_status"), p.get("legal_status_jurisdiction"), p.get("legal_status_as_of")))
        pub_id = scalar(cur, "SELECT id FROM bd.patent_publication WHERE uid = %s", (uid,))
        cur.execute("DELETE FROM bd.patent_classification WHERE publication_id = %s", (pub_id,))
        for c in p.get("categories") or []:
            cur.execute(
                """INSERT INTO bd.patent_classification (publication_id, category_code, is_primary, confidence,
                     basis, taxonomy_version, review)
                   VALUES (%s, %s, %s, %s, %s, %s, 'accepted')""",
                (pub_id, c["code"], bool(c.get("primary")), c.get("confidence"),
                 psycopg2.extras.Json({"basis": c.get("basis")} if c.get("basis") else {}), taxonomy))
        n += 1
    forget(cur, "patent_entity_link", note, "AND t.family_id = %s", (family_id,))
    for l in doc.get("links") or []:
        product_id = material_id = org_id = None
        if l.get("product_uid"):
            product_id = scalar(cur, "SELECT id FROM bd.product WHERE uid = %s", (l["product_uid"],))
            if product_id is None:
                raise ValueError(f"product {l['product_uid']} is not in the library")
        elif l.get("material_uid"):
            material_id = scalar(cur, "SELECT id FROM bd.material WHERE uid = %s", (l["material_uid"],))
            if material_id is None:
                raise ValueError(f"material {l['material_uid']} is not in the library")
        else:
            org_id = ensure_org(cur, l.get("organization"), l.get("organization_uid"), None)
        lpid = locate(cur, source_id, l.get("locator"), evidence, reviewer_id, note)
        cur.execute(
            """INSERT INTO bd.patent_entity_link (family_id, relation, product_id, material_id,
                 organization_id, confidence, provenance_id, review)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'accepted')""",
            (family_id, l["relation"], product_id, material_id, org_id, l.get("confidence"), lpid))
        n += 1
    return f"ok    {rel}: {fam['uid']} + {n} row(s)"


LOADERS = {"sites": load_site, "companies": load_company, "market": load_market, "patents": load_patent}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files or directories; default contrib/{sites,companies,market,patents}")
    ap.add_argument("--dsn", default=os.environ.get("BATTERY_DSN", "dbname=batterydb"))
    ap.add_argument("--reviewer", default="user/contrib-review")
    a = ap.parse_args()
    files: list[str] = []
    if a.paths:
        for p in a.paths:
            files += sorted(glob.glob(os.path.join(p, "**", "*.y*ml"), recursive=True)) if os.path.isdir(p) else [p]
    else:
        for spec in LAYERS.values():
            files += sorted(glob.glob(os.path.join(ROOT, "contrib", spec["dir"], "**", "*.y*ml"), recursive=True))
    if not files:
        print("no site, company, market or patent contributions under contrib/")
        return 0
    # companies first, so a uid pin in a site or agreement resolves; sites before market
    order = {"companies": 0, "sites": 1, "patents": 2, "market": 3}
    docs = []
    for f in files:
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        layer = layer_of(doc)
        if layer not in LOADERS:
            print(f"  --    {os.path.relpath(f, ROOT)}  (not a layer contribution; skipped)")
            continue
        docs.append((order[layer], f, layer, doc))
    docs.sort(key=lambda t: (t[0], t[1]))
    conn = psycopg2.connect(a.dsn)
    failed = 0
    with conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO bd.contributor (uid, display_name, is_bot) VALUES (%s, %s, true)
                           ON CONFLICT (uid) DO NOTHING""", (a.reviewer, "contrib review (owner-approved)"))
            reviewer_id = scalar(cur, "SELECT id FROM bd.contributor WHERE uid = %s", (a.reviewer,))
            for _, f, layer, doc in docs:
                rel = os.path.relpath(f, ROOT)
                try:
                    cur.execute("SAVEPOINT one_file")
                    line = LOADERS[layer](cur, doc, rel, reviewer_id)
                    cur.execute("RELEASE SAVEPOINT one_file")
                except (ValueError, psycopg2.Error) as e:
                    cur.execute("ROLLBACK TO SAVEPOINT one_file")
                    line = f"FAIL  {rel}: {str(e).strip().splitlines()[0]}"
                failed += line.startswith("FAIL")
                print("  " + line)
    conn.close()
    counts = {k: sum(1 for d in docs if d[2] == k) for k in LOADERS}
    print("\n" + ", ".join(f"{v} {k}" for k, v in counts.items()) + f", {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
