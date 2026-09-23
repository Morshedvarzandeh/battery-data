// A selected product the columns cannot describe still gets a report: the
// bounds its source printed, and every value it states, with conditions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'web/index.html'), 'utf8');
const between = (a, b) => page.slice(page.indexOf(a), page.indexOf(b));
const blob = name => JSON.parse(page.match(new RegExp(`const _${name} = (.*);\\n/\\* END GENERATED: ${name}`))[1]);
const source = between('const BOUNDED=', '/* ---------- public library snapshot')
  + between('/* ---------- cell sheet ---------- */', '/* ---------- chemistry and components layer');

class Node {
  constructor(tag) { Object.assign(this, {tag, children: [], attrs: {}, style: {}, className: '', value: '', own: ''}); }
  append(...items) { this.children.push(...items); }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
  set innerHTML(_) { this.children = []; this.own = ''; }
  set textContent(v) { this.children = []; this.own = String(v); }
  get textContent() { return [this.own, ...this.children.map(c => typeof c === 'string' ? c : c.textContent)].join(' '); }
}
const nodes = new Map();
const document = {
  createElement: tag => new Node(tag),
  createTextNode: t => Object.assign(new Node('#text'), {own: String(t)}),
  querySelector: s => nodes.get(s) || nodes.set(s, new Node('div')).get(s),
};
const registry = blob('REGISTRY');
vm.runInNewContext(source + `
const text = s => $(s).textContent;
const bounded = ROWS.find(r => r.bound.ah && r.bound.ah.lower_bound && ["whkg","whl","wkg"].every(k => !hasNum(r, k)));
const full = ROWS.find(r => ["whkg","whl","wkg"].every(k => hasNum(r, k)));
assert.ok(bounded && full, 'fixtures: a cell known only by a capacity bound, and one with every derived figure');
const ah = cellText(bounded, 'ah', 2);
assert.match(ah, /^≥ \\d/);

$('#q').value = bounded.cell.toLowerCase(); drawTable();
assert.ok(text('#tbl tbody').includes(ah), 'the compare row shows the bound, not a dash');
$('#q').value = '';

SEL.add(bounded.cell); drawReport();
let rep = text('#rep');
assert.doesNotMatch(rep, /— Wh\\/kg/, 'no leader is named next to a missing figure');
LEADS.forEach(([k]) => assert.equal(leaderOf([bounded], k), null));
assert.match(rep, /This cell has no specific energy/);
assert.ok(rep.includes(ah));
assert.match(rep, /Recorded specifications/);
bounded.rec.obs.forEach(o => assert.ok(rep.includes(o.q) && rep.includes(asStated(o)), o.q));

const md = repMarkdown();
assert.ok(md.includes('## Recorded specifications') && md.includes('### ' + bounded.cell));
bounded.rec.obs.forEach(o => assert.ok(md.includes('\`' + o.q + '\`'), o.q));
assert.ok(toCSV(repRows()).includes(ah));

SEL.add(full.cell); drawReport(); rep = text('#rep');
assert.match(rep, /1 of 2 have it/);
LEADS.forEach(([k]) => assert.equal(leaderOf([bounded, full], k), full));

$('#kindf').value = 'no such kind';
assert.equal(repRows().length, 2, 'a filter changed after selecting does not empty the report');

for (const dir of [1, -1]) {
  const sorted = ROWS.slice().sort(compareBy('whkg', dir));
  const gap = sorted.findIndex(r => !hasNum(r, 'whkg'));
  assert.ok(gap > 0 && sorted.slice(gap).every(r => !hasNum(r, 'whkg')), 'blanks sort last, direction ' + dir);
}
`, {assert, Node, document, PRODUCTS: blob('CONTRIB').PRODUCTS, GROUPS: registry.GROUPS, REG: registry.REG});
console.log('A selected product with only bounded values is reported by what its source states');
