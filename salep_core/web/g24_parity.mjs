// G24 silüet parite — mesh ortografik silüet ≡ 2D profil (tolerans %15).
// Renderer YOK, saf geometri: salep_meshes.json bbox'ları, canvas-normalize
// haritayla 2D içerik kutusuyla (profile.js layoutContent) karşılaştırılır.
// Corsu: node web/g24_parity.mjs (cwd=salep_core). Çıkış 0 = GEÇTİ.
import { readFileSync } from "node:fs";
import vm from "node:vm";

const TOL = 0.15;

// profile.js klasik betik → vm ile yükle (tarayıcıyla aynı kaynak).
const src = readFileSync("web/static/js/profile.js", "utf8");
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(src + "\nthis.__P = SalepProfile;", sandbox);
const P = sandbox.__P;

const mesh = JSON.parse(readFileSync("sim/models/salep_meshes.json", "utf8")).parts;
function bbox(v) {
  const xs = [], ys = [];
  for (let i = 0; i < v.length; i += 3) { xs.push(v[i]); ys.push(v[i + 1]); }
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}
const B = {};
for (const [k, part] of Object.entries(mesh)) B[k] = bbox(part.vertex);
const yTop = Math.max(...Object.values(B).map((b) => b.y1));
const yBot = Math.min(...Object.values(B).map((b) => b.y0));
const Hm = yTop - yBot;
// Mesh→canvas haritası: bbox üstü 0.02'ye, altı 0.98'e.
const my = (y) => 0.02 + (yTop - y) * (0.96 / Hm);
const mx = (x) => Math.abs(x) * (0.96 / Hm);

// Referans frame (FLOWERING, tam boy — dönüm noktaları uçta).
const ref = {
  visual: { stem_h: 1.0, leaf_scale: 1.0, leaf_turgor: 1.0, wilt: 0.0, yellowing: 0.0,
    flower_count: 12, flower_open: 1.0, root_tint: 0.3, root_necrotic: 0.0,
    tuber_scale: 1.0, soil_wet: 0.5, salt_crust: 0.0 },
  world: { sky: "day", sun_alt_deg: 45, rain_mm: 0 },
  plant: { stage: "FLOWERING" }, sim: { paused: false },
};
const L = P.layoutContent(P.profile2d(ref));
const halfWm = Math.max(...Object.values(B).map((b) => Math.max(Math.abs(b.x0), Math.abs(b.x1))));

const checks = [
  ["soil", my(0), L.soilY],
  ["stemTop", my(B.salep_stem.y1), L.stemTopY],
  ["tuberY", my((B.salep_tuber.y0 + B.salep_tuber.y1) / 2), L.tuberY],
  ["halfW", mx(halfWm), L.halfW],
  ["rootBottom", my(B.salep_root.y0), L.bottomY],
  ["flowerTop", my(B.salep_flower.y1), L.flowerTopY],
];
let fail = 0;
for (const [name, m, d] of checks) {
  const e = Math.abs(m - d);
  const ok = e <= TOL;
  if (!ok) fail++;
  console.log(`  ${ok ? "OK " : "FARK"} ${name}: mesh=${m.toFixed(3)} profil=${d.toFixed(3)} err=${e.toFixed(3)}`);
}
// Yapısal sıra: kök-alt > yumru > toprak > gövde-tepe (iki tarafta da).
const orderM = my(B.salep_root.y0) > my(0) && my(0) > my(B.salep_stem.y1);
const orderD = L.bottomY > L.tuberY && L.tuberY > L.soilY && L.soilY > L.stemTopY;
console.log(`  ${orderM && orderD ? "OK " : "FARK"} sira: mesh=${orderM} profil=${orderD}`);
if (!orderM || !orderD) fail++;

if (fail) { console.log(`G24 BAŞARISIZ: ${fail} uyumsuzluk`); process.exit(1); }
console.log("G24 GEÇTİ: silüet paritesi tolerans içinde");

// dayT kilidi (§9.29 düzeltmesi): x'i kesintisiz gün-içi zaman sürer —
// şafak 0, öğle 0.5, batım 1; gece aralığın dışında (kelepçeli, çizilmez).
const _V0 = { stem_h: 0, leaf_scale: 1, leaf_turgor: 1, wilt: 0, yellowing: 0,
  flower_count: 0, flower_open: 0, root_tint: 1, root_necrotic: 0,
  tuber_scale: 0.3, soil_wet: 0, salt_crust: 0 };
const _T = (frac, photo) => P.profile2d({ sim: { day: 100, day_frac: frac },
  world: { photoperiod_h: photo, sun_alt_deg: 0, rain_mm: 0, sky: "day" },
  visual: _V0, sensors: {}, plant: { stage: "VEGETATIVE", stage_age: 0 } });
let lerpFail = 0;
const _t0 = _T(0.25, 12).dayT, _t1 = _T(0.5, 12).dayT, _t2 = _T(0.75, 12).dayT;
if (!(Math.abs(_t0) < 1e-9 && Math.abs(_t1 - 0.5) < 1e-9 && Math.abs(_t2 - 1) < 1e-9)) {
  console.log("  FARK dayT-uc"); lerpFail++;
} else console.log("  OK  dayT-uc: 0/0.5/1");
let _pm = -2;
for (let h = 0; h <= 24; h++) {
  const t = _T(h / 24, 12).dayT;
  if (t < _pm - 1e-9) { console.log("  FARK dayT-monoton"); lerpFail++; break; }
  _pm = t;
}
if (!lerpFail) console.log("  OK  dayT-monoton: ufukta kelepçesiz akış");
if (lerpFail) { console.log(`G24 BAŞARISIZ: ${lerpFail} dayT uyumsuzluğu`); process.exit(1); }
