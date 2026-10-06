"""Analisis URL: file langsung, media (yt-dlp), atau halaman berisi banyak tautan."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from .config import ALL_EXTS, categorize
from .engine import clean_error, drop_cookie_file, ffmpeg_path, probe, ytdlp_base
from .resolvers import ResolveError, resolve
from .util import Net, filename_from_url, ensure_ext, sanitize

MEDIA_HOSTS = re.compile(r"(youtube\.com|youtu\.be|vimeo\.com|tiktok\.com|twitter\.com|//x\.com|instagram\.com|facebook\.com|"
                         r"fb\.watch|dailymotion\.com|twitch\.tv|soundcloud\.com|bilibili\.com|reddit\.com|streamable\.com)", re.I)


@dataclass
class Analysis:
    kind: str = "none"        # file | media | links | none | error
    url: str = ""
    message: str = ""
    filename: str = ""
    total: int = 0
    resumable: bool = False
    mime: str = ""
    resolver: str = ""
    referer: str = ""
    cookies: str = ""
    media: dict | None = None
    links: list = field(default_factory=list)


def analyze(cfg, url, referer="", cookies="", ua="", alt=()) -> Analysis:
    last = None
    for u in [url, *alt]:
        a = _analyze(cfg, u, referer, cookies, ua)
        if a.kind in ("file", "media", "links"):
            return a
        last = a if last is None or a.kind == "error" else last
    return last


def _analyze(cfg, url, referer, cookies, ua) -> Analysis:
    url = url.strip()
    if not re.match(r"https?://", url, re.I):
        return Analysis(kind="error", url=url, message="URL harus diawali http:// atau https://")
    path = urlparse(url).path.lower()
    if MEDIA_HOSTS.search(url) or path.endswith((".m3u8", ".mpd")):
        info, err = fetch_media_info(cfg, url, referer, cookies)
        if info:
            return Analysis(kind="media", url=url, media=info, referer=referer, cookies=cookies)
        if MEDIA_HOSTS.search(url):
            return Analysis(kind="error", url=url, message=err or "Media tidak dapat dianalisis.")
    net = Net(cfg, referer, cookies, ua, keep_cookies=True)
    try:
        rv = resolve(net, url)
    except ResolveError as e:
        return Analysis(kind="error", url=url, message=str(e))
    except Exception as e:
        return Analysis(kind="error", url=url, message=f"Gagal menghubungi server: {clean_error(e)}")
    net2 = Net(cfg, rv.referer or referer, rv.cookies or cookies, ua, rv.headers)
    try:
        p = probe(net2, rv.url)
    except Exception as e:
        return Analysis(kind="error", url=url, message=clean_error(e))
    if p["mime"] in ("text/html", "application/xhtml+xml") and not p["filename"]:
        if rv.resolver != "direct":
            return Analysis(kind="error", url=url, message=f"Resolver {rv.resolver} tidak menemukan file.")
        info, err = fetch_media_info(cfg, url, referer, cookies)
        if info:
            return Analysis(kind="media", url=url, media=info, referer=referer, cookies=cookies)
        links = scan_links(net2, rv.url)
        if links:
            return Analysis(kind="links", url=url, links=links, message="Halaman ini berisi beberapa file yang bisa diunduh.")
        return Analysis(kind="none", url=url, message="Tidak ada file atau media yang bisa diunduh dari halaman ini. "
                        "Coba buka halaman di browser dan gunakan extension SwiftGet.")
    name = sanitize(p["filename"] or rv.filename or filename_from_url(p["url"]) or filename_from_url(url))
    return Analysis(kind="file", url=url, filename=ensure_ext(name, p["mime"]), total=p["total"], resumable=p["resumable"],
                    mime=p["mime"], resolver=rv.resolver, referer=rv.referer or referer, cookies=rv.cookies or cookies)


def fetch_media_info(cfg, url, referer="", cookies=""):
    """Kembalikan (info, error). info = ringkasan format yt-dlp."""
    try:
        import yt_dlp
    except ImportError:
        return None, "yt-dlp belum terpasang (pip install yt-dlp)."
    o = ytdlp_base(cfg, referer, cookies, url)
    o.update({"skip_download": True, "noplaylist": True, "extract_flat": "in_playlist"})
    try:
        with yt_dlp.YoutubeDL(o) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:
        return None, clean_error(e)
    finally:
        drop_cookie_file(o)
    if not info:
        return None, "Tidak ada media ditemukan."
    return summarize(info), ""


def summarize(info) -> dict:
    thumb = info.get("thumbnail") or ((info.get("thumbnails") or [{}])[-1].get("url"))
    base = {"title": info.get("title") or "Tanpa judul", "uploader": info.get("uploader") or info.get("channel") or "",
            "thumbnail": thumb, "extractor": info.get("extractor_key") or "", "duration": info.get("duration") or 0}
    if info.get("_type") == "playlist":
        entries = [e for e in info.get("entries") or [] if e]
        return {**base, "is_playlist": True, "count": info.get("playlist_count") or len(entries),
                "qualities": [{"height": h, "size": 0, "h264": h <= 1080} for h in (2160, 1440, 1080, 720, 480, 360)], "audio_only": False}
    fm = info.get("formats") or []
    size = lambda f: f.get("filesize") or f.get("filesize_approx") or 0
    vids = [f for f in fm if f.get("vcodec") not in (None, "none") and f.get("height")]
    auds = [f for f in fm if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]
    a_size = max((size(a) for a in auds), default=0)
    by_h, avc = {}, set()
    for f in vids:
        by_h[f["height"]] = max(by_h.get(f["height"], 0), size(f))
        if str(f.get("vcodec", "")).startswith(("avc", "h264")):
            avc.add(f["height"])
    quals = [{"height": h, "size": (s + a_size) if s else 0, "h264": h in avc} for h, s in sorted(by_h.items(), reverse=True)]
    return {**base, "is_playlist": False, "count": 1, "qualities": quals, "audio_only": not vids}


LINK_RX = re.compile(r"""(?:href|src|data-src|content|data-url)\s*=\s*["']([^"'#<>\s]+)["']""", re.I)
RAW_RX = re.compile(r"""https?://[^\s"'<>\\]+?\.(?:m3u8|mpd|mp4|webm|mkv|mp3|zip|rar|7z|exe|dmg|pkg|apk|iso|pdf)(?:\?[^\s"'<>\\]*)?""", re.I)


def scan_links(net: Net, url, limit=200):
    try:
        r = net.get(url, stream=True)
        raw = r.raw.read(3 * 1024 * 1024, decode_content=True)
        r.close()
        text = raw.decode(r.encoding or "utf-8", errors="ignore")
    except Exception:
        return []
    cands = [urljoin(url, m) for m in LINK_RX.findall(text)] + RAW_RX.findall(text.replace("\\/", "/"))
    seen, out = set(), []
    for u in cands:
        if not u.startswith("http") or u in seen:
            continue
        ext = urlparse(u).path.rsplit(".", 1)[-1].lower() if "." in urlparse(u).path else ""
        if ext in ALL_EXTS or ext in ("mpd",):
            seen.add(u)
            name = filename_from_url(u) or u
            out.append({"url": u, "name": name, "ext": ext, "category": categorize(name)})
        if len(out) >= limit:
            break
    return out
