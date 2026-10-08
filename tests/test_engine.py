"""Tes engine tanpa GUI: python -m tests.test_engine"""
import hashlib, os, re, sys, tempfile, threading, time, json, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from swiftget.config import Settings
from swiftget.manager import Manager
from swiftget.models import DB
from swiftget.server import LocalServer

DATA = os.urandom(6 * 1024 * 1024 + 123)
SHA = hashlib.sha256(DATA).hexdigest()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/norange"):
            self.send_response(200); self.send_header("Content-Length", str(len(DATA))); self.end_headers()
            try: self.wfile.write(DATA)
            except Exception: pass
            return
        if self.path.startswith("/page"):
            b = b"<html>hi</html>"; self.send_response(200); self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        origin = f"http://127.0.0.1:{self.server.server_address[1]}/"
        if self.path.startswith("/hotlink") and self.headers.get("Referer") != origin:     # anti-hotlink seperti WordPress/Cloudflare
            self.send_response(403); self.send_header("Content-Length", "0"); self.end_headers(); return
        if self.path.startswith("/norange403") and self.headers.get("Range"):               # WAF yang memblokir header Range
            self.send_response(403); self.send_header("Content-Length", "0"); self.end_headers(); return
        pace = (16384, 0.02) if self.path.startswith("/slow") else (65536, 0.002)           # /slow ≈ 800 KB/s per koneksi
        rng = self.headers.get("Range")
        s, e = 0, len(DATA) - 1
        code = 200
        if rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng); s = int(m.group(1)); e = int(m.group(2) or e); code = 206
        body = DATA[s:e + 1]
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'attachment; filename="tes file.bin"')
        if code == 206: self.send_header("Content-Range", f"bytes {s}-{e}/{len(DATA)}")
        self.end_headers()
        try:
            for i in range(0, len(body), pace[0]):
                self.wfile.write(body[i:i + pace[0]]); time.sleep(pace[1])
        except Exception: pass


def wait(m, tid, status, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if m.tasks[tid].status == status: return True
        time.sleep(0.1)
    return False


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    tmp = os.path.realpath(tempfile.mkdtemp())
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = Settings(__import__("pathlib").Path(tmp) / "s.json"); cfg["download_dir"] = tmp + "/dl"
    m = Manager(cfg, DB(tmp + "/db.sqlite"))
    base = f"http://127.0.0.1:{port}"

    t = m.add(base + "/file", checksum="sha256:" + SHA); assert wait(m, t.id, "completed"), (t.status, t.error)
    assert sha(t.final_path) == SHA and t.final_path.endswith("tes file.bin") and len(t.chunks) > 1
    print("OK multi-koneksi + checksum:", t.final_path, f"{len(t.chunks)} chunk")

    t2 = m.add(base + "/file"); assert wait(m, t2.id, "completed"); assert t2.filename == "tes file (1).bin"
    print("OK nama unik:", t2.filename)

    cfg["speed_limit_kbps"] = 1500; m.apply_settings()
    t3 = m.add(base + "/file", filename="pause.bin"); time.sleep(1.2); m.pause(t3.id)
    time.sleep(1.0); part = t3.downloaded; assert t3.status == "paused" and 0 < part < len(DATA), part
    cfg["speed_limit_kbps"] = 0; m.apply_settings(); m.resume(t3.id)
    assert wait(m, t3.id, "completed"), (t3.status, t3.error); assert sha(t3.final_path) == SHA
    print("OK pause/resume, bytes saat jeda:", part)

    t4 = m.add(base + "/norange", filename="nr.bin"); assert wait(m, t4.id, "completed"); assert sha(t4.final_path) == SHA
    print("OK server tanpa Range (1 koneksi)")

    t5 = m.add(base + "/page"); assert wait(m, t5.id, "error"); print("OK halaman HTML ditolak:", t5.error)
    t6 = m.add(base + "/file", checksum="sha256:" + "0" * 64, filename="bad.bin"); assert wait(m, t6.id, "error"); print("OK checksum salah:", t6.error)

    got = []
    cfg["server_port"] = 0
    approved = []
    def pair(origin):
        approved.append(origin)
        return cfg["token"] if origin.endswith("abc") else None
    ls = LocalServer(cfg, lambda r, d: got.append((r, d)), pair); cfg["server_port"] = 16277; ls.start()
    def call(path, body=None, tok=cfg["token"], origin="chrome-extension://abc"):
        rq = urllib.request.Request(f"http://127.0.0.1:16277{path}", data=json.dumps(body).encode() if body else None,
                                    headers={"X-SwiftGet-Token": tok, "Origin": origin, "Content-Type": "application/json"})
        try: return urllib.request.urlopen(rq).status
        except urllib.error.HTTPError as e: return e.code
    assert call("/add", {"url": "x"}) == 200 and got[0][0] == "add"
    assert call("/add", {"url": "x"}, tok="salah") == 401
    assert call("/add", {"url": "x"}, origin="https://evil.com") == 403
    print("OK server extension: token & origin")
    def pair_call(origin):
        hdr = {"Content-Type": "application/json"}
        if origin: hdr["Origin"] = origin
        rq = urllib.request.Request("http://127.0.0.1:16277/pair", data=b"{}", headers=hdr)
        try:
            r = urllib.request.urlopen(rq); return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code, None
    st, body = pair_call("chrome-extension://abc"); assert st == 200 and body["token"] == cfg["token"]
    assert pair_call("chrome-extension://zzz")[0] == 403
    assert pair_call("https://evil.com")[0] == 403 and pair_call(None)[0] == 403
    print("OK pairing otomatis: setuju, tolak, bukan-extension")

    cfg["speed_limit_kbps"] = 2500; m.apply_settings()
    t7 = m.add(base + "/file", filename="mv.bin", connections=4)
    t0 = time.time()
    while t7.downloaded < 300000 and time.time() - t0 < 10: time.sleep(0.1)
    m.update_task(t7.id, connections=2, save_dir=tmp + "/pindah", filename="baru.bin")
    time.sleep(1.5); cfg["speed_limit_kbps"] = 0; m.apply_settings()
    assert wait(m, t7.id, "completed"), (t7.status, t7.error)
    assert os.path.normpath(t7.final_path) == os.path.normpath(tmp + "/pindah/baru.bin") and sha(t7.final_path) == SHA and t7.connections == 2, t7.final_path
    assert not os.path.exists(tmp + "/dl/Lainnya/mv.bin.part")
    print("OK ubah koneksi+lokasi+nama saat berjalan:", t7.final_path)

    m.update_task(t.id, save_dir=tmp + "/arsip", filename="dipindah.bin"); time.sleep(0.8)
    assert os.path.normpath(t.final_path) == os.path.normpath(tmp + "/arsip/dipindah.bin") and os.path.exists(t.final_path) and t.status == "completed", t.final_path
    print("OK pindahkan file yang sudah selesai")

    from swiftget.engine import build_format
    assert "[vcodec^=avc1]" in build_format({"mode": "video", "height": 1080, "h264": True, "container": "mp4"}, True)
    assert "avc1" not in build_format({"mode": "video", "container": "mkv"}, True)
    assert build_format({"mode": "video", "container": "mp4"}, False).startswith("b[ext=mp4]")
    print("OK pemilih format H.264/AAC")

    mt = m.add("http://127.0.0.1:1/video", kind="media", media_opts={"mode": "video", "height": 360, "container": "mp4"}, start=False)
    m.update_task(mt.id, media_opts={"mode": "audio", "audio_codec": "mp3"}, resume=False); time.sleep(0.5)
    assert mt.media_opts["mode"] == "audio" and mt.category == "Musik" and mt.save_dir.endswith("Musik"), (mt.media_opts, mt.save_dir)
    print("OK ubah resolusi/format unduhan media dari daftar")

    from swiftget.engine import make_cookie_file, drop_cookie_file
    cf = make_cookie_file("https://www.youtube.com/watch?v=1", "a=1; b=2")
    txt = open(cf).read(); assert ".youtube.com\tTRUE\t/\tFALSE\t4102444800\ta\t1" in txt and "b\t2" in txt
    drop_cookie_file({"cookiefile": cf}); assert not os.path.exists(cf)
    print("OK cookie via file sementara (bukan header)")

    # --- duplikat ---
    dups = m.find_duplicates(base + "/file", kind="file", filename="tes file.bin")
    assert any(d["type"] == "task" and d["path"] for d in dups), dups
    assert any(d["path"] for d in m.find_duplicates("http://lain/x", kind="file", filename=t2.filename)), "file di disk"
    assert not m.find_duplicates("http://lain/x", kind="file", filename="tidak-ada.bin")
    print("OK deteksi duplikat (di daftar & di disk)")

    orig = t2.final_path; m0 = os.path.getmtime(orig); time.sleep(1.1)
    r = m.add(base + "/file", filename=t2.filename, dup="replace"); assert wait(m, r.id, "completed"), (r.status, r.error)
    assert r.filename == t2.filename and os.path.normpath(r.final_path) == os.path.normpath(orig) and os.path.getmtime(orig) > m0
    assert sha(orig) == SHA
    print("OK mode ganti (replace): nama sama, file ditimpa")

    n = m.add(base + "/file", filename=t2.filename); assert wait(m, n.id, "completed")
    assert n.filename != t2.filename and os.path.exists(n.final_path) and os.path.exists(orig), n.filename
    print("OK mode nomor:", n.filename)

    import types
    from swiftget.engine import MediaJob, RateLimiter
    from swiftget.models import Task
    class FakeY:
        def __init__(self, params): self.params = params
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False): return {"title": "Vid"}
        def prepare_filename(self, info):
            return self.params["outtmpl"].replace("%(title).170B", "Vid").replace("%(height& [{}p]|)s", " [1080p]").replace("%(ext)s", "mp4")
    fake = types.SimpleNamespace(YoutubeDL=FakeY)
    vd = tmp + "/vid"; os.makedirs(vd)
    mt2 = Task(url="http://v", kind="media", title="Vid", save_dir=vd, media_opts={"mode": "video", "container": "mp4"})
    job = MediaJob(mt2, cfg, RateLimiter(), m)
    tm = "%(title).170B%(height& [{}p]|)s.%(ext)s"
    o = {"outtmpl": os.path.join(vd, tm)}
    assert job._numbered_template(fake, o, mt2.media_opts, tm) == tm                      # belum ada file
    open(vd + "/Vid [1080p].mp4", "w").close()
    assert job._numbered_template(fake, o, mt2.media_opts, tm).endswith(" (1).%(ext)s")
    open(vd + "/Vid [1080p] (1).mp4", "w").close()
    assert job._numbered_template(fake, o, mt2.media_opts, tm).endswith(" (2).%(ext)s")
    print("OK penomoran video duplikat: Judul [1080p] (1), (2)")

    # --- playlist (tanpa jaringan: semua anak berstatus jeda) ---
    from swiftget.analyzer import playlist_summary
    ps = playlist_summary({"title": "P", "entries": [{"title": "A", "url": "https://x/1"}, {"title": "[Private video]", "url": "https://x/2"},
                                                    {"id": "abc", "ie_key": "Youtube", "title": "B"}, None]})
    assert [e["title"] for e in ps["entries"]] == ["A", "B"] and ps["entries"][1]["url"].endswith("watch?v=abc") and ps["count"] == 2
    assert m.add("https://www.youtube.com/watch?v=x", kind="media", cookies="a=b", start=False).cookies == ""
    cfg["max_concurrent"] = 0                                              # jangan jalankan unduhan sungguhan
    ents = [{"title": "Lagu A", "url": "http://127.0.0.1:1/a"}, {"title": "Lagu A", "url": "http://127.0.0.1:1/b"},
            {"title": "Lagu B", "url": "http://127.0.0.1:1/c"}]
    pl = m.add_playlist("http://127.0.0.1:1/list", "Daftar Putar", ents,
                        media_opts={"mode": "video", "height": 720, "container": "mp4"}, start=False)
    kids = m.children(pl.id)
    assert len(kids) == 3 and [k.media_opts["suffix"] for k in kids] == ["", " (1)", ""], [k.media_opts for k in kids]
    assert pl.save_dir.endswith("Daftar Putar") and all(os.path.normpath(k.save_dir) == os.path.normpath(pl.save_dir) for k in kids)
    assert pl.filename == "Daftar Putar" and pl.id not in m.jobs and all(k.parent_id == pl.id for k in kids)
    time.sleep(0.9)
    assert pl.status == "paused" and pl.n_items == 3 and pl.note.startswith("0/3"), (pl.status, pl.note)
    kids[0].status = "completed"; kids[1].status = "error"; time.sleep(0.9)
    assert pl.status == "error" and "1/3 selesai" in pl.note and "1 gagal" in pl.note, (pl.status, pl.note)
    m.resume(pl.id); time.sleep(0.9)
    assert [k.status for k in kids] == ["completed", "queued", "queued"] and pl.status == "queued"
    m.pause(pl.id); time.sleep(0.9)
    assert [k.status for k in kids] == ["completed", "paused", "paused"] and pl.status == "paused"
    d1 = m.find_playlist_duplicates("Daftar Putar")
    assert d1 and d1["tasks"][0].id == pl.id and not m.find_playlist_duplicates("Lain")
    for k in kids[:2]: m.remove(k.id)
    time.sleep(0.9); assert pl.id in m.tasks and m.children(pl.id)[0].id == kids[2].id
    m.remove(pl.id); time.sleep(0.3); assert pl.id not in m.tasks and not m.children(pl.id)
    pl2 = m.add_playlist("http://l", "Dua", ents[:2], media_opts={"mode": "audio"}, start=False)
    for k in m.children(pl2.id): m.remove(k.id)
    time.sleep(0.9); assert pl2.id not in m.tasks, "induk kosong harus hilang otomatis"
    cfg["max_concurrent"] = 3
    print("OK playlist: induk+isi, nama kembar (1), agregasi status, jeda/lanjut massal, hapus, deteksi nama sama")

    # --- 403: anti-hotlink & Range diblokir ---
    h = m.add(base + "/hotlink", filename="hot.bin", referer="http://other.example/halaman")
    assert wait(m, h.id, "completed"), (h.status, h.error); assert sha(h.final_path) == SHA
    nr = m.add(base + "/norange403", filename="nr403.bin")
    assert wait(m, nr.id, "completed"), (nr.status, nr.error); assert sha(nr.final_path) == SHA and not nr.resumable
    print("OK 403 ditangani: anti-hotlink (Referer situs) & Range diblokir (unduh tanpa Range)")

    # --- jalur alternatif ---
    from swiftget.util import route_candidates, route_proxy, mask_proxy
    assert route_candidates(cfg, base) == []                                   # nonaktif secara default
    cfg["route_enabled"] = True; cfg["route_sites"] = "127.0.0.1"
    cfg["route_proxies"] = "# komentar\ndirect\nsocks5://user:rahasia@10.0.0.1:1080"
    assert route_candidates(cfg, base) == ["direct", "socks5://user:rahasia@10.0.0.1:1080"]
    assert route_proxy(cfg, base, 0) == "" and route_proxy(cfg, base, 1).startswith("socks5") and route_proxy(cfg, base, 2) == ""
    assert "rahasia" not in mask_proxy(route_proxy(cfg, base, 1)) and route_candidates(cfg, "http://lain.example/x") == []
    cfg["route_proxies"] = "direct"
    r0 = m.add(base + "/file", filename="route0.bin"); assert wait(m, r0.id, "completed") and sha(r0.final_path) == SHA
    cfg["route_proxies"] = "http://127.0.0.1:9\ndirect"                        # jalur 1 = proxy mati
    r1 = m.add(base + "/file", filename="route1.bin"); assert wait(m, r1.id, "completed", 40), (r1.status, r1.error)
    assert r1.route_idx == 1 and sha(r1.final_path) == SHA
    print("OK pindah jalur otomatis saat proxy mati (jalur ke-2 dipakai)")
    cfg["route_proxies"] = "direct\ndirect"; cfg["route_slow_kbps"] = 100000; cfg["route_slow_secs"] = 1
    r2 = m.add(base + "/slow", filename="route2.bin", connections=1)
    assert wait(m, r2.id, "completed", 60), (r2.status, r2.error, r2.route_idx)
    assert r2.route_idx >= 1 and sha(r2.final_path) == SHA, r2.route_idx
    print("OK pindah jalur otomatis saat melambat, lanjut dari byte terakhir (indeks jalur =", r2.route_idx, ")")
    cfg["route_enabled"] = False

    a = m.add(base + "/file", filename="rm.bin"); wait(m, a.id, "completed"); p = a.final_path
    m.remove(a.id, delete_file=True); time.sleep(0.5); assert not os.path.exists(p); print("OK hapus + file")
    m.shutdown(); print("SEMUA TES LULUS")


if __name__ == "__main__":
    main()
