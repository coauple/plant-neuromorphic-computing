// Terraryum kesiti (2D) — gerçek salep (Orchis mascula) botanik çizimi.
//
// Referans: 4 botanik illüstrasyon (gi2l03, e48h0n, 4q373x, fykikh).
// Anatomi evre bazlı:
//   DORMANT   → tek yumru, kök yok, toprak boş
//   SPROUTING → yumru + beyaz kökler (yumru tabanından) + cigar sürgün
//   VEGETATIVE→ ana yumru buruşur + stolon + yavru yumrular + rozet yapraklar
//   FLOWERING → 2 yumru (koyu+dolgun) + tam kök + rozet + sap yp. + çiçek
//   SENESCENCE→ sararma, solar
//
// GEOMETRİ KİLİDİ: bütün ana koordinatlar SalepProfile.layoutContent'ten
// gelir; bu dosya yalnız İÇ DOLDURMA zenginliğidir — G24 paritesi etkilenmez.
const { SOIL_Y, LEAF_DY, ROOT_K, TIP_GAP, profile2d, layoutContent } = globalThis.SalepProfile;

// ──────────────────────────────────────────────────
//  Yardımcılar
// ──────────────────────────────────────────────────

function hash(i, s) {
  let h = ((i * 2654435761 + (s || 0) * 40503) >>> 0);
  h ^= h >>> 13; h = Math.imul(h, 1274126177) >>> 0; h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}
function clamp01(v) { return Math.max(0, Math.min(1, v)); }
function lerp(a, b, t) { return a + (b - a) * clamp01(t); }
function lerpC(a, b, t) {
  return [lerp(a[0],b[0],t)|0, lerp(a[1],b[1],t)|0, lerp(a[2],b[2],t)|0];
}
function rgb(c)  { return `rgb(${c[0]},${c[1]},${c[2]})`; }
function rgba(c,a) { return `rgba(${c[0]},${c[1]},${c[2]},${a})`; }

// ──────────────────────────────────────────────────
//  1. GÖKYÜZÜ
// ──────────────────────────────────────────────────

// Gece karanlığı 0..1: güneş +8°'de 0, -8°'de 1 (sürekli, dal switch YOK).
function darkness(alt) { return clamp01((8 - alt) / 16); }

// Güneş yayı (saf, test edilebilir): ŞEKİL tamamen dayT'den (gün-içi
// zaman, doğum 0, batım 1) türetilir — sinüs kubbe: t=0'da 0 (ufuk),
// t=0.5'te 1 (tepe), t=1'de 0 (ufuk); [-0.25,1.25] dışına taştığında
// da (alacakaranlık) aynı formülle düzgün negatife döner. YÜKSEKLİK
// ÖLÇEĞİ (peakAltDeg — günün en yüksek güneş açısı) ayrı bir girdi.
//
// BUGFIX (dikey iniş/çıkış): dayT eskiden clamp01 ile 0/1'e sert
// kilitleniyordu; alt=-3'e kadar (alacakaranlık) çizim sürdüğü için x
// donup güneş dikey iniyordu. Şimdi t yumuşak sınırlanıyor.
//
// BUGFIX (hızlandırınca "merdiven"): önceki sürümde y doğrudan ham
// `alt`'a bağlıydı ve kare-kare bir EMA ile yumuşatılıyordu. Sunucu
// alt'ı saniyede yalnız ~5 kez gönderiyor; simülasyon hızlandırılınca
// iki güncelleme arası saatlerce sim-zaman geçiyor, yani gerçek eğri
// yalnızca birkaç kaba noktayla temsil ediliyor — EMA'nın "büyük farkta
// direkt atla" kuralı da bunu sürekli tetikleyip sıçra-süzül-sıçra
// görüntüsü (merdiven) veriyordu. dayT ise saatten türer ve HER hızda
// kesintisiz ara-değerlenir; şekli tamamen ona bağlamak sıçramayı kökten
// kaldırıyor. Yükseklik ÖLÇEĞİ de artık kare-kare değil, günde yalnız
// bir kez (öğlen geçişinde, bkz. trackPeakAlt) güncelleniyor.
export function sunXY(W, gy, peakAltDeg, dayT) {
  const t = Math.max(-0.25, Math.min(1.25, dayT ?? 0.5));
  const shape = Math.sin(Math.PI * t); // ufukta 0, tepede 1, ufuk altında düzgün negatif
  return { x: W * (0.08 + 0.84 * t), y: gy - shape * (peakAltDeg / 90) * gy * 0.88 - 8 };
}

// Günün en yüksek güneş açısını izleyen durum (sunXY saf kalsın diye
// burada, çağıran tarafta). Kare-kare değil, yalnız ÖĞLEN GEÇİŞİNDE
// (dayT 0.5'i aştığı an) o anki alt'a kilitlenir — böylece hız ne
// olursa olsun günde tek, öngörülebilir bir güncelleme olur, ara
// karelerdeki ham alt gürültüsü yörüngeye hiç karışmaz.
let _peakAlt = 45;
let _wasBeforeNoon = true;
function trackPeakAlt(alt, dayT) {
  const beforeNoon = (dayT ?? 0.5) < 0.5;
  if (_wasBeforeNoon && !beforeNoon) _peakAlt = Math.max(5, alt);
  _wasBeforeNoon = beforeNoon;
  return _peakAlt;
}

function drawSky(ctx, W, H, gy, pr) {
  const alt = pr.sunAlt, dark = darkness(alt);
  const peakAlt = trackPeakAlt(alt, pr.dayT);
  // Gündüz bazı (yükseklikle açılır) — geceye doğru koyulaşır
  const t = clamp01(Math.max(0, alt) / 60);
  const dim = 1 - 0.82 * dark;
  const g = ctx.createLinearGradient(0, 0, 0, gy);
  g.addColorStop(0,   `rgb(${(20+28*t)*dim|0},${(28+42*t)*dim|0},${(50+55*t)*dim|0})`);
  g.addColorStop(0.65,`rgb(${(35+52*t)*dim|0},${(46+60*t)*dim|0},${(68+55*t)*dim|0})`);
  g.addColorStop(1,   `rgb(${(55+70*t)*dim|0},${(58+68*t)*dim|0},${(62+48*t)*dim|0})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, gy);

  // Gün batımı sıcaklığı: alt ~3°'de tepe, uzağında söner (sürekli)
  const warmth = Math.exp(-Math.pow((alt - 3) / 7, 2)) * (1 - dark * 0.4);
  if (warmth > 0.02) {
    const wg = ctx.createLinearGradient(0, gy * 0.45, 0, gy);
    wg.addColorStop(0, "rgba(150,90,60,0)");
    wg.addColorStop(1, `rgba(215,125,60,${0.55 * warmth})`);
    ctx.fillStyle = wg; ctx.fillRect(0, 0, W, gy);
  }

  // Güneş diski — parabolik yay: saat x'i sürer (doğu solda doğar,
  // batı sağda batar), yükseklik y'yi; ufukta batar (donma yok)
  const { x: sx, y: sy } = sunXY(W, gy, peakAlt, pr.dayT);
  if (alt > -3) {
    const sunk = clamp01((sy - (gy - 16)) / 20); // 1 gökte, 0 batmış
    const hal = ctx.createRadialGradient(sx, Math.min(sy, gy), 5, sx, Math.min(sy, gy), 52);
    hal.addColorStop(0, `rgba(255,235,170,${(0.35 * sunk).toFixed(3)})`);
    hal.addColorStop(1, "rgba(255,200,80,0)");
    ctx.fillStyle = hal;
    ctx.beginPath(); ctx.arc(sx, Math.min(sy, gy), 52, 0, 7); ctx.fill();
    // Ufukta yumuşak belirme: disk alt -3..+2 arasında solar (sert açılma yok)
    const fade = clamp01((alt + 3) / 5);
    ctx.save(); ctx.globalAlpha = fade;
    if (sy < gy - 2) {
      const sun = ctx.createRadialGradient(sx, sy, 2, sx, sy, 16);
      sun.addColorStop(0, "#fffae0"); sun.addColorStop(0.6, "#e8c040"); sun.addColorStop(1, "#cc9818");
      ctx.fillStyle = sun;
      ctx.beginPath(); ctx.arc(sx, sy, 16, 0, 7); ctx.fill();
    } else {
      // Ufukta yarım güneş: diski ufuk çizgisinde kes
      ctx.save();
      ctx.beginPath(); ctx.rect(0, 0, W, gy);
      ctx.clip();
      const sun = ctx.createRadialGradient(sx, sy, 2, sx, sy, 16);
      sun.addColorStop(0, "#fffae0"); sun.addColorStop(0.6, "#e84818"); sun.addColorStop(1, "#cc9818");
      ctx.fillStyle = sun;
      ctx.beginPath(); ctx.arc(sx, sy, 16, 0, 7); ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }

  // Yıldızlar — karanlıkla süzülerek belirir (atlama yok)
  if (dark > 0.05) {
    for (let i = 0; i < 40; i++) {
      const a = (0.5 + hash(i, 62) * 0.5) * dark;
      ctx.fillStyle = `rgba(210,220,255,${a.toFixed(3)})`;
      ctx.beginPath();
      ctx.arc(hash(i, 60) * W, hash(i, 61) * gy * 0.9, 0.6 + hash(i, 63) * 1.1, 0, 7);
      ctx.fill();
    }
  }

  if (pr.rain > 0) {
    for (let i = 0; i < 5; i++) {
      ctx.fillStyle = `rgba(70,78,92,${0.15+hash(i,70)*0.12})`;
      ctx.beginPath();
      ctx.ellipse(hash(i,71)*W, 12+hash(i,72)*gy*0.3, 60+hash(i,73)*80, 14+hash(i,74)*10, 0,0,7);
      ctx.fill();
    }
  }
}

// ──────────────────────────────────────────────────
//  2. TOPRAK
// ──────────────────────────────────────────────────

function drawSoil(ctx, W, H, gy, pr) {
  const w = pr.soilWet, soilH = H - gy;

  // Dalgalı toprak yüzeyi klibi
  ctx.save();
  ctx.beginPath(); ctx.moveTo(0, gy-1);
  for (let x=0; x<=W; x+=18) {
    ctx.lineTo(x, gy + Math.sin(x*0.035+1.8)*1.8 + Math.sin(x*0.08)*0.9);
  }
  ctx.lineTo(W,H); ctx.lineTo(0,H); ctx.closePath(); ctx.clip();

  // Katman 1: üst humus (koyu)
  const k1 = 1 - 0.38*w;
  let g = ctx.createLinearGradient(0, gy, 0, gy+soilH*0.18);
  g.addColorStop(0, `rgb(${(78*k1)|0},${(55*k1)|0},${(35*k1)|0})`);
  g.addColorStop(1, `rgb(${(58*k1)|0},${(40*k1)|0},${(24*k1)|0})`);
  ctx.fillStyle = g; ctx.fillRect(0, gy-2, W, soilH*0.18+2);

  // Katman 2: orta kil
  const k2 = 1 - 0.32*w;
  g = ctx.createLinearGradient(0, gy+soilH*0.18, 0, gy+soilH*0.5);
  g.addColorStop(0, `rgb(${(50*k2)|0},${(36*k2)|0},${(22*k2)|0})`);
  g.addColorStop(1, `rgb(${(38*k2)|0},${(26*k2)|0},${(16*k2)|0})`);
  ctx.fillStyle = g; ctx.fillRect(0, gy+soilH*0.18, W, soilH*0.32);

  // Katman 3: derin
  const k3 = 1 - 0.28*w;
  g = ctx.createLinearGradient(0, gy+soilH*0.5, 0, H);
  g.addColorStop(0, `rgb(${(30*k3)|0},${(21*k3)|0},${(13*k3)|0})`);
  g.addColorStop(1, `rgb(${(22*k3)|0},${(15*k3)|0},${(9*k3)|0})`);
  ctx.fillStyle = g; ctx.fillRect(0, gy+soilH*0.5, W, soilH*0.5+2);

  // Taşlar (referans görseldeki gibi — gri-bej kübik şekiller)
  for (let i = 0; i < 48; i++) {
    const px = hash(i,3)*W, depth = hash(i,5);
    const py = gy+8 + depth*(soilH-16);
    const rs = 3+hash(i,7)*9, ry = rs*(0.55+hash(i,8)*0.35);
    const dk = 0.25+0.35*(1-depth);
    ctx.fillStyle = `rgba(${(155*dk)|0},${(138*dk)|0},${(115*dk)|0},${0.30+0.22*hash(i,9)})`;
    ctx.beginPath();
    ctx.ellipse(px, py, rs, ry, hash(i,13)*1.8-0.9, 0, 7);
    ctx.fill();
    // Taş kenar gölgesi
    ctx.strokeStyle = `rgba(${(90*dk)|0},${(75*dk)|0},${(55*dk)|0},0.18)`;
    ctx.lineWidth = 0.6;
    ctx.beginPath(); ctx.ellipse(px, py, rs, ry, hash(i,13)*1.8-0.9, 0, 7); ctx.stroke();
  }

  // Toprak içi ince kök ağı (arka plan, tüm evrelerde)
  ctx.strokeStyle = "rgba(100,75,48,0.18)";
  ctx.lineWidth = 0.7;
  for (let i = 0; i < 12; i++) {
    const x0 = hash(i,80)*W, y0 = gy+20+hash(i,81)*soilH*0.65;
    ctx.beginPath(); ctx.moveTo(x0, y0);
    ctx.quadraticCurveTo(x0+(hash(i,82)-0.5)*40, y0+12, x0+(hash(i,83)-0.5)*30, y0+26);
    ctx.stroke();
    if (hash(i,84)>0.5) {
      const x1=x0+(hash(i,85)-0.5)*28, y1=y0+15;
      ctx.beginPath(); ctx.moveTo(x1,y1);
      ctx.lineTo(x1+(hash(i,86)-0.5)*20, y1+14); ctx.stroke();
    }
  }
  ctx.restore();

  // Tuz kabuğu
  if (pr.saltCrust > 0.02) {
    ctx.fillStyle = `rgba(215,215,205,${Math.min(0.82,pr.saltCrust)})`;
    ctx.fillRect(0, gy-3, W, 4);
  }
  // Toprak çizgisi
  ctx.strokeStyle = "#252c34"; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(0, gy);
  for (let x=0; x<=W; x+=18)
    ctx.lineTo(x, gy + Math.sin(x*0.035+1.8)*1.5 + Math.sin(x*0.08)*0.7);
  ctx.stroke();
}

// ──────────────────────────────────────────────────
//  3. KÖK SİSTEMİ
//  Referans: kökler yumru TACINDAN (üstten) çıkar, beyaz/krem rengi,
//  dallanmalı — DORMANT'ta yok, SPROUTING+'tan itibaren gelişir
// ──────────────────────────────────────────────────

function drawRootSystem(ctx, cx, tuberTopY, pr, W, H) {
  if (pr.stage === "DORMANT") return;

  // Kök olgunluğu: SPROUTING başında az, VEGETATIVE+ tam
  const maturity = pr.stage === "SPROUTING"
    ? clamp01((pr.stageAge || 0) / 20)
    : 1.0;
  if (maturity < 0.05) return;

  const nec = pr.rootNecrotic;
  // Renk: sağlıklı beyaz-krem → nekrotik kahverengi
  const baseCol = lerpC([220,200,165], [90,60,35], nec);

  // Ana kökler (yumru tabanından aşağı doğru)
  const nMain = Math.round(lerp(4, 10, maturity));
  for (let i = 0; i < nMain; i++) {
    const angle = Math.PI * (0.1 + 0.8*(i/(nMain-1))); // aşağı yarı daire
    const len = H*0.13*maturity * (0.6 + 0.45*hash(i,20));
    const endX = cx + Math.cos(angle)*len;
    const endY = tuberTopY + Math.sin(angle)*len;
    const midX = lerp(cx, endX, 0.5) + (hash(i,21)-0.5)*14*maturity;
    const midY = tuberTopY + (endY-tuberTopY)*0.6;

    // Kalından inceye (segment)
    const segs = 10;
    for (let s=0; s<segs; s++) {
      const t0=s/segs, t1=(s+1)/segs;
      const x0=(1-t0)*(1-t0)*cx+2*(1-t0)*t0*midX+t0*t0*endX;
      const y0=(1-t0)*(1-t0)*tuberTopY+2*(1-t0)*t0*midY+t0*t0*endY;
      const x1=(1-t1)*(1-t1)*cx+2*(1-t1)*t1*midX+t1*t1*endX;
      const y1=(1-t1)*(1-t1)*tuberTopY+2*(1-t1)*t1*midY+t1*t1*endY;
      ctx.strokeStyle = rgba(baseCol, 0.8-t1*0.35);
      ctx.lineWidth = (2.2-nec*0.6)*(1-t1*0.72);
      ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(x0,y0); ctx.lineTo(x1,y1); ctx.stroke();
    }
    // Yan dallar
    const nBr = maturity>0.5 ? 2+((hash(i,22)>0.5)?1:0) : 1;
    for (let b=0; b<nBr; b++) {
      const bt = 0.35+0.45*hash(i*3+b, 23);
      const bx=(1-bt)*(1-bt)*cx+2*(1-bt)*bt*midX+bt*bt*endX;
      const by=(1-bt)*(1-bt)*tuberTopY+2*(1-bt)*bt*midY+bt*bt*endY;
      const ba=angle+(hash(i*3+b,24)-0.5)*1.0;
      const bl=(10+hash(i*3+b,25)*18)*maturity;
      ctx.strokeStyle = rgba(baseCol, 0.5);
      ctx.lineWidth = 0.8;
      ctx.beginPath(); ctx.moveTo(bx,by);
      ctx.lineTo(bx+Math.cos(ba)*bl, by+Math.sin(ba)*bl); ctx.stroke();
      // İkinci nesil dal
      if (maturity>0.7 && hash(i*5+b,26)>0.55) {
        const bl2 = bl*0.55;
        const ba2 = ba+(hash(i*5+b,27)-0.5)*0.8;
        ctx.lineWidth = 0.45;
        ctx.strokeStyle = rgba(baseCol, 0.32);
        ctx.beginPath();
        ctx.moveTo(bx+Math.cos(ba)*bl, by+Math.sin(ba)*bl);
        ctx.lineTo(bx+Math.cos(ba)*bl+Math.cos(ba2)*bl2, by+Math.sin(ba)*bl+Math.sin(ba2)*bl2);
        ctx.stroke();
      }
    }
  }
}

// ──────────────────────────────────────────────────
//  4. YUMRU SİSTEMİ — evre bazlı
//  Referans: oval yumru, derinlikte, sivri tepe
// ──────────────────────────────────────────────────

function drawOvalTuber(ctx, tx, ty, rx, ry, isOld, alpha) {
  alpha = alpha ?? 1.0;
  ctx.save(); ctx.globalAlpha = alpha;

  // Gölge
  ctx.fillStyle = "rgba(0,0,0,0.20)";
  ctx.beginPath(); ctx.ellipse(tx+4, ty+6, rx+2, ry+1, 0.1, 0, 7); ctx.fill();

  if (isOld) {
    // Yaşlı/buruşuk: koyu kahverengi, radial gradient
    const g = ctx.createRadialGradient(tx-rx*0.2, ty-ry*0.28, rx*0.08, tx, ty, Math.max(rx,ry));
    g.addColorStop(0, "#8a6a42"); g.addColorStop(0.45, "#6a4c28");
    g.addColorStop(0.8, "#4e3418"); g.addColorStop(1, "#342010");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.ellipse(tx, ty, rx, ry, 0.08, 0, 7); ctx.fill();
    // Buruşukluk halkalar
    ctx.strokeStyle = "rgba(38,22,8,0.38)"; ctx.lineWidth = 0.8;
    for (let w=0; w<5; w++) {
      const r = 0.28+w*0.15;
      ctx.beginPath(); ctx.ellipse(tx, ty, rx*r, ry*(r-0.04), 0.08+w*0.06, 0, 7); ctx.stroke();
    }
    // Kırışık çizgiler
    ctx.strokeStyle = "rgba(30,16,5,0.22)"; ctx.lineWidth = 0.5;
    for (let l=0; l<6; l++) {
      const a0 = -0.9+l*0.32;
      ctx.beginPath();
      ctx.moveTo(tx+Math.cos(a0)*rx*0.2, ty+Math.sin(a0)*ry*0.2);
      ctx.lineTo(tx+Math.cos(a0)*rx*0.88, ty+Math.sin(a0)*ry*0.88);
      ctx.stroke();
    }
  } else {
    // Yeni/dolgun: bej-krem, parlak
    const g = ctx.createRadialGradient(tx-rx*0.28, ty-ry*0.38, rx*0.06, tx, ty, Math.max(rx,ry));
    g.addColorStop(0, "#f8ecd0"); g.addColorStop(0.28, "#e8d0a0");
    g.addColorStop(0.65, "#ccb078"); g.addColorStop(1, "#a08040");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.ellipse(tx, ty, rx, ry, 0.08, 0, 7); ctx.fill();
    // Parlak highlight
    const hi = ctx.createRadialGradient(tx-rx*0.3, ty-ry*0.38, 1, tx-rx*0.18, ty-ry*0.25, rx*0.52);
    hi.addColorStop(0,"rgba(255,252,235,0.68)"); hi.addColorStop(1,"rgba(255,252,235,0)");
    ctx.fillStyle = hi;
    ctx.beginPath(); ctx.ellipse(tx-rx*0.18, ty-ry*0.25, rx*0.48, ry*0.36, 0.08, 0, 7); ctx.fill();
    // İnce çevre çizgisi
    ctx.strokeStyle = "rgba(140,105,58,0.25)"; ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.ellipse(tx, ty, rx, ry, 0.08, 0, 7); ctx.stroke();
  }
  // Sivri tepe (üst kısım)
  ctx.restore();
}

function drawTuberSystem(ctx, cx, gy, W, H, pr, L) {
  const X = (x) => x*W, Y = (y) => y*H;
  // Yumru merkezinin derinliği: toprak yüzeyinin ~%22 altında
  const tuberDepthBase = gy + H*0.22;
  const tr = X(pr.tuberR);   // profile.js'den gelen yarıçap

  if (pr.stage === "DORMANT") {
    // TEK YUMRU — dolgun, bej, tek başına
    drawOvalTuber(ctx, cx, tuberDepthBase, tr*1.05, tr*0.85, false);
    return tuberDepthBase - tr*0.85; // TAÇ (kökler buradan çıkar)
  }

  if (pr.stage === "SPROUTING") {
    // Tek yumru, biraz büyüyor
    const grow = clamp01((pr.stageAge||0)/20);
    const curR = tr*(1.0+grow*0.12);
    drawOvalTuber(ctx, cx, tuberDepthBase, curR, curR*0.82, false);
    return tuberDepthBase - curR*0.82; // TAÇ
  }

  // VEGETATIVE+
  const vAge = pr.stageAge || 0;
  const shrink = pr.stage === "VEGETATIVE"
    ? clamp01(vAge/40)
    : clamp01(0.6 + (vAge/60)*0.4);  // FLOWERING+'ta daha da buruşmuş

  // Ana yumru HEP ORTADA (evre değişiminde ışınlanma yok);
  // DORMANT/SPROUTING tek yumru da zaten cx'te çizilir.
  const mainTx = cx;
  const mainR  = tr*(1.15 - shrink*0.45);
  drawOvalTuber(ctx, mainTx, tuberDepthBase+4, mainR, mainR*0.80, shrink > 0.25);

  // Stolon + yavru yumrular (VEGETATIVE ortasından itibaren)
  const stolonFrac = pr.stage === "VEGETATIVE"
    ? clamp01((vAge-8)/30)
    : 1.0;

  if (stolonFrac > 0.05) {
    // Stolon çizgisi (sağa doğru)
    const stolEndX = mainTx + W*0.12*stolonFrac;
    const stolEndY = tuberDepthBase - H*0.02;
    ctx.strokeStyle = "#b8a070"; ctx.lineWidth = 2.8; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(mainTx+mainR*0.7, tuberDepthBase);
    ctx.quadraticCurveTo(mainTx+W*0.07*stolonFrac, tuberDepthBase-H*0.03, stolEndX, stolEndY);
    ctx.stroke();

    // Yavru yumru (stolon ucunda)
    const babyR = tr*0.68*stolonFrac;
    if (babyR > 4) {
      drawOvalTuber(ctx, stolEndX+babyR, stolEndY, babyR, babyR*0.88, false, stolonFrac);
    }

    // İkinci küçük yavru yumru (VEGETATIVE geç + FLOWERING)
    if (stolonFrac > 0.55 && pr.stage !== "VEGETATIVE" || (pr.stage==="VEGETATIVE" && vAge>30)) {
      const baby2R = tr*0.48*clamp01((stolonFrac-0.4)/0.6);
      const baby2X = mainTx - W*0.10*clamp01((stolonFrac-0.4)/0.6);
      const baby2Y = tuberDepthBase + H*0.04;
      if (baby2R > 3) {
        // Sol taraf stolon
        ctx.strokeStyle = "#b0986a"; ctx.lineWidth = 2.2;
        ctx.beginPath(); ctx.moveTo(mainTx-mainR*0.6, tuberDepthBase+4);
        ctx.quadraticCurveTo(mainTx-W*0.06, baby2Y+H*0.02, baby2X, baby2Y);
        ctx.stroke();
        drawOvalTuber(ctx, baby2X, baby2Y, baby2R, baby2R*0.85, false, clamp01((stolonFrac-0.4)/0.6));
      }
    }
  }

  // Kök başlangıcı: ana yumru TACI (tepesi) — referans böyle
  return tuberDepthBase - mainR*0.80;
}

// ──────────────────────────────────────────────────
//  4b. KÖK BOĞAZI (taç) — gövde tabanı ile yumru tacı arası geçiş.
//  Referans: gövde toprağa girince yumruya kadar çıplak inmez; kısa,
//  kalınca bir boyun (taç) ikisini bağlar, üstünden saçak çıkar.
// ──────────────────────────────────────────────────

function drawCrown(ctx, cx, gy, tuberTopY, pr) {
  if (pr.stage === "DORMANT") return; // dormant: toprak yüzeyi tamamen boş, yumru yalnız
  if (tuberTopY <= gy + 3) return;
  const dry = pr.stage === "SENESCENCE" || pr.yellowing > 0.7;
  const topW = 3.5, botW = 7;
  const g = ctx.createLinearGradient(0, gy, 0, tuberTopY);
  g.addColorStop(0, dry ? "#6e5230" : "#4f7a3e");
  g.addColorStop(1, dry ? "#7a5c34" : "#8a7a4a");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.moveTo(cx - topW, gy - 1);
  ctx.lineTo(cx - botW, tuberTopY);
  ctx.lineTo(cx + botW, tuberTopY);
  ctx.lineTo(cx + topW, gy - 1);
  ctx.closePath(); ctx.fill();
  // Taçtan çıkan kısa saçak kökler
  ctx.strokeStyle = "rgba(215,195,160,0.85)";
  ctx.lineWidth = 1.1;
  ctx.lineCap = "round";
  for (let i = 0; i < 5; i++) {
    const t = 0.25 + 0.6 * (i / 4);
    const yy = gy + (tuberTopY - gy) * t;
    const dir = i % 2 === 0 ? 1 : -1;
    const bx = cx + dir * (topW + (botW - topW) * t);
    const len = 6 + hash(i, 51) * 8;
    ctx.beginPath();
    ctx.moveTo(bx, yy);
    ctx.quadraticCurveTo(bx + dir * len * 0.6, yy + 3, bx + dir * len, yy + 6);
    ctx.stroke();
  }
}

// ──────────────────────────────────────────────────
//  5. SÜRGÜN (sadece SPROUTING)
//  Referans: cigar-şekli, ince, yeşil sivri uç
// ──────────────────────────────────────────────────

function drawShoot(ctx, cx, gy, pr, H) {
  if (pr.stage !== "SPROUTING") return;
  const progress = clamp01((pr.stageAge||0)/20);
  // Sürgün yüksekliği: toprak içinden toprak üstüne çıkıyor
  const shootH = H*0.25*progress;  // max yükseklik (toprak altı + üstü)
  const soilPenetration = H*0.08;  // toprak içindeki kısım
  const topY = gy - (shootH - soilPenetration);

  // Sürgün gövdesi — yeşil, cigar şekli
  const wBase = 5+progress*3;
  const g = ctx.createLinearGradient(cx, gy+soilPenetration, cx, topY);
  g.addColorStop(0, "#3a6830"); g.addColorStop(0.5, "#4a8840"); g.addColorStop(1, "#6aaa58");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.moveTo(cx - wBase, gy + soilPenetration*0.5);
  ctx.quadraticCurveTo(cx - wBase*0.7, gy, cx - wBase*0.4, topY + 12);
  ctx.lineTo(cx, topY);   // sivri tepe
  ctx.lineTo(cx + wBase*0.4, topY + 12);
  ctx.quadraticCurveTo(cx + wBase*0.7, gy, cx + wBase, gy + soilPenetration*0.5);
  ctx.closePath();
  ctx.fill();

  // Boyuna çizgiler (cigar yapısı)
  ctx.strokeStyle = "rgba(35,70,25,0.35)"; ctx.lineWidth = 0.6;
  for (let d=-1; d<=1; d+=2) {
    ctx.beginPath();
    ctx.moveTo(cx+d*wBase*0.35, gy+soilPenetration*0.4);
    ctx.quadraticCurveTo(cx+d*wBase*0.2, gy, cx+d*wBase*0.1, topY+10);
    ctx.stroke();
  }
  // Parlak highlight
  ctx.strokeStyle = "rgba(140,210,100,0.28)"; ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.moveTo(cx-wBase*0.1, gy+soilPenetration*0.3);
  ctx.quadraticCurveTo(cx-wBase*0.08, gy, cx-wBase*0.04, topY+14);
  ctx.stroke();
}

// ──────────────────────────────────────────────────
//  6. ROZET YAPRAKLAR (VEGETATIVE+)
//  Referans: gövde tabanında, toprak çizgisine yakın, geniş lanceolate,
//  dışa açık, hepsi birbirinin üzerine binmeden rozet
// ──────────────────────────────────────────────────

function drawRozetLeaf(ctx, ox, oy, dir, len, width, pr, seed) {
  const y = pr.yellowing;
  const baseCol = lerpC([42,112,38],[168,132,42],y);
  const tipCol  = lerpC([52,125,46],[132,92,32],y);

  // Gölge
  ctx.save();
  ctx.fillStyle = "rgba(0,0,0,0.09)";
  ctx.beginPath();
  ctx.moveTo(ox, oy+4);
  ctx.bezierCurveTo(ox+dir*len*0.3+2, oy+4-width*0.6, ox+dir*len*0.7+2, oy+4-width*0.3, ox+dir*len+2, oy+10+4);
  ctx.bezierCurveTo(ox+dir*len*0.7+2, oy+4+width*0.7, ox+dir*len*0.3+2, oy+4+width*1.1, ox, oy+4);
  ctx.fill(); ctx.restore();

  // Yandan bakış: bıçak tabandan yukarı KAVİSLENİR, uç solgunlukla düşer
  const arch = width*0.55;
  const tipX = ox+dir*len, tipY = oy - 6 + pr.leafDroop*22;
  // Ana yaprak (lanceolate — altta geniş, uçta sivri)
  const g = ctx.createLinearGradient(ox, oy, tipX, tipY);
  g.addColorStop(0, rgb(baseCol)); g.addColorStop(0.7, rgb(lerpC(baseCol,tipCol,0.6))); g.addColorStop(1, rgb(tipCol));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.moveTo(ox, oy);
  // Üst kenar (kavisli yükselir, sivri uca iner)
  ctx.bezierCurveTo(ox+dir*len*0.22, oy-width-arch, ox+dir*len*0.60, oy-width*0.6-arch*0.5, tipX, tipY);
  // Uçtan geri (sivri)
  ctx.bezierCurveTo(ox+dir*len*0.62, tipY+width*0.55, ox+dir*len*0.24, oy+width*1.05, ox, oy);
  ctx.fill();

  // Kenar ışığı (üst kenarı izler)
  ctx.strokeStyle = `rgba(${120+(1-y)*60|0},${190-y*40|0},${90-y*30|0},0.22)`;
  ctx.lineWidth = 0.7;
  ctx.beginPath();
  ctx.moveTo(ox+dir*6, oy-2);
  ctx.bezierCurveTo(ox+dir*len*0.22, oy-width-arch+2, ox+dir*len*0.6, oy-width*0.55-arch*0.4, tipX-dir*8, tipY+3);
  ctx.stroke();

  // Orta damar (kavisi izler)
  ctx.strokeStyle = `rgba(${28+y*40|0},${75-y*25|0},${22-y*10|0},${0.65-y*0.2})`;
  ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(ox, oy);
  ctx.bezierCurveTo(ox+dir*len*0.32, oy-arch*0.4, ox+dir*len*0.65, tipY, tipX, tipY); ctx.stroke();

  // Yan damarlar (kavisli orta damardan çıkar, ince)
  ctx.strokeStyle = `rgba(38,88,30,${0.18-y*0.08})`;
  ctx.lineWidth = 0.45;
  for (let v=0; v<5; v++) {
    const t = 0.18+0.6*(v/4);
    const vx = ox+dir*len*t, vy = oy+(tipY-oy)*t;
    const vl = width*(0.38+0.28*(1-t));
    ctx.beginPath(); ctx.moveTo(vx,vy); ctx.lineTo(vx-dir*vl*0.1, vy-vl*0.75); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(vx,vy); ctx.lineTo(vx-dir*vl*0.1, vy+vl*0.65); ctx.stroke();
  }

  // Orkide benekleri (koyu mor, Orchis mascula imzası)
  if (y < 0.55) {
    ctx.fillStyle = `rgba(72,32,72,${0.52-y*0.42})`;
    for (let s=0; s<5; s++) {
      const f=0.18+0.6*hash(seed,s);
      const bx=ox+dir*len*f, by=oy+(hash(seed,9+s)-0.5)*width*1.1;
      ctx.beginPath(); ctx.ellipse(bx, by, 2.6, 1.6, dir*0.3, 0, 7); ctx.fill();
    }
  }
}

function drawRozetLeaves(ctx, cx, gy, W, pr) {
  const stage = pr.stage;
  if (stage === "DORMANT" || stage === "SPROUTING" || pr.stemH < 0.05) return;

  const vAge = pr.stageAge || 0;
  // Yaprak sayısı evre/yaşa göre
  let nLeaves = 3;
  if (stage === "VEGETATIVE") nLeaves = Math.min(6, 3+Math.floor(vAge/8));
  else if (stage === "FLOWERING" || stage === "SENESCENCE") nLeaves = 6;

  const baseX = cx, baseY = gy - 6;  // Toprak seviyesinde
  const maxSpan = W * 0.15;  // Küçük rozet: salkımı bastırmasın

  for (let i = 0; i < nLeaves; i++) {
    const dir = i%2===0 ? 1 : -1;
    // Her yaprak biraz farklı açı + uzunluk
    const leafLen = maxSpan * (0.55 + 0.42*(i/(Math.max(nLeaves-1,1))));
    const leafW   = leafLen * 0.36;  // Kısa ama geniş bıçak
    // Rozet açısı: yapraklar yataydan hafif aşağı eğimli
    const angleOff = (i*0.18) * 0.5;
    const startY   = baseY + 8 + angleOff*12;
    drawRozetLeaf(ctx, baseX, startY, dir, leafLen, leafW, pr, i*10+7);
  }
}

// ──────────────────────────────────────────────────
//  7. GÖVDE
// ──────────────────────────────────────────────────

function drawStem(ctx, cx, gy, stemTop, pr) {
  if (pr.stemH < 0.05) return;
  const dry = pr.stage === "SENESCENCE" || pr.yellowing > 0.7;
  const stemH = gy - stemTop;

  // Gövde gölgesi
  ctx.fillStyle = "rgba(0,0,0,0.07)";
  ctx.beginPath();
  ctx.moveTo(cx+2, gy); ctx.bezierCurveTo(cx+7, gy-stemH*0.5, cx+6, stemTop-4, cx+4, stemTop);
  ctx.lineTo(cx+6, stemTop); ctx.bezierCurveTo(cx+8, gy-stemH*0.5, cx+7, gy, cx+5, gy);
  ctx.fill();

  // Gövde gradient
  const g = ctx.createLinearGradient(cx-4, gy, cx+4, stemTop);
  if (dry) {
    g.addColorStop(0,"#6a4e28"); g.addColorStop(0.5,"#7a5e38"); g.addColorStop(1,"#96784a");
  } else {
    g.addColorStop(0,"#38622a"); g.addColorStop(0.35,"#46783a"); g.addColorStop(0.7,"#548c48"); g.addColorStop(1,"#62a056");
  }
  ctx.fillStyle = g;
  // Hafif bezier eğri
  ctx.beginPath();
  ctx.moveTo(cx-3.5, gy);
  ctx.bezierCurveTo(cx-2.8, gy-stemH*0.35, cx-2.2, gy-stemH*0.65, cx-1.6, stemTop);
  ctx.lineTo(cx+1.6, stemTop);
  ctx.bezierCurveTo(cx+2.2, gy-stemH*0.65, cx+2.8, gy-stemH*0.35, cx+3.5, gy);
  ctx.closePath(); ctx.fill();

  // Boyuna damarlar
  if (!dry) {
    ctx.strokeStyle = "rgba(35,72,24,0.22)"; ctx.lineWidth = 0.5;
    for (let d=-1; d<=1; d+=2) {
      ctx.beginPath(); ctx.moveTo(cx+d*1.1, gy);
      ctx.bezierCurveTo(cx+d*0.9, gy-stemH*0.35, cx+d*0.7, gy-stemH*0.65, cx+d*0.5, stemTop);
      ctx.stroke();
    }
  }

  // Boğum noktaları
  const nN = Math.round(stemH/42);
  for (let n=1; n<=nN; n++) {
    const ny = gy - stemH*n/(nN+1);
    ctx.fillStyle = dry ? "rgba(85,60,30,0.35)" : "rgba(42,88,32,0.32)";
    ctx.beginPath(); ctx.ellipse(cx, ny, 4.5, 1.8, 0, 0, 7); ctx.fill();
  }
}

// ──────────────────────────────────────────────────
//  8. SAP YAPRAKLARI (gövde alt kısmında 2-3 küçük)
//  Referans: gövdeyi saran lanceolate küçük yapraklar
// ──────────────────────────────────────────────────

function drawStemLeaves(ctx, cx, gy, stemTop, pr) {
  if (pr.stemH < 0.40) return;
  const stemH = gy - stemTop;
  const n = pr.stage === "FLOWERING" ? 3 : 2;
  const y = pr.yellowing;
  const col = lerpC([44,118,42],[125,142,50],y);

  for (let i=0; i<n; i++) {
    const t = 0.08 + 0.22*i;  // gövdenin alt %8-50'si
    const leafY = gy - stemH*t;
    const dir = i%2===0 ? 1 : -1;
    const len = 22+i*8;  // küçük, kısa
    const w   = len*0.22;

    // Yaprak tabanı gövdeye yapışık
    const g = ctx.createLinearGradient(cx, leafY, cx+dir*len, leafY+4);
    g.addColorStop(0, rgb(col)); g.addColorStop(1, rgb(lerpC(col,[150,168,58],0.4)));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(cx, leafY);
    ctx.bezierCurveTo(cx+dir*len*0.3, leafY-w, cx+dir*len*0.7, leafY-w*0.4, cx+dir*len, leafY+3);
    ctx.bezierCurveTo(cx+dir*len*0.7, leafY+w*0.6, cx+dir*len*0.3, leafY+w*0.9, cx, leafY);
    ctx.fill();
    // Orta damar
    ctx.strokeStyle = `rgba(28,75,22,0.45)`; ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(cx, leafY);
    ctx.bezierCurveTo(cx+dir*len*0.4, leafY+1, cx+dir*len*0.7, leafY+2, cx+dir*len, leafY+3);
    ctx.stroke();
  }
}

// ──────────────────────────────────────────────────
//  9. ÇİÇEK SALKIMI
// ──────────────────────────────────────────────────

function drawFloret(ctx, x, y, open, seed, wither) {
  if (wither) {
    ctx.fillStyle = "#7a5c3e";
    ctx.beginPath(); ctx.ellipse(x+1, y+3, 2.8, 4.5, 0.28, 0, 7); ctx.fill();
    ctx.strokeStyle = "#5a3e26"; ctx.lineWidth = 0.7;
    ctx.beginPath(); ctx.moveTo(x,y-2); ctx.quadraticCurveTo(x+2,y+3,x+1,y+8); ctx.stroke();
    return;
  }
  if (!open) {
    const bg = ctx.createLinearGradient(x,y+5,x,y-7);
    bg.addColorStop(0,"#587a42"); bg.addColorStop(0.6,"#6e8050"); bg.addColorStop(1,"#8c6092");
    ctx.fillStyle = bg;
    ctx.beginPath();
    ctx.moveTo(x-2.2,y+4.5); ctx.quadraticCurveTo(x-3.2,y-1,x,y-7);
    ctx.quadraticCurveTo(x+3.2,y-1,x+2.2,y+4.5); ctx.closePath(); ctx.fill();
    return;
  }
  const j = (hash(seed,1)-0.5)*2.4;
  // Sapçık
  ctx.strokeStyle = "#527838"; ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.moveTo(x+(j>0?-4:4), y+6); ctx.lineTo(x, y+1.5); ctx.stroke();
  // Mahmuz (uzun, geriye)
  const spurG = ctx.createLinearGradient(x,y,x+13,y+9);
  spurG.addColorStop(0,"#a060a8"); spurG.addColorStop(1,"#784880");
  ctx.strokeStyle = spurG; ctx.lineWidth = 1.6; ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(x,y+1.5); ctx.quadraticCurveTo(x+7+j,y+5, x+13+j,y+9); ctx.stroke();
  // Yan sepaller (iri)
  ctx.fillStyle = "rgba(190,130,195,0.85)";
  ctx.beginPath(); ctx.ellipse(x-7,y-0.5+j*0.5,4.2,6.3,-0.42,0,7); ctx.fill();
  ctx.beginPath(); ctx.ellipse(x+7,y-0.5-j*0.5,4.2,6.3,0.42,0,7); ctx.fill();
  // Miğfer (iri taç)
  const galG = ctx.createRadialGradient(x,y-7,1.5,x,y-4.5,8);
  galG.addColorStop(0,"#c080c8"); galG.addColorStop(1,"#8850a0");
  ctx.fillStyle = galG;
  ctx.beginPath(); ctx.ellipse(x,y-6.5,5.7,5,0,0,7); ctx.fill();
  // Dudak (geniş yelpaze + benekli merkez)
  ctx.fillStyle = "#ddb5d8";
  ctx.beginPath();
  ctx.moveTo(x-6.5,y+1.5);
  ctx.bezierCurveTo(x-7.5,y+9,x-3,y+15,x,y+13.5);
  ctx.bezierCurveTo(x+3,y+15,x+7.5,y+9,x+6.5,y+1.5);
  ctx.bezierCurveTo(x+3,y+7.5,x-3,y+7.5,x-6.5,y+1.5);
  ctx.fill();
  ctx.fillStyle = "#cc90c5";
  ctx.beginPath(); ctx.ellipse(x,y+7.5,3.3,3.6,0,0,7); ctx.fill();
  ctx.fillStyle = "#7a3278";
  for (let s=0; s<4; s++) {
    ctx.beginPath(); ctx.arc(x-3.6+s*2.4+j*0.3, y+6.5+hash(seed,s)*2.4, 1.0, 0, 7); ctx.fill();
  }
}

function drawFlowerSpike(ctx, cx, gy, stemTop, pr, H) {
  if (pr.flowerN <= 0) return;
  const n = Math.min(pr.flowerN, 14);
  const openN = Math.round(n*pr.flowerOpen);
  const wither = pr.stage === "SENESCENCE" || pr.yellowing > 0.82;

  // Salkım gövde UCUNA bağlı, SABİT boy: sap uzadıkça bütün salkım
  // yukarı sürüklenir (aralık açılmaz, seyreklik olmaz). Tepe konumu
  // layoutContent.flowerTopY ile aynı kaynaktan (TIP_GAP).
  const spikeLen = 30 + 5*n;
  const topY = stemTop + TIP_GAP*H;
  ctx.strokeStyle = wither ? "#8a7040" : "#52823e";
  ctx.lineWidth = 1.6;
  ctx.beginPath(); ctx.moveTo(cx, topY-4); ctx.lineTo(cx, topY+spikeLen); ctx.stroke();

  for (let i=0; i<n; i++) {
    const yy = topY + spikeLen*(n===1 ? 0 : i/(n-1));
    const off = 7 + hash(100+i,1)*2;
    const xx = cx + (i%2===0 ? off : -off);
    drawFloret(ctx, xx, yy, i<openN, 100+i, wither);
  }
}

// ──────────────────────────────────────────────────
//  10. MEVSİM SÜSLERI
// ──────────────────────────────────────────────────

function drawSeasons(ctx, W, gy, pr) {
  const doy = pr.doy || 0;
  if (doy >= 60 && doy <= 165) {
    // İlkbahar: arka plan bitkileri (referans görseldeki küçük otlar)
    for (let i=0; i<14; i++) {
      const bx = hash(i,21)*W, by = gy-3-hash(i,23)*7;
      ctx.strokeStyle = `rgba(72,${112+hash(i,24)*30|0},52,0.72)`;
      ctx.lineWidth = 1;
      for (let b=0; b<3; b++) {
        const dx=(hash(i,25+b)-0.5)*10;
        ctx.beginPath(); ctx.moveTo(bx,by+4);
        ctx.quadraticCurveTo(bx+dx*0.6, by-hash(i,29+b)*10-4, bx+dx, by-hash(i,29+b)*13-4);
        ctx.stroke();
      }
    }
    // Küçük kır çiçekleri
    const cols=["#f5f5f5","#e8c440","#c88ac2","#e87878"];
    for (let i=0; i<10; i++) {
      const fx=hash(i,31)*W, fh=8+hash(i,33)*14;
      ctx.strokeStyle="rgba(65,100,50,0.72)"; ctx.lineWidth=0.8;
      ctx.beginPath(); ctx.moveTo(fx,gy-2); ctx.lineTo(fx,gy-2-fh); ctx.stroke();
      ctx.fillStyle=cols[i%4];
      ctx.beginPath(); ctx.arc(fx,gy-3-fh,2.3,0,7); ctx.fill();
    }
  }
  if (doy>=265 && doy<=330) {
    const fc=[[[195,112,38],[155,80,30]],[[175,85,40],[138,62,28]],[[208,148,52],[168,110,38]]];
    for (let i=0; i<10; i++) {
      const px=hash(i,35)*W, py=gy-4-hash(i,37)*10;
      const [ca,cb]=fc[i%3];
      const lg=ctx.createLinearGradient(px-6,py,px+6,py);
      lg.addColorStop(0,rgb(ca)); lg.addColorStop(1,rgb(cb));
      ctx.fillStyle=lg;
      ctx.beginPath(); ctx.ellipse(px,py,7+hash(i,39)*4,3.5,(hash(i,41)-0.5)*1.2,0,7); ctx.fill();
    }
  }
  if ((pr.tempAir??99) < 3) {
    for (let i=0; i<8; i++) {
      const pg=ctx.createRadialGradient(hash(i,43)*W,gy-1+hash(i,45)*9,3, hash(i,43)*W,gy-1+hash(i,45)*9,25+hash(i,47)*25);
      pg.addColorStop(0,"rgba(245,248,255,0.88)"); pg.addColorStop(1,"rgba(228,236,248,0.55)");
      ctx.fillStyle=pg;
      ctx.beginPath(); ctx.ellipse(hash(i,43)*W, gy-1+hash(i,45)*9, 24+hash(i,47)*25, 3.5+hash(i,49)*2, 0, 0, 7); ctx.fill();
    }
  }
}

// ──────────────────────────────────────────────────
//  11. YAĞMUR
// ──────────────────────────────────────────────────

function drawRain(ctx, W, gy, pr) {
  if (pr.rain <= 0) return;
  const seed = Math.floor(performance.now()/100);
  for (let i=0; i<65; i++) {
    const x=((i*173+seed*31)%960)/960*W, y=((i*97+seed*57)%600)/600*gy;
    const len=7+i%5*2;
    ctx.strokeStyle=`rgba(140,170,210,${0.28+i%3*0.09})`;
    ctx.lineWidth=0.75+i%3*0.28;
    ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x-2,y+len); ctx.stroke();
  }
  ctx.fillStyle="rgba(155,182,215,0.22)";
  for (let i=0; i<10; i++) {
    const sx=((i*211+seed*47)%960)/960*W;
    ctx.beginPath(); ctx.ellipse(sx,gy+1,3.5,1.4,0,0,7); ctx.fill();
  }
}

// ──────────────────────────────────────────────────
//  ANA ÇİZİM
// ──────────────────────────────────────────────────

export function drawWorld2d(ctx, W, H, frame) {
  const pr = profile2d(frame);
  const L  = layoutContent(pr);
  const X  = (x) => x*W, Y = (y) => y*H;
  const cx = W*0.5, gy = Y(SOIL_Y);
  const stemTop = Y(L.stemTopY);

  // ─ 1. Gökyüzü ─
  drawSky(ctx, W, H, gy, pr);

  // ─ 2. Mevsim süsleri (toprak üstü arka plan) ─
  drawSeasons(ctx, W, gy, pr);

  // ─ 3. Toprak ─
  drawSoil(ctx, W, H, gy, pr);

  // ─ 4. Yumru sistemi (evre bazlı) ─
  const tuberTopY = drawTuberSystem(ctx, cx, gy, W, H, pr, L);

  // ─ 4b. Kök boğazı (gövde-yumru arası boşluğu doldurur) ─
  drawCrown(ctx, cx, gy, tuberTopY, pr);

  // ─ 5. Kök sistemi (yumru TACINDAN, yukarıdan) ─
  drawRootSystem(ctx, cx, tuberTopY, pr, W, H);

  // ─ 6. Sürgün (yalnız SPROUTING) ─
  drawShoot(ctx, cx, gy, pr, H);

  // ─ 7. Ambient occlusion (gövde-toprak birleşimi) ─
  if (pr.stemH > 0.04) {
    const ao = ctx.createRadialGradient(cx, gy, 2, cx, gy, 22);
    ao.addColorStop(0,"rgba(0,0,0,0.14)"); ao.addColorStop(1,"rgba(0,0,0,0)");
    ctx.fillStyle = ao;
    ctx.beginPath(); ctx.ellipse(cx, gy+1, 22, 5.5, 0, 0, 7); ctx.fill();
  }

  // ─ 8. Rozet yapraklar (toprak seviyesinde, gövde tabanında) ─
  drawRozetLeaves(ctx, cx, gy, W, pr);

  // ─ 9. Gövde ─
  drawStem(ctx, cx, gy, stemTop, pr);

  // ─ 10. Sap yaprakları (gövde alt kısmı) ─
  drawStemLeaves(ctx, cx, gy, stemTop, pr);

  // ─ 11. Çiçek salkımı ─
  drawFlowerSpike(ctx, cx, gy, stemTop, pr, H);

  // ─ 12. Yağmur ─
  drawRain(ctx, W, gy, pr);

  // ─ 13. Gece karartması — SÜREKLİ (güneş yüksekliğinden; atlama yok) ─
  // Gökyüzü kendi koyulaşmasını yapar; burada tüm sahne (toprak dahil)
  // aynı karanlıkla iner, yıldızlar gökte zaten süzülerek belirdi.
  const nightK = clamp01((10 - pr.sunAlt) / 18);
  if (nightK > 0.01) {
    ctx.fillStyle = `rgba(4,8,18,${(0.62 * nightK).toFixed(3)})`;
    ctx.fillRect(0, 0, W, H);
  }

  // ─ 14. Duraklatma ─
  if (pr.paused) {
    ctx.fillStyle = "rgba(216,162,74,0.9)";
    ctx.font = "bold 13px sans-serif";
    ctx.fillText("❚❚ DURAKLATILDI", 12, 20);
  }
}
