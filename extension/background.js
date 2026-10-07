// SwiftGet — background (Chrome/Edge/Brave/Opera/Vivaldi: service worker; Firefox: event page)
const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = { port: 6277, token: "", intercept: true, minSizeMB: 0, excluded: "" };
const SESSION = api.storage.session ?? api.storage.local;

async function cfg() { return { ...DEFAULTS, ...(await api.storage.local.get(DEFAULTS)) }; }

// ---- Pairing otomatis: aplikasi menampilkan dialog "Izinkan?", token dikirim balik tanpa salin-tempel ----------
let pairing = null, lastPair = 0;
async function pairOnce(force = false) {
  if (pairing) return pairing;
  if (!force && Date.now() - lastPair < 20000) return { ok: false, error: "tunggu" };
  lastPair = Date.now();
  pairing = (async () => {
    const c = await cfg();
    try {
      const r = await fetch(`http://127.0.0.1:${c.port}/pair`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "SwiftGet extension" }), signal: AbortSignal.timeout(100000),
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j.token) { await api.storage.local.set({ token: j.token }); return { ok: true }; }
      return { ok: false, error: j.error || `HTTP ${r.status}` };
    } catch (e) { return { ok: false, error: "Aplikasi SwiftGet tidak aktif" }; }
  })().finally(() => { pairing = null; });
  return pairing;
}

// autoPair=true untuk aksi yang sedang ditunggu pengguna (klik tombol/menu); unduhan otomatis tidak boleh menunggu.
async function call(path, body, timeout = 2500, autoPair = false) {
  let c = await cfg();
  if (!c.token && path !== "/ping") {
    if (!autoPair) { pairOnce(); return { ok: false, status: 401, error: "belum terhubung" }; }
    const p = await pairOnce(true);
    if (!p.ok) return { ok: false, status: 401, error: p.error };
    c = await cfg();
  }
  const ctl = new AbortController();
  const to = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(`http://127.0.0.1:${c.port}${path}`, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json", "X-SwiftGet-Token": c.token },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctl.signal,
    });
    const data = await r.json().catch(() => ({}));
    if (r.status === 401 && path !== "/ping") {                    // token kedaluwarsa → sambungkan ulang
      if (!autoPair) { pairOnce(); return { ok: false, status: 401 }; }
      const p = await pairOnce(true);
      return p.ok ? call(path, body, timeout) : { ok: false, status: 401, error: p.error };
    }
    return { ok: r.ok, status: r.status, data };
  } catch (e) {
    return { ok: false, status: 0, error: String(e) };
  } finally { clearTimeout(to); }
}

async function cookieHeader(url) {
  try { return (await api.cookies.getAll({ url })).map(c => `${c.name}=${c.value}`).join("; "); }
  catch { return ""; }
}
const basename = p => (p || "").split(/[\\/]/).pop();

// ---- Ambil alih unduhan browser -------------------------------------------------
api.downloads.onCreated.addListener(async (item) => {
  const c = await cfg();
  const url = item.finalUrl || item.url;
  if (!c.intercept || !c.token || !/^https?:/i.test(url)) return;
  const host = new URL(url).hostname;
  if (c.excluded.split(/[\s,]+/).filter(Boolean).some(d => host === d || host.endsWith("." + d))) return;
  if (c.minSizeMB > 0 && item.fileSize > 0 && item.fileSize < c.minSizeMB * 1048576) return;
  try { await api.downloads.pause(item.id); } catch {}
  const res = await call("/add", {
    url, referer: item.referrer || "", cookies: await cookieHeader(url), userAgent: navigator.userAgent,
    filename: basename(item.filename), size: item.fileSize, mime: item.mime, source: "intercept",
  });
  if (res.ok) {
    try { await api.downloads.cancel(item.id); await api.downloads.erase({ id: item.id }); } catch {}
  } else {
    try { await api.downloads.resume(item.id); } catch {}   // aplikasi mati → biarkan browser lanjut
  }
});

// ---- Deteksi media (HLS/DASH/MP4) di tab -----------------------------------------
const MEDIA_CT = /^(video\/|audio\/|application\/(vnd\.apple\.mpegurl|x-mpegurl|dash\+xml))/i;
let chain = Promise.resolve();

api.webRequest.onResponseStarted.addListener((d) => {
  if (d.tabId < 0) return;
  if (/\.(ts|m4s|aac|vtt)(\?|$)/i.test(d.url)) return;
  const h = n => (d.responseHeaders || []).find(x => x.name.toLowerCase() === n)?.value || "";
  const ct = h("content-type"), size = parseInt(h("content-length") || "0", 10);
  const playlist = /\.(m3u8|mpd)(\?|$)/i.test(d.url) || /mpegurl|dash\+xml/i.test(ct);
  if (!playlist && !(MEDIA_CT.test(ct) && size > 300000)) return;
  chain = chain.then(async () => {
    const k = "s" + d.tabId;
    const list = (await SESSION.get(k))[k] || [];
    if (list.some(x => x.url === d.url)) return;
    list.unshift({ url: d.url, ct, size, playlist, t: Date.now() });
    await SESSION.set({ [k]: list.slice(0, 15) });
    api.action.setBadgeText({ tabId: d.tabId, text: String(Math.min(list.length, 99)) });
    api.action.setBadgeBackgroundColor({ tabId: d.tabId, color: "#3B82F6" });
  }).catch(() => {});
}, { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other"] }, ["responseHeaders"]);

api.tabs.onUpdated.addListener((id, info) => {
  if (info.url) { SESSION.remove("s" + id); api.action.setBadgeText({ tabId: id, text: "" }); }
});
api.tabs.onRemoved.addListener(id => SESSION.remove("s" + id));

// ---- Menu klik kanan ----------------------------------------------------------------
api.runtime.onStartup?.addListener(() => { cfg().then(c => { if (!c.token) pairOnce(true); }); });
api.runtime.onInstalled.addListener(() => {
  pairOnce(true);                                                   // minta izin ke aplikasi begitu extension terpasang
  api.contextMenus.create({ id: "sg-link", title: "Unduh dengan SwiftGet", contexts: ["link"] });
  api.contextMenus.create({ id: "sg-media", title: "Unduh media dengan SwiftGet", contexts: ["video", "audio"] });
  api.contextMenus.create({ id: "sg-page", title: "Unduh video halaman ini dengan SwiftGet", contexts: ["page"] });
});

api.contextMenus.onClicked.addListener(async (info, tab) => {
  const page = info.pageUrl || tab?.url || "";
  const cookies = await cookieHeader(page);
  if (info.menuItemId === "sg-link")
    call("/add", { url: info.linkUrl, referer: page, cookies, userAgent: navigator.userAgent }, 2500, true);
  else if (info.menuItemId === "sg-media")
    call("/media", { url: page, alt: [info.srcUrl].filter(u => /^https?:/.test(u || "")), referer: page, cookies, title: tab?.title }, 2500, true);
  else call("/media", { url: page, referer: page, cookies, title: tab?.title }, 2500, true);
});

// ---- Pesan dari popup / options / content script ----------------------------------
api.runtime.onMessage.addListener((msg, sender, respond) => {
  (async () => {
    if (msg.type === "ping") respond(await call("/ping"));
    else if (msg.type === "media") {
      const page = msg.url;
      respond(await call("/media", { url: page, alt: msg.alt || [], referer: page, cookies: await cookieHeader(page), title: msg.title }, 2500, true));
    } else if (msg.type === "add") {
      respond(await call("/add", { url: msg.url, referer: msg.referer || "", cookies: await cookieHeader(msg.url), userAgent: navigator.userAgent }, 2500, true));
    } else if (msg.type === "pair") {
      respond(await pairOnce(true));
    } else if (msg.type === "state") {
      const k = "s" + msg.tabId;
      respond({ ping: await call("/ping"), list: (await SESSION.get(k))[k] || [] });
    } else respond({});
  })();
  return true;
});
