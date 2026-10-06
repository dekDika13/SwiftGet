"""Resolver: mengubah link halaman hosting menjadi link file langsung.
Tambah situs baru cukup dengan satu fungsi berdekorator @resolver(...)."""
from __future__ import annotations
import base64, re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, urljoin
import html as htmllib


class ResolveError(Exception):
    pass


@dataclass
class Resolved:
    url: str
    filename: str = ""
    referer: str = ""
    cookies: str = ""
    headers: dict = field(default_factory=dict)
    resolver: str = "direct"


REGISTRY = []


def resolver(name, pattern):
    def deco(fn):
        REGISTRY.append((name, re.compile(pattern, re.I), fn))
        return fn
    return deco


def match(url):
    for name, rx, _ in REGISTRY:
        if rx.search(url):
            return name
    return None


def resolve(net, url) -> Resolved:
    for name, rx, fn in REGISTRY:
        if rx.search(url):
            r = fn(net, url)
            r.resolver = name
            return r
    return Resolved(url=url)


def _cookies(net):
    return "; ".join(f"{c.name}={c.value}" for c in net.s.cookies)


def _is_html(r):
    return "text/html" in r.headers.get("Content-Type", "").lower()


# ---------------------------------------------------------------- Google Drive
@resolver("Google Drive", r"(drive|docs)\.google\.com")
def gdrive(net, url):
    if "/folders/" in url:
        raise ResolveError("Folder Google Drive belum didukung. Buka dan unduh file di dalamnya satu per satu.")
    m = re.search(r"docs\.google\.com/(document|spreadsheets|presentation)/d/([\w-]+)", url)
    if m:
        kind, fid = m.groups()
        fmt = {"document": "pdf", "spreadsheets": "xlsx", "presentation": "pptx"}[kind]
        return Resolved(f"https://docs.google.com/{kind}/d/{fid}/export?format={fmt}")
    m = re.search(r"/file/d/([\w-]{10,})", url) or re.search(r"[?&]id=([\w-]{10,})", url) or re.search(r"/d/([\w-]{10,})", url)
    if not m:
        raise ResolveError("ID file Google Drive tidak ditemukan di URL.")
    fid = m.group(1)
    first = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    r = net.get(first, stream=True)
    try:
        if not _is_html(r):
            return Resolved(first, cookies=_cookies(net))
        text = r.text
    finally:
        r.close()
    if "accounts.google.com" in r.url or "ServiceLogin" in text:
        raise ResolveError("File ini privat. Buka di browser (sudah login) dan biarkan extension SwiftGet menangkapnya.")
    if re.search(r"quota exceeded|too many users|terlalu banyak", text, re.I):
        raise ResolveError("Kuota unduhan Google Drive untuk file ini habis (batas dari Google). Coba lagi nanti atau salin file ke Drive kamu.")
    form = re.search(r'<form[^>]+action="([^"]+)"', text)
    if form:
        params = dict(re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', text))
        return Resolved(htmllib.unescape(form.group(1)) + "?" + urlencode(params), cookies=_cookies(net))
    raise ResolveError("Google Drive tidak mengizinkan unduhan file ini (tidak publik atau diblokir).")


# ------------------------------------------------------------------- MediaFire
@resolver("MediaFire", r"mediafire\.com/(file|view|download|\?)")
def mediafire(net, url):
    r = net.get(url, stream=True)
    try:
        if not _is_html(r):
            return Resolved(url)
        text = r.text
    finally:
        r.close()
    m = re.search(r'data-scrambled-url="([^"]+)"', text)
    if m:
        return Resolved(base64.b64decode(m.group(1)).decode(), referer=url)
    m = re.search(r'https?://download\d*\.mediafire\.com/[^"\'\s<>]+', text)
    if m:
        return Resolved(htmllib.unescape(m.group(0)), referer=url)
    raise ResolveError("Link unduhan MediaFire tidak ditemukan (file dihapus atau halaman berubah).")


# ------------------------------------------------------------ Dropbox / OneDrive
@resolver("Dropbox", r"(^|//)(www\.)?dropbox\.com/")
def dropbox(net, url):
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k != "dl"] + [("dl", "1")]
    return Resolved(urlunparse(p._replace(query=urlencode(q))))


@resolver("OneDrive", r"(1drv\.ms|onedrive\.live\.com|sharepoint\.com)")
def onedrive(net, url):
    if "1drv.ms" in url:
        r = net.get(url, stream=True)
        r.close()
        url = r.url
    if "onedrive.live.com" in url:
        url = re.sub(r"/(redir|embed|view\.aspx)", "/download", url, count=1)
    elif "sharepoint.com" in url and "download=1" not in url:
        url += ("&" if "?" in url else "?") + "download=1"
    return Resolved(url)


# --------------------------------------------------------------------- lainnya
@resolver("GitHub", r"github\.com/[^/]+/[^/]+/blob/")
def github_blob(net, url):
    m = re.search(r"github\.com/([^/]+)/([^/]+)/blob/(.+)", url)
    return Resolved(f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3).split('?')[0]}")


@resolver("Pixeldrain", r"pixeldrain\.(com|net)/u/")
def pixeldrain(net, url):
    fid = re.search(r"/u/(\w+)", url).group(1)
    return Resolved(f"https://pixeldrain.com/api/file/{fid}?download")


@resolver("SourceForge", r"sourceforge\.net/projects/.+/download")
def sourceforge(net, url):
    return Resolved(url, headers={"User-Agent": "curl/8.4.0"})


@resolver("Mega", r"mega\.(nz|io)/")
def mega(net, url):
    raise ResolveError("Mega mengenkripsi file di sisi klien sehingga belum didukung. Gunakan MEGAcmd atau megatools.")
