/* ============================================================
   The cell library's filters
   ------------------------------------------------------------
   The 64 tiles are already in the page, written there by the
   generator. Filtering therefore never builds a tile: it hides
   the ones that do not match and reorders the rest with the
   `order` property, which the browser can do without touching
   the DOM tree. A filter change costs a style recalculation,
   not 64 rebuilt cards and 64 redrawn cells.
   ============================================================ */
"use strict";
(function () {
  const grid = document.getElementById("grid");
  if (!grid || !window.BD) return;
  const tiles = [...grid.children];
  const byUid = window.BD.byUid;
  const recs = tiles.map(t => {
    const uid = t.dataset.uid;
    const r = byUid[uid] || {};
    return {el: t, uid: uid, kind: r.kind, manu: r.manu, chem: r.chem, name: r.name,
            ah: +t.dataset.ah || -1, whkg: +t.dataset.whkg || -1, mass: +t.dataset.mass || Infinity};
  });
  const count = document.getElementById("lcount");
  const state = {kind: "", manu: "", chem: "", sort: "ah"};
  const SORTS = {
    ah: (a, b) => b.ah - a.ah,
    whkg: (a, b) => b.whkg - a.whkg,
    mass: (a, b) => a.mass - b.mass,
    name: (a, b) => a.name.localeCompare(b.name),
    maker: (a, b) => a.manu.localeCompare(b.manu) || a.name.localeCompare(b.name),
  };

  function apply() {
    const keep = recs.filter(r => (!state.kind || r.kind === state.kind) &&
                                  (!state.manu || r.manu === state.manu) &&
                                  (!state.chem || r.chem === state.chem));
    recs.forEach(r => { r.el.hidden = true; });
    keep.sort(SORTS[state.sort]).forEach((r, i) => { r.el.hidden = false; r.el.style.order = i; });
    count.textContent = keep.length === recs.length
      ? keep.length + " products"
      : keep.length + " of " + recs.length + " products";
    grid.classList.toggle("is-empty", !keep.length);
  }

  document.getElementById("kindseg").addEventListener("click", e => {
    const b = e.target.closest("button[data-kind]");
    if (!b) return;
    state.kind = b.dataset.kind;
    [...b.parentNode.children].forEach(x => x.setAttribute("aria-pressed", x === b));
    apply();
  });
  const bind = (id, key) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", e => { state[key] = e.target.value; apply(); });
  };
  bind("manupick", "manu"); bind("chempick", "chem"); bind("sortpick", "sort");
  apply();
})();
