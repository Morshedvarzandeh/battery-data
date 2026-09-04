-- =====================================================================
-- battery-data : 190_graph.sql
--
-- THE GRAPH LAYER, AND WHY IT IS A PROJECTION RATHER THAN THE STORE.
--
-- The relational core wins on everything this database is mostly for:
-- numeric range filtering, unit enforcement, condition constraints,
-- bulk analytics, and refusing malformed data at the door. A property
-- graph is weak at exactly those things.
--
-- But a graph wins decisively on the questions that have no bounded join
-- depth: "which pack products transitively contain a cell whose cathode
-- uses material from supplier X", "what is the shortest provenance path
-- from this published capacity figure to a raw cycler file", "which
-- protocols are cited by campaigns that also produced EIS at 45 C".
--
-- So: Postgres is the source of truth, and the graph is a derived,
-- rebuildable artefact. Nothing is stored only in the graph. If the
-- graph is dropped, one command rebuilds it.
--
-- Two backends are supported and both read the same node/edge views:
--   * Apache AGE (in-database, openCypher over these tables)
--   * Neo4j (export via tools/export_graph.py using the same views)
-- =====================================================================

SET search_path = bd_graph, bd, public;

-- ---------------------------------------------------------------------
-- NODES. One row per graph vertex, with a stable typed key.
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW bd_graph.node AS
SELECT 'Organization'      AS label, 'org:'||o.id       AS node_key, o.uid,
       o.name              AS title,
       jsonb_build_object('country',o.country,'roles',o.roles,
                          'stages',bd.organization_stages(o.id)) AS props
  FROM bd.organization o
UNION ALL
SELECT 'Material', 'mat:'||m.id, m.uid, COALESCE(m.common_name,m.name),
       jsonb_build_object('role',m.role,'family',m.family,
                          'formula',m.formula,'elements',m.elements)
  FROM bd.material m
UNION ALL
SELECT 'Product', 'prod:'||p.id, p.uid, p.model_number,
       jsonb_build_object('kind',p.kind,'form_factor',p.form_factor,
                          'form_factor_code',p.form_factor_code,
                          'component_kind',p.component_kind,
                          'lifecycle',p.lifecycle)
  FROM bd.product p
UNION ALL
SELECT 'ProductRevision', 'rev:'||pr.id, pr.uid, pr.revision_label,
       jsonb_build_object('effective_date',pr.effective_date,
                          'preliminary',pr.is_preliminary,
                          'region_scope',pr.region_scope,
                          'chemistry',pc.designation,'family',pc.family,
                          'construction',pc.construction)
  FROM bd.product_revision pr
  LEFT JOIN bd.product_chemistry pc ON pc.product_revision_id = pr.id
UNION ALL
-- where a battery is fielded: a vehicle, a rail programme, a grid site
SELECT 'Application', 'app:'||a.id, a.uid, a.name,
       jsonb_build_object('sector',a.sector,'operator',a.operator_text,
                          'region',a.region,'in_service_from',a.in_service_from)
  FROM bd.application a
UNION ALL
-- a certification claim is its own node so scope and status stay visible
SELECT 'Certification', 'cert:'||c.id, 'cert/'||c.id, c.standard_text,
       jsonb_build_object('scope',c.scope,'status',c.status,
                          'certificate_number',c.certificate_number,
                          'certifying_body',c.certifying_body)
  FROM bd.certification c
UNION ALL
-- upstream: where materials are dug, refined and made into cells
SELECT 'Site', 'site:'||s.id, s.uid, s.name,
       jsonb_build_object('kind',s.kind,'stage',bd.site_stage(s.kind),
                          'status',s.status,'country',s.country,
                          'latitude',s.latitude,'longitude',s.longitude,
                          'commodities',s.commodities,'products',s.products)
  FROM bd.site s
UNION ALL
SELECT 'ProductUnit', 'unit:'||pu.id, pu.uid, pu.serial_number,
       jsonb_build_object('lot',pu.lot_code,'status',pu.battery_status,
                          'prior_cycles',pu.prior_cycle_count)
  FROM bd.product_unit pu
UNION ALL
SELECT 'Protocol', 'proto:'||pt.id, pt.uid, pt.name,
       jsonb_build_object('test_kind',pt.test_kind,'clause',pt.standard_clause,
                          'application_class',pt.application_class)
  FROM bd.protocol pt
UNION ALL
SELECT 'Standard', 'std:'||s.id, s.uid, s.title,
       jsonb_build_object('sdo',s.sdo,'number',s.number,'year',s.year)
  FROM bd.standard s
UNION ALL
SELECT 'TestRun', 'run:'||tr.id, tr.uid, tr.test_kind::text,
       jsonb_build_object('started_at',tr.started_at,'kind',tr.test_kind,
                          'current_sign',tr.current_sign)
  FROM bd.test_run tr
UNION ALL
SELECT 'Campaign', 'camp:'||c.id, c.uid, c.title,
       jsonb_build_object('doi',c.doi,'objective',c.objective)
  FROM bd.campaign c
UNION ALL
SELECT 'Source', 'src:'||s.id, s.uid, COALESCE(s.title,s.uid),
       jsonb_build_object('kind',s.kind,'doi',s.doi,'url',s.url,
                          'revision',s.revision,'license',s.license)
  FROM bd.source s
UNION ALL
SELECT 'Dataset', 'ds:'||d.id, d.uid, d.file_name,
       jsonb_build_object('storage',d.storage,'n_rows',d.n_rows,
                          'columns',d.columns_present)
  FROM bd.dataset d
UNION ALL
SELECT 'Model', 'model:'||m.id, m.uid, m.name,
       jsonb_build_object('kind',m.kind,'format',m.format_name)
  FROM bd.model_parameterisation m
UNION ALL
SELECT 'PatentFamily', 'patfam:'||pf.id, pf.uid, pf.title,
       jsonb_build_object('docdb_family_id',pf.docdb_family_id,
                          'priority_date',pf.earliest_priority_date,
                          'primary_category',pf.primary_category)
  FROM bd.patent_family pf WHERE pf.review='accepted'
UNION ALL
SELECT 'PatentPublication', 'patpub:'||pp.id, pp.uid, pp.title,
       jsonb_build_object('publication_number',pp.publication_number,
                          'jurisdiction',pp.jurisdiction,
                          'legal_status',pp.legal_status,
                          'legal_status_as_of',pp.legal_status_as_of)
  FROM bd.patent_publication pp WHERE pp.review='accepted';

CREATE UNIQUE INDEX ON bd_graph.node (node_key);
CREATE INDEX ON bd_graph.node (label);
CREATE INDEX ON bd_graph.node USING gin (props jsonb_path_ops);

-- ---------------------------------------------------------------------
-- EDGES.
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW bd_graph.edge AS
-- manufacturer -> product
SELECT 'MANUFACTURES'  AS rel, 'org:'||p.manufacturer_id AS src_key,
       'prod:'||p.id   AS dst_key, '{}'::jsonb AS props
  FROM bd.product p
UNION ALL
-- corporate ownership (Sanyo -> Panasonic)
SELECT 'SUBSIDIARY_OF', 'org:'||o.id, 'org:'||o.parent_id, '{}'::jsonb
  FROM bd.organization o WHERE o.parent_id IS NOT NULL
UNION ALL
-- product -> its revisions
SELECT 'HAS_REVISION', 'prod:'||pr.product_id, 'rev:'||pr.id,
       jsonb_build_object('label',pr.revision_label)
  FROM bd.product_revision pr
UNION ALL
SELECT 'SUPERSEDES', 'rev:'||pr.id, 'rev:'||pr.supersedes_id, '{}'::jsonb
  FROM bd.product_revision pr WHERE pr.supersedes_id IS NOT NULL
UNION ALL
-- revision documented by a source
SELECT 'DOCUMENTED_BY', 'rev:'||pr.id, 'src:'||pr.source_id, '{}'::jsonb
  FROM bd.product_revision pr
UNION ALL
-- ASSEMBLY: this is the edge that makes multi-hop worth having.
-- system -> pack -> module -> cell, arbitrary depth, no special cases.
SELECT 'CONTAINS', 'rev:'||pa.parent_revision_id, 'rev:'||pa.child_revision_id,
       jsonb_build_object('quantity',pa.quantity,'series',pa.series_count,
                          'parallel',pa.parallel_count,'topology',pa.topology_string)
  FROM bd.product_assembly pa
UNION ALL
-- bill of materials
SELECT 'USES_MATERIAL', 'rev:'||pm.product_revision_id, 'mat:'||pm.material_id,
       jsonb_build_object('role',pm.role,'mass_fraction',pm.mass_fraction)
  FROM bd.product_material pm
UNION ALL
-- material supply chain
SELECT 'SUPPLIED_BY', 'mat:'||ms.material_id, 'org:'||ms.supplier_org_id,
       jsonb_build_object('grade',ms.grade_name,'plant',ms.plant_name,
                          'country',ms.plant_country)
  FROM bd.material_supply ms
UNION ALL
-- physical units instantiate a revision
SELECT 'INSTANCE_OF', 'unit:'||pu.id, 'rev:'||pu.product_revision_id, '{}'::jsonb
  FROM bd.product_unit pu
UNION ALL
-- test execution chain
SELECT 'TESTED', 'run:'||tr.id, 'unit:'||tr.product_unit_id,
       jsonb_build_object('kind',tr.test_kind)
  FROM bd.test_run tr
UNION ALL
SELECT 'FOLLOWS_PROTOCOL', 'run:'||tr.id, 'proto:'||tr.protocol_id, '{}'::jsonb
  FROM bd.test_run tr WHERE tr.protocol_id IS NOT NULL
UNION ALL
SELECT 'PART_OF_CAMPAIGN', 'run:'||tr.id, 'camp:'||tr.campaign_id, '{}'::jsonb
  FROM bd.test_run tr WHERE tr.campaign_id IS NOT NULL
UNION ALL
SELECT 'PRODUCED', 'run:'||d.test_run_id, 'ds:'||d.id,
       jsonb_build_object('role',d.role)
  FROM bd.dataset d
UNION ALL
-- protocol grounded in a published standard
SELECT 'IMPLEMENTS_STANDARD', 'proto:'||pt.id, 'std:'||pt.standard_id,
       jsonb_build_object('clause',pt.standard_clause)
  FROM bd.protocol pt WHERE pt.standard_id IS NOT NULL
UNION ALL
-- an aging protocol's periodic reference performance test
SELECT 'RPT_PROTOCOL', 'proto:'||pt.id, 'proto:'||pt.rpt_protocol_id,
       jsonb_build_object('interval_cycles',pt.rpt_interval_cycles)
  FROM bd.protocol pt WHERE pt.rpt_protocol_id IS NOT NULL
UNION ALL
-- model fitted from runs
SELECT 'FITTED_FROM', 'model:'||m.id, 'run:'||r, '{}'::jsonb
  FROM bd.model_parameterisation m, unnest(m.fitted_from_run_ids) AS r
UNION ALL
SELECT 'PARAMETERISES', 'model:'||m.id, 'rev:'||m.product_revision_id, '{}'::jsonb
  FROM bd.model_parameterisation m WHERE m.product_revision_id IS NOT NULL
UNION ALL
-- campaign published as a source
SELECT 'PUBLISHED_AS', 'camp:'||c.id, 'src:'||c.source_id, '{}'::jsonb
  FROM bd.campaign c WHERE c.source_id IS NOT NULL
UNION ALL
-- equivalence / second sourcing
SELECT 'EQUIVALENT_TO', 'prod:'||pe.product_a_id, 'prod:'||pe.product_b_id,
       jsonb_build_object('relation',pe.relation)
  FROM bd.product_equivalence pe
UNION ALL
-- upstream and market edges
SELECT 'OPERATES', 'org:'||s.operator_org_id, 'site:'||s.id, '{}'::jsonb
  FROM bd.site s WHERE s.operator_org_id IS NOT NULL
UNION ALL
SELECT 'OWNS', 'org:'||so.org_id, 'site:'||so.site_id,
       jsonb_build_object('share_pct',so.share_pct,'role',so.role,
                          'valid_from',so.valid_from,'valid_to',so.valid_to)
  FROM bd.site_ownership so
UNION ALL
SELECT 'SUPPLIES', 'org:'||sa.supplier_org_id, 'org:'||sa.buyer_org_id,
       jsonb_build_object('subject',sa.subject,'kind',sa.kind,'volume',sa.volume,
                          'volume_unit',sa.volume_unit,'valid_from',sa.valid_from,
                          'valid_to',sa.valid_to,'uid',sa.uid)
  FROM bd.supply_agreement sa
UNION ALL
SELECT 'SUPPLIED_FROM', 'org:'||sa.buyer_org_id, 'site:'||sa.site_id,
       jsonb_build_object('subject',sa.subject,'uid',sa.uid)
  FROM bd.supply_agreement sa WHERE sa.site_id IS NOT NULL
UNION ALL
SELECT 'DISTRIBUTES', 'org:'||d.distributor_org_id, 'org:'||d.manufacturer_org_id,
       jsonb_build_object('status',d.status,'regions',d.regions)
  FROM bd.distribution d WHERE d.manufacturer_org_id IS NOT NULL
UNION ALL
-- company relations, one relationship type per relation kind
SELECT upper(r.relation::text), 'org:'||r.org_id, 'org:'||r.related_org_id,
       jsonb_build_object('share_pct',r.share_pct,'valid_from',r.valid_from,'valid_to',r.valid_to)
  FROM bd.organization_relation r
UNION ALL
-- FIELDED_IN: the claim that a revision, a product or a brand family is
-- used in an application, at the granularity the source supports.
SELECT 'FIELDED_IN',
       CASE WHEN pa.product_revision_id IS NOT NULL THEN 'rev:'||pa.product_revision_id
            WHEN pa.product_id IS NOT NULL THEN 'prod:'||pa.product_id
            ELSE 'org:'||pa.brand_org_id END,
       'app:'||pa.application_id,
       jsonb_build_object('basis',pa.basis,'confidence',pa.confidence,'role',pa.role,
                          'brand_family',pa.brand_family,'quantity_per_unit',pa.quantity_per_unit)
  FROM bd.product_application pa
UNION ALL
SELECT 'HOLDS_CERTIFICATION', 'rev:'||c.product_revision_id, 'cert:'||c.id,
       jsonb_build_object('status',c.status,'scope',c.scope)
  FROM bd.certification c
UNION ALL
SELECT 'CERTIFIED_TO', 'cert:'||c.id, 'std:'||c.standard_id, '{}'::jsonb
  FROM bd.certification c WHERE c.standard_id IS NOT NULL
UNION ALL
-- OFFERED_BY: who sells it; price and date live on the edge
SELECT 'OFFERED_BY', 'prod:'||po.product_id, 'org:'||po.seller_org_id,
       jsonb_build_object('observed_at',po.observed_at,'currency',po.currency,
                          'unit_price',po.unit_price,'region',po.region)
  FROM bd.product_offer po WHERE po.seller_org_id IS NOT NULL
UNION ALL
-- EVIDENCE edges: every observation ties a subject to the source that
-- asserts it. This is what makes "trace this number back" a traversal.
SELECT 'EVIDENCED_BY', 'rev:'||o.product_revision_id, 'src:'||sl.source_id,
       jsonb_build_object('quantity',q.code,'evidence',pv.evidence,
                          'value_si',o.value_si)
  FROM bd.observation o
  JOIN bd.quantity q ON q.id=o.quantity_id
  JOIN bd.provenance pv ON pv.id=o.provenance_id
  JOIN bd.source_location sl ON sl.id=pv.source_location_id
 WHERE o.product_revision_id IS NOT NULL
UNION ALL
-- accepted patent family -> publication -> source
SELECT 'HAS_PUBLICATION', 'patfam:'||pp.family_id, 'patpub:'||pp.id,
       jsonb_build_object('publication_number',pp.publication_number)
  FROM bd.patent_publication pp
 WHERE pp.family_id IS NOT NULL AND pp.review='accepted'
UNION ALL
SELECT 'PUBLISHED_AS', 'patpub:'||pp.id, 'src:'||pp.source_id,
       jsonb_build_object('publication_number',pp.publication_number)
  FROM bd.patent_publication pp
 WHERE pp.source_id IS NOT NULL AND pp.review='accepted'
UNION ALL
-- reviewed links keep the relationship label as evidence-bearing metadata
SELECT 'PATENT_RELATES_TO', 'patfam:'||pel.family_id,
       CASE
         WHEN pel.product_id IS NOT NULL THEN 'prod:'||pel.product_id
         WHEN pel.product_revision_id IS NOT NULL THEN 'rev:'||pel.product_revision_id
         WHEN pel.material_id IS NOT NULL THEN 'mat:'||pel.material_id
         ELSE 'org:'||pel.organization_id
       END,
       jsonb_build_object('relation',pel.relation,'confidence',pel.confidence)
  FROM bd.patent_entity_link pel
 WHERE pel.review='accepted';

CREATE INDEX ON bd_graph.edge (src_key);
CREATE INDEX ON bd_graph.edge (dst_key);
CREATE INDEX ON bd_graph.edge (rel);

-- ---------------------------------------------------------------------
-- Rebuild entry point.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd_graph.refresh()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  REFRESH MATERIALIZED VIEW bd_graph.node;
  REFRESH MATERIALIZED VIEW bd_graph.edge;
END$$;

-- ---------------------------------------------------------------------
-- Recursive traversal in plain SQL, so the multi-hop questions work even
-- with no graph extension installed at all. AGE and Neo4j are then
-- optimisations, not prerequisites.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd_graph.reachable(
  start_key   text,
  rels        text[] DEFAULT NULL,     -- NULL = any relationship
  max_depth   int    DEFAULT 6,
  direction   text   DEFAULT 'out'     -- 'out' | 'in' | 'both'
) RETURNS TABLE (node_key text, label text, uid text, title text,
                 depth int, path text[])
LANGUAGE sql STABLE AS $$
  WITH RECURSIVE walk AS (
    SELECT n.node_key, n.label, n.uid, n.title, 0 AS depth,
           ARRAY[n.node_key] AS path
      FROM bd_graph.node n
     WHERE n.node_key = start_key
    UNION ALL
    SELECT n.node_key, n.label, n.uid, n.title, w.depth + 1,
           w.path || n.node_key
      FROM walk w
      JOIN bd_graph.edge e
        ON (direction IN ('out','both')  AND e.src_key = w.node_key)
        OR (direction IN ('in','both')   AND e.dst_key = w.node_key)
      JOIN bd_graph.node n
        ON n.node_key = CASE WHEN e.src_key = w.node_key
                             THEN e.dst_key ELSE e.src_key END
     WHERE w.depth < max_depth
       AND (rels IS NULL OR e.rel = ANY(rels))
       AND NOT n.node_key = ANY(w.path)          -- cycle guard
  )
  -- One row per reachable node, at its shortest depth. Parallel edges
  -- (a revision with many EVIDENCED_BY edges to one source) would
  -- otherwise return the same node repeatedly.
  SELECT DISTINCT ON (node_key)
         node_key, label, uid, title, depth, path
    FROM walk
   WHERE depth > 0
   ORDER BY node_key, depth, path;
$$;

COMMENT ON FUNCTION bd_graph.reachable IS
$$Multi-hop traversal without a graph extension. Example - every product
that transitively contains a given cell revision:

  SELECT * FROM bd_graph.reachable('rev:1', ARRAY['CONTAINS'], 6, 'in');

Example - full provenance closure of a pack, down to raw datasets:

  SELECT * FROM bd_graph.reachable('rev:9',
    ARRAY['CONTAINS','INSTANCE_OF','TESTED','PRODUCED','EVIDENCED_BY'], 8, 'both');$$;

-- ---------------------------------------------------------------------
-- Optional Apache AGE loader. Safe to skip when the extension is absent.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bd_graph.load_age(graph_name text DEFAULT 'battery')
RETURNS text LANGUAGE plpgsql AS $$
DECLARE n_nodes bigint; n_edges bigint;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='age') THEN
    RETURN 'Apache AGE not installed - use bd_graph.reachable() or '
           'tools/export_graph.py for Neo4j.';
  END IF;
  PERFORM bd_graph.refresh();
  SELECT count(*) INTO n_nodes FROM bd_graph.node;
  SELECT count(*) INTO n_edges FROM bd_graph.edge;
  -- Population is delegated to tools/load_age.py, which batches
  -- create_vlabel/create_elabel plus Cypher CREATE in transactions.
  RETURN format('AGE present. %s nodes / %s edges staged for graph "%s". '
                'Run tools/load_age.py to populate.', n_nodes, n_edges, graph_name);
END$$;

