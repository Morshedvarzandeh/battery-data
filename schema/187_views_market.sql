-- =====================================================================
-- battery-data : 187_views_market.sql
--
-- Query surfaces for the upstream, distribution and market layer, and
-- the generic surfaces the API registry exposes for every other entity.
-- Every view carries provenance columns where the row has provenance,
-- because an API that drops the source undoes the point of the schema.
-- =====================================================================

SET search_path = bd, public;

-- Provenance flattened once, joined by every view below.
CREATE VIEW v_provenance AS
SELECT pv.id AS provenance_id, pv.evidence, pv.extraction, pv.confidence, pv.review,
       s.uid AS source_uid, s.kind AS source_kind, s.title AS source_title, s.url AS source_url,
       s.doi, s.revision AS source_revision, s.document_date, s.license AS source_license,
       s.redistributable, sl.page, sl.section, sl.quote
  FROM provenance pv
  JOIN source_location sl ON sl.id = pv.source_location_id
  JOIN source s ON s.id = sl.source_id;

CREATE VIEW v_organization AS
SELECT o.uid, o.name, o.legal_name, o.country, o.roles, o.website, o.ror_id,
       (SELECT count(*) FROM product p WHERE p.manufacturer_id = o.id)   AS products,
       (SELECT count(*) FROM site s WHERE s.operator_org_id = o.id)      AS sites_operated,
       (SELECT count(*) FROM site_ownership so WHERE so.org_id = o.id)   AS sites_owned,
       (SELECT count(*) FROM supply_agreement sa
         WHERE sa.supplier_org_id = o.id OR sa.buyer_org_id = o.id)      AS supply_agreements,
       (SELECT count(*) FROM distribution d WHERE d.distributor_org_id = o.id) AS distributes_for,
       o.id AS organization_id
  FROM organization o;

CREATE VIEW v_product AS
SELECT p.uid AS product_uid, p.kind::text AS kind, org.name AS manufacturer, p.model_number,
       p.form_factor::text AS form_factor, p.form_factor_code, p.component_kind::text AS component_kind,
       p.iec_designation, p.lifecycle::text AS lifecycle, p.is_rechargeable,
       pc.designation AS chemistry, pc.family::text AS chemistry_family, pc.construction::text AS construction,
       cr.revision_label, s.kind::text AS source_kind, s.url AS source_url, s.document_date,
       (SELECT count(*) FROM observation o WHERE o.product_revision_id = cr.product_revision_id) AS observations,
       (SELECT count(*) FROM curve c WHERE c.product_revision_id = cr.product_revision_id) AS curves,
       cr.product_revision_id
  FROM product p
  JOIN organization org ON org.id = p.manufacturer_id
  LEFT JOIN v_current_revision cr ON cr.product_id = p.id
  LEFT JOIN product_revision pr ON pr.id = cr.product_revision_id
  LEFT JOIN source s ON s.id = pr.source_id
  LEFT JOIN product_chemistry pc ON pc.product_revision_id = cr.product_revision_id;

CREATE VIEW v_material AS
SELECT m.uid, m.name, m.common_name, m.role::text AS role, m.formula, m.elements, m.family,
       m.density_kg_m3, m.theoretical_specific_capacity_ah_kg, m.optimade_ids, m.emmo_iri,
       (SELECT count(*) FROM material_supply ms WHERE ms.material_id = m.id) AS suppliers
  FROM material m;

CREATE VIEW v_model AS
SELECT mp.uid, mp.name, mp.kind::text AS kind, mp.format_name, mp.format_version,
       p.uid AS product_uid, p.model_number, org.name AS manufacturer,
       mp.fit_tool, mp.fit_rmse, mp.fit_rmse_unit,
       v.source_uid, v.source_title, v.doi, v.source_url, v.evidence,
       mp.id AS model_id
  FROM model_parameterisation mp
  LEFT JOIN product_revision pr ON pr.id = mp.product_revision_id
  LEFT JOIN product p ON p.id = pr.product_id
  LEFT JOIN organization org ON org.id = p.manufacturer_id
  JOIN v_provenance v ON v.provenance_id = mp.provenance_id;

CREATE VIEW v_offer AS
SELECT po.id, p.uid AS product_uid, p.model_number, org.name AS manufacturer,
       seller.name AS seller, po.region, po.currency, po.unit_price, po.price_per_kwh,
       po.min_order_qty, po.lead_time_days, po.in_stock, po.grade, po.observed_at,
       v.source_uid, v.source_url, v.quote
  FROM product_offer po
  JOIN product p ON p.id = po.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  LEFT JOIN organization seller ON seller.id = po.seller_org_id
  JOIN v_provenance v ON v.provenance_id = po.provenance_id;

CREATE VIEW v_certification AS
SELECT c.id, p.uid AS product_uid, p.model_number, org.name AS manufacturer,
       c.standard_text AS standard, c.scope, c.status, c.certificate_number, c.certifying_body,
       c.listing_type, c.issued_date, c.expiry_date,
       v.source_uid, v.source_url, v.page, v.quote
  FROM certification c
  JOIN product_revision pr ON pr.id = c.product_revision_id
  JOIN product p ON p.id = pr.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  JOIN v_provenance v ON v.provenance_id = c.provenance_id;

CREATE VIEW v_curve AS
SELECT c.uid, p.uid AS product_uid, p.model_number, org.name AS manufacturer, c.curve_kind,
       qx.code AS x_quantity, qy.code AS y_quantity, c.x_unit, c.y_unit, c.n_points,
       c.x_values, c.y_values, c.z_values,
       cs.temperature_c, cs.direction, cs.pulse_duration_s, cs.soc_pct, cs.rate_value,
       cs.rate_unit::text AS rate_unit, cs.unstated,
       v.source_uid, v.source_url, v.page, v.quote
  FROM curve c
  JOIN quantity qx ON qx.id = c.x_quantity_id
  JOIN quantity qy ON qy.id = c.y_quantity_id
  LEFT JOIN condition_set cs ON cs.id = c.condition_set_id
  JOIN product_revision pr ON pr.id = c.product_revision_id
  JOIN product p ON p.id = pr.product_id
  JOIN organization org ON org.id = p.manufacturer_id
  JOIN v_provenance v ON v.provenance_id = c.provenance_id;

-- ---------------------------------------------------------------------
-- Upstream and market
-- ---------------------------------------------------------------------
CREATE VIEW v_site AS
SELECT s.uid, s.kind::text AS kind, bd.site_stage(s.kind) AS stage, s.name,
       op.name AS operator, op.uid AS operator_uid,
       s.country, s.region, s.locality, s.latitude, s.longitude,
       s.status::text AS status, s.status_as_of, s.commodities, s.products, s.deposit_type,
       s.opened_year,
       (SELECT count(*) FROM resource_estimate r WHERE r.site_id = s.id) AS resource_estimates,
       (SELECT count(*) FROM site_metric m WHERE m.site_id = s.id)      AS metrics,
       (SELECT string_agg(o.name || ' ' || COALESCE(so.share_pct::text || '%', ''), '; ')
          FROM site_ownership so JOIN organization o ON o.id = so.org_id
         WHERE so.site_id = s.id AND so.valid_to IS NULL)                AS owners,
       v.source_uid, v.source_url, v.page, v.quote, v.evidence,
       s.id AS site_id
  FROM site s
  LEFT JOIN organization op ON op.id = s.operator_org_id
  JOIN v_provenance v ON v.provenance_id = s.provenance_id;

CREATE VIEW v_resource_estimate AS
SELECT r.id, s.uid AS site_uid, s.name AS site, s.country, r.commodity,
       r.category::text AS category, r.reporting_code, r.tonnage, r.tonnage_unit,
       r.grade, r.grade_unit, r.cutoff_grade, r.cutoff_unit, r.contained_metal, r.contained_unit,
       r.as_of, r.unstated, v.source_uid, v.source_url, v.page, v.quote
  FROM resource_estimate r
  JOIN site s ON s.id = r.site_id
  JOIN v_provenance v ON v.provenance_id = r.provenance_id;

CREATE VIEW v_site_metric AS
SELECT m.id, s.uid AS site_uid, s.name AS site, s.kind::text AS site_kind, s.country,
       m.metric, m.subject, m.status::text AS status, m.value, m.unit,
       m.period_start, m.period_end, m.as_of, v.source_uid, v.source_url, v.page, v.quote
  FROM site_metric m
  JOIN site s ON s.id = m.site_id
  JOIN v_provenance v ON v.provenance_id = m.provenance_id;

CREATE VIEW v_supply_agreement AS
SELECT sa.uid, sup.name AS supplier, sup.uid AS supplier_uid, buy.name AS buyer, buy.uid AS buyer_uid,
       sa.kind::text AS kind, sa.subject, st.uid AS site_uid, tf.code AS traded_form,
       sa.volume, sa.volume_unit, sa.volume_period, sa.valid_from, sa.valid_to, sa.announced_on,
       v.source_uid, v.source_url, v.page, v.quote
  FROM supply_agreement sa
  JOIN organization sup ON sup.id = sa.supplier_org_id
  JOIN organization buy ON buy.id = sa.buyer_org_id
  LEFT JOIN site st ON st.id = sa.site_id
  LEFT JOIN traded_form tf ON tf.id = sa.traded_form_id
  JOIN v_provenance v ON v.provenance_id = sa.provenance_id;

CREATE VIEW v_distribution AS
SELECT d.id, dist.name AS distributor, dist.uid AS distributor_uid, mfr.name AS manufacturer,
       mfr.uid AS manufacturer_uid, d.status::text AS status, d.regions, d.product_families,
       d.url, d.valid_from, d.valid_to, v.source_uid, v.source_url, v.quote
  FROM distribution d
  JOIN organization dist ON dist.id = d.distributor_org_id
  LEFT JOIN organization mfr ON mfr.id = d.manufacturer_org_id
  JOIN v_provenance v ON v.provenance_id = d.provenance_id;

CREATE VIEW v_commodity_price AS
SELECT cp.id, cp.commodity, tf.code AS traded_form, tf.contained_fraction, cp.grade,
       cp.basis::text AS basis, cp.market, cp.currency, cp.value, cp.per_unit,
       cp.period_start, cp.period_end, cp.provider,
       v.source_uid, v.source_title, v.source_url, v.source_license, v.redistributable, v.page, v.quote
  FROM commodity_price cp
  LEFT JOIN traded_form tf ON tf.id = cp.traded_form_id
  JOIN v_provenance v ON v.provenance_id = cp.provenance_id;

CREATE VIEW v_price_index AS
SELECT pi.id, pi.segment, pi.chemistry_family::text AS chemistry_family, pi.sector, pi.region,
       pi.currency, pi.value, pi.per_unit, pi.basis::text AS basis, pi.period_start, pi.period_end,
       pi.provider, v.source_uid, v.source_title, v.source_url, v.source_license, v.page, v.quote
  FROM price_index pi
  JOIN v_provenance v ON v.provenance_id = pi.provenance_id;

CREATE VIEW v_market_volume AS
SELECT mv.id, mv.metric::text AS metric, org.name AS organization, org.uid AS organization_uid,
       mv.region, mv.country, mv.sector, mv.chemistry_family::text AS chemistry_family,
       mv.value, mv.unit, mv.share_pct, mv.rank, mv.period_start, mv.period_end, mv.provider,
       v.source_uid, v.source_title, v.source_url, v.source_license, v.page, v.quote
  FROM market_volume mv
  LEFT JOIN organization org ON org.id = mv.org_id
  JOIN v_provenance v ON v.provenance_id = mv.provenance_id;

CREATE VIEW v_trade_flow AS
SELECT t.id, t.reporter_country, t.partner_country, t.hs_code, t.commodity,
       t.direction::text AS direction, t.period_start, t.period_end, t.value_usd,
       t.quantity, t.quantity_unit, v.source_uid, v.source_title, v.source_url, v.quote
  FROM trade_flow t
  JOIN v_provenance v ON v.provenance_id = t.provenance_id;


-- ---------------------------------------------------------------------
-- The map itself, companies, patents, and the reference vocabularies,
-- so that every layer answers the same GET.
-- ---------------------------------------------------------------------
CREATE VIEW v_stage AS
SELECT st.code, st.position, st.label, st.definition, st.site_kinds, st.roles,
       (SELECT count(*) FROM site s WHERE bd.site_stage(s.kind) = st.code)        AS sites,
       (SELECT count(*) FROM organization o WHERE o.roles && st.roles)            AS companies
  FROM supply_chain_stage st;

CREATE VIEW v_company AS
SELECT o.uid, o.name, o.legal_name, o.country, o.hq_region, o.hq_locality, o.founded_year,
       o.roles, bd.organization_stages(o.id) AS stages,
       (SELECT string_agg(a.alias, '; ' ORDER BY a.alias) FROM organization_alias a WHERE a.org_id = o.id) AS aliases,
       parent.uid AS parent_uid, parent.name AS parent,
       o.website, o.ror_id, o.gleif_lei AS lei, o.ticker, o.exchange, o.description,
       (SELECT count(*) FROM product p WHERE p.manufacturer_id = o.id)                       AS products,
       (SELECT count(*) FROM site s WHERE s.operator_org_id = o.id)                          AS sites_operated,
       (SELECT count(*) FROM site_ownership so WHERE so.org_id = o.id)                       AS sites_owned,
       (SELECT count(*) FROM supply_agreement sa
         WHERE sa.supplier_org_id = o.id OR sa.buyer_org_id = o.id)                          AS supply_agreements,
       (SELECT count(*) FROM distribution d WHERE d.distributor_org_id = o.id)               AS distributes_for,
       (SELECT count(*) FROM distribution d WHERE d.manufacturer_org_id = o.id)              AS distributed_by,
       (SELECT count(*) FROM patent_entity_link l WHERE l.organization_id = o.id)            AS patent_families,
       (SELECT count(*) FROM organization_relation r WHERE r.org_id = o.id OR r.related_org_id = o.id) AS relations,
       (SELECT count(*) FROM application a WHERE a.operator_org_id = o.id)                   AS applications,
       v.source_uid, v.source_url, v.page, v.quote,
       o.id AS organization_id
  FROM organization o
  LEFT JOIN organization parent ON parent.id = o.parent_id
  LEFT JOIN v_provenance v ON v.provenance_id = o.provenance_id;

CREATE VIEW v_company_relation AS
SELECT r.id, o.uid AS organization_uid, o.name AS organization, r.relation::text AS relation,
       ro.uid AS related_uid, ro.name AS related, r.share_pct, r.valid_from, r.valid_to, r.notes,
       v.source_uid, v.source_url, v.page, v.quote
  FROM organization_relation r
  JOIN organization o  ON o.id = r.org_id
  JOIN organization ro ON ro.id = r.related_org_id
  JOIN v_provenance v ON v.provenance_id = r.provenance_id;

CREATE VIEW v_patent_category AS
SELECT pc.code, pc.label, pc.requested_domain, pc.definition, pc.taxonomy_version,
       (SELECT count(*) FROM patent_family pf WHERE pf.primary_category = pc.code)       AS families,
       (SELECT count(*) FROM patent_classification c WHERE c.category_code = pc.code)    AS publications
  FROM patent_category pc;

CREATE VIEW v_patent_family AS
SELECT pf.uid, pf.docdb_family_id, pf.title, pf.earliest_priority_date,
       pf.primary_category, pc.label AS category, pf.review::text AS review,
       (SELECT count(*) FROM patent_publication pp WHERE pp.family_id = pf.id)                        AS publications,
       (SELECT array_agg(DISTINCT pp.jurisdiction ORDER BY pp.jurisdiction)
          FROM patent_publication pp WHERE pp.family_id = pf.id AND pp.jurisdiction IS NOT NULL)      AS jurisdictions,
       (SELECT string_agg(o.name, '; ' ORDER BY o.name)
          FROM patent_entity_link l JOIN organization o ON o.id = l.organization_id
         WHERE l.family_id = pf.id)                                                                   AS organizations,
       (SELECT string_agg(p.uid, '; ' ORDER BY p.uid)
          FROM patent_entity_link l JOIN product p ON p.id = l.product_id
         WHERE l.family_id = pf.id)                                                                   AS product_uids,
       (SELECT string_agg(m.uid, '; ' ORDER BY m.uid)
          FROM patent_entity_link l JOIN material m ON m.id = l.material_id
         WHERE l.family_id = pf.id)                                                                   AS material_uids,
       v.source_uid, v.source_url, v.quote,
       pf.id AS family_id
  FROM patent_family pf
  LEFT JOIN patent_category pc ON pc.code = pf.primary_category
  LEFT JOIN v_provenance v ON v.provenance_id = pf.provenance_id;

CREATE VIEW v_patent AS
SELECT pp.uid, pp.publication_number, pp.jurisdiction, pp.kind_code, pp.title,
       pf.uid AS family_uid, pf.docdb_family_id, pp.application_number,
       pp.priority_date, pp.filing_date, pp.publication_date, pp.grant_date,
       pp.applicants::text AS applicants, pp.assignees::text AS assignees, pp.inventors::text AS inventors,
       (SELECT array_agg(c.category_code ORDER BY c.is_primary DESC, c.category_code)
          FROM patent_classification c WHERE c.publication_id = pp.id)                    AS categories,
       pp.legal_status, pp.legal_status_jurisdiction, pp.legal_status_as_of,
       pp.publication_url, pp.review::text AS review,
       v.source_uid, v.source_url, v.quote,
       pp.id AS publication_id
  FROM patent_publication pp
  LEFT JOIN patent_family pf ON pf.id = pp.family_id
  LEFT JOIN v_provenance v ON v.provenance_id = pp.provenance_id;

CREATE VIEW v_standard AS
SELECT s.uid, s.sdo, s.number, s.part, s.edition, s.year, s.title, s.url, s.is_open_access,
       (SELECT count(*) FROM certification c WHERE c.standard_id = s.id) AS certifications,
       (SELECT count(*) FROM source src WHERE src.standard_id = s.id)    AS sources
  FROM standard s;

CREATE VIEW v_application AS
SELECT a.uid, a.name, a.sector::text AS sector, COALESCE(o.name, a.operator_text) AS operator,
       o.uid AS operator_uid, a.programme, a.region, a.in_service_from, a.in_service_to,
       a.system_energy_kwh, a.system_power_kw,
       (SELECT count(*) FROM product_application pa WHERE pa.application_id = a.id) AS products
  FROM application a
  LEFT JOIN organization o ON o.id = a.operator_org_id;

CREATE VIEW v_source AS
SELECT s.uid, s.kind::text AS kind, s.title, s.url, s.doi, s.revision, s.document_date,
       s.published_year, s.license, s.redistributable, pub.name AS publisher, s.retrieved_at,
       (SELECT count(*) FROM source_location sl JOIN provenance pv ON pv.source_location_id = sl.id
         WHERE sl.source_id = s.id) AS claims
  FROM source s
  LEFT JOIN organization pub ON pub.id = s.publisher_org_id;

CREATE VIEW v_quantity AS
SELECT q.code, q.label, q.si_unit, q.dimension, q.description, q.required_conditions, q.is_derived,
       q.emmo_iri, q.qudt_quantity_kind, q.bdf_name, q.bpx_key, q.battery_pass_path,
       (SELECT count(*) FROM observation o WHERE o.quantity_id = q.id) AS observations
  FROM quantity q;

CREATE VIEW v_unit AS
SELECT u.symbol, u.si_symbol, u.factor, u.offset_ AS offset, u.dimension, u.qudt_iri
  FROM unit u;

CREATE VIEW v_chemistry AS
SELECT pc.designation, pc.family::text AS family, pc.construction::text AS construction,
       count(*)                                                     AS products,
       array_agg(DISTINCT p.kind::text ORDER BY p.kind::text)       AS product_kinds,
       count(DISTINCT p.manufacturer_id)                            AS manufacturers,
       min(pc.cathode_text) FILTER (WHERE pc.cathode_text IS NOT NULL) AS cathode_example,
       min(pc.anode_text)   FILTER (WHERE pc.anode_text IS NOT NULL)   AS anode_example
  FROM product_chemistry pc
  JOIN v_current_revision cr ON cr.product_revision_id = pc.product_revision_id
  JOIN product p ON p.id = cr.product_id
 WHERE pc.designation IS NOT NULL OR pc.family IS NOT NULL
 GROUP BY pc.designation, pc.family, pc.construction;
