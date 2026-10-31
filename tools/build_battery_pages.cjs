#!/usr/bin/env node
/* Build one reference page per battery in the library, a page per maker, an
 * index, and the sitemap of the pages search engines should index.
 *
 *   web/batteries/index.html                   the library: makers and kinds
 *   web/batteries/<maker>/index.html           one maker: every battery in a table
 *   web/batteries/<maker>/<model>/index.html   one battery: every value with its
 *                                              conditions and its source
 *   web/batteries/sitemap.xml                  the indexable pages only
 *
 * lemonergy.com serves them at /data/batteries/ (a Pages Function in the hub
 * proxies this site's /batteries/, as /data/finder/ proxies the finder), so
 * every library release reaches the pages when GitHub Pages publishes it. The
 * canonical address of every page is the lemonergy.com one.
 *
 * WHY A PAGE, AND WHY NOT ALWAYS AN INDEXED ONE
 * ---------------------------------------------
 * Every battery gets a permanent address a person can link to, cite in a
 * support ticket or open from the finder. Search engines are asked to index a
 * page only when its record carries enough of its own to be worth finding
 * (INDEX_RULE below): most of the library is two catalogues (LiPol, Harding
 * Energy) whose rows hold the same five or six numbers, and three thousand
 * such pages would be thin, near-identical content. Those pages carry
 * `noindex, follow` and stay out of the sitemap; their maker's page, a full
 * table of the catalogue, is the indexed one. A record that gains values
 * crosses the rule on the next build without anyone touching this file.
 *
 * The values read exactly as in the finder: labels, units, conditions,
 * grouping, provenance and similar records all come from web/app.js (BD),
 * so a value cannot say one thing on its page and another in the finder.
 *
 *   python tools/build_web_data.py          # web/data/ first
 *   node tools/build_battery_pages.cjs      # then web/batteries/
 *   node tools/build_battery_pages.cjs --data DIR --out DIR
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const BD = require(path.join(ROOT, 'web', 'app.js'));

const SITE = 'https://lemonergy.com';
const BASE = '/data/batteries/';
const REPO = 'https://github.com/Morshedvarzandeh/battery-data';
const API = 'https://design.lemonergy.com/api/data/demo/v1/products/';
const FINDER = `${SITE}/data/finder/`;
const NOT_STATED = 'Maker not stated';

/* What every catalogue row has. A record is worth indexing when it states
 * more than these, from a named maker's document. */
const BASIC = new Set(['capacity', 'voltage', 'nominal_voltage', 'length', 'width', 'thickness', 'height', 'diameter', 'mass']);
const INDEX_RULE = 'a named maker, at least six stated quantities, and at least one beyond capacity, voltage, size and mass';
const MIN_QUANTITIES = 6;

const KIND = {
  cell: { word: 'cell', name: 'Rechargeable cell', plural: 'rechargeable cells' },
  primary_cell: { word: 'primary cell', name: 'Primary cell', plural: 'primary cells' },
  module: { word: 'battery module', name: 'Battery module', plural: 'battery modules' },
  pack: { word: 'battery pack', name: 'Battery pack', plural: 'battery packs' },
  system: { word: 'battery system', name: 'Battery system', plural: 'battery systems' },
};

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// JSON inside <script>: nothing in it may close the element.
const ldJson = (v) => JSON.stringify(v, null, 1).replace(/</g, '\\u003c');
const num = (v, d) => (v == null ? null : BD.fmt(v, d));
const plural = (n, one, many) => `${n.toLocaleString('en')} ${n === 1 ? one : many}`;

/** kind, maker slug, model slug: the record's uid is already a path. */
function parts(uid) {
  const [kind, maker, model] = uid.split('/');
  return { kind, maker, model };
}
const pagePath = (uid) => { const p = parts(uid); return `${BASE}${p.maker}/${p.model}/`; };
const makerPath = (slug) => `${BASE}${slug}/`;

/** Whether search engines should index a battery's page, and why not if not. */
function indexable(rec) {
  const qs = new Set((rec.obs || []).map((o) => o.q));
  if (rec.manu === NOT_STATED) return { ok: false, why: 'the maker is not stated' };
  if (qs.size < MIN_QUANTITIES) return { ok: false, why: `${qs.size} stated quantities` };
  if (![...qs].some((q) => !BASIC.has(q))) return { ok: false, why: 'only capacity, voltage, size and mass are stated' };
  return { ok: true, why: null };
}

/* ---------------------------------------------------------------- words */

const formatWord = (r) => (r.fmt && BD.FF[r.fmt] && BD.FF[r.fmt] !== 'other' ? BD.FF[r.fmt] : null);
function chemWord(r) {
  if (r.tech === 'Lead-acid') return r.tvar ? `lead-acid (${r.tvar})` : 'lead-acid';
  if (r.cclass) return r.cclass;
  if (r.tech) return r.tech.toLowerCase();
  return r.chem || null;
}
/** "302 Ah LFP prismatic cell" — what the battery is, from what the record states. */
function shortSpec(r) {
  const k = KIND[r.kind] || KIND.cell;
  const size = r.ah != null ? `${num(r.ah)} Ah` : null;
  return [size, chemWord(r), formatWord(r), k.word].filter(Boolean).join(' ');
}

function capacityText(r) { return r.ah != null ? `${num(r.ah)} Ah` : null; }
function voltageText(r) { return r.v != null ? `${num(r.v)} V` : null; }
function massText(g) { return g == null ? null : g >= 1000 ? `${num(g / 1000)} kg` : `${num(g)} g`; }
function dimsText(r) {
  if (!r.dims) return null;
  if (r.shape === 'cyl' && r.dims.length === 2) return `Ø ${num(r.dims[0])} × ${num(r.dims[1])} mm`;
  return `${r.dims.map((d) => num(d)).join(' × ')} mm`;
}

/* ---------------------------------------------------------------- page shell */

function shell(web) {
  const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
  const header = html.match(/<header>[\s\S]*?<\/header>/)[0];
  const footer = html.match(/<footer>[\s\S]*?<\/footer>/)[0]
    .replace(/\s*·\s*<span id="release"><\/span>/, '')
    .replace('<p style="margin:0">', '<p>');
  return { header, footer };
}

function head({ title, description, canonical, robots, ld, css }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
${robots ? `<meta name="robots" content="${robots}">\n` : ''}<link rel="canonical" href="${canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Lemonergy">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${canonical}">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="${css}style.css">
<link rel="stylesheet" href="${css}battery-pages.css">
<script type="application/ld+json">
${ldJson(ld)}
</script>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
`;
}

function crumbs(items) {
  return `<nav class="bp-crumbs" aria-label="Breadcrumb"><ol>${items.map(([label, href]) => `<li>${href ? `<a href="${href}">${esc(label)}</a>` : `<span aria-current="page">${esc(label)}</span>`}</li>`).join('')}</ol></nav>`;
}
function crumbsLd(items) {
  return { '@type': 'BreadcrumbList', itemListElement: items.map(([name, url], i) => ({ '@type': 'ListItem', position: i + 1, name, item: url })) };
}

/* ---------------------------------------------------------------- battery page */

function keyFigures(r, rec) {
  const m = rec.m || {};
  const first = (q) => (rec.obs || []).find((o) => o.q === q && !o.lower_bound && !o.upper_bound);
  const cond = (q) => { const o = first(q); return o ? BD.conditionShort(o) : ''; };
  const calc = 'calculated by Lemonergy from stated values';
  const figures = [
    ['Capacity', capacityText(r), cond('capacity')],
    [r.vq === 'voltage' ? 'Voltage (as printed)' : 'Nominal voltage', voltageText(r), ''],
    ['Energy', r.wh != null ? `${num(r.wh)} Wh` : null, r.wh != null ? `${calc}: capacity × voltage` : ''],
    ['Mass', massText(r.g), ''],
    ['Specific energy', r.whkg != null ? `${num(r.whkg, 0)} Wh/kg` : null, r.whkg != null && r.whkg_d ? calc : ''],
    ['Energy density', m.whl != null ? `${num(m.whl, 0)} Wh/L` : null, m.whl != null && m.whl_derived ? calc : ''],
    ['Dimensions', dimsText(r), ''],
    ['Continuous discharge', BD.dischargeText(r), cond('max_continuous_discharge_current')],
    ['Cycle life', r.cyc != null ? `${num(r.cyc, 0)} cycles` : r.cyc_b ? `${r.cyc_b[0]} ${num(r.cyc_b[1], 0)} cycles` : null, cond('cycle_life')],
    ['Internal resistance', r.ir != null ? `${num(r.ir)} mΩ` : r.ir_b ? `${r.ir_b[0]} ${num(r.ir_b[1])} mΩ` : null, ''],
    ['Operating temperature', r.tmin != null || r.tmax != null ? `${r.tmin != null ? r.tmin : '?'} to ${r.tmax != null ? r.tmax : '?'} °C` : null, ''],
  ];
  return `<dl class="bp-figures">
${figures.map(([k, v, note]) => `  <div${v == null ? ' class="bp-miss"' : ''}><dt>${k}</dt><dd>${v == null ? 'Not stated' : esc(v)}${note ? `<small>${esc(note)}</small>` : ''}</dd></div>`).join('\n')}
</dl>`;
}

/* Condition codes as a reader says them; the rest lose their unit suffix. */
const CONDITION = {
  voltage_lower_v: 'discharge cut-off voltage', voltage_upper_v: 'charge voltage', temperature_c: 'temperature',
  rate_value: 'rate', rate_unit: 'rate unit', rate_reference_capacity_ah: 'capacity the rate refers to', dod_pct: 'depth of discharge',
  soc_pct: 'state of charge', pulse_duration_s: 'pulse duration', frequency_hz: 'frequency', temperature_reference: 'temperature reference',
  dimension_order: 'order of dimensions', cutoff_current_a: 'cut-off current', end_of_life_pct: 'end-of-life capacity',
};
const conditionWord = (c) => CONDITION[c] || c.replace(/_(c|v|a|ah|pct|s|hz|mm|g)$/, '').replace(/_/g, ' ');
const STAT = { absolute_max: 'absolute maximum', absolute_min: 'absolute minimum' };
const statWord = (s) => STAT[s] || String(s).replace(/_/g, ' ');

function valueText(o) {
  if (typeof o.v === 'number') return BD.valueText(o);
  return `${BD.boundPrefix(o)}${o.v} ${BD.unitText(o.u, o.q)}`.trim();
}

function specTables(rec, GROUPS) {
  const { groups } = BD.recordGroups(rec, GROUPS);
  return groups.map((g) => `<h3>${esc(g.group)}</h3>
<div class="tblwrap"><table class="bp-specs">
<thead><tr><th scope="col">Quantity</th><th scope="col">Value</th><th scope="col">Conditions</th><th scope="col">From the source</th></tr></thead>
<tbody>
${g.rows.map((row) => row.obs.map((o) => {
    const unstated = [...new Set((o.unstated || []).filter((u) => u !== 'rate_unit').map(conditionWord))].join(', ');
    const conditions = [BD.conditionShort(o), o.stat ? `${statWord(o.stat)} value` : ''].filter(Boolean).join(' · ');
    const where = [o.pg ? `page ${o.pg}` : '', o.section ? esc(o.section) : ''].filter(Boolean).join(', ');
    return `<tr><th scope="row">${esc(row.label)}</th><td class="r">${esc(valueText(o))}</td>`
      + `<td>${conditions ? esc(conditions) : '<span class="dash">none recorded</span>'}${unstated ? `<small>Not stated: ${esc(unstated)}</small>` : ''}</td>`
      + `<td>${o.quote ? `<q>${esc(o.quote)}</q>` : ''}${where ? `<small>${where}</small>` : ''}</td></tr>`;
  }).join('\n')).join('\n')}
</tbody></table></div>`).join('\n');
}

function chemistryBlock(rec) {
  const c = rec.chem || {};
  const rows = [['Designation', c.designation], ['Cathode', c.cathode], ['Anode', c.anode], ['Electrolyte', c.electrolyte], ['Separator', c.separator]]
    .filter(([, v]) => v);
  const cls = rec.class || {};
  const classified = [cls.tech, cls.variant, cls.chem].filter(Boolean).join(' · ');
  if (!rows.length && !classified) return '';
  const quote = c.cathode_quote || c.anode_quote;
  return `<section class="bp-section" aria-labelledby="chem-title"><h2 id="chem-title">Chemistry</h2>
<dl class="bp-kv">
${classified ? `<div><dt>Classified as</dt><dd>${esc(classified)}</dd></div>\n` : ''}${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('\n')}
</dl>${quote ? `\n<p class="bp-quote"><q>${esc(quote)}</q></p>` : ''}
</section>`;
}

function curvesBlock(rec) {
  const curves = rec.curves || [];
  if (!curves.length) return '';
  // One line per kind of plot: how many curves, and the range of each condition that varies.
  const plots = new Map();
  for (const c of curves) {
    const key = `${c.yq}|${c.xq}|${(c.cond && c.cond.direction) || ''}`;
    if (!plots.has(key)) plots.set(key, { c, n: 0, cond: new Map() });
    const plot = plots.get(key);
    plot.n += 1;
    for (const [k, v] of Object.entries(c.cond || {})) {
      if (k === 'direction') continue;
      if (!plot.cond.has(k)) plot.cond.set(k, new Set());
      plot.cond.get(k).add(v);
    }
  }
  const unitOf = (k) => ({ temperature_c: ' °C', pulse_duration_s: ' s', soc_pct: ' %', dod_pct: ' %', voltage_lower_v: ' V' }[k] || '');
  const range = (k, values) => {
    const vs = [...values];
    const nums = vs.filter((v) => typeof v === 'number').sort((a, b) => a - b);
    const text = nums.length === vs.length && nums.length > 1 ? `${nums[0]} to ${nums[nums.length - 1]}${unitOf(k)}` : vs.join(', ') + unitOf(k);
    return `${conditionWord(k)} ${text}`;
  };
  const lines = [...plots.values()].map(({ c, n, cond }) => {
    const dir = c.cond && c.cond.direction ? ` (${c.cond.direction})` : '';
    const conds = [...cond.entries()].map(([k, v]) => range(k, v)).join('; ');
    return `<li>${esc(BD.label(c.yq))} against ${esc(BD.label(c.xq).toLowerCase())}${esc(dir)}: ${plural(n, 'curve', 'curves')}${conds ? `, ${esc(conds)}` : ''}</li>`;
  });
  return `<section class="bp-section" aria-labelledby="curves-title"><h2 id="curves-title">Curves in the source</h2>
<p>The source document plots ${plural(curves.length, 'curve', 'curves')}; their points are in the record, and the finder draws them.</p>
<ul>${lines.join('')}</ul>
</section>`;
}

function sourceBlock(r, rec) {
  const s = rec.source || {};
  const doc = s.url ? `<a href="${esc(s.url)}" rel="noopener">${esc(s.title || 'Source document')}</a>` : esc(s.title || 'Not recorded');
  const rows = [
    ['Document', doc],
    ['Kind', esc(BD.srcText(s.kind))],
    // With recorded dates, the lifecycle rows below give revision, document date and retrieval.
    ...(!rec.dates && s.ref ? [['Revision', esc(s.ref)]] : []),
    ...(!rec.dates && s.date ? [['Document date', esc(s.date)]] : []),
    ...(!rec.dates && s.retrieved_at ? [['Retrieved', esc(s.retrieved_at)]] : []),
    ...(s.sha256 ? [['SHA-256', `<code>${esc(s.sha256)}</code>`]] : []),
    ...(!s.url ? [['Link', 'Not published: the document is identified by its SHA-256.']] : []),
    ...(s.note ? [['Note', esc(s.note)]] : []),
    ...BD.lifecycleRows(rec).map(([k, v, url]) => [k.charAt(0).toUpperCase() + k.slice(1), url ? `${esc(v)} (<a href="${esc(url)}" rel="noopener">evidence</a>)` : esc(v)]),
    ['Record', `<a href="${REPO}/blob/main/${esc(rec.file)}">${esc(rec.file)}</a>`],
  ];
  return `<section class="bp-section" aria-labelledby="source-title"><h2 id="source-title">Source and dates</h2>
<dl class="bp-kv">
${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('\n')}
</dl>
</section>`;
}

function similarBlock(r, rows, here) {
  const near = BD.similar(r, rows, 6);
  if (!near.length) return '';
  return `<section class="bp-section" aria-labelledby="similar-title"><h2 id="similar-title">Similar batteries</h2>
<p>Nearest in the library by kind, format, chemistry, capacity and specific energy.</p>
<ul class="bp-similar">
${near.map((x) => `<li><a href="${rel(here, pagePath(x.uid))}">${esc(x.manu === NOT_STATED ? x.model : `${x.manu} ${x.model}`)}</a><span>${esc(shortSpec(x))}${x.v != null ? ` · ${esc(voltageText(x))}` : ''}${x.whkg != null ? ` · ${num(x.whkg, 0)} Wh/kg` : ''}</span></li>`).join('\n')}
</ul>
</section>`;
}

/** A path relative to the page at `from` (both site paths ending in /). */
function rel(from, to) {
  const a = from.split('/').filter(Boolean);
  const b = to.split('/').filter(Boolean);
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  return `${'../'.repeat(a.length - i)}${b.slice(i).join('/')}${b.length > i ? '/' : ''}` || './';
}

function batteryPage(r, rec, ctx) {
  const here = pagePath(r.uid);
  const url = SITE + here;
  const k = KIND[r.kind] || KIND.cell;
  const name = r.manu === NOT_STATED ? r.model : `${r.manu} ${r.model}`;
  const spec = shortSpec(r);
  const idx = indexable(rec);
  const qs = new Set((rec.obs || []).map((o) => o.q)).size;
  const src = BD.srcText(r.src);
  const figs = [capacityText(r), voltageText(r), massText(r.g), dimsText(r)].filter(Boolean).join(', ');
  const title = `${name}: ${spec} specifications | Lemonergy Data`;
  let description = `${name}, ${spec}${figs ? `: ${figs}` : ''}. ${plural(qs, 'value', 'values')} from the ${src}, each with the conditions it was stated at.`;
  if (description.length > 200) description = `${description.slice(0, 197).replace(/\s+\S*$/, '')}…`;
  const maker = r.manu === NOT_STATED ? 'an unnamed maker' : r.manu;
  const lede = `${spec.charAt(0).toUpperCase() + spec.slice(1)} from ${maker}${/\.$/.test(maker) ? '' : '.'} Every value below is read from the ${src}${r.year ? ` (${r.yk === 'release' ? 'released' : 'document dated'} ${r.year})` : ''} and keeps the conditions it was stated at; what the source does not state is marked as not stated.`;
  const trail = [['Data', `${SITE}/data/`], ['Batteries', SITE + BASE], [r.manu, SITE + makerPath(parts(r.uid).maker)], [r.model, url]];
  const ld = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'ItemPage', '@id': `${url}#page`, url, name: title.replace(/ \| Lemonergy Data$/, ''), description,
        isPartOf: { '@type': 'WebSite', name: 'Lemonergy', url: `${SITE}/` },
        about: { '@type': 'Thing', name, description: spec },
        ...(rec.source && rec.source.url ? { isBasedOn: rec.source.url } : {}),
        publisher: { '@type': 'Organization', '@id': `${SITE}/#org`, name: 'Lemonergy', url: `${SITE}/` },
        ...(ctx.dates[r.uid] ? { dateModified: ctx.dates[r.uid] } : {}),
      },
      crumbsLd(trail),
    ],
  };
  const actions = [
    `<a class="btn pri" href="${FINDER}#cmp=${encodeURIComponent(r.uid)}">Compare in the finder</a>`,
    rec.source && rec.source.url ? `<a class="btn" href="${esc(rec.source.url)}" rel="noopener">Source document</a>` : '',
    `<a class="btn" href="${API}${r.uid}">Record as JSON (API)</a>`,
    `<a class="btn ghost" href="${REPO}/issues/new?title=${encodeURIComponent(`Correction: ${name}`)}&amp;body=${encodeURIComponent(`Page: ${url}\nRecord: ${rec.file}\n\nWhat is wrong, and the document that shows it:\n`)}">Report a correction</a>`,
  ].filter(Boolean).join('');
  const stock = r.stock ? `<p class="bp-stock">${esc(BD.stockText(r.stock))}</p>` : '';
  const design = rec.design ? '' : '<p class="bp-note">Not offered in Lemonergy Design, which takes lithium-ion and sodium-ion cells only.</p>';
  return `${head({ title, description, canonical: url, robots: idx.ok ? null : 'noindex, follow', ld, css: '../../' })}${ctx.header}
<main id="main" class="wrap bp-page">
${crumbs([['Data', `${SITE}/data/`], ['Batteries', '../../'], [r.manu, '../'], [r.model, null]])}
<p class="eyebrow">${esc([k.name, BD.techText(r), r.cclass && r.cclass !== r.tech ? r.cclass : null, formatWord(r)].filter(Boolean).join(' · '))}</p>
<h1>${esc(name)}</h1>
<p class="lede">${esc(lede)}</p>
${stock}${keyFigures(r, rec)}
<p class="bp-actions">${actions}</p>
${design}<section class="bp-section" aria-labelledby="specs-title"><h2 id="specs-title">Specifications</h2>
<p>${plural(qs, 'quantity', 'quantities')} stated by the ${esc(src)}, grouped as in the finder. Conditions are the rate, temperature and limits each value was stated at.</p>
${specTables(rec, ctx.GROUPS)}
</section>
${chemistryBlock(rec)}
${curvesBlock(rec)}
${sourceBlock(r, rec)}
${similarBlock(r, ctx.rows, here)}
<p class="bp-more"><a href="../">All ${esc(r.manu === NOT_STATED ? 'batteries whose maker is not stated' : `${r.manu} batteries`)}</a> · <a href="../../">The battery library</a> · <a href="${FINDER}">Find and compare batteries</a></p>
</main>
${ctx.footer}
</body>
</html>
`;
}

/* ---------------------------------------------------------------- maker and index pages */

function table(rows, from) {
  return `<div class="tblwrap"><table class="bp-list" data-sortable>
<thead><tr><th scope="col">Model</th><th scope="col">Kind</th><th scope="col">Technology · chemistry</th><th scope="col">Format</th><th scope="col" class="r">Capacity (Ah)</th><th scope="col" class="r">Voltage (V)</th><th scope="col" class="r">Mass (g)</th><th scope="col">Dimensions (mm)</th><th scope="col" class="r">Wh/kg</th></tr></thead>
<tbody>
${rows.map((x) => `<tr><th scope="row"><a href="${rel(from, pagePath(x.uid))}">${esc(x.model)}</a></th><td>${esc((KIND[x.kind] || KIND.cell).name)}</td><td>${esc([BD.techText(x), x.cclass && x.cclass !== x.tech ? x.cclass : null].filter(Boolean).join(' · ') || 'Not stated')}</td><td>${esc(formatWord(x) || '–')}</td><td class="r" data-v="${x.ah == null ? '' : x.ah}">${num(x.ah) || '–'}</td><td class="r" data-v="${x.v == null ? '' : x.v}">${num(x.v) || '–'}</td><td class="r" data-v="${x.g == null ? '' : x.g}">${num(x.g) || '–'}</td><td>${esc(x.dims ? (x.shape === 'cyl' && x.dims.length === 2 ? `Ø ${x.dims.map((d) => num(d)).join(' × ')}` : x.dims.map((d) => num(d)).join(' × ')) : '–')}</td><td class="r" data-v="${x.whkg == null ? '' : x.whkg}">${x.whkg == null ? '–' : num(x.whkg, 0)}</td></tr>`).join('\n')}
</tbody></table></div>`;
}

/** "35 rechargeable cells, 10 battery modules": label(x) gives [singular, plural]; unlabelled rows are counted as not stated. */
function countsText(rows, label, unstated = 'not stated') {
  const c = new Map();
  let missing = 0;
  rows.forEach((x) => {
    const k = label(x);
    if (!k) { missing += 1; return; }
    const id = k[1];
    if (!c.has(id)) c.set(id, { k, n: 0 });
    c.get(id).n += 1;
  });
  const parts = [...c.values()].sort((a, b) => b.n - a.n).map(({ k, n }) => `${n.toLocaleString('en')} ${n === 1 ? k[0] : k[1]}`);
  if (missing && parts.length) parts.push(`${missing.toLocaleString('en')} ${unstated}`);
  return parts.join(', ');
}
const kindLabel = (x) => { const k = KIND[x.kind] || KIND.cell; return [k.word === 'cell' ? 'rechargeable cell' : k.word, k.plural]; };
const techLabel = (x) => (x.tech ? [x.tech, x.tech] : null);
const sourceLabel = (x) => [BD.srcText(x.src), `${BD.srcText(x.src)}s`];

function makerPage(slug, rows, ctx) {
  const here = makerPath(slug);
  const url = SITE + here;
  const maker = rows[0].manu;
  const unnamed = maker === NOT_STATED;
  const heading = unnamed ? 'Batteries whose maker is not stated' : `${maker} batteries`;
  const kinds = countsText(rows, kindLabel);
  const techs = countsText(rows, techLabel, 'with the technology not stated');
  const indexed = rows.filter((x) => ctx.index[x.uid]).length;
  // Documents, not records: one catalogue page can hold a thousand rows.
  const docs = new Map();
  for (const x of rows) docs.set(x.url || x.title || x.uid, x);
  const sources = countsText([...docs.values()], sourceLabel);
  const description = unnamed
    ? `${plural(rows.length, 'battery', 'batteries')} in the Lemonergy library whose source does not name a maker, with their specifications and sources.`
    : `${plural(rows.length, `${maker} battery`, `${maker} batteries`)}: ${kinds}. Capacity, voltage, mass, size and specific energy of each, with its source.`;
  const title = `${heading}: ${plural(rows.length, 'model', 'models')} with specifications | Lemonergy Data`;
  const sorted = [...rows].sort((a, b) => (a.kind > b.kind ? 1 : a.kind < b.kind ? -1 : (a.ah || 0) - (b.ah || 0) || a.model.localeCompare(b.model)));
  const trail = [['Data', `${SITE}/data/`], ['Batteries', SITE + BASE], [unnamed ? NOT_STATED : maker, url]];
  const ld = { '@context': 'https://schema.org', '@graph': [
    { '@type': 'CollectionPage', '@id': `${url}#page`, url, name: heading, description, isPartOf: { '@type': 'WebSite', name: 'Lemonergy', url: `${SITE}/` },
      ...(unnamed ? {} : { about: { '@type': 'Organization', name: maker } }) },
    crumbsLd(trail)] };
  return `${head({ title, description, canonical: url, robots: unnamed ? 'noindex, follow' : null, ld, css: '../' })}${ctx.header}
<main id="main" class="wrap bp-page">
${crumbs([['Data', `${SITE}/data/`], ['Batteries', '../'], [unnamed ? NOT_STATED : maker, null]])}
<p class="eyebrow">Battery library · ${unnamed ? 'maker not stated' : 'manufacturer'}</p>
<h1>${esc(heading)}</h1>
<p class="lede">${esc(`${plural(rows.length, 'record', 'records')} in the library: ${kinds}${techs ? `; ${techs}` : ''}. Taken from ${sources}. Each model has its own page with every value, the conditions it was stated at and its source.`)}</p>
${indexed < rows.length && !unnamed ? `<p class="bp-note">${indexed ? `${plural(indexed, 'page', 'pages')} of ${rows.length.toLocaleString('en')} ${indexed === 1 ? 'states' : 'state'} more than capacity, voltage, size and mass.` : 'These records state capacity, voltage, size and mass; this table is the place to compare them.'} Select a column heading to sort.</p>\n` : ''}${table(sorted, here)}
<p class="bp-more"><a href="../">The battery library</a> · <a href="${FINDER}">Find and compare batteries</a></p>
</main>
${ctx.footer}
<script src="../battery-pages.js" defer></script>
</body>
</html>
`;
}

function indexPage(groups, ctx) {
  const url = SITE + BASE;
  const all = ctx.rows;
  const makers = [...groups.entries()].map(([slug, rows]) => ({ slug, rows, maker: rows[0].manu }))
    .sort((a, b) => (a.maker === NOT_STATED) - (b.maker === NOT_STATED) || a.maker.localeCompare(b.maker));
  const description = `${plural(all.length, 'battery', 'batteries')} from ${plural(makers.filter((m) => m.maker !== NOT_STATED).length, 'maker', 'makers')}: cells, primary cells, modules and packs, each with its specifications, the conditions they were stated at and the source document.`;
  const title = 'Battery library: specifications with their conditions and sources | Lemonergy Data';
  const ld = { '@context': 'https://schema.org', '@graph': [
    { '@type': 'CollectionPage', '@id': `${url}#page`, url, name: 'Battery library', description, isPartOf: { '@type': 'WebSite', name: 'Lemonergy', url: `${SITE}/` } },
    crumbsLd([['Data', `${SITE}/data/`], ['Batteries', url]])] };
  const rowsHtml = makers.map(({ slug, rows, maker }) => `<tr><th scope="row"><a href="${slug}/">${esc(maker)}</a></th><td class="r" data-v="${rows.length}">${rows.length.toLocaleString('en')}</td><td>${esc(countsText(rows, kindLabel))}</td><td>${esc(countsText(rows, techLabel) || 'Not stated')}</td></tr>`).join('\n');
  return `${head({ title, description, canonical: url, robots: null, ld, css: '' })}${ctx.header}
<main id="main" class="wrap bp-page">
${crumbs([['Data', `${SITE}/data/`], ['Batteries', null]])}
<p class="eyebrow">Battery library</p>
<h1>Battery specifications with their conditions and sources</h1>
<p class="lede">${esc(description)} Where a source says nothing, the page says so instead of filling the gap.</p>
<p class="bp-actions"><a class="btn pri" href="${FINDER}">Find and compare batteries</a><a class="btn" href="${REPO}">The open library on GitHub</a></p>
<section class="bp-section" aria-labelledby="makers-title"><h2 id="makers-title">By maker</h2>
<div class="tblwrap"><table class="bp-list" data-sortable>
<thead><tr><th scope="col">Maker</th><th scope="col" class="r">Records</th><th scope="col">Kinds</th><th scope="col">Technologies</th></tr></thead>
<tbody>
${rowsHtml}
</tbody></table></div>
</section>
</main>
${ctx.footer}
<script src="battery-pages.js" defer></script>
</body>
</html>
`;
}

function sitemap(entries) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries.map(({ loc, lastmod }) => `<url><loc>${loc}</loc>${lastmod ? `<lastmod>${lastmod}</lastmod>` : ''}</url>`).join('\n')}
</urlset>
`;
}

/** The newest full date a record carries: when its source was retrieved or its lifecycle checked. */
function lastDate(rec) {
  const d = rec.dates || {};
  const dates = [d.source_retrieved, d.lifecycle_checked].map((x) => x && x.precision === 'day' && x.date).filter(Boolean);
  if (rec.source && /^\d{4}-\d{2}-\d{2}$/.test(rec.source.retrieved_at || '')) dates.push(rec.source.retrieved_at);
  return dates.sort().pop() || null;
}

/** Every page, as { path relative to the output directory: text }. */
function build({ data = path.join(ROOT, 'web', 'data'), web = path.join(ROOT, 'web') } = {}) {
  const read = (f) => JSON.parse(fs.readFileSync(path.join(data, f), 'utf8'));
  const rows = read('cells.json').filter((r) => r.kind !== 'component');
  const GROUPS = read('registry.json').GROUPS;
  const records = new Map();
  for (const f of fs.readdirSync(path.join(data, 'records'))) {
    for (const rec of JSON.parse(fs.readFileSync(path.join(data, 'records', f), 'utf8'))) records.set(rec.uid, rec);
  }
  const { header, footer } = shell(web);
  const index = {};
  const dates = {};
  for (const r of rows) {
    const rec = records.get(r.uid);
    if (!rec) throw new Error(`${r.uid}: no full record in ${data}/records`);
    index[r.uid] = indexable(rec).ok;
    dates[r.uid] = lastDate(rec);
  }
  const ctx = { rows, GROUPS, header, footer, index, dates };
  const files = {};
  const groups = new Map();
  for (const r of rows) {
    const p = parts(r.uid);
    if (!groups.has(p.maker)) groups.set(p.maker, []);
    groups.get(p.maker).push(r);
    files[`${p.maker}/${p.model}/index.html`] = batteryPage(r, records.get(r.uid), ctx);
  }
  for (const [slug, list] of groups) files[`${slug}/index.html`] = makerPage(slug, list, ctx);
  files['index.html'] = indexPage(groups, ctx);
  const entries = [{ loc: SITE + BASE }];
  for (const [slug, list] of [...groups].sort()) {
    if (list[0].manu !== NOT_STATED) entries.push({ loc: SITE + makerPath(slug) });
    for (const r of [...list].sort((a, b) => a.uid.localeCompare(b.uid))) if (index[r.uid]) entries.push({ loc: SITE + pagePath(r.uid), lastmod: dates[r.uid] });
  }
  files['sitemap.xml'] = sitemap(entries);
  files['style.css'] = fs.readFileSync(path.join(web, 'style.css'), 'utf8');
  files['battery-pages.css'] = fs.readFileSync(path.join(web, 'battery-pages.css'), 'utf8');
  files['battery-pages.js'] = fs.readFileSync(path.join(web, 'battery-pages.js'), 'utf8');
  const stats = { batteries: rows.length, indexed: Object.values(index).filter(Boolean).length, makers: groups.size, sitemap: entries.length };
  return { files, stats };
}

function main() {
  const argv = process.argv.slice(2);
  const opt = (name, fallback) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : fallback; };
  const out = opt('--out', path.join(ROOT, 'web', 'batteries'));
  const { files, stats } = build({ data: opt('--data', path.join(ROOT, 'web', 'data')) });
  fs.rmSync(out, { recursive: true, force: true });
  for (const [rel, text] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(out, rel)), { recursive: true });
    fs.writeFileSync(path.join(out, rel), text);
  }
  console.log(`wrote ${path.relative(ROOT, out) || out}/: ${stats.batteries} battery pages (${stats.indexed} indexable), `
    + `${stats.makers} maker pages, sitemap of ${stats.sitemap} pages; index rule: ${INDEX_RULE}`);
}

module.exports = { build, indexable, pagePath, rel, shortSpec, INDEX_RULE, BASIC, MIN_QUANTITIES };
if (require.main === module) main();
