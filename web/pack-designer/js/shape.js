// shape.js — the space the pack has to live in, when that space is not a box.
//
// Real installations are rarely rectangular. A boat locker is a wedge, a
// bicycle downtube is a long slot, a wall cavity has a pipe through it, and a
// drone bay is whatever was left after the electronics. Asking someone for a
// width, a depth and a height and then quietly packing a cuboid gives them a
// number they cannot use.
//
// So the footprint is a polygon. Everything here is plain geometry in
// millimetres on the XY plane, with Z handled by layer count elsewhere:
//   - a few parametric shapes for people who want to type numbers
//   - an arbitrary polygon for people who want to draw one
//   - an EXACT test for whether a cell fits, not a sampled one
//
// Exactness matters more than it sounds. A sampled test (are the four corners
// inside?) passes a cell that straddles a notch narrower than itself, and the
// pack then does not physically go in. Both tests here are exact for
// polygons: rectangles by segment intersection, circles by distance to edge.
//
// No imports, no DOM, so this can be unit-tested with node.

export const SHAPE_KINDS = ['rect', 'circle', 'lshape', 'polygon'];

// ---------------------------------------------------------------------------
// Parametric shapes -> polygon
// ---------------------------------------------------------------------------
// Every shape resolves to a closed CCW-ish ring of {x, y}, centred on its own
// bounding box so the 3D view and the layout agree about where the origin is.

const CIRCLE_SEGMENTS = 96;   // 0.03% area error at this count; visually round

export function shapeToPolygon(shape) {
  switch (shape.kind) {
    case 'rect': {
      const w = num(shape.w, 200), d = num(shape.d, 150);
      return centre([
        { x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: d }, { x: 0, y: d },
      ]);
    }
    case 'circle': {
      const r = num(shape.diameter, 200) / 2;
      const pts = [];
      for (let i = 0; i < CIRCLE_SEGMENTS; i++) {
        const a = (i / CIRCLE_SEGMENTS) * Math.PI * 2;
        pts.push({ x: r + r * Math.cos(a), y: r + r * Math.sin(a) });
      }
      return centre(pts);
    }
    case 'lshape': {
      // Outer w x d with a bite taken out of the top-right corner. The bite
      // is what makes this useful: it is the pipe, the wheel arch, the strut.
      const w = num(shape.w, 300), d = num(shape.d, 220);
      const cw = Math.min(num(shape.cutW, 120), w - 1);
      const cd = Math.min(num(shape.cutD, 90), d - 1);
      return centre([
        { x: 0, y: 0 }, { x: w, y: 0 }, { x: w, y: d - cd },
        { x: w - cw, y: d - cd }, { x: w - cw, y: d }, { x: 0, y: d },
      ]);
    }
    case 'polygon':
    default: {
      const pts = (shape.points || []).map((p) => ({ x: num(p.x, 0), y: num(p.y, 0) }));
      return pts.length >= 3 ? centre(pts) : [];
    }
  }
}

function num(v, dflt) {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : dflt;
}

function centre(pts) {
  const b = bbox(pts);
  const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2;
  return pts.map((p) => ({ x: p.x - cx, y: p.y - cy }));
}

export function bbox(pts) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of pts) {
    if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
  }
  return pts.length
    ? { minX, minY, maxX, maxY, w: maxX - minX, d: maxY - minY }
    : { minX: 0, minY: 0, maxX: 0, maxY: 0, w: 0, d: 0 };
}

// Shoelace. Sign tells winding; callers want the magnitude.
export function area(pts) {
  let a = 0;
  for (let i = 0, n = pts.length; i < n; i++) {
    const p = pts[i], q = pts[(i + 1) % n];
    a += p.x * q.y - q.x * p.y;
  }
  return Math.abs(a) / 2;
}

// ---------------------------------------------------------------------------
// Point and fit tests
// ---------------------------------------------------------------------------

// Ray casting. Points exactly on an edge are not relied upon either way; the
// fit tests below never depend on the boundary case because they also require
// clearance.
export function pointInPolygon(pt, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i], b = poly[j];
    if ((a.y > pt.y) !== (b.y > pt.y)
        && pt.x < ((b.x - a.x) * (pt.y - a.y)) / (b.y - a.y) + a.x) {
      inside = !inside;
    }
  }
  return inside;
}

// Shortest distance from a point to a segment. Used for the round-footprint
// test, where "does it fit" is exactly "is the centre further from every edge
// than the radius".
function distToSegment(p, a, b) {
  const vx = b.x - a.x, vy = b.y - a.y;
  const len2 = vx * vx + vy * vy;
  let t = len2 === 0 ? 0 : ((p.x - a.x) * vx + (p.y - a.y) * vy) / len2;
  t = Math.max(0, Math.min(1, t));
  const dx = p.x - (a.x + t * vx), dy = p.y - (a.y + t * vy);
  return Math.hypot(dx, dy);
}

export function distToPolygon(pt, poly) {
  let best = Infinity;
  for (let i = 0, n = poly.length; i < n; i++) {
    const d = distToSegment(pt, poly[i], poly[(i + 1) % n]);
    if (d < best) best = d;
  }
  return best;
}

function segmentsCross(p1, p2, p3, p4) {
  const d = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const d1 = d(p3, p4, p1), d2 = d(p3, p4, p2);
  const d3 = d(p1, p2, p3), d4 = d(p1, p2, p4);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

// Does a cell footprint centred at (cx, cy) lie entirely inside the polygon?
//
// round: circular footprint of diameter fx (an upright cylinder)
// otherwise: axis-aligned rectangle fx by fy
//
// clearance is subtracted from the usable space — the enclosure wall, plus
// whatever the person wants to keep free.
export function footprintFits(cx, cy, fx, fy, round, poly, clearance = 0) {
  const c = { x: cx, y: cy };
  if (!pointInPolygon(c, poly)) return false;
  if (round) {
    return distToPolygon(c, poly) >= fx / 2 + clearance;
  }
  const hx = fx / 2 + clearance, hy = fy / 2 + clearance;
  const corners = [
    { x: cx - hx, y: cy - hy }, { x: cx + hx, y: cy - hy },
    { x: cx + hx, y: cy + hy }, { x: cx - hx, y: cy + hy },
  ];
  // Every corner inside, and no wall crossing an edge of the footprint. The
  // second half is what a corners-only test misses: a notch narrower than the
  // cell can pass straight through with all four corners still inside.
  for (const p of corners) if (!pointInPolygon(p, poly)) return false;
  for (let i = 0; i < 4; i++) {
    const a = corners[i], b = corners[(i + 1) % 4];
    for (let j = 0, n = poly.length; j < n; j++) {
      if (segmentsCross(a, b, poly[j], poly[(j + 1) % n])) return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
// Filling a shape with cells
// ---------------------------------------------------------------------------

// Lay a lattice over the polygon's bounding box and keep the positions where a
// whole cell fits. Returns them in serpentine order (row by row, alternating
// direction) so that consecutive cells are neighbours and a parallel group
// stays physically together — the same convention layoutPack uses.
//
// pitchX / pitchY come from the caller so hex and grid share this code.
export function fillShape(poly, fx, fy, round, pitchX, pitchY, clearance, hexOffset = false) {
  if (poly.length < 3) return [];
  const b = bbox(poly);
  const rows = [];
  const nRows = Math.max(1, Math.floor(b.d / pitchY) + 2);
  const nCols = Math.max(1, Math.floor(b.w / pitchX) + 2);
  for (let iy = 0; iy < nRows; iy++) {
    const y = b.minY + fy / 2 + iy * pitchY;
    if (y - fy / 2 > b.maxY) break;
    const row = [];
    const shift = (hexOffset && iy % 2 === 1) ? pitchX / 2 : 0;
    for (let ix = 0; ix < nCols; ix++) {
      const x = b.minX + fx / 2 + shift + ix * pitchX;
      if (x - fx / 2 > b.maxX) break;
      if (footprintFits(x, y, fx, fy, round, poly, clearance)) row.push({ x, y });
    }
    if (row.length) rows.push(row);
  }
  // Serpentine.
  const out = [];
  rows.forEach((row, i) => {
    const ordered = i % 2 === 0 ? row : row.slice().reverse();
    for (const p of ordered) out.push(p);
  });
  return out;
}

// How many cells the shape holds, and how well the space is used. Reported
// before anyone commits to a topology, because "your locker holds 84 cells"
// is the number that decides whether the project is possible at all.
export function shapeCapacity(poly, fx, fy, round, pitchX, pitchY, clearance, hexOffset) {
  const pts = fillShape(poly, fx, fy, round, pitchX, pitchY, clearance, hexOffset);
  const cellArea = round ? Math.PI * (fx / 2) ** 2 : fx * fy;
  const a = area(poly);
  return {
    count: pts.length,
    positions: pts,
    areaMm2: a,
    utilisation: a > 0 ? (pts.length * cellArea) / a : 0,
  };
}

// ---------------------------------------------------------------------------
// Presets — the shapes people actually ask for, as starting points
// ---------------------------------------------------------------------------

export const SHAPE_PRESETS = [
  { id: 'box', name: 'Rectangle', kind: 'rect', w: 300, d: 200, heightMm: 120,
    hint: 'A plain box. Type the two numbers you measured.' },
  { id: 'round', name: 'Circle', kind: 'circle', diameter: 260, heightMm: 150,
    hint: 'A drum, a tube, a round hatch.' },
  { id: 'lbay', name: 'L-shape', kind: 'lshape', w: 320, d: 240, cutW: 130, cutD: 95, heightMm: 140,
    hint: 'A rectangle with a corner taken out — a strut, a wheel arch, a pipe.' },
  { id: 'slot', name: 'Long slot', kind: 'rect', w: 480, d: 80, heightMm: 90,
    hint: 'A downtube or a rail. Long and narrow changes which cell wins.' },
];
