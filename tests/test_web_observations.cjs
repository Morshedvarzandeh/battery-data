// The finder's record view and Markdown export must keep every repeated rating
// with its own conditions, state what the source leaves unstated, and keep
// launch, partial-precision, conflicting and future dates distinct.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const BD = require(path.join(root, 'web/app.js'));

const toRecord = (doc, extra) => ({
  uid: doc.product.uid, cell: `${doc.product.manufacturer} ${doc.product.model_number}`, manu: doc.product.manufacturer,
  model: doc.product.model_number, kind: doc.product.kind, fmt: doc.product.form_factor || '', chem: doc.chemistry || {},
  source: { title: doc.source.title, url: doc.source.url, ref: doc.source.revision, note: doc.source.note },
  obs: doc.observations.map(o => ({ q: o.quantity, v: o.value, u: o.unit, stat: o.statistic,
    cond: Object.fromEntries(Object.entries(o.conditions || {}).filter(([k]) => k !== 'unstated')),
    unstated: (o.conditions && o.conditions.unstated) || [], quote: o.locator.quote, pg: o.locator.page, section: o.locator.section, src: 'datasheet' })),
  lifecycle: doc.lifecycle, bms: doc.bms, file: 'test', ...extra });

// 1. Two conductor-dependent carry ratings on one contactor survive as two rows.
const batch = JSON.parse(fs.readFileSync(path.join(root, 'review/batches/2026-09-16-electrical-components.json')));
const gv = toRecord(batch.candidates.find(c => c.document.product.model_number === 'GV211BAX').document);
const GROUPS = { Contactors: ['continuous_carry_current', 'contact_voltage_rating'] };
assert.equal(BD.known(gv).continuous_carry_current.length, 2);
const { groups, absent } = BD.recordGroups(gv, GROUPS);
const carry = groups[0].rows.find(r => r.q === 'continuous_carry_current');
assert.equal(carry.obs.length, 2);
const md = BD.recordMarkdown(gv, GROUPS);
assert.match(md, /\| 100 \| A \|/); assert.match(md, /\| 150 \| A \|/);
assert.match(md, /8 AWG/); assert.match(md, /4 AWG/);
assert.match(md, /power_terminal_temperature_max_c/);
assert.match(md, /not stated: temperature_c/);
assert.ok(absent.every(q => !BD.known(gv)[q]), 'absent list names only quantities the record lacks');
console.log('Record view and Markdown keep both conductor-dependent ratings and their conditions');

// 2. BMS dates: launch day, year-only release, conflict and announced-only stay distinct.
const bmsBatch = JSON.parse(fs.readFileSync(path.join(root, 'review/batches/2026-10-09-bms-market.json')));
for (const [model, expected, absentText] of [
  ['c-BMS24X', '2023-05-17 (day precision; launch announcement)', ''],
  ['Lithiumate Pro Master', '2007 (year precision; commercial release)', '2007-01-01'],
  ['G5 High-Voltage BMS', 'Conflicting dates; unresolved', ''],
  ['G5 Plus High-Voltage BMS', 'Announced; not released', '']]) {
  const d = bmsBatch.candidates.find(e => e.document.product.model_number === model).document;
  const rec = toRecord(d);
  const rows = BD.lifecycleRows(rec).map(r => r[1]);
  assert.ok(rows.some(v => v.includes(expected)), `${model}: ${expected}`);
  const text = BD.recordMarkdown(rec, {});
  assert.ok(text.includes(expected), expected);
  if (absentText) assert.ok(!text.includes(absentText), absentText);
  assert.ok(text.includes('([evidence](https://'));
}
console.log('BMS display/export distinguish launch, partial release years, conflicts and future availability');

// 3. A record with only a document-year date says so without inventing a day.
const dated = { cell: 'Historical cell', manu: 'Example', chem: {}, fmt: '', obs: [], source: { title: 'Historical specification', url: 'https://example.com/spec' },
  dates: { source_document: { date: '2013', precision: 'year' }, source_revision: 'Rev A', source_retrieved: { date: '2026-09-21', precision: 'day' },
    lifecycle_checked: { date: null, precision: null }, release: { status: 'not_researched' }, events: [] }, file: 'test' };
const datedRows = Object.fromEntries(BD.lifecycleRows(dated).map(([k, v]) => [k, v]));
assert.equal(datedRows['source document date'], '2013 (year precision)');
assert.equal(datedRows['product lifecycle checked'], 'Not recorded');
assert.equal(datedRows['product release'], 'Not researched');
assert.ok(!BD.recordMarkdown(dated, {}).includes('2013-01-01'));
console.log('Year-precision dates stay year-precision');

// 4. Short conditions, CSV and similarity helpers.
assert.equal(BD.conditionShort({ cond: { rate_value: 0.2, rate_unit: 'C', temperature_c: 25, voltage_lower_v: 2.5 } }), '0.2 C · 25 °C · to 2.5 V');
const rows = [
  { uid: 'a', manu: 'M', model: 'A', kind: 'cell', chem: 'NCA', fmt: 'cylindrical', ah: 4.9, v: 3.6, vq: 'nominal_voltage', g: 69, wh: 17.6, whkg: 256, whkg_d: true, depth: 4, n: 6, src: 'datasheet', dims: null },
  { uid: 'b', manu: 'M', model: 'B, "big"', kind: 'cell', chem: 'NCA', fmt: 'cylindrical', ah: 5.0, v: 3.6, vq: 'nominal_voltage', g: 70, wh: 18, whkg: 257, whkg_d: false, depth: 6, n: 9, src: 'datasheet', dims: [21, 70] },
  { uid: 'c', manu: 'M', model: 'C', kind: 'cell', chem: 'LFP', fmt: 'prismatic_hardcase', ah: 280, v: 3.2, vq: 'nominal_voltage', g: 5400, wh: 896, whkg: 166, whkg_d: true, depth: 3, n: 4, src: 'manufacturer_web', dims: null }];
const csv = BD.toCSV(rows).split('\n');
assert.equal(csv.length, 4);
assert.match(csv[0], /^uid,manufacturer,model,kind/);
assert.ok(csv[2].includes('"B, ""big"""'), 'CSV quotes commas and doubles quotes');
assert.ok(csv[1].includes('21 x 70') === false && csv[2].includes('21 x 70'));
assert.deepEqual(BD.similar(rows[0], rows, 2).map(r => r.uid), ['b', 'c']);
console.log('CSV export and similarity helpers behave');

// 5. Technology and chemistry are separate classes, and search understands both.
{
  const tax = JSON.parse(fs.readFileSync(path.join(root, 'web/data/technologies-and-chemistries.json')));
  const idx = BD.searchIndex(tax);
  const sodium = { model: 'JNC32700S', manu: 'Maker not stated', chem: 'Sodium-ion', tech: 'Sodium-ion', tvar: null, cclass: 'NFPP', kind: 'cell' };
  const pana = { model: 'NCR-18650GA', manu: 'Panasonic', chem: null, tech: null, tvar: null, cclass: null, kind: 'cell' };
  const lfp = { model: 'LF105', manu: 'EVE Energy', chem: 'LFP', tech: 'Lithium-ion', tvar: null, cclass: 'LFP', kind: 'cell' };
  const lipo = { model: '101723', manu: 'Harding Energy', chem: 'Lithium polymer', tech: 'Lithium-ion', tvar: 'Lithium polymer', cclass: null, kind: 'cell' };
  const q = s => BD.parseQuery(s, idx);
  assert.ok(BD.matchesQuery(sodium, q('na')), '"na" is sodium-ion');
  assert.ok(!BD.matchesQuery(pana, q('na')), '"na" is a class word, not a substring of Panasonic');
  assert.ok(BD.matchesQuery(pana, q('panasonic')));
  assert.deepEqual(q('lead acid').map(t => t.alias), ['lead acid'], 'two-word class names are one term');
  assert.ok([...q('AGM')[0].keys].includes('v:Lead-acid' + BD.SEP + 'AGM'), 'AGM is a lead-acid variant');
  assert.ok(BD.matchesQuery(lfp, q('li-ion lf105')) && BD.matchesQuery(lfp, q('LiFePO4')));
  assert.ok(!BD.matchesQuery(lfp, q('nmc')));
  assert.ok(BD.matchesQuery(sodium, q('nfpp')) && !BD.matchesQuery(sodium, q('lithium')));
  assert.ok(BD.matchesQuery(lipo, q('lipo')) && BD.matchesQuery(lipo, q('li')) && !BD.matchesQuery(lfp, q('lipo')));
  const li = [...q('li')[0].keys];
  assert.ok(li.includes('t:Lithium-ion') && li.includes('t:Lithium primary'), '"li" names every lithium technology');
  assert.ok(!idx.map.has('pb'), '"pb" stays free: the sodium sheets use it for Prussian blue');
  const csv = BD.toCSV([sodium]).split('\n');
  assert.ok(csv[0].includes('technology,technology_variant,chemistry,chemistry_as_printed'));
  assert.ok(csv[1].includes('Sodium-ion,,NFPP,Sodium-ion'));
  console.log('Technology and chemistry stay separate; search understands both');
}

// 6. Lead-acid: its own ratings are labelled, the search finds the variants, and
//    every row says whether Lemonergy Design may use it (never, for lead-acid).
{
  const tax = JSON.parse(fs.readFileSync(path.join(root, 'web/data/technologies-and-chemistries.json')));
  const idx = BD.searchIndex(tax);
  const q = s => BD.parseQuery(s, idx);
  const agm = { model: 'BAT412800084', manu: 'Victron Energy', chem: 'Lead-acid AGM', tech: 'Lead-acid', tvar: 'AGM', cclass: 'PbO2/Pb', kind: 'module', nodesign: true };
  const efb = { model: 'VARTA Dynamic EFB 572501076', manu: 'Clarios', chem: 'Lead-acid EFB', tech: 'Lead-acid', tvar: 'EFB', cclass: 'PbO2/Pb', kind: 'module', nodesign: true };
  const lfp = { model: 'LF105', manu: 'EVE Energy', chem: 'LFP', tech: 'Lithium-ion', tvar: null, cclass: 'LFP', kind: 'cell' };
  assert.ok(BD.matchesQuery(agm, q('agm')) && !BD.matchesQuery(efb, q('agm')));
  assert.ok(BD.matchesQuery(efb, q('enhanced flooded')) && BD.matchesQuery(agm, q('lead acid')) && BD.matchesQuery(agm, q('victron')));
  assert.ok(BD.matchesQuery(agm, q('pbo2')) && !BD.matchesQuery(lfp, q('lead')));
  assert.equal(tax.technologies.find(t => t.name === 'Lead-acid').design, false, 'lead-acid is never offered to Design');
  assert.deepEqual(tax.technologies.filter(t => t.design).map(t => t.name), ['Lithium-ion', 'Sodium-ion']);
  const csv = BD.toCSV([agm, lfp]).split('\n');
  const col = csv[0].split(',').indexOf('lemonergy_design');
  assert.ok(col > 0);
  assert.equal(csv[1].split(',')[col], 'no'); assert.equal(csv[2].split(',')[col], 'yes');
  const doc = JSON.parse(fs.readFileSync(path.join(root, 'contrib/cells/victron-energy/bat412800084.yaml')));
  const rec = toRecord(doc);
  const G = { Ratings: ['cranking_current', 'reserve_capacity', 'float_charge_voltage', 'cyclic_charge_voltage'] };
  const rows = BD.recordGroups(rec, G).groups[0].rows;
  assert.deepEqual(rows.map(r => r.label), ['Cranking current (CCA, MCA, …)', 'Reserve capacity', 'Float charge voltage', 'Cyclic (absorption) charge voltage']);
  assert.equal(rows.find(r => r.q === 'cyclic_charge_voltage').obs.length, 4, 'normal and fastest-recharge ranges both kept');
  assert.match(BD.recordMarkdown(rec, G), /`cranking_current` \| 400 \| A \| temperature_c: -17.8; extra: \{"rating":"CCA"/);
  console.log('Lead-acid ratings are labelled, its variants are searchable, and Design is marked off');
}
