"""Fungsi bantu: format angka, nama file, dan klien HTTP."""
from __future__ import annotations
import mimetypes, os, re
from http.cookiejar import DefaultCookiePolicy
from urllib.parse import unquote, urlparse

import requests


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


class Net:
    """Pembungkus requests dengan header, cookie, dan proxy bawaan."""

    def __init__(self, cfg, referer="", cookies="", ua="", extra=None, keep_cookies=False):
        self.s = requests.Session()
        if not keep_cookies:
            self.s.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        if cfg["proxy"]:
            self.s.proxies = {"http": cfg["proxy"], "https": cfg["proxy"]}
        self.timeout = cfg["timeout"]
        self.h = {"User-Agent": ua or cfg["user_agent"], "Accept": "*/*",
                  "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}
        if referer:
            self.h["Referer"] = referer
        if cookies:
            self.h["Cookie"] = cookies
        if extra:
            self.h.update(extra)

    def get(self, url, **kw):
        kw.setdefault("timeout", (10, self.timeout))
        kw.setdefault("allow_redirects", True)
        headers = {**self.h, **kw.pop("headers", {})}
        return self.s.get(url, headers=headers, **kw)

    def drop_cookie_header(self):
        self.h.pop("Cookie", None)
