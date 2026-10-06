// SwiftGet — tombol "Unduh" melayang di atas video
(() => {
  const api = globalThis.browser ?? globalThis.chrome;
  if (window.__swiftget) return;
  window.__swiftget = true;

  const host = document.createElement("div");
  host.style.cssText = "all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `<style>
    .btn{position:fixed;display:none;align-items:center;gap:7px;padding:8px 14px 8px 11px;border-radius:999px;border:0;cursor:pointer;
      background:linear-gradient(135deg,#3b82f6,#0ea5e9);color:#fff;font:600 12.5px/1 system-ui,-apple-system,Segoe UI,sans-serif;
      box-shadow:0 8px 22px rgba(0,0,0,.4);pointer-events:auto;transition:transform .12s,filter .12s}
    .btn.show{display:flex}.btn:hover{transform:translateY(-1px);filter:brightness(1.1)}
    svg{width:15px;height:15px}
  </style><button class="btn" id="b"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg><span id="t">Unduh</span></button>`;
  const btn = root.getElementById("b"), label = root.getElementById("t");
  document.documentElement.appendChild(host);

  let current = null, hideTimer = 0, flash = 0;
  const big = v => { const r = v.getBoundingClientRect(); return r.width >= 240 && r.height >= 135 && r.bottom > 0 && r.top < innerHeight; };

  function place(v) {
    const r = v.getBoundingClientRect();
    btn.style.left = Math.max(8, Math.min(innerWidth - 120, r.right - 112)) + "px";
    btn.style.top = Math.max(8, r.top + 12) + "px";
  }
  function hide() { btn.classList.remove("show"); current = null; }

  document.addEventListener("mousemove", (e) => {
    const vids = [...document.querySelectorAll("video")].filter(big);
    const v = vids.find(v => { const r = v.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom; });
    if (v) { current = v; place(v); btn.classList.add("show"); clearTimeout(hideTimer); hideTimer = setTimeout(hide, 2800); }
    else if (!btn.matches(":hover")) hide();
  }, { passive: true, capture: true });
  addEventListener("scroll", () => current && place(current), { passive: true, capture: true });

  btn.addEventListener("click", async (e) => {
    e.stopPropagation(); e.preventDefault();
    const v = current;
    const alt = v ? [v.currentSrc, ...[...v.querySelectorAll("source")].map(s => s.src)].filter(u => /^https?:/.test(u || "")) : [];
    label.textContent = "Mengirim…";
    try {
      const res = await api.runtime.sendMessage({ type: "media", url: location.href, alt, title: document.title });
      label.textContent = res?.ok ? "Terkirim ✓" : "Aplikasi tidak aktif";
    } catch { label.textContent = "Gagal"; }
    clearTimeout(flash); flash = setTimeout(() => (label.textContent = "Unduh"), 2200);
  }, true);
})();
