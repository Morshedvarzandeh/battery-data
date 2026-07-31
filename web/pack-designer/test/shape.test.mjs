// Geometry tests for the footprint editor.
//
// The claim worth testing is exactness. A fit test that samples the corners of
// a cell passes a cell straddling a notch narrower than itself, and the pack
// then does not physically go into the space someone measured. Half of what is
// below exists to hold that line.
//
//     node web/pack-designer/test/shape.test.mjs

import {
  shapeToPolygon, bbox, area, pointInPolygon, distToPolygon,
  footprintFits, fillShape, shapeCapacity, SHAPE_PRESETS,
} from '../js/shape.js';
import { layoutInShape, summarize, orientedFootprint } from '../js/pack-engine.js';
import { cellById } from '../js/cells.js';

let failures = 0;
const ok = (name, cond) => {
  if (cond) { console.log(`  ok    ${name}`); } else { console.log(`  FAIL  ${name}`); failures++; }
};
const near = (a, b, tol = 1e-6) => Math.abs(a - b) <= tol;

console.log('shapes resolve to the polygons they claim');
{
  ok('rect area', near(area(shapeToPolygon({ kind: 'rect', w: 200, d: 100 })), 20000));
  const c = shapeToPolygon({ kind: 'circle', diameter: 200 });
  ok('circle area within 0.1% of pi*r^2',
     Math.abs(area(c) - Math.PI * 1e4) / (Math.PI * 1e4) < 0.001);
  ok('L area = outer minus the bite',
     near(area(shapeToPolygon({ kind: 'lshape', w: 300, d: 200, cutW: 100, cutD: 50 })),
          300 * 200 - 100 * 50));
  ok('polygon under three points is empty',
     shapeToPolygon({ kind: 'polygon', points: [{ x: 0, y: 0 }, { x: 1, y: 1 }] }).length === 0);
  ok('every preset resolves', SHAPE_PRESETS.every((p) => shapeToPolygon(p).length >= 3));
  const b = bbox(shapeToPolygon({ kind: 'rect', w: 300, d: 120 }));
  ok('shapes are centred on their bounding box',
     near(b.minX, -150) && near(b.maxX, 150) && near(b.minY, -60) && near(b.maxY, 60));
}

console.log('point and distance tests');
{
  const sq = shapeToPolygon({ kind: 'rect', w: 100, d: 100 });
  ok('centre is inside', pointInPolygon({ x: 0, y: 0 }, sq));
  ok('outside is outside', !pointInPolygon({ x: 60, y: 0 }, sq));
  ok('distance to wall is exact', near(distToPolygon({ x: 0, y: 0 }, sq), 50, 1e-9));
}

console.log('fit is exact, not sampled');
{
  // A slot narrower than the cell, cut into the top edge. All four corners of
  // a cell centred above it are inside the polygon; the cell still does not
  // fit, because the wall passes straight through it.
  const notch = [
    { x: -100, y: -50 }, { x: 100, y: -50 }, { x: 100, y: 50 },
    { x: 10, y: 50 }, { x: 10, y: 0 }, { x: -10, y: 0 },
    { x: -10, y: 50 }, { x: -100, y: 50 },
  ];
  ok('cell straddling a sub-cell notch is rejected',
     footprintFits(0, 25, 40, 40, false, notch, 0) === false);
  ok('the same cell in clear space is accepted',
     footprintFits(-60, -25, 40, 40, false, notch, 0) === true);

  const sq = shapeToPolygon({ kind: 'rect', w: 100, d: 100 });
  ok('round cell exactly filling the square fits', footprintFits(0, 0, 100, 100, true, sq, 0));
  ok('a hair larger does not', !footprintFits(0, 0, 100.2, 100, true, sq, 0));
  ok('clearance is subtracted from the space',
     footprintFits(0, 0, 90, 90, true, sq, 4) && !footprintFits(0, 0, 90, 90, true, sq, 6));
}

console.log('filling');
{
  const sq = shapeToPolygon({ kind: 'rect', w: 210, d: 210 });
  const hex = shapeCapacity(sq, 21, 21, true, 22, 22 * Math.sqrt(3) / 2, 0, true);
  const grid = shapeCapacity(sq, 21, 21, true, 22, 22, 0, false);
  ok('hex fits more than grid in the same square', hex.count > grid.count);
  ok('utilisation is a fraction under 1', hex.utilisation > 0 && hex.utilisation < 1);

  let maxStep = 0;
  for (let i = 1; i < hex.positions.length; i++) {
    const a = hex.positions[i - 1], b = hex.positions[i];
    maxStep = Math.max(maxStep, Math.hypot(a.x - b.x, a.y - b.y));
  }
  ok('serpentine order keeps consecutive cells adjacent', maxStep < 44);

  // Every placed cell must actually be inside, which is the property the whole
  // module exists to guarantee.
  ok('every placed cell fits',
     hex.positions.every((q) => footprintFits(q.x, q.y, 21, 21, true, sq, 0)));

  ok('a space smaller than one cell holds nothing',
     fillShape(shapeToPolygon({ kind: 'rect', w: 10, d: 10 }), 21, 21, true, 22, 22, 0, false).length === 0);
}

console.log('layout in a shape');
{
  const cell = cellById('samsung-inr21700-50e');
  const poly = shapeToPolygon({ kind: 'lshape', w: 320, d: 240, cutW: 130, cutD: 95 });
  const L = layoutInShape(cell, 13, 8, poly, { heightMm: 140 });
  ok('layout is produced', !!L);
  ok('placed count never exceeds capacity', L.N <= L.capacity);
  ok('positions match N', L.positions.length === L.N);
  const od = orientedFootprint(cell, 'upright');
  ok('every laid-out cell is inside the polygon',
     L.positions.every((q) => footprintFits(q.x, q.y, od.fx, od.fy, od.round, poly, L.wallMm)));

  // Volume must be the prism over the footprint, not the bounding box: a
  // circle in a bounding box would be flattered by 4/pi otherwise.
  const circle = shapeToPolygon({ kind: 'circle', diameter: 260 });
  const C = layoutInShape(cell, 10, 5, circle, { heightMm: 150 });
  const bboxVolL = (bbox(circle).w * bbox(circle).d * C.outer.z) / 1e6;
  ok('circle volume is the prism, not the bounding box',
     C.volumeL < bboxVolL * 0.8);

  // An over-ask is reported, not silently drawn through the wall.
  const tight = layoutInShape(cell, 50, 50, shapeToPolygon({ kind: 'rect', w: 120, d: 120 }),
    { heightMm: 100 });
  ok('shortfall is reported when the ask exceeds the space',
     tight.shortfall === tight.wanted - tight.capacity && tight.shortfall > 0);
  ok('a space too small for any cell returns null',
     layoutInShape(cell, 1, 1, shapeToPolygon({ kind: 'rect', w: 12, d: 12 }), { heightMm: 100 }) === null);

  const s = summarize(cell, L.s, L.p, L);
  ok('summary energy matches the cells actually placed',
     near(s.energyWh, L.s * L.p * cell.nominalV * cell.capacityAh, 1e-6));
}

console.log(failures ? `\n${failures} failure(s)` : '\nall shape tests pass');
process.exit(failures ? 1 : 0);
