// The battery pages (tools/build_battery_pages.cjs): one per battery, each a
// complete page with its own canonical address; indexed only when its record
// is substantial; every value on its page with its conditions; links that
// resolve; and nothing that reads "undefined" or "NaN".
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..');
const BD = require(path.join(root, 'web/app.js'));
const pages = require(path.join(root, 'tools/build_battery_pages.cjs'));

// The finder's data first, built from contrib/ into a temporary directory.
const data = fs.mkdtempSync(path.join(os.tmpdir(), 'battery-pages-'));
const py = spawnSync(process.env.PYTHON || 'python3', [path.join(root, 'tools/build_web_data.py'), '--out', data], { encoding: 'utf8' });
assert.equal(py.status, 0, py.stderr);
const rows = JSON.parse(fs.readFileSync(path.join(data, 'cells.json'), 'utf8')).filter((r) => r.kind !== 'component');
const records = new Map();
for (const f of fs.readdirSync(path.join(data, 'records'))) for (const rec of JSON.parse(fs.readFileSync(path.join(data, 'records', f), 'utf8'))) records.set(rec.uid, rec);
const { files, stats } = pages.build({ data });
const SITE = 'https://lemonergy.com/data/batteries/';
const meta = (html, name) => (html.match(new RegExp(`<meta name="${name}" content="([^"]*)">`)) || [])[1];
const ld = (html) => JSON.parse(html.match(/<script type="application\/ld\+json">\n([\s\S]*?)\n<\/script>/)[1]);

// 1. One page per battery, at the path its uid names, and the finder links to it.
assert.equal(stats.batteries, rows.length);
for (const r of rows) {
  const [, maker, model] = r.uid.split('/');
  const html = files[`${maker}/${model}/index.html`];
  assert.ok(html, `${r.uid} has a page`);
  assert.equal(pages.pagePath(r.uid), `/data/batteries/${maker}/${model}/`);
  assert.equal(BD.pageUrl(r.uid), `${SITE}${maker}/${model}/`, 'the finder links the same address');
  assert.match(html, new RegExp(`<link rel="canonical" href="${SITE}${maker}/${model}/">`));
}
assert.equal(BD.pageUrl('component/acme/fuse-1'), null, 'components have no battery page');
console.log(`One page per battery (${rows.length}), at its uid's path`);

// 2. Indexed only when substantial; the sitemap lists exactly the indexed pages.
const sitemap = files['sitemap.xml'];
const listed = new Set([...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]));
let indexed = 0;
for (const r of rows) {
  const rec = records.get(r.uid);
  const [, maker, model] = r.uid.split('/');
  const html = files[`${maker}/${model}/index.html`];
  const qs = new Set(rec.obs.map((o) => o.q));
  const expect = rec.manu !== 'Maker not stated' && qs.size >= pages.MIN_QUANTITIES && [...qs].some((q) => !pages.BASIC.has(q));
  assert.equal(pages.indexable(rec).ok, expect, r.uid);
  assert.equal(meta(html, 'robots'), expect ? undefined : 'noindex, follow', `${r.uid}: robots`);
  assert.equal(listed.has(`${SITE}${maker}/${model}/`), expect, `${r.uid}: in the sitemap only if indexed`);
  if (expect) indexed += 1;
}
assert.equal(indexed, stats.indexed);
assert.ok(indexed > 100 && indexed < rows.length / 2, `${indexed} indexed: the rule keeps catalogue rows out`);
for (const loc of listed) {
  const rel = loc.slice(SITE.length);
  assert.ok(files[`${rel}index.html`], `${loc} is a page`);
  assert.equal(meta(files[`${rel}index.html`], 'robots'), undefined, `${loc} is not marked noindex`);
}
assert.ok(listed.has(SITE), 'the library index is listed');
assert.equal(meta(files['maker-not-stated/index.html'], 'robots'), 'noindex, follow');
console.log(`Indexed only when substantial: ${indexed} battery pages, ${listed.size} in the sitemap`);

// 3. Every value of a record is on its page, with its conditions; the key figures say what is calculated.
for (const uid of ['cell/catl/302ah-lifepo4', 'module/trojan-battery/t-105']) {
  const rec = records.get(uid);
  const [, maker, model] = uid.split('/');
  const html = files[`${maker}/${model}/index.html`];
  const specs = html.slice(html.indexOf('id="specs-title"'), html.indexOf('</section>', html.indexOf('id="specs-title"')));
  assert.equal((specs.match(/<tr><th scope="row">/g) || []).length, rec.obs.length, `${uid}: every observation is a row`);
  for (const o of rec.obs) if (o.quote) assert.ok(specs.includes(o.quote.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')), `${uid}: quote for ${o.q}`);
  assert.match(html, /calculated by Lemonergy from stated values: capacity × voltage/);
}
const catl = files['catl/302ah-lifepo4/index.html'];
assert.match(catl, /Not stated: discharge cut-off voltage/, 'unstated conditions read as words');
assert.match(catl, /Not published: the document is identified by its SHA-256\./, 'a document without a link says so');
assert.match(catl, /Pulse discharge current against state of charge \(discharge\): 20 curves/, 'curves are summarised, not listed one by one');
const lipol = files[Object.keys(files).find((f) => f.startsWith('lipol-battery/lp654045'))];
assert.equal(meta(lipol, 'robots'), 'noindex, follow');
assert.match(lipol, /<dt>Mass<\/dt><dd>Not stated<\/dd>/, 'a key figure the source does not state is marked, never filled');
console.log('Every value is on its page with its conditions; gaps are marked');

// 4. Markup, titles, links and text are well-formed on every page.
const titles = new Map();
for (const [file, html] of Object.entries(files)) {
  if (!file.endsWith('.html')) continue;
  assert.doesNotMatch(html, /\bundefined\b|\bNaN\b|>null</, `${file}: no undefined, NaN or null in the text`);
  const graph = ld(html)['@graph'];
  assert.ok(graph.some((x) => x['@type'] === 'BreadcrumbList'), `${file}: breadcrumbs`);
  const description = meta(html, 'description');
  assert.ok(description && description.length >= 50 && description.length <= 200, `${file}: description of ${description && description.length}`);
  const title = html.match(/<title>([^<]+)<\/title>/)[1];
  if (!meta(html, 'robots')) {
    assert.ok(!titles.has(title), `${file}: title also used by ${titles.get(title)}`);
    titles.set(title, file);
  }
  // Every link inside the library resolves to a generated page or asset.
  const dir = path.posix.dirname(file);
  for (const [, href] of html.matchAll(/(?:href|src)="([^"#:?]+)"/g)) {
    if (href.startsWith('/')) continue;
    const target = path.posix.normalize(path.posix.join(dir, href));
    assert.ok(files[target] || files[path.posix.join(target, 'index.html')], `${file}: ${href} resolves`);
  }
}
// 5. Every value is traceable: one sources page lists each document once with the records it
//    supports, each maker page lists its documents, and each battery page gives a citation.
const sourcesHtml = files['sources/index.html'];
assert.ok(sourcesHtml, 'the sources page exists');
assert.ok(listed.has(`${SITE}sources/`), 'the sources page is in the sitemap');
assert.equal(meta(sourcesHtml, 'robots'), undefined, 'the sources page is indexable');
const docKeys = new Map();
for (const r of rows) {
  const key = `${r.uid.split('/')[1]}|${pages.docKey(records.get(r.uid).source || {}, r.uid)}`;
  docKeys.set(key, (docKeys.get(key) || 0) + 1);
}
assert.equal(stats.documents, docKeys.size);
const sourceRows = [...sourcesHtml.matchAll(/<tr><th scope="row">[\s\S]*?<\/tr>/g)].map((m) => m[0]);
assert.equal(sourceRows.length, docKeys.size, 'each document is listed once');
const supported = sourceRows.reduce((n, row) => n + Number(row.match(/data-v="(\d+)"/)[1]), 0);
assert.equal(supported, rows.length, 'the documents account for every battery');
for (const [file, html] of Object.entries(files)) {
  const m = file.match(/^([^/]+)\/index\.html$/);
  if (!m || m[1] === 'sources') continue;
  const own = [...docKeys.keys()].filter((k) => k.startsWith(`${m[1]}|`)).length;
  const section = html.slice(html.indexOf('id="sources-title"'), html.indexOf('id="models-title"'));
  assert.equal((section.match(/<tr><th scope="row">/g) || []).length, own, `${file}: its ${own} documents`);
}
for (const r of rows) {
  const [, maker, model] = r.uid.split('/');
  const html = files[`${maker}/${model}/index.html`];
  const cite = (html.match(/<p class="bp-cite">([^<]*)<\/p>/) || [])[1];
  assert.ok(cite && cite.endsWith(`record ${r.uid}: ${SITE}${maker}/${model}/`), `${r.uid}: a citation naming the record and its page`);
  assert.equal(cite, pages.citation(r, records.get(r.uid)).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'));
  assert.ok(html.includes('<a href="../../sources/">All sources of the library</a>'), `${r.uid}: links the sources page`);
}
assert.match(files['catl/302ah-lifepo4/index.html'], /CATL\. “CATL 302Ah 3\.22V LiFePO4 power battery — Product Specification”, datasheet, CATL product specification, C-sample stage, 2022\. Not public; SHA-256 2f4be57c/);
assert.doesNotMatch(lipol, /Ltd\.\. /, 'no doubled full stop after a maker that ends in one');
console.log(`Every value is traceable: ${docKeys.size} documents on the sources page, a citation on every battery page`);

// The licence line covers the values, not the quotes: those stay their publishers'.
for (const [file, html] of Object.entries(files)) {
  if (!file.endsWith('.html')) continue;
  assert.match(html, /Values CC BY 4\.0; quoted text and source documents belong to their publishers/, `${file}: licence line`);
  assert.doesNotMatch(html, /Data CC BY 4\.0/, `${file}: no blanket data licence over quoted text`);
}
const item = ld(catl)['@graph'].find((x) => x['@type'] === 'ItemPage');
assert.equal(item.url, `${SITE}catl/302ah-lifepo4/`);
assert.equal(item.about.name, 'CATL 302Ah LiFePO4');
console.log('Markup, titles, descriptions and links are well-formed on every page');

fs.rmSync(data, { recursive: true, force: true });
