# Pack designer

A static, no-build-step 3D battery pack designer that runs on the cells this
repository documents. Open `web/pack-designer/index.html` from any static file
server (or GitHub Pages); everything, including Three.js, is vendored.

## What it does

- **Design** — pick a cell (18 curated cells: cylindrical 18650/21700/26650/
  32700/4680, prismatic LFP/LTO, NMC pouches, Na-ion), set series × parallel,
  choose grid or staggered-hex packing for cylinders and stacking for
  prismatic/pouch, and adjust cell spacers, wall thickness and busbar
  headroom. The 3D view colors cells by series group (following the actual
  serpentine welding order) or chemistry, shows the enclosure and the series
  current path, and explodes for inspection.
- **From usage** — start from an application preset (e-bike, drone, ESS, EV,
  power tool, …) or raw requirements (voltage window, energy, continuous and
  peak power, charge rate, mass/size limits, temperature, cycle-life target).
  The optimizer enumerates cell × S × P candidates, sizes P by the binding
  constraint (energy vs continuous vs peak current), checks feasibility, and
  ranks the survivors with reasons and warnings.
- **Fit box** — enumerate arrangements, orientations and layer counts to
  pack the current configuration into a target envelope, or just minimize
  volume.
- **Standards** — a rule engine audits the design against UN 38.3 / IATA
  transport thresholds, ECE R100 / ISO 6469-3 voltage classes, IEC 62619 /
  IEC 62133-2 protection requirements, thermal-propagation spacing practice,
  and a certification-path map by application. Findings carry the actual
  numbers and the standard they derive from.

## Honesty rules

- Every cell record carries `dataQuality` (`datasheet` vs `estimate`) and a
  `sourceNote` saying exactly what was estimated. Cells from this repo's
  `contrib/cells/` YAMLs use those values verbatim.
- Pack mass adds 8% for interconnects plus an aluminium-wall estimate, and
  the UI says so. DCIR is cells-only (interconnects excluded), labeled.
- Standards output is engineering guidance derived from public standards —
  not certification, and the page repeats that disclaimer.
- Hex (staggered) packing is only offered where it is geometrically real:
  upright cylinders. Lying cylinders and prismatic cells pack rectangularly.

## Architecture

| File | Role |
|---|---|
| `js/cells.js` | Cell library + chemistry data (self-contained, no imports) |
| `js/presets.js` | Application usage presets |
| `js/standards.js` | Standards rule engine over a computed design context |
| `js/pack-engine.js` | Pure electrical + layout math (Z-up, mm) |
| `js/optimizer.js` | Requirement search + space fitting |
| `js/viewer3d.js` | Three.js instanced rendering |
| `js/app.js` | UI state and wiring |

The three data modules are import-free so they can be consumed by tooling
(node scripts, tests) without a browser.
