"""Fungsi bantu: format angka, nama file, dan klien HTTP."""
from __future__ import annotations
import mimetypes, os, re
from http.cookiejar import DefaultCookiePolicy
from urllib.parse import unquote, urlparse

import requests


def route_candidates(cfg, url) -> list:
    """Daftar jalur (proxy) untuk URL ini, atau [] bila fitur jalur alternatif nonaktif / situsnya tidak termasuk."""
    if not cfg["route_enabled"]:
        return []
    host = (urlparse(url).hostname or "").lower()
    sites = [s.strip().lower() for s in re.split(r"[\s,]+", cfg["route_sites"]) if s.strip()]
    if not any(host == s or host.endswith("." + s) for s in sites):
        return []
    return [ln.strip() for ln in cfg["route_proxies"].splitlines() if ln.strip() and not ln.strip().startswith("#")]


def route_proxy(cfg, url, idx=0):
    """Proxy untuk jalur ke-idx: None = fitur tidak berlaku, '' = langsung (direct), selain itu alamat proxy."""
    c = route_candidates(cfg, url)
    if not c:
        return None
    p = c[idx % len(c)]
    return "" if p.lower() == "direct" else p


def mask_proxy(p) -> str:
    """Tampilkan jalur tanpa user:password."""
    if not p:
        return "langsung (tanpa proxy)"
    u = urlparse(p)
    return f"{u.scheme}://{u.hostname}:{u.port}" if u.hostname and u.port else (f"{u.scheme}://{u.hostname}" if u.hostname else "proxy")


YT_RX = re.compile(r"(youtube\.com|youtu\.be|youtube-nocookie\.com)", re.I)


def is_youtube(url: str) -> bool:
    return bool(YT_RX.search(url or ""))


def fmt_size(n) -> str:
    if n is None or n < 0:
        return "—"
    f, i = float(n), 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while f >= 1024 and i < 4:
        f /= 1024
        i += 1
    return f"{int(f)} B" if i == 0 else f"{f:.1f} {units[i]}" if i < 3 else f"{f:.2f} {units[i]}"


def fmt_speed(bps) -> str:
    return "—" if not bps or bps < 1 else fmt_size(bps) + "/s"


def fmt_eta(s) -> str:
    if s is None or s < 0 or s > 86400 * 30:
        return "—"
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}j {m:02d}m" if h else f"{m}m {s:02d}d" if m else f"{s}d"


def fmt_duration(s) -> str:
    if not s:
        return ""
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name or "").strip(" .")
    if len(name) > 200:
        base, ext = os.path.splitext(name)
        name = base[: 200 - len(ext)] + ext
    return name or "download"


def filename_from_headers(h) -> str:
    cd = h.get("Content-Disposition") or ""
    if not cd:
        return ""
    m = re.search(r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)", cd, re.I)
    if m:
        try:
            return sanitize(unquote(m.group(2).strip('" '), encoding=m.group(1) or "utf-8"))
        except LookupError:
            pass
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.I) or re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    if not m:
        return ""
    name = m.group(1).strip()
    try:  # header dibaca latin-1 oleh requests; coba pulihkan UTF-8
        name = name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return sanitize(unquote(name))


def filename_from_url(url: str) -> str:
    base = os.path.basename(urlparse(url).path)
    return sanitize(unquote(base)) if base else ""


def ensure_ext(name: str, mime: str) -> str:
    if "." in name or not mime or mime in ("application/octet-stream", "text/html"):
        return name
    return name + (mimetypes.guess_extension(mime) or "")


def unique_name(directory: str, name: str, reserved=()) -> str:
    base, ext = os.path.splitext(name)
    cand, i = name, 0
    while (os.path.exists(os.path.join(directory, cand)) or os.path.exists(os.path.join(directory, cand + ".part"))
           or (directory, cand) in reserved):
        i += 1
        cand = f"{base} ({i}){ext}"
    return cand


UNSAFE_HEADERS = {"host", "content-length", "range", "cookie", "connection", "transfer-encoding", "if-none-match",
                  "if-modified-since", "if-range", "accept-encoding"}


class Net:
    """Pembungkus requests dengan header, cookie, dan proxy bawaan."""

    def __init__(self, cfg, referer="", cookies="", ua="", extra=None, keep_cookies=False, proxy=None):
        """proxy=None → pakai proxy global; proxy='' → tanpa proxy (jalur 'direct'); proxy='socks5://…' → proxy itu."""
        self.s = requests.Session()
        if not keep_cookies:
            self.s.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        px = cfg["proxy"] if proxy is None else proxy
        if px:
            self.s.proxies = {"http": px, "https": px}
        self.timeout = cfg["timeout"]
        self.h = {"User-Agent": ua or cfg["user_agent"], "Accept": "*/*",
                  "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}
        if referer:
            self.h["Referer"] = referer
        if cookies:
            self.h["Cookie"] = cookies
        for k, v in (extra or {}).items():            # header tambahan (resolver / tiruan header browser)
            if isinstance(k, str) and isinstance(v, str) and k.lower() not in UNSAFE_HEADERS and len(v) < 4096:
                self.h[k] = v

    def get(self, url, **kw):
        kw.setdefault("timeout", (10, self.timeout))
        kw.setdefault("allow_redirects", True)
        headers = {**self.h, **kw.pop("headers", {})}
        return self.s.get(url, headers=headers, **kw)

    def drop_cookie_header(self):
        self.h.pop("Cookie", None)
