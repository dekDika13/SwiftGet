const api = globalThis.browser ?? globalThis.chrome;
const $ = id => document.getElementById(id);
const size = n => !n ? "" : n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.round(n / 1024) + " KB";

(async () => {
  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  const s = await api.runtime.sendMessage({ type: "state", tabId: tab.id });
  const ok = s.ping?.ok, authed = s.ping?.data?.auth;
  $("st").textContent = !ok ? "Aplikasi tidak aktif" : authed ? "Terhubung" : "Token salah";
  $("st").className = "pill " + (ok && authed ? "ok" : "bad");
  $("page").onclick = async () => {
    const r = await api.runtime.sendMessage({ type: "media", url: tab.url, title: tab.title });
    $("page").textContent = r?.ok ? "Terkirim ke SwiftGet ✓" : "Gagal — cek koneksi";
  };
  $("opt").onclick = e => { e.preventDefault(); api.runtime.openOptionsPage(); };
  const list = s.list || [];
  $("list").innerHTML = list.length ? "" : "<p class='muted'>Putar videonya dulu, lalu buka lagi popup ini.</p>";
  for (const m of list) {
    const row = document.createElement("div"); row.className = "row";
    const name = decodeURIComponent(new URL(m.url).pathname.split("/").pop() || m.url).slice(0, 38);
    row.innerHTML = `<div><b>${m.playlist ? "STREAM" : (m.ct.split("/")[1] || "media").toUpperCase()}</b> <span class="muted">${size(m.size)}</span><div class="muted u"></div></div><button>Unduh</button>`;
    row.querySelector(".u").textContent = name;
    row.querySelector("button").onclick = async (ev) => {
      const r = await api.runtime.sendMessage(m.playlist ? { type: "media", url: m.url, title: tab.title } : { type: "add", url: m.url, referer: tab.url });
      ev.target.textContent = r?.ok ? "✓" : "!";
    };
    $("list").appendChild(row);
  }
})();
