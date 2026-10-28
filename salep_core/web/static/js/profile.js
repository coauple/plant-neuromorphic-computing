// 2D vektör profil — SAF MATEMATİK, klasik betik (modül DEĞİL).
// Tarayıcıda <script> ile, node paritesinde vm ile yüklenir; iki
// sekmenin aynı Frame'den aynı sayıları okumasının garantisi budur.
// Birimler: canvas-normalize 0..1, y aşağı artar.
//
// Ölçek disiplini (mesh-gerçek, salep_meshes.json bbox'ından türetildi):
//   mesh boyu 1.606 (y: -0.606..1.0), toprak çizgisi y=0 →
//   SOIL_Y = 1.0/1.606 = 0.623 ≈ 0.62; gövde 1.0/1.606 = 0.623 ≈ STEM_K;
//   yaprak yarı-genişlik 0.55/1.606 = 0.342 ≈ LEAF_SPAN_K;
//   kök derinliği 0.606/1.606 = 0.377 ≈ 0.30*ROOT_K; yumru ±0.22/1.606.
(function (g) {
  const SOIL_Y = 0.62;
  const STEM_K = 0.60;
  const LEAF_SPAN_K = 0.34;
  const LEAF_DY = 0.035;
  const ROOT_K = 1.25;
  const TUBER_R0 = 0.05;
  const TUBER_RK = 0.085;
  const TIP_GAP = 8 / 600; // salkım tepesi-gövde ucu açıklığı (sabit px, H=600)

  function profile2d(f) {
    const v = f.visual, p = f.plant, w = f.world;
    const tuberR = TUBER_R0 + TUBER_RK * v.tuber_scale;
    return {
      stemH: v.stem_h,
      leafSpan: v.leaf_scale * (1 - 0.5 * v.wilt),
      leafDroop: v.wilt,
      yellowing: v.yellowing,
      tuberR,
      tuberY: SOIL_Y + 0.03,
      rootLen: 0.30 * (1 - v.root_necrotic),
      rootNecrotic: v.root_necrotic,
      rootTint: v.root_tint,
      flowerN: v.flower_count,
      flowerOpen: v.flower_open,
      soilWet: v.soil_wet,
      saltCrust: v.salt_crust,
      sky: w.sky,
      sunAlt: w.sun_alt_deg,
      // Gün-içi zaman: doğum 0 → batım 1 (saatten, kesintisiz — azimut
      // işaret değeri ufukta x'i donduruyordu, o yüzden saat kullanılır).
      dayT: (() => {
        const span = Math.max(0.5, w.photoperiod_h);
        const hr = (f.sim.day_frac || 0) * 24;
        return (hr - (12 - span / 2)) / span;
      })(),
      rain: w.rain_mm,
      tempAir: w.temp_air,
      doy: ((f.sim.day % 365) + 365) % 365,
      stage: p.stage,
      stageAge: p.stage_age,
      paused: f.sim.paused,
    };
  }

  // Profil → içerik kutusu (G24 paritesinin 2D tarafı; world2d.js
  // BÜTÜN koordinatları buradan alır — çizimle parite aynı kaynaktır).
  function layoutContent(pr) {
    const stemTopY = SOIL_Y - STEM_K * pr.stemH;
    const flowerTopY = stemTopY + TIP_GAP;
    const leafTopY = SOIL_Y - 5 * LEAF_DY;
    const rootBottomY = SOIL_Y + pr.rootLen * ROOT_K;
    const tuberBottomY = pr.tuberY + pr.tuberR;
    return {
      soilY: SOIL_Y,
      stemTopY,
      flowerTopY,
      leafTopY,
      rootBottomY,
      tuberBottomY,
      topY: Math.min(stemTopY, flowerTopY, leafTopY),
      bottomY: Math.max(rootBottomY, tuberBottomY),
      halfW: LEAF_SPAN_K * pr.leafSpan,
      tuberY: pr.tuberY,
      tuberR: pr.tuberR,
    };
  }

  const NUM_KEYS_VIS = ["stem_h", "leaf_scale", "leaf_turgor", "wilt",
    "yellowing", "flower_open", "root_tint", "root_necrotic",
    "tuber_scale", "soil_wet", "salt_crust"];
  const NUM_KEYS_SEN = ["hs", "ts", "hn", "tn", "ph", "npk", "ec"];
  // Dünya/gün alanları da ara-değerlenmezse güneş-gökyüzü-mevsim her
  // WS karesinde (5 Hz) donup sıçrıyor — 60fps akıcılık burada kırılıyordu.
  const NUM_KEYS_WORLD = ["sun_alt_deg", "temp_air", "rain_mm"];
  // Azimut ara-değerlenmez — hiçbir tüketici okumuyor (x'i kesintisiz
  // gün-içi zaman/dayT sürer). Eski dairesel lerp §9.29'daydı, dayT
  // geçişiyle gereksiz kaldı.

  function lerpFrame(a, b, t) {
    if (!a) return b;
    if (!b || t <= 0) return a;
    if (t >= 1) return b;
    const out = JSON.parse(JSON.stringify(a));
    for (const k of NUM_KEYS_VIS) {
      if (typeof a.visual[k] === "number" && typeof b.visual[k] === "number")
        out.visual[k] = a.visual[k] + (b.visual[k] - a.visual[k]) * t;
    }
    for (const k of NUM_KEYS_SEN) {
      if (typeof a.sensors[k] === "number" && typeof b.sensors[k] === "number")
        out.sensors[k] = a.sensors[k] + (b.sensors[k] - a.sensors[k]) * t;
    }
    for (const k of NUM_KEYS_WORLD) {
      if (typeof a.world[k] === "number" && typeof b.world[k] === "number")
        out.world[k] = a.world[k] + (b.world[k] - a.world[k]) * t;
    }
    // dayT gün-içi saatten türediği için (profile2d) ayrıca
    // ara-değerlenmez — day+day_frac sayacı zaten pürüzsüz akıyor.
    // Sürekli gün sayacı: day+day_frac'ı birlikte ara-değerle, sonra ayır —
    // böylece doy (ve dolayısıyla mevsim/gündüz-gece) da pürüzsüz akar.
    const da = a.sim.day + (a.sim.day_frac || 0);
    const db = b.sim.day + (b.sim.day_frac || 0);
    const d = da + (db - da) * t;
    out.sim.day = Math.floor(d);
    out.sim.day_frac = d - out.sim.day;
    return out;
  }

  g.SalepProfile = {
    SOIL_Y, STEM_K, LEAF_SPAN_K, LEAF_DY, ROOT_K,
    TUBER_R0, TUBER_RK, TIP_GAP,
    profile2d, layoutContent, lerpFrame,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
