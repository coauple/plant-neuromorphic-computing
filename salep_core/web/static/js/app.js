// Uygulama kablolaması — sekmeler + HUD + senaryo kartları + toast.
import { connectWorld, connectNpu } from "./ws.js";
import { drawWorld2d } from "./world2d.js";
import { initSignal } from "./signal.js";
const { lerpFrame } = globalThis.SalepProfile;

const $ = (id) => document.getElementById(id);
const cv2 = $("view2d"), ctx2 = cv2.getContext("2d");

let prev = null, cur = null, tPrev = 0, tCur = 0;
let three = null, threeReady = false;
let _seenEvt = "";

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), 2600);
}

function hud(f) {
  // Üst şeritte yalnız hız/duraklatma kalır; gün, dönem, sıcaklık, nem,
  // mevsim, gök, yağış Canlı Veriler panelinde tek kaynaktan yazılır.
  // Hız göstergesi: 1x = 5 sn'de 1 saat; duraklatma açık yazılır
  const fx = f.sim.speed * 120;
  $("hud-speed").textContent = f.sim.paused
    ? "duraklatıldı"
    : (fx < 10 ? `H ${fx.toFixed(1)}x` : `H ${fx.toFixed(0)}x`);
  // İklim şeridi: kuşak sabit (WorldDriver Akdeniz/Ege tipidir);
  // mevsim + gök + yağış her karede v2 frame'den tazelenir.
  // Mevsim sınırları meteorolojik: 60/151/243/334 (1 Mar/1 Haz/1 Eyl/1 Ara).
  const doy = f.sim.doy;
  const season =
    doy < 60 ? "Kış" : doy < 151 ? "İlkbahar" : doy < 243 ? "Yaz" : doy < 334 ? "Sonbahar" : "Kış";
  const skyTr =
    { day: "gündüz", dusk: "alacakaranlık", night: "gece" }[f.world.sky] || f.world.sky;
  const rainTr = `yağış ${f.world.rain_mm.toFixed(1)}mm`;
  // Bitki gelişme dönemi Türkçe etikete çevrilir (karede stage adı İngilizce gelir).
  const stageTr =
    { DORMANT: "Dormansi (uyku)", SPROUTING: "Filizlenme", VEGETATIVE: "Vejetatif dönem",
      FLOWERING: "Çiçeklenme", SENESCENCE: "Sararma", DEAD: "Ölü" }[f.plant.stage]
    || f.plant.stage;
  // Canlı veri paneli (eski NPU panelinin yeri): aynı karenin değerleri.
  const w = f.world;
  $("data-date").textContent = `${dateOfDoy(doy)} · gün ${f.sim.day}`;
  $("data-stage").textContent = stageTr;
  $("data-season").textContent = season;
  $("data-temp").textContent = `${w.temp_air_display.toFixed(1)}°C`;
  // Fiziğin gördüğü günlük ortalama (bitki buna tepki verir — anlık değil).
  $("data-applied").textContent = `${w.temp_air.toFixed(1)}°C (günlük ort)`;
  $("data-soilt").textContent = `${w.temp_soil.toFixed(1)}°C`;
  // Gök derecesiz yazılır: gündüz / alacakaranlık / gece.
  $("data-sky").textContent = skyTr;
  $("data-rain").textContent = rainTr;
  $("data-photo").textContent = `${w.photoperiod_h.toFixed(1)} saat`;
  // UV gözlenmiyorsa (dosyasız koşu) null gelir — çizgi gösterilir.
  $("data-uv").textContent =
    (w.uv_index === null || w.uv_index === undefined) ? "—" : `${w.uv_index.toFixed(1)}`;
  // Boy morfolojik model birimidir (§9.27), gerçek cm değildir.
  $("data-height").textContent = `${f.plant.stem_height.toFixed(2)}`;
  // Bitki sensörleri: aynı karenin fizik + NPU-kanal değerleri.
  // Kanallar 0-100 ham NPU birimidir; panelde fiziksel karşılığıyla
  // gösterilir — yalnız gösterim katmanı, kare şeması ve fizik aynı.
  const p = f.plant, s = f.sensors || {};
  const ch = (v) => (v === null || v === undefined) ? "—" : `${Math.round(v)}`;
  const pct = (v) => (v === null || v === undefined) ? "—" : `${Math.round(v)}%`;
  // hs/ts ters eşlemesi (sensor_map.map_hs: -5°C=0, 40°C=100).
  const cToTemp = (v) => (v === null || v === undefined) ? "—" : `${(v / 100 * 45 - 5).toFixed(1)}°C`;
  // pH kanal 0-100 → pH 4-9 (taban 45 ≈ 6.3, hafif asidik toprak).
  const cToPh = (v) => (v === null || v === undefined) ? "—" : `${(4 + v / 100 * 5).toFixed(1)}`;
  $("sens-soil").textContent = `${p.soil_moisture.toFixed(1)}%`;
  $("sens-ec").textContent = `${p.soil_ec.toFixed(2)} mS/cm (ec ${ch(s.ec)})`;
  $("sens-hn").textContent = pct(s.hn);
  $("sens-hs").textContent = cToTemp(s.hs);
  $("sens-ts").textContent = cToTemp(s.ts);
  $("sens-tn").textContent = pct(s.tn);
  $("sens-ph").textContent = cToPh(s.ph);
  $("sens-npk").textContent = `${ch(s.npk)} endeks`;
  $("sens-leaf").textContent = `${p.leaf_health.toFixed(0)}`;
  $("sens-root").textContent = `${p.root_health.toFixed(0)}`;
  $("sens-water").textContent = `${p.water_balance.toFixed(2)}`;
  $("sens-o2").textContent = `${p.o2_deficit} gün`;
  // Ölüm/ekim ilanı (§9.55): karedeki olaylardan yalnız yeni olan,
  // bir kez toast'lanır (sulama/gübre olayları sessizdir).
  const evts = f.events || [];
  const last = evts[evts.length - 1];
  if (last && (last.kind === "plant_death" || last.kind === "resow")) {
    const sig = `${last.day}:${last.kind}:${last.seed || last.cause || ""}`;
    if (sig !== _seenEvt) {
      _seenEvt = sig;
      if (last.kind === "plant_death") {
        toast(`Bitki öldü (${last.cause === "root_rot" ? "kök çürüklüğü" : "besinsizlik"}) — 5 gün sonra yeniden ekim`);
      } else {
        toast(`Yeni ekim — tohum ${last.seed}`);
      }
    }
  }
}

const world = connectWorld(
  `ws://${location.host}/ws/world`,
  (f) => { prev = cur; tPrev = tCur; cur = f; tCur = performance.now(); hud(f); if (sig) { try { sig.update(f); } catch (e) {} } },
  (ok) => { $("dot-world").className = "dot " + (ok ? "on" : "off"); },
);
// Sinyal yayılımı paneli: SVG şema + canlı lob akışı (frame.lobes).
let sig = null;
try {
  sig = initSignal($("sigsvg"), {
    live: $("sig-live"), chain: $("sig-chain"),
    aff: $("sig-aff"), k4: $("sig-k4"), npu: $("sig-npu"),
  });
} catch (e) { console.error("signal panel kapalı:", e); }
// NPU telemetrisi (/ws/npu TELE): kablo nabzı + panel okuması.
// Binary yoksa sunucu offline döner — şema sessiz durur, uydurma yok.
if (sig) {
  connectNpu(
    `ws://${location.host}/ws/npu`,
    (d) => { try { sig.tele(d); } catch (e) {} },
    (ok, mode) => { if (!ok || mode === "offline") { try { sig.tele(null); } catch (e) {} } },
  );
}
// Gün-ay: 365 günlük yıllar, Şubat 28 (artık yıl yok — simülasyon takvimi).
const MONTHS_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const MDAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
function dateOfDoy(doy) {
  let m = 0;
  while (m < 11 && doy >= MDAYS[m]) { doy -= MDAYS[m]; m++; }
  return `${doy + 1} ${MONTHS_TR[m]}`;
}

function frameNow() {
  if (!cur) return null;
  const span = Math.max(1, tCur - tPrev);
  const a = Math.min(1.2, (performance.now() - tCur) / span);
  return lerpFrame(prev, cur, a);
}

(function loop() {
  requestAnimationFrame(loop);
  const f = frameNow();
  if (f) {
    if (!$("view2d").classList.contains("hidden")) drawWorld2d(ctx2, cv2.width, cv2.height, f);
    if (threeReady && three) { try { three.setFrame(f); } catch (e) {} }
  }
})();

// Sekmeler — 3D tembel yüklenir (vendor yoksa not düşer, 2D çalışır).
$("tab2d").onclick = () => {
  $("tab2d").classList.add("active");
  $("tab3d").classList.remove("active");
  $("view2d").classList.remove("hidden");
  $("view3d-wrap").classList.add("hidden");
};
$("tab3d").onclick = async () => {
  $("tab3d").classList.add("active");
  $("tab2d").classList.remove("active");
  $("view2d").classList.add("hidden");
  $("view3d-wrap").classList.remove("hidden");
  if (!three) {
    try {
      const mod = await import("./world3d.js");
      three = await mod.init3d($("view3d"), "/static/data/salep_meshes.json");
      threeReady = true;
    } catch (e) {
      const n = $("view3d-note");
      n.textContent = "3D kapalı: yerel Three.js vendor'ı yok (internet gerekli, bir kez). 2D sekme tam çalışır.";
      n.classList.remove("hidden");
    }
  }
};

// Müdahale paneli (sulama/gübre/toprak/hız) → /ws/world komutları.
const CMDS = {
  water: { cmd: "water", mm: 20 },
  water10: { cmd: "water", mm: 10 },
  water20: { cmd: "water", mm: 20 },
  drought: { cmd: "drought" },
  fert: { cmd: "fert", mass: 30 },
  fert15: { cmd: "fert", mass: 15 },
  fert30: { cmd: "fert", mass: 30 },
  soil_kumlu: { cmd: "soil", preset: "kumlu" },
  soil_tinli: { cmd: "soil", preset: "tınlı" },
  soil_killi: { cmd: "soil", preset: "killi" },
  pause: { cmd: "pause" },
  resume: { cmd: "resume" },
  // Saat ölçeği: 1x = 5 gerçek-sn'de 1 sim-saati (süreklilik akıcı);
  // sim birimi gün/sn olduğu için v = saat/24/5.
  speed1: { cmd: "speed", v: 1 / 120 },
  speed8: { cmd: "speed", v: 8 / 120 },
  // Sprint: 2 gerçek-sn'de 1 sim-günü (0.5 gün/sn → HUD'da H 60x).
  sprint: { cmd: "speed", v: 60 / 120 },
};
document.querySelectorAll(".panel.actions button").forEach((b) => {
  b.onclick = () => {
    const c = CMDS[b.dataset.cmd];
    world.send(c);
    toast(`komut gönderildi: ${b.dataset.cmd}`);
  };
});

// Yan panel boy eşitliği: üç yan panel (Canlı Veriler + Sensörler +
// Müdahaleler) yan yana durur, en uzununun boyuna eşitlenir — satır
// yüksekliğine (terraryuma) esnemez.
function equalSides() {
  const ps = [...document.querySelectorAll(".grid > .panel.data, .grid > .panel.actions")];
  if (ps.length < 2) return;
  ps.forEach((p) => { p.style.minHeight = ""; });
  // Dar ekranda paneller alt alta düşer — o zaman eşitlik uygulanmaz.
  if (new Set(ps.map((p) => p.offsetTop)).size > 1) return;
  const h = Math.max(...ps.map((p) => p.offsetHeight));
  ps.forEach((p) => { p.style.minHeight = `${h}px`; });
}
addEventListener("resize", equalSides);
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", equalSides);
} else {
  equalSides();
}

// Tohum satırı (§9.54): çerçeve DIŞI /seeds kanalından; kare akışından
// bağımsız, açılışta + 30 sn'de bir (toprak düğmesi en geç o zaman yansır).
let _seedTimer = 0;
async function refreshSeed() {
  const now = Date.now();
  if (now - _seedTimer < 5000) return;  // kare başına fetch yok
  _seedTimer = now;
  try {
    const r = await fetch("/seeds");
    if (!r.ok) return;
    const d = await r.json();
    const p = (d.plants || [])[0];
    if (!p) return;
    $("data-seed").textContent = `${p.seed} · ${p.soil}`;
    $("data-seed").title = JSON.stringify(p.params);
  } catch (_) { /* sessiz: kare akışı etkilenmez */ }
}
refreshSeed();
setInterval(refreshSeed, 30000);
