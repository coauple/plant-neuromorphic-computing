// Sinyal yayılımı paneli — duyusal lob + pattern lob CANLI şeması.
//
// Topoloji ve yerleşim prototipten (kullanıcının verdiği şema); sürücü
// canlıdır: P1 (bitki faz hattı) ateşi frame.lobes.p1'den (hat 0=p1a,
// 1=p1b; T-satırı p1 bitleri), P2 ateşi frame.lobes.aff'tan (post=P2
// indeksi), pattern act/spike frame.lobes.k4'ten (live_k4 akışı),
// sensör teli frame.sensors'tan, kablo /ws/npu telemetrisinden (wire/f).
// Örnek/sentetik atım YOK: olay gelmezse şema sessiz durur. Gelen TEK
// gerçek atım tel boyunca dal-dal kaskadla gezer (gecikme sahnelemedir).

const NS = "http://www.w3.org/2000/svg";
const SVG_W = 1540;
function T(x, y) { return [SVG_W - y, x]; }

const NUM_UNITS = 29;
const P1_SLOTS = 16, P2_SLOTS = 64, SA = 7, SB = 8;  // p1a=slot7, p1b=slot8
const ORD_A = [0, 2, 3, 5, 6, 8], ORD_B = [1, 4, 7, 9];
const C_PLANT = "#7fd6a0", C_SENS = "#f0b56a", C_AFF = "#7fb0d1";
const SENS_KEYS = ["hn", "hs", "ec", "ts", "tn", "ph", "npk"];

const P2 = [
  { id: "p2a", sens: "HN",  line: "a", tau: 35, w0: 0.2 },
  { id: "p2b", sens: "HS",  line: "b", tau: 45, w0: 0.2 },
  { id: "p2c", sens: "HN",  line: "a", tau: 35, w0: 0.1, kind: "kopya" },
  { id: "p2d", sens: "HN",  line: "a", tau: 36, w0: 0,   kind: "decoy" },
  { id: "p2e", sens: "HS",  line: "b", tau: 46, w0: 0,   kind: "decoy" },
  { id: "p2f", sens: "EC",  line: "a", tau: 26, w0: 0.2, neg: true },
  { id: "p2g", sens: "TS",  line: "a", tau: 37, w0: null },
  { id: "p2h", sens: "TN",  line: "b", tau: 37, w0: null },
  { id: "p2i", sens: "PH",  line: "a", tau: 37, w0: null },
  { id: "p2j", sens: "NPK", line: "b", tau: 37, w0: null },
];

const G_ACT = { comps: [7, 19], rc: 3.6, soma: 38, rs: 7, c: [[0, 3], [7, 7], [19, 7], [38, 10], [54, 3.5], [70, 3.5]] };
const G_RES = G_ACT;
const G_P1 = { comps: [9], rc: 3.6, soma: 32, rs: 8, c: [[0, 3], [9, 6], [32, 10]] };

export function initSignal(svg, ids) {
  const S = {
    svg, ids, lobeSegs: [], SEG: {}, LI: {}, waveItems: [],
    neurons: [], LN: { proot: null, sroot: null, p1: [], n2: [] },
    ring: [], p1: [], acts: [], AKEY: {}, T1KEYS: [], T2KEYS: [],
    SW: [], AFKEYS: [], AFTREE: null, rootDot: null,
    lastAffTick: -1, lastP1Tick: -1, lastK4Tick: -1, lastTeleT: -1,
    firedP2: new Map(), firedP1: new Map(), firedPat: new Map(), raf: 0,
  };
  buildPatternTree(S);
  buildSensoryLobe(S);
  buildWaveLayers(S);
  S.raf = requestAnimationFrame((t) => waveFrame(S, t));
  return {
    update(frame) { updateSignal(S, frame); },
    tele(d) { updateTele(S, d); },
  };
}

// ---------- pattern ağacı (fraktal grow, 29 birim) ----------
function split(units, depth) {
  if (units.length === 1) return { leaf: true, unit: units[0], depth };
  const mid = Math.ceil(units.length / 2);
  return { leaf: false, depth, left: split(units.slice(0, mid), depth + 1), right: split(units.slice(mid), depth + 1) };
}

function buildPatternTree(S) {
  const svg = S.svg;
  const root = split([...Array(NUM_UNITS).keys()], 0);
  let maxDepth = 0;
  (function findDepth(n) { if (n.leaf) maxDepth = Math.max(maxDepth, n.depth); else { findDepth(n.left); findDepth(n.right); } })(root);
  const ROOT_X = 500, ROOT_Y = 730, CROWN_X = 500, CROWN_Y = 620;
  const FAN = 146 * Math.PI / 180, R_BASE = 395, BRANCH_PULL = 0.5;
  let _seed = 7;
  const rnd = () => { _seed = (_seed * 16807) % 2147483647; return _seed / 2147483647; };
  const leaves = [];
  (function collect(n) { if (n.leaf) leaves.push(n); else { collect(n.left); collect(n.right); } })(root);
  const NL = leaves.length, slot = FAN / (NL - 1);
  leaves.forEach((n, i) => {
    const t = i / (NL - 1);
    const ang = -FAN / 2 + FAN * t + (rnd() - 0.5) * slot * 0.9;
    const wave = Math.sin(i * 0.9 + 1.3) * 32 + Math.sin(i * 2.3) * 18;
    const rad = R_BASE + wave + (rnd() - 0.5) * 60;
    n.angle = ang + (rnd() - 0.5) * 0.45;
    n.x = CROWN_X + rad * Math.sin(ang);
    n.y = CROWN_Y - rad * Math.cos(ang);
    n.hx = n.x; n.hy = n.y;
  });
  const footprint = (n) => {
    const fx = Math.sin(n.angle), fy = -Math.cos(n.angle);
    return [
      { x: n.x + fx * 22, y: n.y + fy * 22, r: 17 },
      { x: n.x + fx * 42, y: n.y + fy * 42, r: 10 },
      { x: n.x + fx * 62, y: n.y + fy * 62, r: 15 },
    ];
  };
  const MARGIN = 8;
  for (let it = 0; it < 400; it++) {
    for (let i = 0; i < NL; i++) for (let j = i + 1; j < NL; j++) {
      const A = leaves[i], B = leaves[j], fa = footprint(A), fb = footprint(B);
      let px = 0, py = 0, worst = 0;
      for (const ca of fa) for (const cb of fb) {
        const dx = cb.x - ca.x, dy = cb.y - ca.y, d = Math.hypot(dx, dy) || 0.01;
        const over = ca.r + cb.r + MARGIN - d;
        if (over > 0) { px += dx / d * over; py += dy / d * over; worst = Math.max(worst, over); }
      }
      if (worst > 0) {
        const m = Math.hypot(px, py) || 1, k = worst * 0.5 / m;
        A.x -= px * k; A.y -= py * k; B.x += px * k; B.y += py * k;
      }
    }
    for (const n of leaves) {
      n.x += (n.hx - n.x) * 0.02; n.y += (n.hy - n.y) * 0.02;
      for (const c of footprint(n)) {
        if (c.x - c.r < 30) n.x += 30 - (c.x - c.r);
        if (c.x + c.r > 970) n.x -= (c.x + c.r) - 970;
        if (c.y - c.r < 55) n.y += 55 - (c.y - c.r);
      }
      n.y = Math.min(600, n.y);
    }
  }
  const centroid = (n) => {
    if (n.leaf) return [n.x, n.y];
    const l = centroid(n.left), r = centroid(n.right);
    const wl = n.left.count, wr = n.right.count;
    return [(l[0] * wl + r[0] * wr) / (wl + wr), (l[1] * wl + r[1] * wr) / (wl + wr)];
  };
  (function count(n) { n.count = n.leaf ? 1 : count(n.left) + count(n.right); return n.count; })(root);
  const grow = (n, px, py) => {
    n.x1 = px; n.y1 = py;
    if (n.leaf) { n.x2 = n.x; n.y2 = n.y; return; }
    const [cx, cy] = centroid(n);
    const pull = BRANCH_PULL + (rnd() - 0.5) * 0.22;
    const dx = cx - px, dy = cy - py, len = Math.hypot(dx, dy) || 1;
    const side = (rnd() - 0.5) * len * 0.16;
    n.x2 = px + dx * pull - dy / len * side;
    n.y2 = py + dy * pull + dx / len * side;
    grow(n.left, n.x2, n.y2); grow(n.right, n.x2, n.y2);
  };
  root.leaf = false;
  root.x1 = ROOT_X; root.y1 = ROOT_Y; root.x2 = CROWN_X; root.y2 = CROWN_Y;
  grow(root.left, CROWN_X, CROWN_Y); grow(root.right, CROWN_X, CROWN_Y);
  S.edgesByDepth = [];
  const drawEdges = (n) => {
    const l = document.createElementNS(NS, "line");
    const [X1, Y1] = T(n.x1, n.y1), [X2, Y2] = T(n.x2, n.y2);
    l.setAttribute("x1", X1); l.setAttribute("y1", Y1);
    l.setAttribute("x2", X2); l.setAttribute("y2", Y2);
    l.setAttribute("class", "edge");
    l.setAttribute("stroke-width", Math.max(0.9, 3.4 - n.depth * 0.55));
    svg.appendChild(l);
    (S.edgesByDepth[n.depth] = S.edgesByDepth[n.depth] || []).push(l);
    if (!n.leaf) { drawEdges(n.left); drawEdges(n.right); }
  };
  drawEdges(root);
  const rd = document.createElementNS(NS, "circle");
  { const [RX, RY] = T(ROOT_X, ROOT_Y); rd.setAttribute("cx", RX); rd.setAttribute("cy", RY); }
  rd.setAttribute("r", 6); rd.setAttribute("fill", "var(--wire-hot)");
  svg.appendChild(rd); S.rootDot = rd;
  S._grow = grow;
  const rl = document.createElementNS(NS, "text");
  { const [RX, RY] = T(ROOT_X, ROOT_Y); rl.setAttribute("x", RX + 4); rl.setAttribute("y", RY - 12); }
  rl.style.textAnchor = "start"; rl.setAttribute("class", "rootlbl");
  rl.textContent = "KABLO (afferent)";
  svg.appendChild(rl);
  const line = (x1, y1, x2, y2) => {
    const l = document.createElementNS(NS, "line");
    const [X1, Y1] = T(x1, y1), [X2, Y2] = T(x2, y2);
    l.setAttribute("x1", X1); l.setAttribute("y1", Y1);
    l.setAttribute("x2", X2); l.setAttribute("y2", Y2);
    l.setAttribute("stroke", "var(--wire)"); l.setAttribute("stroke-width", "0.9");
    svg.appendChild(l); return l;
  };
  const buildNeuron = (n) => {
    const u = n.unit, angle = n.angle;
    const fx = Math.sin(angle), fy = -Math.cos(angle);
    const rx = Math.cos(angle), ry = Math.sin(angle);
    const compCx = n.x + fx * 22, compCy = n.y + fy * 22;
    const somaX = n.x + fx * 62, somaY = n.y + fy * 62;
    line(n.x, n.y, compCx, compCy);
    const compEls = [], offs = [-12, -4, 4, 12];
    for (let k = 0; k < 4; k++) {
      const cx = compCx + rx * offs[k], cy = compCy + ry * offs[k];
      line(cx, cy, somaX, somaY);
      const c = document.createElementNS(NS, "circle");
      const [CX, CY] = T(cx, cy);
      c.setAttribute("cx", CX); c.setAttribute("cy", CY); c.setAttribute("r", 5);
      c.setAttribute("class", "comp"); c.setAttribute("fill", "var(--comp)");
      svg.appendChild(c); compEls.push(c);
    }
    const soma = document.createElementNS(NS, "circle");
    { const [SX, SY] = T(somaX, somaY); soma.setAttribute("cx", SX); soma.setAttribute("cy", SY); }
    soma.setAttribute("r", 9); soma.setAttribute("class", "soma");
    soma.setAttribute("fill", "var(--soma)"); soma.setAttribute("stroke", "#3a444d"); soma.setAttribute("stroke-width", "1");
    svg.appendChild(soma);
    const lbl = document.createElementNS(NS, "text");
    { const [LX, LY] = T(somaX + fx * 15, somaY + fy * 15 + 3); lbl.setAttribute("x", LX); lbl.setAttribute("y", LY); }
    lbl.setAttribute("class", "lbl"); lbl.textContent = u;
    svg.appendChild(lbl);
    S.neurons[u] = { soma, compEls };
  };
  (function collectLeaves(n) { if (n.leaf) buildNeuron(n); else { collectLeaves(n.left); collectLeaves(n.right); } })(root);
}

// ---------- duyusal lob yardımcıları ----------
function el(S, tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  let a = attrs;
  if (tag === "circle" && "cx" in a && "cy" in a) {
    const [X, Y] = T(a.cx, a.cy); a = Object.assign({}, a, { cx: X, cy: Y });
  } else if (tag === "text" && "x" in a && "y" in a) {
    const [X, Y] = T(a.x, a.y); a = Object.assign({}, a, { x: X, y: Y });
  }
  for (const k in a) e.setAttribute(k, a[k]);
  (parent || S.lobeNodes).appendChild(e); return e;
}
function bl(S, x1, y1, x2, y2, col, w) {
  const [X1, Y1] = T(x1, y1), [X2, Y2] = T(x2, y2);
  return el(S, "line", { x1: X1, y1: Y1, x2: X2, y2: Y2, stroke: col, "stroke-width": w, "stroke-linecap": "round" }, S.lobeBase);
}
function wire(S, key, x1, y1, x2, y2, baseCol, cometCol, w, d) {
  bl(S, x1, y1, x2, y2, baseCol, w);
  const [X1, Y1] = T(x1, y1), [X2, Y2] = T(x2, y2);
  const sg = { key, x1: X1, y1: Y1, x2: X2, y2: Y2, col: cometCol, w, d, len: Math.hypot(X2 - X1, Y2 - Y1) };
  S.lobeSegs.push(sg); S.SEG[key] = sg; return sg;
}
function txt(S, x, y, s, cls, anchor) {
  const t = el(S, "text", { x, y, class: cls || "lt" }); t.textContent = s;
  if (anchor) t.style.textAnchor = anchor; return t;
}

function buildSensoryLobe(S) {
  const svg = S.svg, grow = S._grow;
  const LC = { x: 500, y: 1250 }, PLANT_Y = 1390;
  const R1 = 205, FAN1 = 66 * Math.PI / 180, R2 = 392, FAN2 = 72 * Math.PI / 180;
  S._LC = LC; S._PLANT_Y = PLANT_Y;
  const polar = (r, a) => [LC.x + r * Math.sin(a), LC.y - r * Math.cos(a)];
  let _ls = 11; const lr = () => { _ls = (_ls * 16807) % 2147483647; return _ls / 2147483647; };
  S.lobeBase = document.createElementNS(NS, "g");
  svg.insertBefore(S.lobeBase, S.rootDot);
  S.lobeNodes = document.createElementNS(NS, "g");
  svg.appendChild(S.lobeNodes);
  const oriOf = (o) => Math.atan2(o.x - LC.x, LC.y - o.y) + o.j;
  S._oriOf = oriOf;
  const circlesOf = (o) => { const a = oriOf(o), fx = Math.sin(a), fy = -Math.cos(a); return o.spec.c.map(([d, r]) => [o.x + fx * d, o.y + fy * d, r]); };
  const relax = (items, iters, margin) => {
    for (let it = 0; it < iters; it++) {
      const cs = items.map(circlesOf);
      for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
        const A = items[i], B = items[j]; if (A.fixed && B.fixed) continue;
        let px = 0, py = 0, worst = 0;
        for (const a of cs[i]) for (const b of cs[j]) {
          const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 0.01, over = a[2] + b[2] + margin - d;
          if (over > 0) { px += dx / d * over; py += dy / d * over; worst = Math.max(worst, over); }
        }
        if (worst > 0) {
          const m = Math.hypot(px, py) || 1, k = worst * 0.5 / m, wa = A.fixed ? 0 : (B.fixed ? 2 : 1), wb = B.fixed ? 0 : (A.fixed ? 2 : 1);
          A.x -= px * k * wa; A.y -= py * k * wa; B.x += px * k * wb; B.y += py * k * wb;
        }
      }
      items.forEach((o) => {
        if (o.fixed) return;
        o.x += (o.hx - o.x) * 0.012; o.y += (o.hy - o.y) * 0.012;
        o.x = Math.max(30, Math.min(970, o.x));
      });
    }
  };
  // P2 tacı: 64 slot (10 aktif + 54 yedek)
  const LEFT_RES = [4, 3, 3, 4, 3, 3, 4], RIGHT_RES = [3, 4, 3, 3, 4, 3, 4];
  const ring = S.ring; let resN = 10;
  const addRes = (slot, n) => { for (let i = 0; i < n; i++) ring.push({ type: "res", slot, w: 14, id: resN++ }); };
  for (let s = 0; s < P1_SLOTS; s++) {
    if (s < SA) addRes(s, LEFT_RES[s]);
    else if (s === SA) { addRes(s, 2); ORD_A.forEach((u) => ring.push({ type: "act", slot: s, u, w: 22 })); }
    else if (s === SB) { ORD_B.forEach((u) => ring.push({ type: "act", slot: s, u, w: 22 })); addRes(s, 4); }
    else addRes(s, RIGHT_RES[s - SB - 1]);
  }
  const L_TOT = ring.reduce((a, r) => a + r.w, 0);
  { let cum = 0;
    ring.forEach((r) => {
      r.ang0 = -FAN2 + 2 * FAN2 * ((cum + r.w / 2) / L_TOT); cum += r.w;
      r.act = r.type === "act";
      r.spec = r.act ? G_ACT : G_RES;
      r.j = r.act ? (lr() - 0.5) * 0.18 : (lr() - 0.5) * 0.7;
      const wave = 34 * Math.sin(r.ang0 * 5.3 + 0.8) + 18 * Math.sin(r.ang0 * 11.7);
      const edge = Math.abs(r.ang0 - 0) < 0.55 ? 0 : 1;
      const rad = R2 + (r.act ? (lr() - 0.5) * 34 + 12 * Math.sin(r.ang0 * 14) : 0.7 * wave + (((r.idx = (ring._n = (ring._n || 0) + 1)) % 2) * 2 - 1) * 26 + (lr() - 0.5) * 40 * (0.5 + edge * 0.5));
      const aj = r.ang0 + (r.act ? (lr() - 0.5) * 0.012 : (lr() - 0.5) * 0.025);
      [r.x, r.y] = polar(rad, aj); r.hx = r.x; r.hy = r.y;
      r.fixed = r.act;
    }); }
  relax(ring, 900, 2.5);
  ring.forEach((r) => { r.ang = oriOf(r); r.k = r.act ? "u" + r.u : "r" + r.id; });
  // P1 tacı: 16 slot
  const sectorAng = (s) => { const it = ring.filter((r) => r.slot === s && r.type !== "gap"); return it.reduce((a, r) => a + r.ang0, 0) / it.length; };
  const p1 = S.p1;
  for (let s = 0; s < P1_SLOTS; s++) {
    const a0 = 0.5 * (-FAN1 + 2 * FAN1 * s / (P1_SLOTS - 1)) + 0.5 * sectorAng(s);
    const o = { slot: s, spec: G_P1, j: (lr() - 0.5) * 0.5, act: s === SA || s === SB, line: s === SA ? "a" : s === SB ? "b" : null };
    [o.x, o.y] = polar(R1 + (lr() - 0.5) * 60, a0 + (lr() - 0.5) * 0.05); o.hx = o.x; o.hy = o.y;
    p1.push(o);
  }
  relax(p1, 250, 4);
  p1.forEach((o) => { o.ang = oriOf(o); });
  const mkTree = (list, depth) => {
    if (list.length === 1) { const n = list[0]; n.leaf = true; n.depth = depth; n.count = 1; n.ha = !!n.act; return n; }
    const mid = Math.ceil(list.length / 2);
    const n = { leaf: false, depth, left: mkTree(list.slice(0, mid), depth + 1), right: mkTree(list.slice(mid), depth + 1) };
    n.count = n.left.count + n.right.count; n.ha = n.left.ha || n.right.ha; return n;
  };
  let eIdx = 0;
  const drawTree = (n, prefix, wA, wB, wMin, onLeaf, keys) => {
    const key = prefix + "_" + (eIdx++);
    const w = Math.max(wMin, wA - n.depth * wB);
    wire(S, key, n.x1, n.y1, n.x2, n.y2, "#2c3844", C_PLANT, w, n.depth); keys.push(key);
    if (n.leaf) onLeaf(n, key);
    else { drawTree(n.left, prefix, wA, wB, wMin, onLeaf, keys); drawTree(n.right, prefix, wA, wB, wMin, onLeaf, keys); }
  };
  const glyph = (o, spec, act, key) => {
    const fx = Math.sin(o.ang), fy = -Math.cos(o.ang);
    const sx = o.x + fx * spec.soma, sy = o.y + fy * spec.soma;
    if (key) wire(S, key, o.x, o.y, sx, sy, "#3a444d", C_PLANT, 1.2, 0);
    else bl(S, o.x, o.y, sx, sy, "#3a444d", act ? 1.1 : 0.9);
    const comps = spec.comps.map((d) => el(S, "circle", { cx: o.x + fx * d, cy: o.y + fy * d, r: spec.rc, class: "ln", fill: "var(--comp)", "fill-opacity": 0.5 }));
    const soma = el(S, "circle", { cx: sx, cy: sy, r: spec.rs, class: "ln soma-l", fill: "var(--soma)", stroke: "#3a444d", "stroke-width": act ? 1.2 : 0.9 });
    return { comps, soma, sx, sy };
  };
  const P1LEAF = [], AKEY = S.AKEY;
  const t1 = mkTree(p1, 0);
  t1.x1 = LC.x; t1.y1 = PLANT_Y; t1.x2 = LC.x; t1.y2 = LC.y;
  grow(t1.left, LC.x, LC.y); grow(t1.right, LC.x, LC.y);
  drawTree(t1, "t1", 3.4, 0.55, 1, (n, key) => { P1LEAF[n.slot] = key; }, S.T1KEYS);
  p1.forEach((o) => {
    const g = glyph(o, G_P1, o.act, "p1in_" + o.slot);
    o.g = g;
    S.LN.p1[o.slot] = { comp: g.comps[0], soma: g.soma };
    const sub = mkTree(ring.filter((r) => r.slot === o.slot), 0);
    grow(sub, g.sx, g.sy);
    S.T2KEYS[o.slot] = [];
    drawTree(sub, "t2s" + o.slot, 2.2, 0.4, 0.8, (n, key) => { AKEY[n.k] = key; }, S.T2KEYS[o.slot]);
  });
  ring.forEach((r) => {
    const g = glyph(r, r.spec, r.act, null);
    r.g = g;
    const rec = { r, a: g.comps[0], b: g.comps[1], soma: g.soma };
    S.LN.n2.push(rec); r.rec = rec;
    if (r.act) {
      const d = P2[r.u];
      const tt = document.createElementNS(NS, "title");
      tt.textContent = `${d.id}${d.kind ? " (" + d.kind + ")" : ""}\nA ← ${d.line === "a" ? "p1a" : "p1b"}\nB ← sensör teli · ${d.sens} τ${d.tau}\n→ afferent post ${r.u}`;
      g.soma.appendChild(tt);
      if (d.kind === "decoy") { g.soma.setAttribute("fill", "none"); g.soma.setAttribute("stroke-dasharray", "2 1.5"); }
      if (d.neg) g.soma.setAttribute("stroke", "#6a4a80");
      txt(S, g.sx + 9, g.sy + 3, "abcdefghij"[r.u], "lt sm", "start");
    } else {
      const tt = document.createElementNS(NS, "title"); tt.textContent = "yedek P2 slotu #" + r.id + " — hazır";
      g.soma.appendChild(tt);
    }
  });
  S.acts = ring.filter((r) => r.act);
  S._P1LEAF = P1LEAF;
  // Sensör teli: tek tel, tacı boydan boya gezer
  const swPts = [];
  {
    const ang = (r) => Math.atan2(r.x - LC.x, LC.y - r.y);
    const order = ring.slice().sort((p, q) => ang(p) - ang(q));
    const bpos = (r) => { const fx = Math.sin(r.ang), fy = -Math.cos(r.ang), d = r.spec.comps[1]; return [r.x + fx * d, r.y + fy * d]; };
    const first = bpos(order[0]);
    const rx = Math.min(972, first[0] + 8);
    swPts.push([rx, PLANT_Y]); swPts.push([rx, first[1]]);
    order.forEach((r) => { r.bIdx = swPts.length; swPts.push(bpos(r)); });
  }
  for (let i = 0; i < swPts.length - 1; i++) {
    const k = "sw" + i; S.SW.push(k);
    wire(S, k, swPts[i][0], swPts[i][1], swPts[i + 1][0], swPts[i + 1][1], "#4a3c24", C_SENS, i === 0 ? 2.2 : 1.3, 0);
  }
  // Afferent ters ağaç: 64 akson → tek nokta → KABLO
  {
    const angOf = (x, y) => Math.atan2(x - LC.x, LC.y - y);
    const afLeaves = ring.map((r) => ({ u: r.act ? r.u : undefined, x: r.g.sx, y: r.g.sy, a: angOf(r.g.sx, r.g.sy) })).sort((p, q) => p.a - q.a);
    const at = mkTree(afLeaves, 0); S.AFTREE = at;
    const TR = 785; // ROOT_Y + 55
    at.x1 = 500; at.y1 = 730; at.x2 = 500; at.y2 = TR;
    grow(at.left, 500, TR); grow(at.right, 500, TR);
    let ai = 0;
    (function draw(n) {
      const key = "af" + (ai++), w = n.leaf ? 1.0 : Math.max(0.9, 2.7 - n.depth * 0.42);
      wire(S, key, n.x1, n.y1, n.x2, n.y2, "#33414d", C_AFF, w, n.depth);
      n.chain = [key]; S.AFKEYS.push(key);
      if (!n.leaf) { draw(n.left); draw(n.right); }
    })(at);
  }
  S.LN.proot = el(S, "circle", { cx: LC.x, cy: PLANT_Y, r: 6, class: "ln", fill: "#25392d", stroke: C_PLANT, "stroke-width": 1.2 });
  txt(S, LC.x, PLANT_Y + 24, "BİTKİ (tek tel)", "ll", "middle");
  S.LN.sroot = el(S, "circle", { cx: swPts[0][0], cy: PLANT_Y, r: 6, class: "ln", fill: "#3a3326", stroke: C_SENS, "stroke-width": 1.2 });
  txt(S, swPts[0][0] + 20, PLANT_Y + 24, "SENSÖR (tek tel, ortak)", "ll", "end");
  txt(S, 10, 880, "P2 KOŞUL BANKASI", "ll", "start");
  txt(S, 10, 893, "64 slot · 10 aktif · 54 yedek (işlevli)", "lt sm", "start");
  txt(S, 10, 1440, "P1 FAZ HATTI", "ll", "start");
  txt(S, 10, 1453, "16 slot · 2 aktif · 14 yedek (işlevli)", "lt sm", "start");
  { const a = p1[SA].g, b = p1[SB].g;
    txt(S, a.sx - 10, a.sy + 4, "p1a τ4 hızlı", "lt in", "end");
    txt(S, b.sx + 10, b.sy + 4, "p1b τ12 yavaş", "lt in", "start"); }
  txt(S, 512, 774, "AFFERENT", "ll", "start");
  txt(S, 512, 787, "64 P2 aksonu → ters ağaç → tek nokta → KABLO", "lt sm", "start");
}

// ---------- dalga katmanları (sürekli nabız motoru) ----------
const smooth = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
function buildWaveLayers(S) {
  const svg = S.svg;
  const defs = document.createElementNS(NS, "defs");
  defs.innerHTML = '<filter id="softglow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.2"/></filter>';
  svg.insertBefore(defs, svg.firstChild);
  const glowG = document.createElementNS(NS, "g"); glowG.setAttribute("filter", "url(#softglow)");
  const coreG = document.createElementNS(NS, "g");
  svg.insertBefore(glowG, S.rootDot); svg.insertBefore(coreG, S.rootDot);
  const mk = (g, x1, y1, x2, y2, col, w) => {
    const l = document.createElementNS(NS, "line");
    l.setAttribute("x1", x1); l.setAttribute("y1", y1); l.setAttribute("x2", x2); l.setAttribute("y2", y2);
    l.setAttribute("class", "wave-line"); l.setAttribute("stroke", col);
    l.setAttribute("stroke-width", w); l.setAttribute("stroke-opacity", 0);
    g.appendChild(l); return l;
  };
  for (const sg of S.lobeSegs) {
    S.LI[sg.key] = {
      len: Math.hypot(sg.x2 - sg.x1, sg.y2 - sg.y1), start: Infinity, travel: 1, tau: 1,
      glow: mk(glowG, sg.x1, sg.y1, sg.x2, sg.y2, sg.col, sg.w + 4),
      core: mk(coreG, sg.x1, sg.y1, sg.x2, sg.y2, "#f4faff", sg.w + 0.3),
    };
  }
}
function fireEdge(S, key, travel, tau) {
  const it = S.LI[key];
  if (!it) return;
  it.start = performance.now(); it.travel = travel || 500; it.tau = tau || 700;
}
function waveFrame(S, now) {
  for (const k in S.LI) {
    const e = S.LI[k];
    if (!isFinite(e.start)) continue;
    const t = now - e.start, p = t / e.travel;
    if (p <= 0) continue;
    if (p > 1 && t > e.start + e.travel + e.tau * 4.5) {
      e.start = Infinity;
      e.glow.setAttribute("stroke-opacity", 0); e.core.setAttribute("stroke-opacity", 0);
      continue;
    }
    const tail = Math.max(e.len * 0.75, 28), head = Math.min(1, p) * (e.len + tail);
    e.core.setAttribute("stroke-dasharray", tail + " " + (e.len + tail));
    e.core.setAttribute("stroke-dashoffset", tail - head);
    e.core.setAttribute("stroke-opacity", (1 - smooth((p - 0.7) / 0.5)).toFixed(3));
    const rise = smooth(p / 0.6);
    const decay = Math.exp(-Math.max(0, t - e.travel * 0.6) / e.tau);
    e.glow.setAttribute("stroke-opacity", (rise * decay * 0.85).toFixed(3));
  }
  // sönümler
  for (const [key, rec] of S.firedP2) {
    if (now - rec.t0 > 2500) { p2Rest(S, rec.r); S.firedP2.delete(key); }
  }
  for (const [key, rec] of S.firedP1) {
    if (now - rec.t0 > 2500) { p1Rest(S, rec.rec); S.firedP1.delete(key); }
  }
  for (const [key, rec] of S.firedPat) {
    if (now - rec.t0 > 2200) { patRest(S, rec.u); S.firedPat.delete(key); }
  }
  S.raf = requestAnimationFrame((t) => waveFrame(S, t));
}

// ---------- canlı ateşleme ----------
function findAfChain(n, u, path) {
  if (n.leaf) return (n.u === u) ? path.concat(n.chain) : null;
  return findAfChain(n.left, u, path.concat(n.chain)) || findAfChain(n.right, u, path.concat(n.chain));
}
function p2Rest(S, r) {
  const rec = S.LN.n2.find((n) => n.r === r);
  if (!rec) return;
  const d = r.act ? P2[r.u] : null;
  rec.soma.classList.remove("fired");
  rec.soma.setAttribute("fill", d && d.kind === "decoy" ? "none" : "var(--soma)");
  rec.soma.setAttribute("stroke", d && d.neg ? "#6a4a80" : "#3a444d");
  rec.a.setAttribute("fill", "var(--comp)"); rec.a.setAttribute("fill-opacity", 0.5);
  rec.b.setAttribute("fill", "var(--comp)"); rec.b.setAttribute("fill-opacity", 0.5);
}
function fireP2(S, u, tau, tick) {
  const r = S.acts.find((x) => x.u === u);
  if (!r || !r.rec) return;
  const rec = r.rec, now = performance.now();
  rec.soma.classList.add("fired");
  rec.soma.setAttribute("fill", "var(--soma-fire)"); rec.soma.setAttribute("stroke", "#f5e08a");
  rec.a.setAttribute("fill", C_PLANT); rec.a.setAttribute("fill-opacity", 0.95);
  rec.b.setAttribute("fill", C_SENS); rec.b.setAttribute("fill-opacity", 0.95);
  S.firedP2.set("p2-" + u, { r, t0: now });
  // dalga: P1→P2 dalı + afferent zincir + kablo
  const ak = S.AKEY[r.k];
  if (ak) fireEdge(S, ak, 450, 600);
  const chain = findAfChain(S.AFTREE, u, []) || [];
  chain.forEach((k, i) => setTimeout(() => fireEdge(S, k, 400, 600), i * 60));
  S.rootDot.setAttribute("r", 8);
  setTimeout(() => S.rootDot.setAttribute("r", 6), 600);
}
// bitki faz hattı: P1a=hat 0 (slot SA), P1b=hat 1 (slot SB).
// GERÇEK T-satırı p1 biti; bitki kökü → T1 dalı → P1 soması yanar,
// aynı hattaki P2'lerin A-dalı eşik-altı sürüşle kısık yanar (spike değil).
const P1_SLOT = [SA, SB]; // p1a=slot7, p1b=slot8
const P1_NAME = ["p1a", "p1b"];
function p1Rest(S, rec) {
  if (!rec) return;
  rec.soma.setAttribute("fill", "var(--soma)"); rec.soma.setAttribute("stroke", "#3a444d");
  rec.comp.setAttribute("fill", "var(--comp)"); rec.comp.setAttribute("fill-opacity", 0.5);
}
function driveP2(S, line) {
  const want = line === 0 ? "a" : "b";
  for (const r of S.acts) {
    const d = P2[r.u];
    if (!d || d.line !== want || !r.rec) continue;
    if (S.firedP2.has("p2-" + r.u)) continue; // spike parlıyorsa elleme
    r.rec.a.setAttribute("fill", C_PLANT); r.rec.a.setAttribute("fill-opacity", 0.55);
    setTimeout(((rr) => () => {
      if (S.firedP2.has("p2-" + rr.u)) return;
      rr.rec.a.setAttribute("fill", "var(--comp)"); rr.rec.a.setAttribute("fill-opacity", 0.5);
    })(r), 700);
  }
}
function fireP1(S, line, tick) {
  const slot = P1_SLOT[line];
  if (slot === undefined) return;
  const rec = S.LN.p1[slot];
  if (!rec) return;
  // Dalga kaskadı: TEK gerçek olay dal-dal gezer (referans plan disiplini).
  // Gecikmeler yalnız görsel sahnelemedir, sentetik olay üretilmez —
  // tüm kollar aynı T-satırı p1 bitinden türer.
  const LVL = 85; // ms/derinlik
  let maxD = 0;
  for (const k of S.T1KEYS) {
    const sg = S.SEG[k];
    const d = sg ? sg.d : 0;
    if (d > maxD) maxD = d;
    setTimeout(() => fireEdge(S, k, 320, 500), d * LVL);
  }
  const arr = (maxD + 1) * LVL; // P1 varışı
  setTimeout(() => {
    fireEdge(S, "p1in_" + slot, 350, 500);
    rec.soma.setAttribute("fill", "var(--soma-fire)"); rec.soma.setAttribute("stroke", "#f5e08a");
    rec.comp.setAttribute("fill", C_PLANT); rec.comp.setAttribute("fill-opacity", 0.95);
    S.firedP1.set("p1-" + line, { rec, t0: performance.now() });
  }, arr);
  // P1 → T2 dalları: varıştan sonra derinliğe göre açılır
  const t2 = (S.T2KEYS && S.T2KEYS[slot]) || [];
  for (const k of t2) {
    const sg = S.SEG[k];
    setTimeout(() => fireEdge(S, k, 300, 450), arr + 60 + (sg ? sg.d : 0) * 70);
  }
  setTimeout(() => driveP2(S, line), arr + 120);
  S.LN.proot.setAttribute("r", 8);
  setTimeout(() => S.LN.proot.setAttribute("r", 6), 500);
}
function patRest(S, u) {
  const n = S.neurons[u];
  if (!n) return;
  n.soma.classList.remove("fired");
  n.soma.setAttribute("fill", "var(--soma-recv)"); n.soma.setAttribute("r", "9"); n.soma.setAttribute("stroke", "#455360");
  n.compEls.forEach((c) => { c.setAttribute("fill", "var(--comp)"); c.setAttribute("fill-opacity", "0.35"); });
}
function firePat(S, u, dal, act, spk) {
  const n = S.neurons[u];
  if (!n) return;
  const now = performance.now();
  if (spk === 1) {
    n.soma.classList.add("fired");
    n.soma.setAttribute("fill", "var(--soma-fire)"); n.soma.setAttribute("r", "13"); n.soma.setAttribute("stroke", "#f5e08a");
  } else {
    n.soma.setAttribute("fill", "var(--soma-recv)"); n.soma.setAttribute("r", "9"); n.soma.setAttribute("stroke", "#455360");
  }
  if (dal >= 0 && dal < 4) {
    const t = Math.min(1, act / 0.5);
    n.compEls[dal].setAttribute("fill", "var(--comp-lit)");
    n.compEls[dal].setAttribute("fill-opacity", (0.25 + t * 0.75).toFixed(2));
  }
  S.firedPat.set("pat-" + u, { u, t0: now });
}

function setText(elm, s) { if (elm) elm.textContent = s; }

function updateSignal(S, frame) {
  if (!frame) return;
  const ids = S.ids || {};
  // sensör teli: değer değişiminde zayıf nabız (canlı nefes)
  const s = frame.sensors || {};
  let sum = 0, n = 0;
  for (const k of SENS_KEYS) { const v = parseFloat(s[k]); if (isFinite(v)) { sum += v; n++; } }
  if (n > 0) {
    const avg = sum / n;
    if (S._lastSensAvg === undefined || Math.abs(avg - S._lastSensAvg) > 1.5) {
      S._lastSensAvg = avg;
      const op = (0.25 + 0.75 * Math.min(1, avg / 100)).toFixed(2);
      S.LN.sroot.setAttribute("fill-opacity", op);
      // sensör teli boyunca akış: tek gerçek değişim, tel sırasıyla gezer
      const nsw = S.SW.length;
      S.SW.forEach((k, i) => setTimeout(() => fireEdge(S, k, 380, 420), (i / Math.max(1, nsw)) * 900));
    }
  }
  const L = frame.lobes;
  if (!L) {
    setText(ids.live, "zincir kapalı");
    setText(ids.chain, "lob akışı yok (sensör teli canlı)");
    setText(ids.aff, "—"); setText(ids.k4, "—");
    return;
  }
  setText(ids.live, "CANLI");
  const ch = `duyusal ${L.sensory_alive === false ? "ölü" : "canlı"} · pattern ${L.pattern_alive ? "canlı" : "ölü"}${L.pattern_broken ? " (kırık!)" : ""} · tick ${L.fed_tick}`;
  setText(ids.chain, ch);
  // bitki: yeni P1 olayları → faz hattı ateşi (GERÇEK T-satırı p1 biti)
  const p1 = Array.isArray(L.p1) ? L.p1 : [];
  const fp1 = p1.filter((e) => e && e[0] > S.lastP1Tick);
  let plantStr = "";
  if (fp1.length) {
    S.lastP1Tick = Math.max(...fp1.map((e) => e[0]));
    // tampon geriden gelirse hepsini yakma: son 6 olay
    fp1.slice(-6).forEach(([tick, line]) => fireP1(S, line, tick));
    const [ptick, pline] = fp1[fp1.length - 1];
    plantStr = `bitki ${P1_NAME[pline] || ("hat" + pline)}@tick ${ptick}`;
  }
  // afferent: yeni olaylar → P2 ateşi (GERÇEK post)
  const aff = Array.isArray(L.aff) ? L.aff : [];
  const fresh = aff.filter((e) => e && e[0] > S.lastAffTick);
  if (fresh.length) {
    S.lastAffTick = Math.max(...fresh.map((e) => e[0]));
    // tampon geriden gelirse hepsini yakma: son 6 olay
    fresh.slice(-6).forEach(([tick, post, tau]) => fireP2(S, post, tau, tick));
    const [tick, post, tau] = fresh[fresh.length - 1];
    const pid = (P2[post] && P2[post].id) || ("post" + post);
    setText(ids.aff, `tick ${tick} · ${pid} (post ${post}, τ${tau})` + (plantStr ? ` · ${plantStr}` : ""));
  } else if (plantStr) {
    setText(ids.aff, plantStr);
  }
  // pattern: yeni spike/act → birim (GERÇEK live_k4)
  const k4 = Array.isArray(L.k4) ? L.k4 : [];
  const fk = k4.filter((e) => e && e[0] > S.lastK4Tick);
  if (fk.length) {
    S.lastK4Tick = Math.max(...fk.map((e) => e[0]));
    fk.slice(-24).forEach(([tick, birim, dal, act, spk]) => firePat(S, birim, dal, act, spk));
    const spks = fk.filter((e) => e[4] === 1).map((e) => e[1]);
    const acts = fk.map((e) => e[3]);
    const mx = Math.max(...acts);
    setText(ids.k4, `tick ${S.lastK4Tick} · ${spks.length ? "ateş: " + [...new Set(spks)].join(",") : "ateş yok"} · maxact ${mx.toFixed(3)}${L.k4_act_min ? " (eşik " + L.k4_act_min + ")" : ""}`);
  }
}

function updateTele(S, d) {
  const ids = S.ids || {};
  if (!d || typeof d.t !== "number") {
    setText(ids.npu, "NPU bağlı değil");
    return;
  }
  S.lastTeleT = d.t;
  const f = String(d.f || "");
  const nf = [...f].filter((c) => c === "1").length;
  const w = `tel=${Number(d.wire).toFixed(2)} ateş=${nf}/${f.length || 9}`;
  setText(ids.npu, `CANLI t${d.t} · ${w}`);
  // kablo: NPU teli nabzı
  if (nf > 0) {
    S.rootDot.setAttribute("r", 7);
    setTimeout(() => S.rootDot.setAttribute("r", 6), 400);
  }
}
