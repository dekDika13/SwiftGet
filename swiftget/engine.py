"""Mesin unduhan: multi-koneksi berbasis chunk (file) dan yt-dlp (media)."""
from __future__ import annotations
import errno, hashlib, os, re, shutil, sys, threading, time
from collections import deque
from urllib.parse import urlparse

import requests

from .config import categorize, data_dir
from .models import Task
from .resolvers import resolve
from .util import Net, ensure_ext, filename_from_headers, filename_from_url, mask_proxy, route_candidates, sanitize

MB = 1024 * 1024


class DownloadError(Exception):
    pass


def clean_error(e) -> str:
    s = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).strip()
    s = re.sub(r"^(ERROR:\s*)+", "", s)
    return s or e.__class__.__name__


class RateLimiter:
    """Pembatas kecepatan global (token bucket)."""

    def __init__(self):
        self.rate = 0
        self._lock = threading.Lock()
        self._allow = 0.0
        self._t = time.monotonic()

    def set_rate(self, bps):
        self.rate = max(0, int(bps))

    def consume(self, n, stop: threading.Event):
        if self.rate <= 0:
            return
        with self._lock:
            now = time.monotonic()
            self._allow = min(self._allow + (now - self._t) * self.rate, self.rate)
            self._t = now
            self._allow -= n
            deficit = -self._allow
        if deficit > 0:
            stop.wait(deficit / self.rate)


class HttpStatusError(DownloadError):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


RETRY_CODES = (400, 401, 403, 405, 406, 412)


def _probe_once(net: Net, url: str, use_range: bool) -> dict:
    r = net.get(url, headers={"Range": "bytes=0-0"} if use_range else {}, stream=True)
    try:
        code, h = r.status_code, r.headers
        if code >= 400 and not (use_range and code == 416):
            hint = " (butuh login/izin)" if code in (401, 403) else ""
            raise HttpStatusError(code, f"Server menjawab HTTP {code}{hint}")
        total, resumable = 0, False
        if use_range and code in (206, 416):
            m = re.search(r"/(\d+)\s*$", h.get("Content-Range", "")) or re.search(r"\*/(\d+)", h.get("Content-Range", ""))
            total = int(m.group(1)) if m else 0
            resumable = bool(total)
        else:
            total = int(h.get("Content-Length") or 0)
        return {"url": r.url, "total": total, "resumable": resumable,
                "mime": h.get("Content-Type", "").split(";")[0].strip().lower(),
                "etag": h.get("ETag") or h.get("Last-Modified") or "",
                "filename": filename_from_headers(h), "status": code}
    finally:
        r.close()


def probe(net: Net, url: str) -> dict:
    """Ambil metadata file (ukuran, resume, nama, tipe). Bila ditolak (403 dll.) coba cara lain, seperti browser:
    tanpa header Range, dengan Referer = situs asal, dengan header ala browser. Header yang berhasil dipakai seterusnya (net.h)."""
    origin = "{0.scheme}://{0.netloc}/".format(urlparse(url))
    like = {"Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8", "Referer": origin,
            "Sec-Fetch-Dest": "image", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "same-origin"}
    plans = [({}, True), ({}, False), ({"Referer": origin}, True), ({"Referer": origin}, False), (like, True), (like, False)]
    base, seen, first = dict(net.h), set(), None
    for upd, rng in plans:
        merged = {**base, **upd}
        key = (tuple(sorted(merged.items())), rng)
        if key in seen:
            continue
        seen.add(key)
        net.h.clear()
        net.h.update(merged)
        try:
            return _probe_once(net, url, rng)
        except HttpStatusError as e:
            first = first or e
            if e.code not in RETRY_CODES:
                raise
    net.h.clear()
    net.h.update(base)
    raise HttpStatusError(first.code, f"{first} — sudah dicoba dengan beberapa jenis header. "
                                      "Coba buka tautan di browser (klik kanan › Buka tautan di browser).")


class Job:
    def __init__(self, task: Task, cfg, limiter: RateLimiter, manager):
        self.t, self.cfg, self.limiter, self.mgr = task, cfg, limiter, manager
        self.stop = threading.Event()
        self.reason = ""

    def request_stop(self, reason):
        self.reason = reason
        self.stop.set()


def route_error(msg) -> "DownloadError":
    e = DownloadError(msg)
    e.route = True            # kegagalan koneksi: layak dicoba lewat jalur lain
    return e


class FileJob(Job):
    def run(self):
        t, cfg = self.t, self.cfg
        t.status, t.error, t.speed, t.eta, t.note = "preparing", "", 0, -1, "Menganalisis tautan…"
        # --- jalur alternatif (opsional): proxy khusus untuk situs tertentu; resolve + unduh harus lewat IP yang sama
        cands, proxy, self.route_note, self._slow_since = route_candidates(cfg, t.url), None, "", None
        self.rotatable = False
        if cands:
            i = t.route_idx % len(cands)
            proxy = "" if cands[i].lower() == "direct" else cands[i]
            self.route_note = f"Jalur {i + 1}/{len(cands)}: {mask_proxy(proxy)}"
            t.note = self.route_note
            limit = int(cfg["speed_limit_kbps"])
            self.rotatable = (len(cands) > 1 and bool(cfg["route_auto"]) and t.route_idx < len(cands) * 2 - 1
                              and not (limit and limit <= int(cfg["route_slow_kbps"]) * 2))   # batas buatan sendiri ≠ dibatasi situs
        net0 = Net(cfg, t.referer, t.cookies, t.user_agent, t.headers, keep_cookies=True, proxy=proxy)
        rv = resolve(net0, t.url)
        t.resolver = rv.resolver
        if self.stop.is_set():
            return
        self.net = Net(cfg, rv.referer or t.referer, rv.cookies or t.cookies, t.user_agent, {**t.headers, **rv.headers},
                       proxy=proxy)
        p = probe(self.net, rv.url)
        if self.stop.is_set():
            return
        self.url = p["url"]
        if urlparse(self.url).netloc != urlparse(rv.url).netloc:
            self.net.drop_cookie_header()
        if p["mime"] == "text/html" and not p["filename"] and not re.search(r"\.html?$", urlparse(t.url).path, re.I):
            raise DownloadError("URL ini mengarah ke halaman web, bukan file. Gunakan 'Analisis' atau extension browser.")

        resume_ok = (bool(t.chunks) and t.resumable and p["resumable"] and t.filename
                     and os.path.exists(self._part()) and t.total == p["total"]
                     and (not t.etag or not p["etag"] or t.etag == p["etag"]))
        if t.chunks and not resume_ok:
            self._discard_part()
            t.chunks, t.downloaded = [], 0
        if not t.filename:
            name = sanitize(p["filename"] or rv.filename or filename_from_url(self.url) or filename_from_url(t.url))
            self.mgr.assign_name(t, ensure_ext(name, p["mime"]))
        os.makedirs(t.save_dir, exist_ok=True)
        if not resume_ok:
            t.total, t.resumable, t.etag = p["total"], p["resumable"], p["etag"]
            if t.total > 0 and shutil.disk_usage(t.save_dir).free < t.total + 16 * MB:
                raise DownloadError("Ruang disk tidak cukup.")
            if t.resumable and t.total > 0:
                n = 1 if t.total < MB else max(1, min(int(t.connections), 32))
                size = min(max(MB, -(-t.total // (n * 4))), 64 * MB)
                t.chunks = [[s, min(s + size, t.total) - 1, 0] for s in range(0, t.total, size)]
            else:
                t.chunks = [[0, -1, 0]]
            with open(self._part(), "wb") as f:
                if t.resumable and t.total > 0:
                    f.truncate(t.total)

        t.status, t.note = "downloading", self.route_note
        self._t0 = time.monotonic()
        self.lock, self.claimed, self.err = threading.Lock(), set(), None
        pending = sum(1 for c in t.chunks if c[1] < 0 or c[2] < c[1] - c[0] + 1)
        n = 1 if not t.resumable else max(1, min(int(t.connections), pending))
        threads = [threading.Thread(target=self._worker, daemon=True) for _ in range(n)]
        for th in threads:
            th.start()
        hist = deque(maxlen=8)
        while any(th.is_alive() for th in threads):
            time.sleep(0.4)
            self._tick(hist)
            self._maybe_rotate()
        self._tick(hist)
        t.speed, t.eta = 0, -1
        if self.err:
            raise self.err
        if self.stop.is_set():
            return
        if t.resumable and any(c[2] < c[1] - c[0] + 1 for c in t.chunks):
            raise DownloadError("Unduhan tidak lengkap.")
        os.replace(self._part(), os.path.join(t.save_dir, t.filename))
        t.final_path = os.path.join(t.save_dir, t.filename)
        t.downloaded = t.total = os.path.getsize(t.final_path)
        if t.checksum and not self._verify():
            t.status, t.error = "error", "Checksum tidak cocok — file mungkin rusak atau dimodifikasi."
            return
        t.status, t.finished, t.note = "completed", time.time(), ""

    # -- util
    def _part(self):
        return os.path.join(self.t.save_dir, self.t.filename + ".part")

    def _discard_part(self):
        try:
            os.remove(self._part())
        except OSError:
            pass

    def _tick(self, hist):
        t, now = self.t, time.monotonic()
        done = sum(c[2] for c in t.chunks)
        hist.append((now, done))
        t0, d0 = hist[0]
        t.speed = (done - d0) / (now - t0) if now > t0 else 0
        t.downloaded = done
        t.eta = (t.total - done) / t.speed if t.speed > 1 and t.total > 0 else -1

    def _maybe_rotate(self):
        """Terlalu lambat cukup lama → hentikan; manager menjalankan lagi lewat jalur berikutnya (lanjut dari byte terakhir)."""
        if not self.rotatable or self.stop.is_set():
            return
        t, cfg = self.t, self.cfg
        now = time.monotonic()
        secs = int(cfg["route_slow_secs"])
        remaining = t.total - t.downloaded if t.total > 0 else 10 ** 9
        if now - self._t0 < max(3, secs // 2) or remaining < MB or t.speed >= int(cfg["route_slow_kbps"]) * 1024:
            self._slow_since = None
            return
        self._slow_since = self._slow_since or now
        if now - self._slow_since >= secs:
            t.note = "Terlalu lambat, pindah jalur…"
            self.request_stop("rotate")

    def _verify(self):
        t = self.t
        t.status, t.note = "verifying", "Memeriksa checksum…"
        algo, _, hx = t.checksum.partition(":")
        if not hx:
            hx, algo = algo, {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}.get(len(algo), "sha256")
        h = hashlib.new(algo.lower())
        with open(t.final_path, "rb") as f:
            for blk in iter(lambda: f.read(MB), b""):
                h.update(blk)
        return h.hexdigest().lower() == hx.strip().lower()

    def _claim(self):
        with self.lock:
            for i, c in enumerate(self.t.chunks):
                if i not in self.claimed and (c[1] < 0 or c[2] < c[1] - c[0] + 1):
                    self.claimed.add(i)
                    return i
        return None

    def _worker(self):
        try:
            with open(self._part(), "r+b") as f:
                while not self.stop.is_set():
                    i = self._claim()
                    if i is None:
                        return
                    (self._range if self.t.resumable else self._stream)(i, f)
        except Exception as e:
            with self.lock:
                self.err = self.err or (e if isinstance(e, DownloadError) else DownloadError(clean_error(e)))
            self.stop.set()

    def _range(self, i, f):
        c, attempts = self.t.chunks[i], 0
        while not self.stop.is_set():
            pos = c[0] + c[2]
            if pos > c[1]:
                return
            try:
                with self.net.get(self.url, headers={"Range": f"bytes={pos}-{c[1]}"}, stream=True) as r:
                    if r.status_code != 206:
                        raise DownloadError(f"Server menolak permintaan rentang (HTTP {r.status_code}).")
                    for data in r.iter_content(65536):
                        if self.stop.is_set():
                            return
                        room = c[1] - (c[0] + c[2]) + 1
                        data = data[:room]
                        self.limiter.consume(len(data), self.stop)
                        f.seek(c[0] + c[2])
                        f.write(data)
                        c[2] += len(data)
                        if c[0] + c[2] > c[1]:
                            return
                attempts = attempts + 1 if c[0] + c[2] == pos else 0
            except DownloadError:
                raise
            except requests.RequestException as e:
                attempts += 1
                if attempts > self.cfg["retries"]:
                    raise route_error(f"Koneksi gagal: {clean_error(e)}")
            except OSError as e:
                raise DownloadError("Disk penuh." if e.errno == errno.ENOSPC else f"Gagal menulis file: {e}")
            if attempts:
                self.stop.wait(min(2 ** attempts, 20))
            if attempts > self.cfg["retries"]:
                raise DownloadError("Server menutup koneksi berulang kali.")

    def _stream(self, i, f):
        c, attempts = self.t.chunks[i], 0
        while not self.stop.is_set():
            try:
                f.seek(0)
                f.truncate()
                c[2] = 0
                with self.net.get(self.url, stream=True) as r:
                    if r.status_code >= 400:
                        raise DownloadError(f"Server menjawab HTTP {r.status_code}")
                    for data in r.iter_content(65536):
                        if self.stop.is_set():
                            return
                        self.limiter.consume(len(data), self.stop)
                        f.write(data)
                        c[2] += len(data)
                c[1] = c[2] - 1
                self.t.total = c[2]
                return
            except requests.RequestException as e:
                attempts += 1
                if attempts > self.cfg["retries"]:
                    raise DownloadError(f"Koneksi gagal: {clean_error(e)}")
                self.stop.wait(min(2 ** attempts, 20))


def ffmpeg_path(cfg):
    """Cari FFmpeg: pengaturan → PATH → lokasi umum → paket pip imageio-ffmpeg (tanpa Homebrew)."""
    p = cfg["ffmpeg_path"]
    if p and os.path.exists(p):
        return p
    w = shutil.which("ffmpeg")
    if w:
        return w
    for cand in ("/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg", "/opt/local/bin/ffmpeg"):
        if os.path.exists(cand):
            return cand
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        return exe if exe and os.path.exists(exe) else None
    except Exception:
        return None


def build_format(mo: dict, has_ffmpeg: bool) -> str:
    """Pemilih format yt-dlp. Mode 'compat' = H.264 + AAC di MP4 (bisa diputar di Mac, iPhone, Windows)."""
    if mo.get("mode") == "audio":
        return "bestaudio/best"
    h = int(mo.get("height") or 0)
    hf = f"[height<={h}]" if h else ""
    if not has_ffmpeg:
        return f"b[ext=mp4]{hf}/b{hf}/b"
    compat = mo.get("container", "mp4") == "mp4" and mo.get("compat", True)
    if compat and (mo.get("h264", True) or mo.get("playlist")):
        return (f"bv*[vcodec^=avc1]{hf}+ba[ext=m4a]/bv*[vcodec^=avc1]{hf}+ba/b[ext=mp4]{hf}/bv*{hf}+ba/b{hf}/b")
    return f"bv*{hf}+ba/b{hf}/b"


def make_cookie_file(url, header) -> str:
    """Ubah header 'a=b; c=d' menjadi file cookie Netscape sementara (yt-dlp menolak cookie lewat header)."""
    import tempfile
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    dom = host[4:] if host.startswith("www.") else host
    lines = ["# Netscape HTTP Cookie File"]
    for part in header.split(";"):
        name, _, val = part.strip().partition("=")
        if name:
            lines.append(f".{dom}\tTRUE\t/\tFALSE\t4102444800\t{name}\t{val}")
    fd, path = tempfile.mkstemp(prefix="sg_cookies_", suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def drop_cookie_file(o):
    p = o.get("cookiefile") if isinstance(o, dict) else None
    if p and os.path.basename(p).startswith("sg_cookies_"):
        try:
            os.remove(p)
        except OSError:
            pass


def ytdlp_base(cfg, referer="", cookies="", url="") -> dict:
    o = {"quiet": True, "no_warnings": True, "noprogress": True,
         "socket_timeout": cfg["timeout"], "proxy": cfg["proxy"] or None}
    ff = ffmpeg_path(cfg)
    if ff:
        o["ffmpeg_location"] = ff
    if cfg["cookies_browser"]:
        o["cookiesfrombrowser"] = (cfg["cookies_browser"],)
    if referer:
        o["http_headers"] = {"Referer": referer}
    if cookies and url:
        o["cookiefile"] = make_cookie_file(url, cookies)
    return o


class MediaJob(Job):
    def run(self):
        import yt_dlp
        t, cfg, mo = self.t, self.cfg, self.t.media_opts
        Cancel = getattr(yt_dlp.utils, "DownloadCancelled", Exception)
        t.status, t.error, t.speed, t.eta, t.note = "preparing", "", 0, -1, "Menyiapkan media…"
        os.makedirs(t.save_dir, exist_ok=True)
        files = {}
        has_ff = bool(ffmpeg_path(cfg))

        def hook(d):
            if self.stop.is_set():
                raise Cancel("stopped")
            fn = d.get("filename") or d.get("tmpfilename") or ""
            info = d.get("info_dict") or {}
            if info.get("title") and not t.title:
                t.title = info["title"]
            if d["status"] == "downloading":
                files[fn] = (d.get("downloaded_bytes") or 0, d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
                t.status, t.note = "downloading", ""
                t.downloaded = sum(v[0] for v in files.values())
                t.total = sum(v[1] for v in files.values())
                t.speed = d.get("speed") or 0
                t.eta = d["eta"] if d.get("eta") is not None else -1
            elif d["status"] == "finished":
                n = d.get("total_bytes") or d.get("downloaded_bytes") or 0
                files[fn] = (n, n)

        def pp(d):
            if d["status"] == "started":
                t.status, t.note, t.speed, t.eta = "processing", "Memproses " + d["postprocessor"], 0, -1

        playlist = bool(mo.get("playlist"))
        q = "%(height& [{}p]|)s" if mo.get("mode") != "audio" else ""
        sfx = str(mo.get("suffix", "")).replace("%", "%%")          # " (1)" untuk judul kembar di dalam satu playlist
        tmpl = (f"%(playlist_title|Playlist)s/%(title).150B{q}{sfx}.%(ext)s" if playlist
                else f"%(title).170B{q}{sfx}.%(ext)s")
        o = ytdlp_base(cfg, t.referer, t.cookies, t.url)
        o.update({"outtmpl": os.path.join(t.save_dir, tmpl), "format": build_format(mo, has_ff),
                  "noplaylist": not playlist, "progress_hooks": [hook], "postprocessor_hooks": [pp],
                  "ratelimit": self.limiter.rate or None, "retries": cfg["retries"], "fragment_retries": cfg["retries"],
                  "concurrent_fragment_downloads": min(int(t.connections), 16), "continuedl": True,
                  "windowsfilenames": True, "overwrites": t.dup == "replace"})
        pps = []
        if mo.get("mode") == "audio":
            if mo.get("audio_codec", "best") != "best":
                pps.append({"key": "FFmpegExtractAudio", "preferredcodec": mo["audio_codec"],
                            "preferredquality": str(mo.get("audio_quality", "192"))})
        else:
            c = mo.get("container", "mp4")
            if c:
                o["merge_output_format"] = c
            if c == "mp4" and mo.get("compat", True):
                o["format_sort"] = ["res", "vcodec:h264", "acodec:aac"]
        if has_ff and cfg["embed_metadata"]:
            pps.append({"key": "FFmpegMetadata"})
        if has_ff and cfg["embed_thumbnail"]:
            o["writethumbnail"] = True
            pps.append({"key": "EmbedThumbnail"})
        if mo.get("subs"):
            o.update({"writesubtitles": True, "subtitleslangs": ["id", "en"]})
        o["postprocessors"] = pps
        if t.dup == "number" and not playlist:
            try:
                tmpl = self._numbered_template(yt_dlp, o, mo, tmpl)
                o["outtmpl"] = os.path.join(t.save_dir, tmpl)
            except Exception:
                pass                                      # gagal memeriksa duplikat: lanjut dengan nama biasa
        first_err, path, vcodec = None, "", ""
        # YouTube kadang menjawab 403: coba jalur klien alternatif sebelum menyerah
        for clients in ([None, ["android_vr"], ["tv"]] if re.search(r"youtu", t.url) else [None]):
            if clients:
                o["extractor_args"] = {"youtube": {"player_client": clients}}
                t.note, t.status = "Mencoba jalur alternatif…", "preparing"
                files.clear()
            try:
                with yt_dlp.YoutubeDL(o) as y:
                    info = y.extract_info(t.url, download=True)
                    path = self._final_path(y, info, playlist)
                    rd = (info.get("requested_downloads") or [{}])[0]
                    vcodec = rd.get("vcodec") or info.get("vcodec") or ""
                first_err = None
                break
            except Exception as e:
                if self.stop.is_set():
                    drop_cookie_file(o)
                    return
                first_err = first_err or e
                if "403" not in str(e):
                    break
        drop_cookie_file(o)
        if first_err:
            raise DownloadError(clean_error(first_err))
        if self.stop.is_set():
            return
        warn = ""
        ff = ffmpeg_path(cfg)
        if (mo.get("mode") == "video" and mo.get("container", "mp4") == "mp4" and mo.get("compat", True) and not playlist
                and ff and path and os.path.isfile(path) and vcodec and not vcodec.startswith(("avc", "h264"))):
            ok = self._transcode(ff, path)
            if self.stop.is_set():
                return
            if not ok:
                warn = "Konversi H.264 gagal; file asli (VP9/AV1) mungkin tidak bisa diputar di QuickTime/iPhone."
        t.final_path = path or t.save_dir
        t.filename = os.path.basename(t.final_path.rstrip("/\\")) or t.title
        if os.path.isfile(t.final_path):
            t.total = t.downloaded = os.path.getsize(t.final_path)
        t.status, t.finished, t.note, t.speed = "completed", time.time(), warn, 0

    def _numbered_template(self, yt_dlp, o, mo, tmpl):
        """Jika file hasil sudah ada, kembalikan template bernomor: 'Judul [1080p] (1).mp4', '(2)', dst."""
        t = self.t
        if t.title:                                       # pemeriksaan murah dulu: ada file berjudul serupa?
            try:
                from yt_dlp.utils import sanitize_filename
                stem = sanitize_filename(t.title)[:40].lower()
            except Exception:
                stem = sanitize(t.title)[:40].lower()
            if not any(f.lower().startswith(stem) for f in os.listdir(t.save_dir)):
                return tmpl
        probe = dict(o, skip_download=True, progress_hooks=[], postprocessor_hooks=[], postprocessors=[])
        with yt_dlp.YoutubeDL(probe) as y:
            info = y.extract_info(t.url, download=False)
            base = os.path.splitext(y.prepare_filename(info))[0]
        if mo.get("mode") == "audio":
            codec = mo.get("audio_codec", "best")
            exts = [codec] if codec != "best" else ["m4a", "webm", "opus", "mp3", "mp4"]
        else:
            exts = [mo.get("container", "mp4")]
        if not any(os.path.exists(f"{base}.{e}") for e in exts):
            return tmpl
        n = 1
        while any(os.path.exists(f"{base} ({n}).{e}") for e in exts):
            n += 1
        return tmpl.replace(".%(ext)s", f" ({n}).%(ext)s")

    def _transcode(self, ff, path) -> bool:
        """Ubah video VP9/AV1 menjadi H.264 + AAC agar kompatibel di semua perangkat."""
        import subprocess
        t = self.t
        t.status, t.speed, t.eta = "processing", 0, -1
        t.note = "Mengonversi ke H.264 agar bisa diputar di semua perangkat…"
        tmp = path + ".h264.mp4"
        cmd = [ff, "-y", "-i", path, "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp]
        kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
        try:
            pr = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
            while pr.poll() is None:
                if self.stop.is_set():
                    pr.terminate()
                    pr.wait()
                    break
                time.sleep(0.5)
            if pr.returncode == 0 and os.path.exists(tmp) and not self.stop.is_set():
                os.replace(tmp, path)
                return True
        except OSError:
            pass
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False

    @staticmethod
    def _final_path(y, info, playlist):
        try:
            if info.get("_type") == "playlist" or playlist and info.get("entries"):
                for e in info.get("entries") or []:
                    rd = (e or {}).get("requested_downloads") or []
                    if rd:
                        return os.path.dirname(rd[0]["filepath"])
                return ""
            rd = info.get("requested_downloads") or []
            return rd[0]["filepath"] if rd else y.prepare_filename(info)
        except Exception:
            return ""
