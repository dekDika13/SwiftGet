"""Manajer antrean: jadwal, prioritas, jeda/lanjut, dan penyimpanan riwayat."""
from __future__ import annotations
import os, shutil, threading, time
from urllib.parse import parse_qs, urlparse
from collections import deque
from pathlib import Path

from .config import OTHER, categorize
from .engine import FileJob, MediaJob, RateLimiter, clean_error
from .models import ACTIVE, DB, Task
from .util import is_youtube, sanitize, unique_name


def _norm_url(u: str) -> str:
    u = u.strip().split("#")[0]
    p = urlparse(u)
    if "youtube.com" in p.netloc and p.path == "/watch" and parse_qs(p.query).get("v"):
        return "yt:" + parse_qs(p.query)["v"][0]
    if p.netloc.endswith("youtu.be") and p.path.strip("/"):
        return "yt:" + p.path.strip("/")
    return u.rstrip("/")


def _media_key(t: Task):
    o = t.media_opts
    return (o.get("mode"), int(o.get("height") or 0), o.get("container"), o.get("audio_codec") if o.get("mode") == "audio" else None)


class Manager:
    def __init__(self, cfg, db: DB):
        self.cfg, self.db = cfg, db
        self.lock = threading.RLock()
        self.tasks: dict[int, Task] = {}
        self.jobs: dict[int, object] = {}
        self.threads: dict[int, threading.Thread] = {}
        self.reserved: set = set()
        self.limiter = RateLimiter()
        self.on_event = None          # callback(kind, task_id)
        self.speed = 0.0
        self.speed_hist = deque([0.0] * 60, maxlen=60)
        self._was_busy = False
        self._pl_seen = set()
        self._running = True
        self.apply_settings()
        for t in db.load_all():
            if t.status in ACTIVE:
                t.status = "paused"
            self.tasks[t.id] = t
        threading.Thread(target=self._loop, daemon=True).start()

    # ---------------------------------------------------------------- setup
    def apply_settings(self):
        self.limiter.set_rate(int(self.cfg["speed_limit_kbps"]) * 1024)

    def default_dir(self, category: str) -> str:
        base = Path(self.cfg["download_dir"])
        return str(base / category) if self.cfg["auto_categorize"] and category else str(base)

    def assign_name(self, t: Task, name: str):
        """Tetapkan nama file + kategori + folder untuk tugas (unik, kecuali mode 'replace')."""
        with self.lock:
            name = sanitize(name)
            if t.auto_dir:
                t.category = categorize(name)
                t.save_dir = self.default_dir(t.category)
            os.makedirs(t.save_dir, exist_ok=True)
            t.filename = name if t.dup == "replace" else unique_name(t.save_dir, name, self.reserved)
            self.reserved.add((t.save_dir, t.filename))

    def find_duplicates(self, url, *, kind="file", filename="", save_dir=None, media_opts=None, title=""):
        """Cari unduhan yang sama: di daftar (URL sama) dan di disk (nama file sama / judul serupa)."""
        out, seen = [], set()
        nurl, mo = _norm_url(url), media_opts or {}
        probe = Task(kind=kind, media_opts=mo)
        for t in list(self.tasks.values()):
            if _norm_url(t.url) != nurl or (kind == "media") != (t.kind == "media"):
                continue
            if kind == "media" and _media_key(t) != _media_key(probe):
                continue
            path = t.path if t.status == "completed" and os.path.exists(t.path) else ""
            out.append({"type": "task", "task": t, "path": path, "status": t.status})
            seen.add(path)
        try:
            if kind == "file" and filename:
                d = save_dir or self.default_dir(categorize(filename))
                p = os.path.join(d, sanitize(filename))
                if os.path.exists(p) and p not in seen:
                    out.append({"type": "file", "path": p, "status": "file"})
            elif kind == "media" and title:
                d = save_dir or self.default_dir("Musik" if mo.get("mode") == "audio" else "Video")
                try:
                    from yt_dlp.utils import sanitize_filename as sf
                    stem = sf(title)
                except Exception:
                    stem = sanitize(title)
                stem = stem[:50].lower()
                if os.path.isdir(d) and not any(x["path"] for x in out):
                    for f in sorted(os.listdir(d)):
                        full = os.path.join(d, f)
                        if f.lower().startswith(stem) and os.path.isfile(full) and not f.endswith((".part", ".ytdl", ".temp")):
                            out.append({"type": "file", "path": full, "status": "file"})
                            break
        except OSError:
            pass
        return out

    # ------------------------------------------------------------------ API
    def add(self, url, *, kind="file", filename="", save_dir=None, connections=None, referer="", cookies="",
            user_agent="", headers=None, media_opts=None, start=True, start_at=0.0, checksum="", title="",
            dup="number", parent_id=0) -> Task:
        if kind == "media" and is_youtube(url):
            cookies = ""                       # cookie browser membuat YouTube menolak ("page needs to be reloaded")
        t = Task(url=url.strip(), kind=kind, referer=referer, cookies=cookies, user_agent=user_agent, parent_id=parent_id,
                 headers=headers or {}, media_opts=media_opts or {}, checksum=checksum.strip(), title=title,
                 connections=int(connections or self.cfg["connections"]), start_at=start_at, dup=dup)
        if kind == "media":
            t.category = "Musik" if t.media_opts.get("mode") == "audio" else "Video"
        elif filename:
            t.filename = sanitize(filename)
            t.category = categorize(t.filename)
        else:
            t.category = OTHER
        t.auto_dir = not save_dir
        t.save_dir = save_dir or self.default_dir(t.category)
        t.status = "scheduled" if start_at > time.time() else ("queued" if start else "paused")
        with self.lock:
            self.db.insert(t)
            t.order = float(t.id)
            if t.filename and kind == "file":
                if dup != "replace":
                    t.filename = unique_name(t.save_dir, t.filename, self.reserved)
                self.reserved.add((t.save_dir, t.filename))
            self.tasks[t.id] = t
            self.db.update(t)
        return t

    def children(self, pid):
        return [x for x in list(self.tasks.values()) if x.parent_id == pid]

    def add_playlist(self, url, name, entries, *, media_opts, base_dir=None, connections=None, referer="", cookies="",
                     user_agent="", start=True, start_at=0.0, dup="number") -> Task:
        """Buat playlist: 1 tugas induk (yang tampil di daftar) + 1 tugas media per video."""
        audio = media_opts.get("mode") == "audio"
        cat = "Musik" if audio else "Video"
        folder = sanitize(name)
        path = os.path.join(base_dir or self.default_dir(cat), folder)
        with self.lock:                                  # atomik: loop jangan melihat induk tanpa isi
            parent = Task(url=url.strip(), kind="playlist", filename=folder, title=folder, save_dir=path, final_path=path,
                          category=cat, auto_dir=False, media_opts=dict(media_opts), dup=dup,
                          connections=int(connections or self.cfg["media_connections"]),
                          status="queued" if start else "paused")
            self.db.insert(parent)
            parent.order = float(parent.id)
            self.tasks[parent.id] = parent
            self.db.update(parent)
            seen = {}
            for e in entries:
                title = e.get("title") or e["url"]
                key = sanitize(title).lower()
                n = seen.get(key, 0)
                seen[key] = n + 1
                mo = {**media_opts, "playlist": False, "suffix": f" ({n})" if n else ""}      # judul kembar → " (1)" di belakang
                self.add(e["url"], kind="media", media_opts=mo, title=title, save_dir=path, connections=parent.connections,
                         referer=referer, cookies=cookies, user_agent=user_agent, start=start, start_at=start_at,
                         dup=dup, parent_id=parent.id)
        return parent

    def find_playlist_duplicates(self, name, base_dir=None, audio=False):
        """Playlist dengan nama/folder sama: di daftar dan/atau di disk. None bila tidak ada."""
        path = os.path.join(base_dir or self.default_dir("Musik" if audio else "Video"), sanitize(name))
        tasks = [t for t in list(self.tasks.values())
                 if t.kind == "playlist" and os.path.normpath(t.save_dir) == os.path.normpath(path)]
        on_disk = os.path.isdir(path) and bool(os.listdir(path))
        return {"tasks": tasks, "path": path, "disk": on_disk} if tasks or on_disk else None

    def _refresh_playlists(self):
        """Hitung status/progres induk playlist dari isinya (dipanggil dalam loop, di bawah lock)."""
        kids = {}
        for t in self.tasks.values():
            if t.parent_id:
                kids.setdefault(t.parent_id, []).append(t)
        for p in [t for t in self.tasks.values() if t.kind == "playlist"]:
            ks = kids.get(p.id, [])
            n = len(ks)
            if n == 0:                                   # semua isi dihapus dari daftar → hapus induknya
                self.tasks.pop(p.id, None)
                self.db.delete(p.id)
                continue
            p.n_items = n
            done = sum(k.status == "completed" for k in ks)
            err = sum(k.status == "error" for k in ks)
            if any(k.is_active for k in ks):
                st = "downloading"
            elif any(k.status in ("queued", "scheduled") for k in ks):
                st = "queued"
            elif err:
                st = "error"
            elif any(k.status == "paused" for k in ks):
                st = "paused"
            else:
                st = "completed"
            prog = sum(1.0 if k.status == "completed" else (min(1.0, k.downloaded / k.total) if k.total > 0 else 0.0)
                       for k in ks) / n
            p.total, p.downloaded = 1000, int(prog * 1000)
            p.speed = sum(k.speed for k in ks if k.is_active)
            rem = sum(max(0, k.total - k.downloaded) for k in ks if k.status != "completed" and k.total > 0)
            p.eta = rem / p.speed if p.speed > 1 and rem > 0 else -1
            p.note = f"{done}/{n} selesai" + (f"  ·  {err} gagal" if err else "")
            p.error = f"{err} video gagal — buka playlist untuk melihat" if err else ""
            old = p.status
            p.status = st
            if st == "completed" and not p.finished:
                p.finished = time.time()
            if old != st:
                self.db.update(p)
                if p.id in self._pl_seen and st in ("completed", "error"):
                    self._emit(st, p.id)
            self._pl_seen.add(p.id)

    def pause(self, tid):
        t0 = self.tasks.get(tid)
        if t0 and t0.kind == "playlist":
            for k in self.children(tid):
                self.pause(k.id)
            return
        with self.lock:
            t = self.tasks.get(tid)
            if t and (t.status in ACTIVE or t.status in ("queued", "scheduled")):
                job = self.jobs.get(tid)
                if job:
                    job.request_stop("pause")
                t.status, t.speed, t.eta = "paused", 0, -1
                self.db.update(t)

    def resume(self, tid):
        t0 = self.tasks.get(tid)
        if t0 and t0.kind == "playlist":
            for k in self.children(tid):
                self.resume(k.id)
            return
        with self.lock:
            t = self.tasks.get(tid)
            if t and t.status in ("paused", "error", "scheduled"):
                t.status, t.error, t.start_at = "queued", "", 0
                self.db.update(t)

    def update_task(self, tid, *, connections=None, save_dir=None, filename=None, media_opts=None, resume=True):
        """Ubah koneksi / lokasi / nama. Unduhan aktif dijeda sebentar, diubah, lalu dilanjutkan."""
        with self.lock:
            t = self.tasks.get(tid)
            if not t:
                return
            job, th = self.jobs.get(tid), self.threads.get(tid)
            was_running = t.status in ACTIVE or t.status in ("queued", "scheduled")
            if job:
                job.request_stop("pause")
            if was_running:
                t.status, t.speed, t.eta = "paused", 0, -1

        def apply():
            if th:
                th.join(15)
            with self.lock:
                if connections:
                    t.connections = max(1, min(32, int(connections)))
                if media_opts and t.kind == "media" and t.status != "completed":
                    t.media_opts = dict(media_opts)
                    cat = "Musik" if media_opts.get("mode") == "audio" else "Video"
                    if t.auto_dir and not save_dir and cat != t.category:
                        t.save_dir = self.default_dir(cat)
                    t.category = cat
                    t.downloaded = t.total = 0
                    t.final_path = ""
                try:
                    self._relocate(t, save_dir, filename)
                    if save_dir:
                        t.auto_dir = False
                    if resume and t.status != "completed" and (was_running or t.status in ("error", "paused")):
                        t.status, t.error = "queued", ""
                except OSError as e:
                    t.status, t.error = "error", f"Gagal memindahkan file: {e}"
                self.db.update(t)
        threading.Thread(target=apply, daemon=True).start()

    def _relocate(self, t: Task, new_dir, new_name):
        old_dir, new_dir = t.save_dir, (new_dir or t.save_dir)
        if t.kind == "file":
            old_name = t.filename
            name = sanitize(new_name) if new_name else old_name
            if not old_name:                      # belum bernama: cukup ganti folder
                t.save_dir = new_dir
                if name:
                    t.filename = unique_name(new_dir, name, self.reserved)
                return
            if (new_dir, name) == (old_dir, old_name):
                return
            os.makedirs(new_dir, exist_ok=True)
            name = unique_name(new_dir, name, self.reserved)
            if t.status == "completed":
                src = t.final_path or os.path.join(old_dir, old_name)
                if os.path.exists(src):
                    dst = os.path.join(new_dir, name)
                    shutil.move(src, dst)
                    t.final_path = dst
            else:
                src = os.path.join(old_dir, old_name + ".part")
                if os.path.exists(src):
                    shutil.move(src, os.path.join(new_dir, name + ".part"))
            self.reserved.discard((old_dir, old_name))
            self.reserved.add((new_dir, name))
            t.save_dir, t.filename = new_dir, name
        else:                                     # media (yt-dlp)
            t.save_dir = new_dir
            fp = t.final_path
            if t.status == "completed" and fp and os.path.exists(fp):
                base = os.path.basename(fp.rstrip("/\\"))
                if new_name and os.path.isfile(fp):
                    base = sanitize(new_name)
                dst = os.path.join(new_dir, base)
                if os.path.abspath(dst) != os.path.abspath(fp):
                    os.makedirs(new_dir, exist_ok=True)
                    shutil.move(fp, dst)
                    t.final_path, t.filename = dst, base

    def retry(self, tid):
        self.resume(tid)

    def redownload(self, tid):
        t0 = self.tasks.get(tid)
        if t0 and t0.kind == "playlist":
            for k in self.children(tid):
                self.redownload(k.id)
            return
        with self.lock:
            t = self.tasks.get(tid)
            if not t or tid in self.jobs:
                return
            self._wipe_files(t, final=True)
            t.chunks, t.downloaded, t.total, t.final_path = [], 0, 0, ""
            if t.kind == "file":
                t.filename = ""
            t.status, t.error = "queued", ""
            self.db.update(t)

    def remove(self, tid, delete_file=False):
        t0 = self.tasks.get(tid)
        if t0 and t0.kind == "playlist":
            for k in self.children(tid):
                self.remove(k.id, delete_file)
            with self.lock:
                self.tasks.pop(tid, None)
            self.db.delete(tid)
            if delete_file:
                threading.Thread(target=self._rmdir_later, args=(t0.save_dir,), daemon=True).start()
            return
        with self.lock:
            t = self.tasks.pop(tid, None)
            job = self.jobs.get(tid)
            th = self.threads.get(tid)
        if not t:
            return
        if job:
            job.request_stop("cancel")
        self.db.delete(tid)

        def cleanup():
            if th:
                th.join(8)
            self._wipe_files(t, final=delete_file)
        threading.Thread(target=cleanup, daemon=True).start()

    @staticmethod
    def _rmdir_later(folder):
        for delay in (2, 6, 15):                         # tunggu pembersihan file anak; hanya hapus folder bila kosong
            time.sleep(delay)
            try:
                os.rmdir(folder)
                return
            except OSError:
                pass

    def _wipe_files(self, t: Task, final: bool):
        try:
            if t.kind == "file" and t.filename:
                part = os.path.join(t.save_dir, t.filename + ".part")
                if os.path.exists(part):
                    os.remove(part)
                self.reserved.discard((t.save_dir, t.filename))
            if final and t.final_path and os.path.isfile(t.final_path):
                os.remove(t.final_path)
        except OSError:
            pass

    def clear_finished(self):
        for t in [t for t in list(self.tasks.values()) if t.status == "completed" and not t.parent_id]:
            self.remove(t.id)

    def start_all(self):
        for t in list(self.tasks.values()):
            if t.status in ("paused", "error"):
                self.resume(t.id)

    def pause_all(self):
        for t in list(self.tasks.values()):
            self.pause(t.id)

    def move(self, tid, delta):
        with self.lock:
            ordered = sorted((t for t in self.tasks.values() if t.status != "completed"), key=lambda t: t.order)
            ids = [t.id for t in ordered]
            if tid not in ids:
                return
            i, j = ids.index(tid), ids.index(tid) + delta
            if 0 <= j < len(ids):
                a, b = self.tasks[ids[i]], self.tasks[ids[j]]
                a.order, b.order = b.order, a.order
                self.db.update(a)
                self.db.update(b)

    def shutdown(self):
        self._running = False
        for t in list(self.tasks.values()):
            self.pause(t.id)
        for th in list(self.threads.values()):
            th.join(5)
        for t in self.tasks.values():
            self.db.update(t)

    # ----------------------------------------------------------------- loop
    def _emit(self, kind, tid=0):
        if self.on_event:
            try:
                self.on_event(kind, tid)
            except Exception:
                pass

    def _start(self, t: Task):
        job = (MediaJob if t.kind == "media" else FileJob)(t, self.cfg, self.limiter, self)
        t.status = "preparing"
        self.jobs[t.id] = job
        th = threading.Thread(target=self._run, args=(t, job), daemon=True)
        self.threads[t.id] = th
        th.start()

    def _run(self, t: Task, job):
        try:
            job.run()
            if t.status == "completed" and not t.parent_id:
                self._emit("completed", t.id)
        except Exception as e:
            if job.reason not in ("pause", "cancel"):
                t.status, t.error = "error", clean_error(e)
                if not t.parent_id:
                    self._emit("error", t.id)
        finally:
            t.speed, t.eta = 0, -1
            with self.lock:
                self.jobs.pop(t.id, None)
                self.threads.pop(t.id, None)
                if t.status in ACTIVE:
                    t.status = "paused"
            if t.id in self.tasks:
                self.db.update(t)

    def _loop(self):
        last_save = 0.0
        while self._running:
            now = time.time()
            with self.lock:
                for t in self.tasks.values():
                    if t.status == "scheduled" and t.start_at <= now:
                        t.status = "queued"
                real = [t for t in self.tasks.values() if t.kind != "playlist"]
                active = [t for t in real if t.status in ACTIVE]
                slots = int(self.cfg["max_concurrent"]) - len(active)
                if slots > 0:
                    queued = sorted((t for t in real if t.status == "queued" and t.id not in self.jobs),
                                    key=lambda t: t.order)
                    for t in queued[:slots]:
                        self._start(t)
                self._refresh_playlists()
                self.speed = sum(t.speed for t in active)
                busy = bool(active) or any(t.status == "queued" for t in real)
            self.speed_hist.append(self.speed)
            if self._was_busy and not busy:
                self._emit("queue_done")
            self._was_busy = busy
            if now - last_save > 3:
                last_save = now
                for t in active:
                    self.db.update(t)
            time.sleep(0.5)
