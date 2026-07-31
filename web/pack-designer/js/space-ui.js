// space-ui.js — the "My space" tab: say what shape the space is, see what fits.
//
// The whole point is that this must not feel like CAD. Someone who has just
// measured a locker with a tape should be able to type two numbers and get an
// answer, the way they would on a pocket calculator. Drawing is there for the
// awkward shapes, but it is the second option, not the first — a tool that
// opens on a blank canvas and a pen tool has already lost most of the people
// it was built for.
//
// So: four shapes as buttons, a couple of number fields, and a plan view that
// redraws as you type. Drawing is one more button along.

import { SHAPE_PRESETS, shapeToPolygon, bbox, area, shapeCapacity } from './shape.js';

const $ = (id) => document.getElementById(id);

// Which numbers each shape needs. Kept to the fewest that define it — nobody
// wants to fill in eight boxes to describe a rectangle.
const FIELDS = {
  rect:    [['w', 'Width'], ['d', 'Depth']],
  circle:  [['diameter', 'Diameter']],
  lshape:  [['w', 'Width'], ['d', 'Depth'], ['cutW', 'Cut width'], ['cutD', 'Cut depth']],
  polygon: [],
};

export class SpaceUI {
  constructor(onApply, getCellContext) {
    this.onApply = onApply;
    this.getCellContext = getCellContext;   // () => {cell, od, pitchX, pitchY, hex}
    this.shape = { ...SHAPE_PRESETS[0] };
    this.drawing = false;
    this.dragIndex = -1;
    this.lastFit = null;
    this._build();
  }

  _build() {
    const pick = $('shapePick');
    pick.innerHTML = '';
    for (const pr of SHAPE_PRESETS) {
      const b = document.createElement('button');
      b.textContent = pr.name;
      b.dataset.id = pr.id;
      b.onclick = () => { this.shape = { ...pr }; this.drawing = false; this._sync(); };
      pick.appendChild(b);
    }
    const draw = document.createElement('button');
    draw.textContent = 'Draw my own';
    draw.dataset.id = 'draw';
    draw.onclick = () => {
      this.shape = { id: 'draw', kind: 'polygon', points: [], heightMm: 120,
        hint: 'Click in the plan view to place each corner, in order round the outline.' };
      this.drawing = true;
      this._sync();
    };
    pick.appendChild(draw);

    $('btnUndoPt').onclick = () => {
      if (this.shape.points?.length) { this.shape.points.pop(); this._sync(); }
    };
    $('btnClearPts').onclick = () => { this.shape.points = []; this._sync(); };
    $('btnApplyShape').onclick = () => {
      if (this.lastFit?.poly?.length >= 3) this.onApply(this.shape, this.lastFit);
    };

    for (const id of ['shHeight', 'shWall', 'shGap']) {
      $(id).oninput = () => this._sync();
    }
    this._wireCanvas();
    this._sync();
  }

  // --- canvas -------------------------------------------------------------

  _wireCanvas() {
    const c = $('shapeCanvas');
    const toMm = (ev) => {
      const r = c.getBoundingClientRect();
      const px = (ev.clientX - r.left) * (c.width / r.width);
      const py = (ev.clientY - r.top) * (c.height / r.height);
      const v = this._view;
      if (!v) return null;
      return {
        x: Math.round(((px - v.ox) / v.k) / 10) * 10,   // snap to 10 mm
        y: Math.round(((v.oy - py) / v.k) / 10) * 10,
      };
    };

    c.addEventListener('pointerdown', (ev) => {
      if (!this.drawing) return;
      const m = toMm(ev); if (!m) return;
      const pts = this.shape.points || (this.shape.points = []);
      // Grab an existing corner if the click is near one, else add a corner.
      const hit = pts.findIndex((p) => Math.hypot(p.x - m.x, p.y - m.y) < 14);
      if (hit >= 0) { this.dragIndex = hit; c.setPointerCapture(ev.pointerId); }
      else { pts.push(m); this._sync(); }
    });
    c.addEventListener('pointermove', (ev) => {
      if (this.dragIndex < 0) return;
      const m = toMm(ev); if (!m) return;
      this.shape.points[this.dragIndex] = m;
      this._sync();
    });
    const stop = () => { this.dragIndex = -1; };
    c.addEventListener('pointerup', stop);
    c.addEventListener('pointercancel', stop);
  }

  // --- state --------------------------------------------------------------

  _readFields() {
    for (const [key] of FIELDS[this.shape.kind] || []) {
      const el = $('sf_' + key);
      if (el) this.shape[key] = Number(el.value) || this.shape[key];
    }
    this.shape.heightMm = Number($('shHeight').value) || 120;
  }

  _renderFields() {
    const host = $('shapeFields');
    const spec = FIELDS[this.shape.kind] || [];
    host.innerHTML = '';
    for (const [key, label] of spec) {
      const wrap = document.createElement('div');
      wrap.innerHTML = `<label class="f">${label}</label>`;
      const inp = document.createElement('input');
      inp.type = 'number'; inp.id = 'sf_' + key; inp.value = this.shape[key] ?? '';
      inp.min = '1';
      inp.oninput = () => { this._readFields(); this._sync(false); };
      wrap.appendChild(inp);
      host.appendChild(wrap);
    }
    $('shapeNumbers').style.display = spec.length ? '' : 'none';
    $('shapeDrawSec').style.display = this.drawing ? '' : 'none';
  }

  _sync(rebuildFields = true) {
    document.querySelectorAll('#shapePick button').forEach((b) =>
      b.classList.toggle('on', b.dataset.id === (this.drawing ? 'draw' : this.shape.id)));
    $('shapeHint').textContent = this.shape.hint || '';
    if (rebuildFields) this._renderFields();
    else $('shapeDrawSec').style.display = this.drawing ? '' : 'none';
    this._readFields();
    this._compute();
    this._draw();
  }

  _compute() {
    const poly = shapeToPolygon(this.shape);
    const ctx = this.getCellContext();
    const host = $('shapeFit');
    if (poly.length < 3 || !ctx) {
      this.lastFit = { poly };
      host.innerHTML = `<div class="empty">${
        this.drawing ? 'Place at least three corners.' : 'Enter the measurements.'}</div>`;
      return;
    }
    const wall = Number($('shWall').value) || 0;
    const gap = Number($('shGap').value) || 0;
    const { cell, od } = ctx;
    const pitchX = od.fx + gap;
    const pitchY = ctx.hex ? pitchX * (Math.sqrt(3) / 2) : od.fy + gap;
    const cap = shapeCapacity(poly, od.fx, od.fy, od.round, pitchX, pitchY, wall, ctx.hex);

    // Layers the stated height allows.
    const headroom = cell.form === 'cylindrical' ? 8 : 15;
    const usableZ = this.shape.heightMm - 2 * wall - headroom;
    const layers = Math.max(0, Math.floor((usableZ + 2) / (od.fz + 2)));
    const total = cap.count * layers;

    this.lastFit = { poly, perLayer: cap.count, layers, total, wall, gap,
                     utilisation: cap.utilisation, positions: cap.positions };

    const b = bbox(poly);
    const wh = total * cell.nominalV * cell.capacityAh;
    const kg = (total * cell.massG) / 1000;
    host.innerHTML = total === 0
      ? `<div class="fitwarn">No ${cell.name} fits in this space. It needs at least
         ${fmt(od.fx + 2 * wall)} &times; ${fmt(od.fy + 2 * wall)} mm of floor and
         ${fmt(od.fz + 2 * wall + headroom)} mm of height.</div>`
      : `<div class="fitbig">${total} cells</div>
         <div class="fitline"><span>per layer</span><b>${cap.count}</b></div>
         <div class="fitline"><span>layers that fit the height</span><b>${layers}</b></div>
         <div class="fitline"><span>floor area used</span><b>${(cap.utilisation * 100).toFixed(0)}%</b></div>
         <div class="fitline"><span>bounding size</span><b>${fmt(b.w)} &times; ${fmt(b.d)} mm</b></div>
         <div class="fitline"><span>energy if filled</span><b>${fmt(wh)} Wh</b></div>
         <div class="fitline"><span>cell mass</span><b>${kg.toFixed(1)} kg</b></div>
         ${this._topologies(total, cell)}`;
  }

  // Series/parallel splits that use the whole space. Someone who knows their
  // system voltage cares about this line and nothing else on the page.
  _topologies(total, cell) {
    const rows = [];
    for (const v of [12, 24, 36, 48, 52, 72]) {
      const s = Math.round(v / cell.nominalV);
      if (s < 1) continue;
      const p = Math.floor(total / s);
      if (p < 1) continue;
      rows.push(`<div class="fitline"><span>${v} V nominal</span>
        <b>${s}S${p}P · ${fmt(s * p * cell.nominalV * cell.capacityAh)} Wh</b></div>`);
    }
    return rows.length
      ? `<div style="margin-top:10px;padding-top:8px;border-top:1px solid var(--line)">
           <div class="f" style="margin-bottom:2px">Best use of the space</div>${rows.join('')}</div>`
      : '';
  }

  // --- drawing ------------------------------------------------------------

  _draw() {
    const c = $('shapeCanvas'), g = c.getContext('2d');
    const poly = this.lastFit?.poly || [];
    const css = getComputedStyle(document.body);
    const ink = css.getPropertyValue('--ink') || '#111';
    const line = css.getPropertyValue('--line') || '#ddd';
    const accent = css.getPropertyValue('--accent') || '#0e9c82';
    g.clearRect(0, 0, c.width, c.height);

    if (poly.length < 3) {
      this._view = { k: 1, ox: c.width / 2, oy: c.height / 2 };
      if (this.drawing) this._drawGrid(g, c, line);
      this._drawPoints(g, accent);
      $('shapeScale').textContent = '';
      return;
    }

    const b = bbox(poly);
    const pad = 34;
    const k = Math.min((c.width - 2 * pad) / Math.max(b.w, 1),
                       (c.height - 2 * pad) / Math.max(b.d, 1));
    const ox = c.width / 2, oy = c.height / 2;
    this._view = { k, ox, oy };
    const X = (mm) => ox + mm * k, Y = (mm) => oy - mm * k;

    this._drawGrid(g, c, line);

    // Cells first, so the outline reads on top of them.
    const ctx = this.getCellContext();
    const pos = this.lastFit.positions || [];
    if (ctx && pos.length) {
      const { od } = ctx;
      g.fillStyle = withAlpha(accent, 0.5);
      g.strokeStyle = withAlpha(accent, 0.9);
      g.lineWidth = 1;
      for (const q of pos) {
        g.beginPath();
        if (od.round) g.arc(X(q.x), Y(q.y), (od.fx / 2) * k, 0, Math.PI * 2);
        else g.rect(X(q.x - od.fx / 2), Y(q.y + od.fy / 2), od.fx * k, od.fy * k);
        g.fill(); g.stroke();
      }
    }

    // Outline.
    g.beginPath();
    poly.forEach((p, i) => (i ? g.lineTo(X(p.x), Y(p.y)) : g.moveTo(X(p.x), Y(p.y))));
    g.closePath();
    g.strokeStyle = ink; g.lineWidth = 2; g.stroke();

    this._drawPoints(g, accent);
    this._dimensions(g, b, X, Y, ink);
    $('shapeScale').textContent =
      `${fmt(b.w)} × ${fmt(b.d)} mm · ${(area(poly) / 100).toFixed(0)} cm² floor`
      + (this.lastFit.perLayer ? ` · ${this.lastFit.perLayer} cells per layer` : '');
  }

  _drawGrid(g, c, line) {
    const v = this._view; if (!v) return;
    const step = 10 * v.k;
    if (step < 4) return;
    g.strokeStyle = withAlpha(line, 0.7); g.lineWidth = 0.5;
    g.beginPath();
    for (let x = v.ox % step; x < c.width; x += step) { g.moveTo(x, 0); g.lineTo(x, c.height); }
    for (let y = v.oy % step; y < c.height; y += step) { g.moveTo(0, y); g.lineTo(c.width, y); }
    g.stroke();
  }

  _drawPoints(g, accent) {
    if (!this.drawing) return;
    const v = this._view, pts = this.shape.points || [];
    g.fillStyle = accent;
    for (const p of pts) {
      g.beginPath();
      g.arc(v.ox + p.x * v.k, v.oy - p.y * v.k, 4.5, 0, Math.PI * 2);
      g.fill();
    }
  }

  // Two dimension lines. Anything more turns a plan view into a drawing, and
  // the person already knows what they measured.
  _dimensions(g, b, X, Y, ink) {
    g.strokeStyle = withAlpha(ink, 0.45);
    g.fillStyle = withAlpha(ink, 0.75);
    g.lineWidth = 1;
    g.font = '11px ui-monospace, monospace';
    g.textAlign = 'center';
    const yb = Y(b.minY) + 16;
    g.beginPath(); g.moveTo(X(b.minX), yb); g.lineTo(X(b.maxX), yb); g.stroke();
    g.fillText(`${fmt(b.w)}`, (X(b.minX) + X(b.maxX)) / 2, yb + 13);
    const xl = X(b.minX) - 14;
    g.beginPath(); g.moveTo(xl, Y(b.minY)); g.lineTo(xl, Y(b.maxY)); g.stroke();
    g.save();
    g.translate(xl - 6, (Y(b.minY) + Y(b.maxY)) / 2);
    g.rotate(-Math.PI / 2);
    g.fillText(`${fmt(b.d)}`, 0, 0);
    g.restore();
  }

  refresh() { this._sync(false); }
}

function fmt(v) {
  return v >= 100 ? Math.round(v).toString() : (Math.round(v * 10) / 10).toString();
}

// Canvas has no notion of a CSS variable, and the theme colours arrive as hex
// or rgb strings. Cheap conversion beats duplicating the palette here.
function withAlpha(col, a) {
  const c = String(col).trim();
  if (c.startsWith('#')) {
    const h = c.length === 4
      ? c.slice(1).split('').map((x) => x + x).join('')
      : c.slice(1, 7);
    const n = parseInt(h, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  const m = c.match(/(\d+)[,\s]+(\d+)[,\s]+(\d+)/);
  return m ? `rgba(${m[1]},${m[2]},${m[3]},${a})` : c;
}
