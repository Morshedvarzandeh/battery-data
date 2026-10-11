// Exercise the real sheet renderer and Markdown export with repeated quantities.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');
const page = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const source = page.slice(page.indexOf('function known(d){'), page.indexOf('/* ---------- chemistry and components layer'));
const batch = JSON.parse(fs.readFileSync(path.join(root, 'review/batches/2026-09-16-electrical-components.json')));
const doc = batch.candidates.find(c => c.document.product.model_number === 'GV211BAX').document;
const obs = doc.observations.map(o => ({q:o.quantity,v:o.value,u:o.unit,stat:o.statistic,
  cond:Object.fromEntries(Object.entries(o.conditions||{}).filter(([k])=>k!=='unstated')),
  unstated:o.conditions?.unstated||[],quote:o.locator.quote,pg:o.locator.page,section:o.locator.section,src:'datasheet'}));
function element(tag, attrs, ...children) {return {tag,attrs,children,style:{},append(...items){this.children.push(...items);}};}
const nodes = new Map();
const context = {assert, ROWS:[{cell:'GV211BAX',manu:'Sensata',chem:'',fmt:'',rec:{obs,source:{title:doc.source.title,url:doc.source.url}}}],
  GROUPS:{Contactors:['continuous_carry_current']},REG:{continuous_carry_current:['temperature_c','conductor_description']},UNIT:{},
  el:element,f:(n,p)=>n.toFixed(p),$:key=>{if(!nodes.has(key))nodes.set(key,element('div',{}));return nodes.get(key);}};
vm.runInNewContext(source + `
curCell='GV211BAX';
assert.equal(known(ROWS[0]).continuous_carry_current.length,2);
drawSheet();
const markdown=sheetMD();
assert.match(markdown,/100.00/);
assert.match(markdown,/150.00/);
assert.match(markdown,/8 AWG/);
assert.match(markdown,/4 AWG/);
assert.match(markdown,/power_terminal_temperature_max_c/);
assert.match(markdown,/not stated: temperature_c/);
`,context);
const text = node => typeof node==='string'?node:[node.textContent||'',...(node.children||[]).map(text)].join(' ');
const rendered=text(nodes.get('#sheet'));
assert.match(rendered,/100.0/);
assert.match(rendered,/150.0/);
assert.match(rendered,/8 AWG/);
assert.match(rendered,/4 AWG/);
console.log('Sheet display and Markdown retain both conductor-dependent ratings and their conditions');
const bmsBatch=JSON.parse(fs.readFileSync(path.join(root,'review/batches/2026-10-09-bms-market.json')));
for(const [model,expected,absent] of [
  ['c-BMS24X','2023-05-17 (day precision; launch announcement)',''],
  ['Lithiumate Pro Master','2007 (year precision; commercial release)','2007-01-01'],
  ['G5 High-Voltage BMS','Conflicting dates; unresolved',''],
  ['G5 Plus High-Voltage BMS','Announced; not released','']]){
  const d=bmsBatch.candidates.find(e=>e.document.product.model_number===model).document;
  context.ROWS=[{cell:model,manu:d.product.manufacturer,chem:'',fmt:'',rec:{obs:[],source:d.source,lifecycle:d.lifecycle,bms:d.bms}}];
  vm.runInNewContext(`curCell=ROWS[0].cell; drawSheet(); resultMD=sheetMD();`,context);
  const renderedBms=text(nodes.get('#sheet'));
  assert.ok(renderedBms.includes(expected),expected);
  assert.ok(context.resultMD.includes(expected),expected);
  if(absent)assert.ok(!context.resultMD.includes(absent),absent);
  assert.ok(context.resultMD.includes('([evidence](https://'));
}
console.log('BMS display/export distinguish launch, partial release years, conflicts and future availability');
