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
- **My space** — when the space is not a box. Pick a rectangle, circle,
  L-shape or long slot and type the measurements, or draw the outline corner
  by corner on a 10 mm grid. The plan view fills it with cells as you type and
  says how many fit, how much of the floor is used, and the best S/P split for
  12/24/36/48/52/72 V. "Use this space" pushes the footprint into the 3D view,
  where the enclosure follows the outline rather than a bounding box.
- **Standards** — a rule engine audits the design against UN 38.3 / IATA
  transport thresholds, ECE R100 / ISO 6469-3 voltage classes, IEC 62619 /
  IEC 62133-2 protection requirements, thermal-propagation spacing practice,
  and a certification-path map by application. Findings carry the actual
  numbers and the standard they derive from.

## Honesty rules

- Provenance is two fields, not one flag. `basis` says where the electrical
  core came from — `contrib` (a document held in this repository, named by
  `contribUid`), `external_datasheet`, `teardown`, `composite` or `recalled` —
  and `inferredFields` lists what was worked out rather than read. A cell can
  be sourced and still have inferred dimensions; one flag could not say that,
  and it marked the best-evidenced cells here as estimates while cells with no
  document at all read as datasheet-grade.
- `basis: 'contrib'` is checked, not asserted: `tools/check_pack_cells.py`
  runs in CI and fails if a `contribUid` resolves to nothing, if basis and
  contribUid disagree, or if a repeated value has drifted from the YAML.
- Pack mass adds 8% for interconnects plus an aluminium-wall estimate, and
  the UI says so. DCIR is cells-only (interconnects excluded), labeled — which
  also makes the short-circuit estimate an upper bound, stated as such.
- Power sizing and headroom are quoted at the MINIMUM pack voltage, not the
  nominal. A constant-power load draws its highest current at the bottom of
  the discharge, and sizing at nominal understates it by vNom/vMin — about
  1.44x for NMC. Designs that meet a rating on paper and overload at low SOC
  are exactly what that hides.
- Standards output is engineering guidance derived from public standards —
  not certification, and the page repeats that disclaimer.
- Hex (staggered) packing is only offered where it is geometrically real:
  upright cylinders. Lying cylinders and prismatic cells pack rectangularly.
- Fitting a cell into a footprint is an EXACT test, not a sampled one. A
  corners-only check passes a cell straddling a notch narrower than itself,
  and the pack then does not go in. Rectangular footprints test corner
  containment plus wall-edge intersection; round footprints test distance to
  every edge. `web/pack-designer/test/shape.test.mjs` holds that line in CI.
- Volume for a non-rectangular space is the prism over the actual footprint,
  not over its bounding box — a circle would otherwise be flattered by 4/pi.
- Asking for more cells than the space holds returns what fits and reports the
  shortfall, rather than drawing cells through the wall.

## Architecture

| File | Role |
|---|---|
| `js/cells.js` | Cell library + chemistry data (self-contained, no imports) |
| `js/presets.js` | Application usage presets |
| `js/standards.js` | Standards rule engine over a computed design context |
| `js/pack-engine.js` | Pure electrical + layout math (Z-up, mm) |
| `js/optimizer.js` | Requirement search + space fitting |
| `js/shape.js` | Footprint geometry: primitives, exact fit tests, filling |
| `js/space-ui.js` | The "My space" tab: shape picker, plan view, capacity |
| `js/viewer3d.js` | Three.js instanced rendering |
| `js/app.js` | UI state and wiring |

The three data modules are import-free so they can be consumed by tooling
(node scripts, tests) without a browser.
