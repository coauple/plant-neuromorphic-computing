// NPU beyin ağı — 9 post w/Δw + ateş LED'leri + sensör barları.
// Canlı /ws/npu telemetrisi; yoksa kayıtlı örnek (data/npu_sample.json).
export const POSTS = ["HN", "EC", "HS", "TS", "TN", "PH", "NPK", "X1", "X2"];

export async function loadSample(url) {
  const r = await fetch(url);
  return await r.json();
}

export function drawBrain(ctx, W, H, tele, frame) {
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0b0e11";
  ctx.fillRect(0, 0, W, H);
  ctx.font = "11px sans-serif";
  if (!tele || !tele.w) {
    ctx.fillStyle = "#8d99a3";
    ctx.fillText("NPU bağlı değil — kayıtlı örnek bekleniyor", 12, 24);
    return;
  }
  const live = !tele._sample;
  ctx.fillStyle = live ? "#8fd18a" : "#8d99a3";
  ctx.fillText(live ? "CANLI" : "KAYITLI ÖRNEK", W - 92, 16);
  const w = tele.w, prev = tele._prev || w;
  const bw = (W - 20) / 9;
  ctx.font = "11px sans-serif";
  for (let i = 0; i < 9; i++) {
    const x = 10 + i * bw;
    const hgt = Math.min(H - 120, (w[i] / 2.0) * (H - 120));
    ctx.fillStyle = "#3b4a38";
    ctx.fillRect(x + 2, 30 + (H - 120 - hgt), bw - 6, hgt);
    const dw = w[i] - (prev[i] || 0);
    ctx.fillStyle = dw >= 0 ? "#8fd18a" : "#d16868";
    ctx.fillRect(x + 2, 30 + (H - 120 - hgt) - 3, bw - 6, 2);
    const fired = tele.f && tele.f[i] === "1";
    ctx.fillStyle = fired ? "#e8c85a" : "#2a3138";
    ctx.beginPath(); ctx.arc(x + bw / 2 - 1, H - 76, 5, 0, 7); ctx.fill();
    ctx.fillStyle = "#8d99a3";
    ctx.fillText(POSTS[i] || `P${i}`, x + 2, H - 60);
    ctx.fillText(w[i].toFixed(2), x + 2, H - 46);
  }
  // Sensör barları (world frame'den)
  if (frame && frame.sensors) {
    const keys = ["hs", "ts", "hn", "tn", "ph", "npk", "ec"];
    ctx.fillStyle = "#8d99a3";
    ctx.fillText("sensörler", 12, H - 28);
    keys.forEach((k, i) => {
      const v = frame.sensors[k] || 0;
      const x = 12 + i * ((W - 24) / 7);
      ctx.fillStyle = "#22303a";
      ctx.fillRect(x, H - 22, (W - 24) / 7 - 4, 8);
      ctx.fillStyle = "#7fb0d1";
      ctx.fillRect(x, H - 22, ((W - 24) / 7 - 4) * (v / 100), 8);
    });
  }
  tele._prev = w.slice();
}
