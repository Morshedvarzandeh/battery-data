/* Lemonergy Data — cell finder.
 *
 * Data comes from web/data/ (built by tools/build_web_data.py):
 *   cells.json              one compact row per product, for the table and chart
 *   records/<maker>.json    full records, fetched when a record is opened
 *   registry.json           quantity registry + headings, for the full-record view
 *   technologies-and-chemistries.json
 *                           the two classifications (technology, chemistry) and
 *                           the words a reader may type for each
 *   summary.json            the honest counts in the hero, and any seller's stock list
 *                           (offers/*.json: a seller's own statement, kept off the records)
 *   coverage-status.json    the target list, marked sourced/missing by looking
 *
 * The first half is pure functions (no DOM) and is exported for tests
 * (tests/test_web_observations.cjs). The second half is the page.
 */
(function (root) {
  "use strict";
  const BD = {};

  /* ------------------------------------------------------------------ pure */
  BD.FF = { cylindrical: "cylindrical", pouch: "pouch", prismatic_hardcase: "prismatic", prismatic: "prismatic",
    coin: "coin / button", button: "coin / button", blade: "prismatic", rack: "rack", container: "container", brick: "brick", other: "other" };
  BD.UNIT = { mass: "g", diameter: "mm", height: "mm", length: "mm", width: "mm", thickness: "mm", volume: "L",
    nominal_voltage: "V", capacity: "Ah", voltage: "V", max_continuous_discharge_current: "A", max_pulse_discharge_current: "A",
    max_continuous_charge_current: "A", standard_charge_current: "A", specific_energy: "Wh/kg", energy_density: "Wh/L",
    max_continuous_discharge_rate: "C", max_pulse_discharge_rate: "C", max_continuous_charge_rate: "C", standard_charge_rate: "C",
    internal_resistance_ac: "mΩ", internal_resistance_dc: "mΩ", cycle_life: "cycles", calendar_life: "years",
    operating_temperature_min: "°C", operating_temperature_max: "°C", storage_temperature_min: "°C", storage_temperature_max: "°C" };
  BD.LABEL = { max_continuous_discharge_current: "Continuous discharge current", max_continuous_charge_current: "Continuous charge current",
    max_pulse_discharge_current: "Pulse discharge current", standard_charge_current: "Standard charge current",
    max_continuous_discharge_rate: "Continuous discharge rate", max_pulse_discharge_rate: "Pulse discharge rate",
    max_continuous_charge_rate: "Charge rate, maximum", standard_charge_rate: "Charge rate, standard",
    internal_resistance_ac: "AC internal resistance", internal_resistance_dc: "DC internal resistance",
    cv_cutoff_current: "CV cut-off current", operating_temperature_min: "Operating temperature, min",
    operating_temperature_max: "Operating temperature, max", specific_energy: "Specific energy", energy_density: "Energy density",
    bms_series_cells_min: "Series cells, min", bms_series_cells_max: "Series cells, max", bms_pack_voltage_max: "Pack voltage, max",
    bms_temperature_channels: "Temperature channels", bms_can_ports: "CAN ports", bms_balancing_current: "Balancing current",
    bms_cell_banks_max: "Cell banks, max" };
  BD.label = function (q) {
    if (BD.LABEL[q]) return BD.LABEL[q];
    const s = q.replace(/_/g, " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  };
  BD.fmt = function (v, d) {
    if (v == null || Number.isNaN(v)) return null;
    if (d == null) d = Math.abs(v) < 1 ? 3 : Math.abs(v) < 10 ? 2 : 1;
    if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString("en");
    return (+v.toFixed(d)).toLocaleString("en", { maximumFractionDigits: d });
  };
  BD.boundPrefix = function (o) { return o.lower_bound ? "≥ " : o.upper_bound ? "≤ " : ""; };
  /** The conditions a value was rated at, short form: "0.2 C · 25 °C · to 2.5 V". */
  BD.conditionShort = function (o) {
    const c = (o && o.cond) || {}, p = [];
    if (c.rate_value != null) p.push(c.rate_value + " " + (c.rate_unit || "C"));
    if (c.temperature_c != null) p.push(c.temperature_c + " °C");
    if (c.voltage_lower_v != null) p.push("to " + c.voltage_lower_v + " V");
    if (c.dod_pct != null) p.push(c.dod_pct + " % DoD");
    if (c.soc_pct != null) p.push(c.soc_pct + " % SoC");
    if (c.frequency_hz != null) p.push(c.frequency_hz + " Hz");
    if (c.pulse_duration_s != null) p.push(c.pulse_duration_s + " s pulse");
    return p.join(" · ");
  };
  /** Every recorded condition, long form, plus what the source leaves unstated. */
  BD.conditionDetails = function (o) {
    const parts = Object.entries((o && o.cond) || {}).map(([k, v]) => k + ": " + (typeof v === "object" ? JSON.stringify(v) : v));
    if (o && o.unstated && o.unstated.length) parts.push("not stated: " + o.unstated.join(", "));
    return parts.join("; ") || "no required conditions";
  };
  BD.known = function (rec) {
    const k = {};
    (rec.obs || []).forEach(o => { (k[o.q] = k[o.q] || []).push(o); });
    return k;
  };
  /** Provenance and dates rows: [label, text, url?]. Unknowns are stated, never filled. */
  BD.lifecycleRows = function (rec) {
    const life = rec && rec.lifecycle, bms = rec && rec.bms, dates = rec && rec.dates, rows = [];
    const src = (rec && rec.source) || {};
    if (dates) {
      const label = d => d && d.date ? d.date + " (" + d.precision + " precision)" : "Not recorded";
      rows.push(["source document date", label(dates.source_document), src.url],
        ["source revision", dates.source_revision || "Not recorded"],
        ["specification source retrieved", label(dates.source_retrieved), src.url],
        ["product lifecycle checked", label(dates.lifecycle_checked)]);
    } else if (src.date) {
      rows.push(["source document date", src.date, src.url]);
    }
    if (bms) rows.push(["record scope", String(bms.identity_scope || "").replace(/_/g, " ")],
      ["architecture / balancing", bms.architecture + " / " + bms.balancing],
      ["interfaces", (bms.interfaces || []).join(", ") || "not recorded"], ["scope notes", bms.note]);
    if (!life) return rows.concat([["product release", "Not researched"],
      ["date context", "Source retrieval and document revision do not establish product release or current availability."]]);
    const labels = { manufacturer_listed: "Manufacturer-listed", announced: "Announced; not released",
      legacy_support_only: "Legacy support only", discontinued: "Discontinued", unknown: "Unknown" };
    rows.push(["market status", (labels[life.market_status] || life.market_status) + " · checked " + life.checked_at, life.market_evidence && life.market_evidence.url]);
    const release = life.release || {}, event = release.event;
    rows.push(["product release", event
      ? event.date + " (" + event.precision + " precision; " + String(event.event_type).replace(/_/g, " ") + ")"
      : release.status === "conflicting" ? "Conflicting dates; unresolved" : "Not established", event && event.evidence && event.evidence.url]);
    if (release.note) rows.push(["release evidence notes", release.note]);
    (life.events || []).forEach(e => rows.push([String(e.event_type).replace(/_/g, " "),
      (e.date || e.date_text) + " (" + e.precision + " precision)" + (e.note ? " · " + e.note : ""), e.evidence && e.evidence.url]));
    return rows;
  };
  /** The record arranged for reading: only headings with an observation, and the list of what is absent. */
  BD.recordGroups = function (rec, GROUPS) {
    const K = BD.known(rec), groups = [], absent = [], placed = new Set();
    Object.entries(GROUPS || {}).forEach(([g, codes]) => {
      const rows = [];
      codes.forEach(q => { placed.add(q); if (K[q]) rows.push({ q, label: BD.label(q), obs: K[q] }); else absent.push(q); });
      if (rows.length) groups.push({ group: g, rows, n: rows.length, of: codes.length });
    });
    // quantities the registry knows but no heading places (should not happen; shown rather than lost)
    const stray = Object.keys(K).filter(q => !placed.has(q));
    if (stray.length) groups.push({ group: "Other recorded quantities", rows: stray.map(q => ({ q, label: BD.label(q), obs: K[q] })), n: stray.length, of: stray.length });
    return { groups, absent };
  };
  /** How a stored unit reads. A C-rate is stored as "C-rate" because "C" is the coulomb in the unit table. */
  BD.UNIT_TEXT = { "C-rate": "C", mohm: "mΩ", W_per_kg: "W/kg" };
  BD.unitText = function (u, q) { return BD.UNIT_TEXT[u] || u || BD.UNIT[q] || ""; };
  BD.valueText = function (o) {
    return BD.boundPrefix(o) + BD.fmt(o.v, o.v < 10 ? 2 : o.v < 1000 ? 1 : 0) + " " + BD.unitText(o.u, o.q);
  };
  /** Source kind as a reader would say it. */
  BD.SRC = { datasheet: "datasheet", manufacturer_web: "manufacturer web page", distributor_listing: "supplier list",
    regulatory_filing: "regulatory filing", third_party_test: "third-party test", user_submission: "user submission" };
  BD.srcText = function (k) { return BD.SRC[k] || String(k || "source").replace(/_/g, " "); };
  /** Continuous discharge as the source printed it: amperes, or a C-rate when no ampere figure exists. */
  BD.dischargeText = function (r) {
    if (r.a != null) return BD.fmt(r.a, 1) + " A" + (r.crate ? " · " + BD.fmt(r.crate, 1) + " C" : "");
    if (r.crate_s && r.crate != null) return BD.fmt(r.crate, 1) + " C (printed as a C-rate)";
    return null;
  };
  /** A seller's stock line: "In stock at Lemonergy · as of 2026-10-28". */
  BD.stockText = function (st) {
    if (!st) return null;
    return (st.s === "in_stock" ? "In stock at " : "Available on request from ") + st.by + " · as of " + st.d;
  };
  /** Markdown export of one record: every observation with its conditions and evidence, then what is not stated. */
  BD.recordMarkdown = function (rec, GROUPS) {
    const esc = v => String(v == null ? "" : v).replace(/\|/g, "\\|").replace(/\n/g, " ");
    const S = rec.source || {}, L = ["# " + rec.cell, "",
      [rec.manu, rec.chem && rec.chem.designation, rec.fmt && BD.FF[rec.fmt], rec.component_type].filter(Boolean).join(" · "), "",
      S.title ? "Source: [" + S.title + "](" + S.url + ")" : "Source: not stated", S.note || "", ""];
    L.push("## Product and release evidence", "");
    BD.lifecycleRows(rec).forEach(([k, v, url]) => L.push(k + ": " + v + (url ? " ([evidence](" + url + "))" : "")));
    L.push("");
    const { groups, absent } = BD.recordGroups(rec, GROUPS);
    groups.forEach(g => {
      L.push("## " + g.group, "", "| Quantity | Value | Unit | Recorded conditions | Source |", "|---|--:|---|---|---|");
      g.rows.forEach(r => r.obs.forEach(o => {
        const evidence = [o.stat, o.src, o.pg ? "page " + o.pg : "", o.section].filter(Boolean).join("; ");
        L.push("| `" + r.q + "` | " + BD.boundPrefix(o) + BD.fmt(o.v, 2) + " | " + BD.unitText(o.u, r.q) + " | " + esc(BD.conditionDetails(o)) + " | " + esc(evidence) + " |");
      }));
      L.push("");
    });
    if (absent.length) L.push("## Not stated by the source", "", absent.map(q => "`" + q + "`").join(", "), "");
    L.push("---", "", "Lemonergy Data · [Free battery library](https://github.com/Morshedvarzandeh/battery-data) · [API](https://lemonergy.com/data/#reference)");
    return L.join("\n");
  };
  BD.CSV_COLS = [["uid", r => r.uid], ["manufacturer", r => r.manu], ["model", r => r.model], ["kind", r => r.kind], ["component_type", r => r.ct],
    ["technology", r => r.tech], ["technology_variant", r => r.tvar], ["chemistry", r => r.cclass], ["chemistry_as_printed", r => r.chem],
    ["format", r => r.fmt], ["format_code", r => r.ffc], ["capacity_ah", r => r.ah], ["voltage_v", r => r.v],
    ["voltage_quantity", r => r.vq], ["mass_g", r => r.g], ["energy_wh", r => r.wh], ["wh_per_kg", r => r.whkg], ["wh_per_kg_derived", r => r.whkg_d],
    ["wh_per_l", r => r.whl], ["continuous_discharge_a", r => r.a], ["continuous_discharge_c_rate", r => r.crate], ["c_rate_as_printed", r => r.crate_s ? "yes" : ""], ["cycle_life", r => r.cyc], ["cycle_life_bound", r => r.cyc_b && r.cyc_b.join(" ")], ["internal_resistance_mohm", r => r.ir],
    ["internal_resistance_bound_mohm", r => r.ir_b && r.ir_b.join(" ")],
    ["dimensions_mm", r => r.dims && r.dims.join(" x ")], ["t_min_c", r => r.tmin], ["t_max_c", r => r.tmax], ["specs_stated_of_8", r => r.depth],
    ["observations", r => r.n], ["source_kind", r => r.src], ["document_year", r => r.doc], ["year", r => r.year], ["year_kind", r => r.yk], ["source_url", r => r.url],
    ["availability", r => BD.stockText(r.stock)]];
  BD.toCSV = function (rows) {
    const cell = v => { if (v == null) return ""; const s = String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return [BD.CSV_COLS.map(c => c[0]).join(",")].concat(rows.map(r => BD.CSV_COLS.map(c => cell(c[1](r))).join(","))).join("\n");
  };
  /* Technology (lithium-ion, sodium-ion, lead-acid › AGM…) and chemistry (LFP,
   * NMC, NFPP…) are two classifications, kept apart. Search understands the
   * words for both: "na", "lead acid", "AGM", "LiFePO4". A word that names a
   * class matches by class, never as a substring, so "na" finds sodium-ion
   * cells and not Panasonic. Every other word is a substring, as before. */
  BD.SEP = " \u203a ";
  BD.normalizeText = s => String(s == null ? "" : s).toLowerCase().replace(/[-_/]+/g, " ").replace(/\s+/g, " ").trim();
  BD.searchIndex = function (tax) {
    const map = new Map(); let maxWords = 1;
    const add = (alias, key) => {
      const a = BD.normalizeText(alias); if (!a) return;
      if (!map.has(a)) map.set(a, new Set());
      map.get(a).add(key); maxWords = Math.max(maxWords, a.split(" ").length);
    };
    ((tax && tax.technologies) || []).forEach(t => {
      [t.name].concat(t.aliases || []).forEach(a => add(a, "t:" + t.name));
      (t.variants || []).forEach(v => [v.name].concat(v.aliases || []).forEach(a => add(a, "v:" + t.name + BD.SEP + v.name)));
    });
    ((tax && tax.chemistries) || []).forEach(c => [c.name].concat(c.aliases || []).forEach(a => add(a, "c:" + c.name)));
    return { map, maxWords };
  };
  /** Split a query into class words (longest phrase first) and plain substrings. */
  BD.parseQuery = function (q, idx) {
    const toks = BD.normalizeText(q).split(" ").filter(Boolean), terms = [];
    for (let i = 0; i < toks.length;) {
      let hit = null;
      if (idx) for (let n = Math.min(idx.maxWords, toks.length - i); n >= 1 && !hit; n--) {
        const phrase = toks.slice(i, i + n).join(" ");
        if (idx.map.has(phrase)) hit = { alias: phrase, keys: idx.map.get(phrase), n };
      }
      if (hit) { terms.push({ alias: hit.alias, keys: hit.keys }); i += hit.n; } else { terms.push({ text: toks[i] }); i += 1; }
    }
    return terms;
  };
  BD.classKeys = r => {
    const k = [];
    if (r.tech) { k.push("t:" + r.tech); if (r.tvar) k.push("v:" + r.tech + BD.SEP + r.tvar); }
    if (r.cclass) k.push("c:" + r.cclass);
    return k;
  };
  BD.matchesQuery = function (r, terms) {
    if (!terms || !terms.length) return true;
    const hay = BD.normalizeText([r.model, r.manu, r.chem, r.fmt, r.ffc, BD.FF[r.fmt], r.ct, r.kind].join(" ")), keys = BD.classKeys(r);
    return terms.every(t => t.keys ? keys.some(k => t.keys.has(k)) : hay.includes(t.text));
  };
  BD.techText = r => r.tech ? r.tech + (r.tvar ? " · " + r.tvar : "") : null;

  /** Nearest records by format, chemistry, capacity and specific energy. */
  BD.similar = function (row, rows, k) {
    k = k || 5;
    const cand = rows.filter(r => r.uid !== row.uid && r.kind === row.kind && r.ah != null && row.ah != null);
    const score = r => {
      let d = Math.abs(Math.log10(r.ah) - Math.log10(row.ah)) * 2;
      d += r.fmt === row.fmt ? 0 : 1;
      d += r.chem && row.chem ? (r.chem === row.chem ? 0 : 0.6) : 0.3;
      if (r.whkg != null && row.whkg != null) d += Math.abs(r.whkg - row.whkg) / 150; else d += 0.3;
      d -= r.depth * 0.04; // prefer records that state more
      return d;
    };
    return cand.map(r => [score(r), r]).sort((a, b) => a[0] - b[0]).slice(0, k).map(x => x[1]);
  };

  if (typeof module !== "undefined" && module.exports) module.exports = BD; else root.BD = BD;
  if (typeof document === "undefined") return;

  /* ------------------------------------------------------------------ page */
  const $ = s => document.querySelector(s);
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const mfrLabel = m => m.replace(" Co., Ltd.", "").replace(" Energy Solution", " ES");
  const state = { q: "", kind: new Set(["cell"]), tech: new Set(), chem: new Set(), ff: new Set(), mfr: new Set(), year: new Set(), core: false, stock: false, sort: "depth", dir: -1, shown: 100, sel: null, cmp: [], view: "table" };
  let rows = [], REG = { REG: {}, GROUPS: {} }, summary = null, IDX = null, terms = [], termsFor = null, EMPTY_HTML = "";
  const shards = new Map();

  const DATA = (document.currentScript && document.currentScript.dataset.base) || "data/";
  const getJSON = u => fetch(DATA + u, { cache: "no-cache" }).then(r => { if (!r.ok) throw new Error(u + ": " + r.status); return r.json(); });

  async function boot() {
    try {
      let tax;
      [rows, REG, summary, tax] = await Promise.all([getJSON("cells.json"), getJSON("registry.json"), getJSON("summary.json"),
        getJSON("technologies-and-chemistries.json").catch(() => ({ technologies: [], chemistries: [] }))]);
      IDX = BD.searchIndex(tax);
      FACETS.tech.order = [].concat(...tax.technologies.map(t => [t.name].concat((t.variants || []).map(v => t.name + BD.SEP + v.name)))).concat(["Not stated"]);
      FACETS.chem.order = tax.chemistries.map(c => c.name).concat(["Not stated"]);
    } catch (e) {
      $("#count").textContent = "The data files are not built. Run: python tools/build_web_data.py — then serve this folder.";
      return;
    }
    EMPTY_HTML = $("#empty").innerHTML;
    facts(); fillFilters(); wire(); readHash(); render(); renderCmp(); coverage();
    const first = sorted(filtered())[0]; if (state.sel) select(state.sel); else if (first) select(first.uid);
  }
  function facts() {
    const s = summary;
    $("#f-n").textContent = s.battery_records.toLocaleString("en");
    $("#f-c").textContent = s.component_records.toLocaleString("en");
    $("#f-core").textContent = s.with_capacity_voltage_mass.toLocaleString("en");
    $("#f-dis").textContent = s.with_continuous_discharge.toLocaleString("en");
    $("#f-cyc").textContent = s.with_cycle_life.toLocaleString("en");
    $("#release").textContent = s.observations.toLocaleString("en") + " observations from contrib/";
  }
  // Facets: pick several makers, chemistries or formats at once. Within a
  // facet the picks are OR-ed, across facets AND-ed. Each menu's counts are
  // computed against every *other* active filter, so a count says how many
  // more rows ticking that box would bring in.
  const KIND = { cell: "Rechargeable cells", primary_cell: "Primary cells", pack: "Modules, packs and systems", component: "Electrical components" };
  const kindOf = r => ["pack", "module", "system"].includes(r.kind) ? "pack" : r.kind;
  const FACETS = {
    kind: { label: "Kind", value: kindOf, text: v => KIND[v] || v, order: Object.keys(KIND) },
    mfr: { label: "Company", value: r => r.manu, text: mfrLabel },
    // Technology and chemistry are separate filters. A technology tick keeps
    // all of its variants; a variant tick (Lead-acid › AGM) keeps only that one.
    tech: { label: "Technology", values: r => r.kind === "component" ? [] : r.tech ? [r.tech].concat(r.tvar ? [r.tech + BD.SEP + r.tvar] : []) : ["Not stated"],
      text: v => v.includes(BD.SEP) ? v.split(BD.SEP)[1] : v, sub: v => v.includes(BD.SEP), order: [], all: true },
    chem: { label: "Chemistry", values: r => r.kind === "component" ? [] : [r.cclass || "Not stated"], text: v => v, order: [], all: true },
    ff: { label: "Format", value: r => r.fmt ? BD.FF[r.fmt] || r.fmt : null, text: v => v },
    year: { label: "Year", value: r => r.year || "not stated", text: v => v, desc: true },
  };
  const componentsOnly = () => state.kind.size === 1 && state.kind.has("component");
  const facetValues = (f, r) => f.values ? f.values(r) : [f.value(r)];
  function matches(r, skip) {
    for (const k of Object.keys(FACETS)) if (k !== skip && state[k].size && !facetValues(FACETS[k], r).some(v => state[k].has(v))) return false;
    if (state.core && !isCore(r)) return false;
    if (state.stock && !(r.stock && r.stock.s === "in_stock")) return false;
    if (termsFor !== state.q) { terms = BD.parseQuery(state.q, IDX); termsFor = state.q; }
    return BD.matchesQuery(r, terms);
  }
  function facetMenu(k) {
    const f = FACETS[k], menu = $("#facet-" + k), btn = document.querySelector('.facet[data-facet="' + k + '"] .facet-btn');
    const counts = new Map();
    // Listed classes stay visible at zero: "Lead-acid 0" says the library has none yet.
    if (f.all) f.order.forEach(v => counts.set(v, 0));
    rows.forEach(r => facetValues(f, r).forEach(v => { if (!v) return; if (!counts.has(v)) counts.set(v, 0); if (matches(r, k)) counts.set(v, counts.get(v) + 1); }));
    const q = (menu.dataset.q || "").toLowerCase();
    const entries = [...counts].filter(([v]) => !q || f.text(v).toLowerCase().includes(q))
      .sort((a, b) => f.order ? f.order.indexOf(a[0]) - f.order.indexOf(b[0])
        : f.desc ? (a[0] === "not stated") - (b[0] === "not stated") || String(b[0]).localeCompare(String(a[0]))
        : (state[k].has(b[0]) - state[k].has(a[0])) || (b[1] - a[1]) || f.text(a[0]).localeCompare(f.text(b[0])));
    menu.innerHTML = (counts.size > 8 ? '<input class="fsearch" type="search" placeholder="Filter ' + f.label.toLowerCase() + '…" value="' + esc(menu.dataset.q || "") + '" aria-label="Filter list">' : "") +
      entries.map(([v, n]) => '<label class="' + (n === 0 && !state[k].has(v) ? "zero" : "") + (f.sub && f.sub(v) ? " sub" : "") + '"><input type="checkbox" value="' + esc(v) + '"' + (state[k].has(v) ? " checked" : "") + "><span>" + esc(f.text(v)) + "</span><small>" + n.toLocaleString("en") + "</small></label>").join("") +
      '<div class="facet-foot"><button type="button" data-act="clear">Clear</button><button type="button" data-act="close">Done</button></div>';
    btn.innerHTML = esc(f.label) + (state[k].size ? '<span class="n">' + state[k].size + "</span>" : "");
    btn.classList.toggle("on", state[k].size > 0 && !(k === "kind" && state[k].size === 1 && state[k].has("cell")));
    menu.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.addEventListener("change", () => { if (cb.checked) state[k].add(cb.value); else state[k].delete(cb.value); refilter(); facetMenu(k); }));
    const fs = menu.querySelector(".fsearch"); if (fs) { fs.addEventListener("input", () => { menu.dataset.q = fs.value; const pos = fs.selectionStart; facetMenu(k); const nf = menu.querySelector(".fsearch"); nf.focus(); nf.setSelectionRange(pos, pos); }); }
    menu.querySelector('[data-act="clear"]').onclick = () => { state[k].clear(); menu.dataset.q = ""; refilter(); facetMenu(k); };
    menu.querySelector('[data-act="close"]').onclick = () => closeFacets();
    const kindDefault = state.kind.size === 1 && state.kind.has("cell");
    $("#f-clear").hidden = !Object.keys(FACETS).some(x => x === "kind" ? !kindDefault : state[x].size);
  }
  function closeFacets() { document.querySelectorAll(".facet-menu").forEach(m => { m.hidden = true; }); document.querySelectorAll(".facet-btn").forEach(b => b.setAttribute("aria-expanded", "false")); }
  function fillFilters() {
    Object.keys(FACETS).forEach(k => {
      const btn = document.querySelector('.facet[data-facet="' + k + '"] .facet-btn'), menu = $("#facet-" + k);
      btn.addEventListener("click", () => { const open = !menu.hidden; closeFacets(); if (!open) { facetMenu(k); menu.hidden = false; btn.setAttribute("aria-expanded", "true"); } });
      facetMenu(k);
    });
    // composedPath, not closest: a click on the count badge replaces the badge while the event is in flight.
    document.addEventListener("click", e => { if (!e.composedPath().some(n => n.classList && n.classList.contains("facet"))) closeFacets(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeFacets(); });
    $("#f-clear").onclick = () => { Object.keys(FACETS).forEach(k => state[k].clear()); state.kind.add("cell"); refilter(); Object.keys(FACETS).forEach(facetMenu); };
  }
  function refreshFacets() { Object.keys(FACETS).forEach(k => { if (!$("#facet-" + k).hidden) facetMenu(k); else facetMenu(k); }); }
  const isCore = r => r.ah != null && r.v != null && r.g != null;
  function filtered() { return rows.filter(r => matches(r, null)); }
  function sorted(list) {
    const k = state.sort, d = state.dir;
    const tie = (a, b) => (b.depth - a.depth) || ((b.src === "datasheet") - (a.src === "datasheet")) || (a.manu + a.model).localeCompare(b.manu + b.model);
    return list.slice().sort((a, b) => {
      let x = a[k], y = b[k];
      if (k === "model") { x = a.model || ""; y = b.model || ""; }
      if (k === "ff") { x = a.fmt || a.ffc; y = b.fmt || b.ffc; }
      if (x == null && y == null) return tie(a, b);
      if (x == null) return 1; if (y == null) return -1;
      if (typeof x === "string") return d * x.localeCompare(y) || tie(a, b);
      return d * (x - y) || tie(a, b);
    });
  }
  const CELL_COLS = [["model", "Cell", ""], ["manu", "Company", ""], ["tech", "Technology", ""], ["cclass", "Chemistry", ""], ["ff", "Format", ""], ["ah", "Ah", "r"], ["v", "V", "r"], ["g", "g", "r"],
    ["whkg", "Wh/kg", "r"], ["a", "A cont.", "r"], ["cyc", "Cycles", "r"], ["year", "Year", "r"], ["depth", "Stated", ""]];
  const COMP_COLS = [["model", "Component", ""], ["manu", "Company", ""], ["ct", "Type", ""], ["ratings", "Key ratings as printed", ""], ["year", "Year", "r"], ["n", "Observations", "r"]];
  const SORT_LABEL = { depth: "how much the source states", model: "name", manu: "company", year: "year", tech: "technology", cclass: "chemistry", chem: "chemistry", ff: "format", ah: "capacity", v: "voltage", g: "mass",
    whkg: "specific energy", a: "discharge current", cyc: "cycle life", ct: "type", n: "observation count", ratings: "ratings" };
  const depthHTML = d => '<span class="depth" title="' + d + ' of 8 core specifications stated">' + Array.from({ length: 8 }, (_, i) => '<i class="' + (i < d ? "on" : "") + '"></i>').join("") + "</span>";
  const num = (v, d) => v == null ? '<td class="r dash">–</td>' : '<td class="r">' + BD.fmt(v, d) + "</td>";
  // Amperes when printed; a C-rate printed without amperes shows as such and is never converted.
  // A printed bound shows as one ("≥3,000"); it is not a point value and does not sort as one.
  const boundCell = (b, d) => '<td class="r" title="Printed as a bound, not a point value"><span class="printed">' + esc(b[0]) + BD.fmt(b[1], d) + "</span></td>";
  const ampCell = r => r.a != null ? num(r.a, 1) : r.crate_s && r.crate != null
    ? '<td class="r" title="Printed as a C-rate; the capacity it refers to is not stated, so no ampere value is derived"><span class="printed">' + BD.fmt(r.crate, 1) + '</span><sup style="color:var(--muted);font-size:9px"> C</sup></td>'
    : '<td class="r dash">–</td>';
  // On its own line under the model, so a long model name cannot push it out of the cell.
  const stockPill = r => r.stock && r.stock.s === "in_stock" ? '<small class="stock" title="' + esc(BD.stockText(r.stock)) + '">In stock · ' + esc(r.stock.by) + "</small>" : "";
  // Year: a documented product release reads plain; a document date reads with a "doc" mark — the sheet's year, not the product's.
  const yearCell = r => r.year == null ? '<td class="r dash" title="Neither a release date nor a dated document is recorded">–</td>'
    : r.yk === "release" ? '<td class="r" title="Documented product release">' + esc(r.year) + "</td>"
    : '<td class="r" title="Date of the source document, not the product release"><span class="printed">' + esc(r.year) + '</span><sup style="color:var(--muted);font-size:9px"> doc</sup></td>';
  function header() {
    const cols = componentsOnly() ? COMP_COLS : CELL_COLS;
    if (!cols.some(c => c[0] === state.sort)) { state.sort = componentsOnly() ? "n" : "depth"; state.dir = -1; }
    $("#tbl thead tr").innerHTML = cols.map(([k, t, cls]) => '<th class="' + cls + (state.sort === k ? " on" : "") + '" data-k="' + k + '">' + t + (state.sort === k ? '<span class="dir">' + (state.dir < 0 ? "▼" : "▲") + "</span>" : "") + "</th>").join("");
    document.querySelectorAll("#tbl th").forEach(th => th.addEventListener("click", () => {
      const k = th.dataset.k; if (state.sort === k) state.dir *= -1; else { state.sort = k; state.dir = ["model", "manu", "tech", "cclass", "chem", "ff", "ct", "ratings"].includes(k) ? 1 : -1; }
      render();
    }));
  }
  function rowHTML(r) {
    const sub = r.kind !== "cell" && r.kind !== "component" ? r.kind.replace("_", " ") : (r.vq === "voltage" ? "" : "");
    const company = '<td class="company" title="' + esc(r.manu) + '">' + esc(r.manu) + "</td>";
    if (componentsOnly()) {
      return '<td class="model">' + esc(r.model) + (sub ? "<small>" + esc(sub) + "</small>" : "") + "</td>" + company + "<td>" + esc((r.ct || "").replace(/_/g, " ")) +
        '</td><td class="ratings">' + (r.ratings.length ? r.ratings.map(esc).join(" · ") : '<span class="dash">–</span>') + "</td>" + yearCell(r) + '<td class="r">' + r.n + "</td>";
    }
    const v = r.v == null ? '<td class="r dash">–</td>' : r.vq === "voltage" ? '<td class="r"><span class="printed" title="Printed as “Voltage”; the source does not say it is the nominal voltage">' + BD.fmt(r.v, 2) + "</span></td>" : '<td class="r">' + BD.fmt(r.v, 2) + "</td>";
    const whkg = r.whkg == null ? '<td class="r dash">–</td>' : '<td class="r"' + (r.whkg_d ? ' title="Calculated from capacity, voltage and mass"' : "") + ">" + BD.fmt(r.whkg, 0) + (r.whkg_d ? "<sup style=\"color:var(--muted);font-size:9px\"> calc</sup>" : "") + "</td>";
    return '<td class="model">' + esc(r.model || "—") + stockPill(r) + (sub ? "<small>" + esc(sub) + "</small>" : "") + "</td>" + company +
      '<td class="chem" title="' + esc(BD.techText(r) || "Technology not stated") + '">' + (r.tech ? esc(r.tech) + (r.tvar ? "<small>" + esc(r.tvar) + "</small>" : "") : '<span class="dash">–</span>') + "</td>" +
      '<td class="chem" title="' + esc(r.chem ? "As printed: " + r.chem : "Not stated by the source") + '">' + (r.cclass ? esc(r.cclass) : '<span class="dash">–</span>') + "</td>" +
      '<td class="ff">' + (r.fmt ? esc(BD.FF[r.fmt] || r.fmt) : r.ffc ? esc(r.ffc) : '<span class="dash">–</span>') + (r.ffc && r.fmt ? ' <span class="pill">' + esc(r.ffc) + "</span>" : "") + "</td>" +
      num(r.ah, r.ah < 1 ? 3 : 1) + v + num(r.g, 1) + whkg + ampCell(r) + (r.cyc == null && r.cyc_b ? boundCell(r.cyc_b, 0) : num(r.cyc, 0)) + yearCell(r) + "<td>" + depthHTML(r.depth) + "</td>";
  }
  // When nothing matches because the library holds no such battery yet, say so.
  function emptyMessage() {
    const none = [];
    for (const v of state.tech) if (!rows.some(r => FACETS.tech.values(r).includes(v))) none.push(FACETS.tech.text(v));
    for (const t of terms) if (t.keys && !rows.some(r => BD.classKeys(r).some(k => t.keys.has(k)))) none.push(...[...t.keys].map(k => k.slice(2).split(BD.SEP).pop()));
    if (!none.length) return EMPTY_HTML;
    none.splice(0, none.length, ...new Set(none));
    return "The library has no " + esc(none.join(", ")) + " records yet. " +
      '<a href="mailto:info@lemonergy.com?subject=' + encodeURIComponent("Battery data: please add " + none.join(", ")) + '">Ask for them</a>, or ' +
      '<a href="https://github.com/Morshedvarzandeh/battery-data/blob/main/docs/06-submitting-a-datasheet.md">submit a datasheet</a> and it joins the review queue.';
  }
  function refilter() { state.shown = 100; const list = render(); if (list.length && !list.some(r => r.uid === state.sel)) select(list[0].uid); refreshFacets(); }
  function render() {
    header();
    const list = sorted(filtered());
    $("#count").textContent = list.length.toLocaleString("en") + " of " + rows.length.toLocaleString("en") + " records · sorted by " + SORT_LABEL[state.sort];
    const tb = $("#tbl tbody"); tb.innerHTML = "";
    list.slice(0, state.shown).forEach(r => {
      const tr = document.createElement("tr"); tr.dataset.uid = r.uid; tr.className = (state.sel === r.uid ? "sel " : "") + (state.cmp.includes(r.uid) ? "incmp" : "");
      tr.innerHTML = rowHTML(r);
      tr.addEventListener("click", () => select(r.uid));
      tb.appendChild(tr);
    });
    $("#more").hidden = list.length <= state.shown; $("#empty").hidden = list.length > 0;
    if (!list.length) $("#empty").innerHTML = emptyMessage();
    $("#csv").disabled = list.length === 0;
    if (state.view === "chart") drawChart(list);
    return list;
  }

  /* inspector */
  function select(uid) {
    const r = rows.find(x => x.uid === uid); if (!r) return;
    state.sel = uid;
    document.querySelectorAll("#tbl tbody tr").forEach(t => { t.classList.toggle("sel", t.dataset.uid === uid); t.classList.toggle("incmp", state.cmp.includes(t.dataset.uid)); });
    const show = (v, unit, d) => v == null ? null : BD.fmt(v, d) + (unit ? " " + unit : "");
    const spec = (k, disp, c, calc) => '<div class="spec ' + (disp == null ? "miss" : "") + (calc ? " calc" : "") + '"><span class="k">' + k + '</span><span class="v">' + (disp == null ? "not stated" : disp) + "</span>" + (c ? '<span class="c">' + c + "</span>" : "") + "</div>";
    const inCmp = state.cmp.includes(uid);
    let specs = "";
    if (r.kind === "component") {
      specs = r.ratings.length ? r.ratings.map(t => spec(esc(t.replace(/ [\d.,]+ \S*$/, "")), esc(t.match(/[\d.,]+ \S*$/)[0]))).join("") : '<div class="spec miss"><span class="k">Ratings</span><span class="v">open the full record</span></div>';
    } else {
      const missing = [];
      if (r.a == null && !r.crate_s) missing.push("continuous discharge current"); if (r.cyc == null && !r.cyc_b) missing.push("cycle life"); if (r.ir == null && !r.ir_b) missing.push("internal resistance");
      if (r.vq !== "nominal_voltage") missing.push("nominal voltage"); if (r.g == null) missing.push("mass"); if (r.tmin == null) missing.push("operating temperature");
      specs = spec("Capacity", show(r.ah, "Ah", r.ah < 1 ? 3 : 2), r.ah != null ? '<span id="capcond">conditions load with the record…</span>' : "") +
        spec(r.vq === "voltage" ? 'Voltage <span class="pill warn" title="Printed as “Voltage”; not asserted as nominal">as printed</span>' : "Nominal voltage", show(r.v, "V", 2)) +
        spec("Energy", show(r.wh, "Wh", 2), null, true) + spec("Mass", show(r.g, "g", 1)) +
        spec("Specific energy", show(r.whkg, "Wh/kg", 0), null, r.whkg_d) + spec("Continuous discharge", BD.dischargeText(r), r.crate_s ? "no ampere figure is printed; the capacity the C-rate refers to is not stated" : null) +
        spec("Cycle life", r.cyc != null ? show(r.cyc, "cycles", 0) : r.cyc_b ? r.cyc_b[0] + " " + BD.fmt(r.cyc_b[1], 0) + " cycles" : null, r.cyc == null && r.cyc_b ? "printed as a bound; conditions in the full record" : null) +
        spec("Internal resistance", r.ir != null ? show(r.ir, "mΩ", 1) : r.ir_b ? r.ir_b[0] + " " + BD.fmt(r.ir_b[1], 2) + " mΩ" : null, r.ir == null && r.ir_b ? "printed as a bound" : null) +
        spec("Dimensions", r.dims ? r.dims.map(x => BD.fmt(x, 1)).join(" × ") + " mm" + (r.shape === "cyl" && r.dims.length === 2 ? " (Ø × h)" : "") : null) +
        spec("Operating temperature", r.tmin != null ? r.tmin + " to " + r.tmax + " °C" : null) +
        (missing.length ? '<div class="gap"><b>Not stated by the source:</b> ' + missing.join(", ") + ". " + (r.a == null && !r.crate_s ? "Without a discharge rating this record cannot size a pack for power." : "") + "</div>" : "");
    }
    const sim = BD.similar(r, rows, 5);
    const seller = r.stock && ((summary && summary.sellers) || []).find(s => s.name === r.stock.by);
    const buy = seller ? '<div class="buy"><div><b>' + esc(BD.stockText(r.stock)) + '</b><small title="' + esc(seller.statement) + '">The seller\'s own statement, not a datasheet value. It does not change this record or its rank.</small></div>' +
      '<a class="btn sm pri" href="' + esc(seller.contact + (seller.contact.startsWith("mailto:") ? "?subject=" + encodeURIComponent("Quote request: " + r.model) +
        "&body=" + encodeURIComponent("Product: " + r.model + "\nRecord: " + r.uid + "\nQuantity:\nDelivery country:\n") : "")) + '">Request a quote</a></div>' : "";
    $("#insp").innerHTML =
      '<div class="hd"><p class="eyebrow">' + esc(r.manu) + "</p><h2>" + esc(r.model || "—") + '</h2><div class="meta">' +
      (r.tech ? '<span class="pill">' + esc(r.tech) + "</span>" : "") + (r.tvar ? '<span class="pill">' + esc(r.tvar) + "</span>" : "") +
      (r.cclass ? '<span class="pill">' + esc(r.cclass) + "</span>" : "") + (r.fmt ? '<span class="pill">' + esc(BD.FF[r.fmt] || r.fmt) + "</span>" : "") + (r.ffc ? '<span class="pill">' + esc(r.ffc) + "</span>" : "") +
      '<span class="pill">' + esc((r.ct || r.kind).replace(/_/g, " ")) + '</span><span class="pill src">' + esc(BD.srcText(r.src)) + "</span></div></div>" + buy + specs +
      '<div class="srcbox">Source: ' + esc(r.title || BD.srcText(r.src)) + (r.yk === "release" ? " · released " + esc(r.year) : r.year ? " · document dated " + esc(r.year) + " (product release not researched)" : " · no date recorded") + " · " + r.n + " observations" +
      (r.url ? ' · <a href="' + esc(r.url) + '" target="_blank" rel="noopener">open ↗</a>' : "") + "</div>" +
      (sim.length ? '<div class="similar"><span class="lbl">Similar records</span>' + sim.map(s => '<button type="button" data-u="' + esc(s.uid) + '">' + esc(s.model) + "<span>" + esc(mfrLabel(s.manu)) + (s.ah != null ? " · " + BD.fmt(s.ah, 1) + " Ah" : "") + (s.whkg != null ? " · " + BD.fmt(s.whkg, 0) + " Wh/kg" : "") + "</span></button>").join("") + "</div>" : "") +
      '<div class="acts"><button class="btn sm pri" id="fullrec" type="button">Full record</button><button class="btn sm' + (inCmp ? "" : state.cmp.length ? " pri" : "") + '" id="cmpbtn" type="button">' + (inCmp ? "Remove from comparison" : state.cmp.length ? "Add as cell " + (state.cmp.length + 1) + " of 4" : "Compare +") + "</button></div>";
    $("#cmpbtn").onclick = () => { if (inCmp) state.cmp = state.cmp.filter(x => x !== uid); else { if (state.cmp.length >= 4) state.cmp.shift(); state.cmp.push(uid); } writeHash(); renderCmp(); select(uid); if (state.cmp.length === 1) $("#cmpbar").scrollIntoView({ behavior: "smooth", block: "nearest" }); };
    $("#fullrec").onclick = () => openRecord(r);
    document.querySelectorAll("#insp .similar button").forEach(b => b.onclick = () => select(b.dataset.u));
    if (r.kind !== "component" && r.ah != null) loadRecord(r).then(rec => {
      const cap = (rec.obs || []).find(o => o.q === "capacity");
      const el = $("#capcond"); if (!el || !cap) return;
      const c = BD.conditionShort(cap);
      el.innerHTML = (cap.stat ? esc(cap.stat) + " · " : "") + (c ? esc(c) : '<span style="color:var(--missing)">rate, temperature and cut-off not stated</span>') + (cap.unstated && cap.unstated.length && c ? ' <span style="color:var(--missing)">· not stated: ' + esc(cap.unstated.join(", ")) + "</span>" : "");
    }).catch(() => {});
    if (window.innerWidth < 1000) $("#insp").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function loadRecord(r) {
    if (!shards.has(r.shard)) shards.set(r.shard, getJSON("records/" + r.shard + ".json"));
    return shards.get(r.shard).then(list => list.find(x => x.uid === r.uid));
  }

  /* full record */
  async function openRecord(r) {
    const rec = await loadRecord(r).catch(() => null);
    if (!rec) return;
    const { groups, absent } = BD.recordGroups(rec, REG.GROUPS);
    const kv = (k, v, url, na) => '<div class="kv"><span class="k">' + esc(k) + '</span><span class="v' + (na ? " na" : "") + '">' + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(v) + "</a>" : esc(v)) + "</span></div>";
    const S = rec.source || {};
    let h = '<div class="hd"><h2>' + esc(rec.cell) + '</h2><button class="btn sm" id="recmd" type="button">Export Markdown</button><button class="btn sm" id="recjson" type="button">Copy JSON</button><button class="btn sm ghost" id="recclose" type="button" aria-label="Close">Close ✕</button></div><div class="body">';
    h += "<h3>Source and dates</h3>" + kv("source document", S.title || "not stated", S.url) + kv("reference", S.ref || "not stated in this document", null, !S.ref) + (S.note ? kv("source notes", S.note) : "") +
      BD.lifecycleRows(rec).map(([k, v, url]) => kv(k, v, url, /^not /i.test(String(v)))).join("");
    const ch = rec.chem || {};
    if (r.tech || ch.designation || ch.cathode || ch.anode) h += "<h3>Technology and chemistry</h3>" + kv("technology", BD.techText(r) || "not stated", null, !r.tech) +
      kv("chemistry", r.cclass || "not stated by the source", null, !r.cclass) + (ch.designation ? kv("designation as printed", ch.designation) : "") + (ch.cathode ? kv("cathode", ch.cathode) : "") + (ch.anode ? kv("anode", ch.anode) : "") + (ch.electrolyte ? kv("electrolyte", ch.electrolyte) : "") + (ch.separator ? kv("separator", ch.separator) : "");
    groups.forEach(g => {
      h += "<h3>" + esc(g.group) + "<span>" + g.n + " of " + g.of + " recorded</span></h3>";
      g.rows.forEach(row => row.obs.forEach(o => {
        const req = (REG.REG[row.q] || []).length;
        h += '<div class="obs"><span class="q">' + esc(row.label) + "<small>" + esc(row.q) + "</small></span><span class=\"v\">" + esc(BD.valueText(o)) + "</span>" +
          '<span class="d">' + (o.stat ? '<span class="pill">' + esc(o.stat) + "</span>" : "") + '<span class="pill src">' + esc(BD.srcText(o.src)) + (o.pg ? " · page " + o.pg : "") + "</span>" +
          (Object.keys(o.cond || {}).length ? "<span>" + esc(BD.conditionDetails({ cond: o.cond })) + "</span>" : req ? '<span class="warn">no conditions recorded</span>' : "") +
          (o.unstated && o.unstated.length ? '<span class="warn">not stated: ' + esc(o.unstated.join(", ")) + "</span>" : "") + "</span>" +
          (o.quote ? '<span class="quote">“' + esc(o.quote) + "”" + (o.section ? " — " + esc(o.section) : "") + "</span>" : "") + "</div>";
      }));
    });
    if (rec.curves && rec.curves.length) h += "<h3>Curves<span>" + rec.curves.length + " recorded</span></h3>" + rec.curves.map(c => kv(c.kind.replace(/_/g, " "), c.x.length + " points · " + c.xq + " (" + c.xu + ") against " + c.yq + " (" + c.yu + ")" + (Object.keys(c.cond || {}).length ? " · " + BD.conditionDetails({ cond: c.cond }) : ""))).join("");
    if (absent.length) h += '<details class="rest"><summary>Not stated by the source: ' + absent.length + " quantities in the registry</summary><ul>" + absent.map(q => "<li>" + esc(q) + "</li>").join("") + "</ul></details>";
    h += '<p style="font-size:12.5px;color:var(--muted);margin-top:22px">Record file: <code>' + esc(rec.file) + "</code></p></div>";
    let host = $("#record");
    if (!host) { host = document.createElement("div"); host.id = "record"; host.className = "record"; host.setAttribute("role", "dialog"); host.setAttribute("aria-modal", "true"); document.body.appendChild(host); }
    host.innerHTML = '<div class="panel">' + h + "</div>"; host.hidden = false;
    const close = () => { host.hidden = true; };
    $("#recclose").onclick = close; host.onclick = e => { if (e.target === host) close(); };
    document.addEventListener("keydown", function esc1(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc1); } });
    $("#recmd").onclick = () => save((rec.uid.replace(/\//g, "-")) + ".md", BD.recordMarkdown(rec, REG.GROUPS), "text/markdown");
    $("#recjson").onclick = async e => { try { await navigator.clipboard.writeText(JSON.stringify(rec, null, 2)); e.target.textContent = "Copied"; } catch (_) { e.target.textContent = "Copy blocked"; } setTimeout(() => e.target.textContent = "Copy JSON", 1500); };
    $("#recclose").focus();
  }
  function save(name, text, mime) {
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: mime + ";charset=utf-8" })); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  /* compare */
  function renderCmp() {
    const sel = state.cmp.map(u => rows.find(r => r.uid === u)).filter(Boolean);
    // The bar above the table says what to do next; the tray below holds the result.
    $("#cmpbar").hidden = sel.length === 0;
    $("#cmpbar-step").textContent = sel.length === 1 ? "1 of 4 picked — select the next cell in the table and press “Add as cell 2”"
      : sel.length < 4 ? sel.length + " of 4 picked — add another, or compare them now" : "4 of 4 picked — compare them, or remove one to swap";
    $("#cmpbar-chips").innerHTML = sel.map(r => '<span class="pill"><b>' + esc(r.model) + "</b> " + esc(mfrLabel(r.manu)) + '<button type="button" data-u="' + esc(r.uid) + '" aria-label="Remove ' + esc(r.model) + '">×</button></span>').join("");
    $("#cmpbar-go").hidden = sel.length < 2;
    document.querySelectorAll("#cmpbar-chips button").forEach(b => b.onclick = () => { state.cmp = state.cmp.filter(x => x !== b.dataset.u); writeHash(); renderCmp(); if (state.sel) select(state.sel); });
    $("#tray").hidden = sel.length < 2; $("#traycount").textContent = sel.length + " of 4 · the better value in each row is marked";
    if (sel.length < 2) { render(); return; }
    const R = [["Technology", r => BD.techText(r), null], ["Chemistry", r => r.cclass, null], ["Format", r => r.fmt ? BD.FF[r.fmt] : r.ffc, null], ["Capacity (Ah)", r => r.ah, "max"], ["Voltage (V)", r => r.v, null],
      ["Energy (Wh)", r => r.wh, "max"], ["Mass (g)", r => r.g, "min"], ["Wh/kg", r => r.whkg, "max"], ["Continuous discharge (A)", r => r.a, "max"], ["Continuous discharge (C)", r => r.crate, "max"],
      ["Cycle life", r => r.cyc, "max"], ["Internal resistance (mΩ)", r => r.ir, "min"], ["Dimensions (mm)", r => r.dims && r.dims.join(" × "), null],
      ["Source", r => BD.srcText(r.src) + (r.doc ? " · " + r.doc : ""), null], ["Specs stated (of 8)", r => r.depth, "max"], ["Availability", r => BD.stockText(r.stock), null]];
    let h = "<thead><tr><th></th>" + sel.map(r => "<th>" + esc(r.model) + '<br><span style="font-weight:400;color:var(--muted);font-size:12px">' + esc(mfrLabel(r.manu)) + '</span><button class="x" data-u="' + esc(r.uid) + '" aria-label="Remove" type="button">×</button></th>').join("") + "</tr></thead><tbody>";
    R.forEach(([k, f, best]) => {
      const vals = sel.map(f); let bi = -1;
      if (best) { const nums = vals.map(v => typeof v === "number" ? v : null); const cand = nums.filter(v => v != null); if (cand.length > 1) { const t = best === "max" ? Math.max.apply(null, cand) : Math.min.apply(null, cand); bi = nums.indexOf(t); } }
      h += "<tr><td>" + k + "</td>" + vals.map((v, i) => '<td class="r ' + (i === bi ? "best" : "") + (v == null ? " dash" : "") + '">' + (v == null ? "–" : typeof v === "number" ? BD.fmt(v, v < 1 ? 3 : 1) : esc(v)) + "</td>").join("") + "</tr>";
    });
    $("#cmptbl").innerHTML = h + "</tbody>";
    document.querySelectorAll("#cmptbl .x").forEach(b => b.onclick = () => { state.cmp = state.cmp.filter(x => x !== b.dataset.u); writeHash(); renderCmp(); if (state.sel) select(state.sel); });
  }
  function writeHash() { const h = state.cmp.length ? "#cmp=" + state.cmp.join(",") : ""; history.replaceState(null, "", location.pathname + location.search + h); }
  function readHash() { const m = /cmp=([^&]+)/.exec(location.hash); if (m) state.cmp = decodeURIComponent(m[1]).split(",").filter(u => rows.some(r => r.uid === u)).slice(0, 4); if (state.cmp.length) state.sel = state.cmp[0]; }

  /* chart: specific energy against energy per cell, for records that state enough */
  const COL = { cylindrical: "var(--s1)", pouch: "var(--s2)", prismatic: "var(--s3)" };
  function drawChart(list) {
    const pts = list.filter(r => r.whkg != null && r.wh != null && r.wh > 0);
    const W = 900, H = 420, P = { l: 56, r: 16, t: 16, b: 44 };
    const xs = pts.map(p => Math.log10(p.wh)), ys = pts.map(p => p.whkg);
    const x0 = Math.floor(Math.min(-1, ...xs)), x1 = Math.ceil(Math.max(1, ...xs)), y1 = Math.ceil((Math.max(100, ...ys) + 20) / 50) * 50;
    const X = v => P.l + (Math.log10(v) - x0) / (x1 - x0) * (W - P.l - P.r), Y = v => H - P.b - (v / y1) * (H - P.t - P.b);
    let g = "";
    for (let e = x0; e <= x1; e++) { const x = X(Math.pow(10, e)); g += '<line x1="' + x + '" x2="' + x + '" y1="' + P.t + '" y2="' + (H - P.b) + '" stroke="var(--line)"/><text x="' + x + '" y="' + (H - P.b + 18) + '" text-anchor="middle" font-size="11" fill="var(--muted)">' + (Math.pow(10, e) >= 1 ? Math.pow(10, e).toLocaleString("en") : Math.pow(10, e)) + " Wh</text>"; }
    for (let y = 0; y <= y1; y += 50) { g += '<line x1="' + P.l + '" x2="' + (W - P.r) + '" y1="' + Y(y) + '" y2="' + Y(y) + '" stroke="var(--line)"/><text x="' + (P.l - 8) + '" y="' + (Y(y) + 4) + '" text-anchor="end" font-size="11" fill="var(--muted)">' + y + "</text>"; }
    g += '<text x="' + ((P.l + W - P.r) / 2) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="11.5" fill="var(--ink-2)">Energy per cell, Wh (log scale)</text>';
    g += '<text transform="translate(14 ' + ((P.t + H - P.b) / 2) + ') rotate(-90)" text-anchor="middle" font-size="11.5" fill="var(--ink-2)">Specific energy, Wh/kg</text>';
    const counts = {};
    pts.forEach(p => { const k = BD.FF[p.fmt] || "other"; counts[k] = (counts[k] || 0) + 1; const c = COL[k] || "var(--s0)"; g += '<circle cx="' + X(p.wh).toFixed(1) + '" cy="' + Y(p.whkg).toFixed(1) + '" r="' + (k === "other" ? 3.2 : 4.2) + '" fill="' + c + '" fill-opacity="' + (p.whkg_d ? .55 : .9) + '" stroke="var(--surface)" stroke-width="1.2" data-u="' + esc(p.uid) + '"/>'; });
    $("#chart").innerHTML = '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Specific energy against energy per cell">' + g + "</svg>";
    $("#legend").innerHTML = [["cylindrical", "var(--s1)"], ["pouch", "var(--s2)"], ["prismatic", "var(--s3)"], ["other / not stated", "var(--s0)"]].map(([k, c]) => "<span><i style=\"background:" + c + '"></i>' + k + " (" + (counts[k] || (k.startsWith("other") ? counts.other || 0 : 0)) + ")</span>").join("") + "<span>· pale = Wh/kg calculated, strong = printed</span>";
    const printed = pts.filter(p => !p.whkg_d).length;
    $("#chartcap").textContent = pts.length.toLocaleString("en") + " of " + list.length.toLocaleString("en") + " filtered records state capacity, voltage and mass, or print a specific energy (" + printed + " do). Upper bounds and lower bounds are not plotted. Hover a point for the cell; click to open its record.";
    const svg = $("#chart svg"), tip = $("#tip");
    svg.querySelectorAll("circle").forEach(c => { c.style.cursor = "pointer"; c.addEventListener("mousemove", e => { const r = rows.find(x => x.uid === c.dataset.u); tip.textContent = r.manu + " " + r.model + " · " + BD.fmt(r.wh) + " Wh · " + BD.fmt(r.whkg, 0) + " Wh/kg"; tip.hidden = false; tip.style.left = (e.clientX + 12) + "px"; tip.style.top = (e.clientY - 28) + "px"; }); c.addEventListener("mouseleave", () => tip.hidden = true); c.addEventListener("click", () => select(c.dataset.u)); });
  }

  /* coverage targets */
  async function coverage() {
    const segs = await getJSON("coverage-status.json").catch(() => []);
    $("#segs").innerHTML = segs.map(s => { const have = s.cells.filter(c => c.status === "sourced").length; return '<div class="seg-card"><b>' + esc(s.segment) + "</b><small>" + esc(s.note) + " · " + have + " of " + s.cells.length + " sourced</small><ul>" +
      s.cells.map(c => '<li class="' + (c.status === "sourced" ? "have" : "") + '">' + (c.uid && c.status === "sourced" ? '<a href="#" data-u="' + esc(c.uid) + '">' + esc(c.name) + "</a>" : esc(c.name)) + '<span class="st">' + (c.status === "sourced" ? "sourced" : "wanted") + "</span></li>").join("") + "</ul></div>"; }).join("");
    document.querySelectorAll("#segs a[data-u]").forEach(a => a.onclick = e => { e.preventDefault(); const u = a.dataset.u; state.kind.clear(); state.q = ""; $("#q").value = ""; render(); refreshFacets(); select(u); $("#finder").scrollIntoView({ behavior: "smooth" }); });
  }

  /* code sample */
  const CODE = {
    curl: '<b>curl</b> "https://design.lemonergy.com/api/data/demo/v1/batteries?q=21700"\n\n<b>#</b> one record, with every observation and its conditions\n<b>curl</b> "https://design.lemonergy.com/api/data/demo/v1/products/cell/samsung-sdi/inr21700-50e"',
    py: '<b>import</b> requests\n\nBASE = "https://design.lemonergy.com/api/data/demo/v1"\ncells = requests.get(f"{BASE}/batteries", params={"q": "21700"}).json()\n\n<b>for</b> c <b>in</b> cells["data"]:\n    cap = next(o <b>for</b> o <b>in</b> c["observations"] <b>if</b> o["quantity"] == "capacity")\n    print(c["model_number"], cap["value"], cap["unit"], cap["conditions"])',
    js: '<b>const</b> BASE = "https://design.lemonergy.com/api/data/demo/v1";\n<b>const</b> res = <b>await</b> fetch(`${BASE}/compare?products=cell/molicel/inr21700-p50b,cell/samsung-sdi/inr21700-50e`);\n<b>const</b> { data, catalog_release } = <b>await</b> res.json();\nconsole.log(catalog_release, data);  <b>// the release id makes the result reproducible</b>'
  };
  function setCode(l) { $("#codeblock").innerHTML = CODE[l]; document.querySelectorAll(".code .tabs [role=tab]").forEach(b => b.setAttribute("aria-selected", String(b.dataset.lang === l))); }

  function wire() {
    $("#sform").addEventListener("submit", e => { e.preventDefault(); state.q = $("#q").value; state.shown = 100; render(); });
    $("#q").addEventListener("input", e => { state.q = e.target.value; state.shown = 100; render(); refreshFacets(); });
    document.querySelectorAll(".chip").forEach(c => c.onclick = () => {
      if (c.dataset.stock !== undefined) { state.stock = true; const b = $("#f-stock"); if (b) b.checked = true; state.q = ""; $("#q").value = ""; state.chem.clear(); state.shown = 100; const l = render(); if (l[0]) select(l[0].uid); refreshFacets(); return; }
      if (c.dataset.kind !== undefined) { state.kind.clear(); if (c.dataset.kind) state.kind.add(c.dataset.kind); }
      state.chem.clear();
      if (c.dataset.chem) { state.chem.add(c.dataset.chem); state.q = ""; $("#q").value = ""; }
      else { state.q = c.dataset.q || ""; $("#q").value = state.q; }
      state.shown = 100; const list = render(); if (list[0]) select(list[0].uid); refreshFacets();
    });
    $("#f-core-only").addEventListener("change", e => { state.core = e.target.checked; refilter(); });
    const stockBox = $("#f-stock"), stockN = (summary && summary.available_now) || 0;
    if (stockBox) {
      stockBox.closest("label").hidden = stockN === 0;
      stockBox.addEventListener("change", e => { state.stock = e.target.checked; refilter(); });
    }
    $("#morebtn").onclick = () => { state.shown += 100; render(); };
    $("#csv").onclick = () => save("lemonergy-data-" + new Date().toISOString().slice(0, 10) + ".csv", BD.toCSV(sorted(filtered())), "text/csv");
    $("#v-table").onclick = () => { state.view = "table"; $("#v-table").setAttribute("aria-pressed", "true"); $("#v-chart").setAttribute("aria-pressed", "false"); $("#tableview").hidden = false; $("#chartview").hidden = true; };
    $("#v-chart").onclick = () => { state.view = "chart"; $("#v-chart").setAttribute("aria-pressed", "true"); $("#v-table").setAttribute("aria-pressed", "false"); $("#tableview").hidden = true; $("#chartview").hidden = false; render(); };
    $("#trayclear").onclick = $("#cmpbar-clear").onclick = () => { state.cmp = []; writeHash(); renderCmp(); if (state.sel) select(state.sel); };
    $("#cmpbar-go").onclick = e => { e.preventDefault(); $("#tray").scrollIntoView({ behavior: "smooth", block: "start" }); };
    $("#traylink").onclick = async e => { try { await navigator.clipboard.writeText(location.href); e.target.textContent = "Copied"; } catch (_) { e.target.textContent = "Copy the address bar"; } setTimeout(() => e.target.textContent = "Copy link", 1500); };
    setCode("curl");
    document.querySelectorAll(".code .tabs [role=tab]").forEach(b => b.onclick = () => setCode(b.dataset.lang));
    $("#copycode").onclick = async e => { try { await navigator.clipboard.writeText($("#codeblock").textContent); e.target.textContent = "Copied"; } catch (_) { e.target.textContent = "Select to copy"; } setTimeout(() => e.target.textContent = "Copy", 1500); };
  }

  boot();
})(typeof window !== "undefined" ? window : globalThis);
