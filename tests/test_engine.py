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
            for i in range(0, len(body), 65536):
                self.wfile.write(body[i:i + 65536]); time.sleep(0.002)
        except Exception: pass


def wait(m, tid, status, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if m.tasks[tid].status == status: return True
        time.sleep(0.1)
    return False


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    tmp = tempfile.mkdtemp()
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
    ls = LocalServer(cfg, lambda r, d: got.append((r, d))); cfg["server_port"] = 16277; ls.start()
    def call(path, body=None, tok=cfg["token"], origin="chrome-extension://abc"):
        rq = urllib.request.Request(f"http://127.0.0.1:16277{path}", data=json.dumps(body).encode() if body else None,
                                    headers={"X-SwiftGet-Token": tok, "Origin": origin, "Content-Type": "application/json"})
        try: return urllib.request.urlopen(rq).status
        except urllib.error.HTTPError as e: return e.code
    assert call("/add", {"url": "x"}) == 200 and got[0][0] == "add"
    assert call("/add", {"url": "x"}, tok="salah") == 401
    assert call("/add", {"url": "x"}, origin="https://evil.com") == 403
    print("OK server extension: token & origin")

    cfg["speed_limit_kbps"] = 2500; m.apply_settings()
    t7 = m.add(base + "/file", filename="mv.bin", connections=4)
    t0 = time.time()
    while t7.downloaded < 300000 and time.time() - t0 < 10: time.sleep(0.1)
    m.update_task(t7.id, connections=2, save_dir=tmp + "/pindah", filename="baru.bin")
    time.sleep(1.5); cfg["speed_limit_kbps"] = 0; m.apply_settings()
    assert wait(m, t7.id, "completed"), (t7.status, t7.error)
    assert os.path.normpath(t7.final_path) == os.path.normpath(tmp + "/pindah/baru.bin") and sha(t7.final_path) == SHA and t7.connections == 2
    assert not os.path.exists(tmp + "/dl/Lainnya/mv.bin.part")
    print("OK ubah koneksi+lokasi+nama saat berjalan:", t7.final_path)

    m.update_task(t.id, save_dir=tmp + "/arsip", filename="dipindah.bin"); time.sleep(0.8)
    assert os.path.normpath(t.final_path) == os.path.normpath(tmp + "/arsip/dipindah.bin") and os.path.exists(t.final_path) and t.status == "completed"
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

    a = m.add(base + "/file", filename="rm.bin"); wait(m, a.id, "completed"); p = a.final_path
    m.remove(a.id, delete_file=True); time.sleep(0.5); assert not os.path.exists(p); print("OK hapus + file")
    m.shutdown(); print("SEMUA TES LULUS")


if __name__ == "__main__":
    main()
