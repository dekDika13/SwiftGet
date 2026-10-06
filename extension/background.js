// SwiftGet — background (Chrome/Edge/Brave/Opera/Vivaldi: service worker; Firefox: event page)
const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = { port: 6277, token: "", intercept: true, minSizeMB: 0, excluded: "" };
const SESSION = api.storage.session ?? api.storage.local;

async function cfg() { return { ...DEFAULTS, ...(await api.storage.local.get(DEFAULTS)) }; }

async function call(path, body, timeout = 2500) {
  const c = await cfg();
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
api.runtime.onInstalled.addListener(() => {
  api.contextMenus.create({ id: "sg-link", title: "Unduh dengan SwiftGet", contexts: ["link"] });
  api.contextMenus.create({ id: "sg-media", title: "Unduh media dengan SwiftGet", contexts: ["video", "audio"] });
  api.contextMenus.create({ id: "sg-page", title: "Unduh video halaman ini dengan SwiftGet", contexts: ["page"] });
});

api.contextMenus.onClicked.addListener(async (info, tab) => {
  const page = info.pageUrl || tab?.url || "";
  const cookies = await cookieHeader(page);
  if (info.menuItemId === "sg-link")
    call("/add", { url: info.linkUrl, referer: page, cookies, userAgent: navigator.userAgent });
  else if (info.menuItemId === "sg-media")
    call("/media", { url: page, alt: [info.srcUrl].filter(u => /^https?:/.test(u || "")), referer: page, cookies, title: tab?.title });
  else call("/media", { url: page, referer: page, cookies, title: tab?.title });
});

// ---- Pesan dari popup / options / content script ----------------------------------
api.runtime.onMessage.addListener((msg, sender, respond) => {
  (async () => {
    if (msg.type === "ping") respond(await call("/ping"));
    else if (msg.type === "media") {
      const page = msg.url;
      respond(await call("/media", { url: page, alt: msg.alt || [], referer: page, cookies: await cookieHeader(page), title: msg.title }));
    } else if (msg.type === "add") {
      respond(await call("/add", { url: msg.url, referer: msg.referer || "", cookies: await cookieHeader(msg.url), userAgent: navigator.userAgent }));
    } else if (msg.type === "state") {
      const k = "s" + msg.tabId;
      respond({ ping: await call("/ping"), list: (await SESSION.get(k))[k] || [] });
    } else respond({});
  })();
  return true;
});
