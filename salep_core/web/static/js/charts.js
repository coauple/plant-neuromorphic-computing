// Zaman serisi — sparkline + olay işaretleri (DOM yok, saf çizim).
const HIST_N = 240;

export function makeHistory() {
  return { soil: [], temp: [], hs: [], tn: [], events: [] };
}

export function pushHistory(hist, frame) {
  const push = (arr, v) => { arr.push(v); if (arr.length > HIST_N) arr.shift(); };
  push(hist.soil, frame.plant.soil_moisture);
  push(hist.temp, frame.world.temp_air_display);
  push(hist.hs, frame.sensors.hs);
  push(hist.tn, frame.sensors.tn);
  const evs = frame.events || [];
  if (evs.length) hist.events.push({ day: frame.sim.day, n: evs.length });
  if (hist.events.length > 40) hist.events.splice(0, hist.events.length - 40);
}

function spark(ctx, arr, x, y, w, h, color, min, max) {
  if (arr.length < 2) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  arr.forEach((v, i) => {
    const px = x + (i / (HIST_N - 1)) * w;
    const py = y + h - ((v - min) / Math.max(1e-9, max - min)) * h;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  });
  ctx.stroke();
}

export function drawCharts(ctx, W, H, hist) {
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0b0e11";
  ctx.fillRect(0, 0, W, H);
  ctx.font = "11px sans-serif";
  const rows = [
    ["toprak nemi", hist.soil, "#8fd18a", 0, 100],
    ["hava °C", hist.temp, "#d8a24a", 0, 40],
    ["hs / tn", hist.hs, "#7fb0d1", 0, 100],
  ];
  const rh = H / 3;
  rows.forEach(([label, arr, color, mn, mx], i) => {
    const y = i * rh;
    ctx.fillStyle = "#8d99a3";
    ctx.fillText(label, 8, y + 14);
    spark(ctx, arr, 90, y + 8, W - 100, rh - 16, color, mn, mx);
    if (i === 2 && hist.tn.length > 1) spark(ctx, hist.tn, 90, y + 8, W - 100, rh - 16, "#d16868", mn, mx);
  });
}
