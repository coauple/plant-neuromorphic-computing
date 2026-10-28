// WS taşıma — latest-wins + geri bağlanma (DOM yok).
export function connectWorld(url, onFrame, onStatus) {
  let ws = null, backoff = 500, closed = false, latest = null, raf = 0;
  function pump() {
    if (latest) {
      const f = latest; latest = null;
      try { onFrame(f, performance.now()); } catch (e) { console.error(e); }
    }
    if (!closed) raf = requestAnimationFrame(pump);
  }
  function open() {
    ws = new WebSocket(url);
    ws.onopen = () => { backoff = 500; if (onStatus) onStatus(true); };
    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d && d.v === 2) latest = d; // yalnız v2 frame yuvaya girer (§9.27)
      } catch (e) { /* bozuk satır atılır */ }
    };
    ws.onclose = () => {
      if (onStatus) onStatus(false);
      if (!closed) setTimeout(open, (backoff = Math.min(backoff * 2, 8000)));
    };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }
  open();
  raf = requestAnimationFrame(pump);
  return {
    send(o) { try { ws.send(JSON.stringify(o)); } catch (e) {} },
    close() { closed = true; cancelAnimationFrame(raf); try { ws.close(); } catch (e) {} },
  };
}

export function connectNpu(url, onTele, onStatus) {
  let ws = null, backoff = 800, closed = false;
  function open() {
    ws = new WebSocket(url);
    ws.onopen = () => { backoff = 800; if (onStatus) onStatus(true, ""); };
    ws.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        if (d && d.status === "offline") { if (onStatus) onStatus(true, "offline"); return; }
        if (d && typeof d.t === "number") { try { onTele(d); } catch (e) { console.error(e); } }
      } catch (e) { /* atılır */ }
    };
    ws.onclose = () => {
      if (onStatus) onStatus(false, "");
      if (!closed) setTimeout(open, (backoff = Math.min(backoff * 2, 8000)));
    };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }
  open();
  return {
    send(o) { try { ws.send(JSON.stringify(o)); } catch (e) {} },
    close() { closed = true; try { ws.close(); } catch (e) {} },
  };
}
