"""Server HTTP lokal (127.0.0.1) untuk komunikasi dengan extension browser."""
from __future__ import annotations
import json, secrets, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import APP_NAME, APP_VERSION

EXT_ORIGINS = ("chrome-extension://", "moz-extension://", "safari-web-extension://")


class LocalServer:
    def __init__(self, cfg, handler, pair=None):
        """pair(origin) -> token | None. Dipanggil saat extension meminta terhubung (menunggu persetujuan pengguna)."""
        self.cfg, self.handler, self.pair, self.httpd = cfg, handler, pair, None

    def start(self):
        outer = self

        class H(BaseHTTPRequestHandler):
            server_version = APP_NAME

            def log_message(self, *a):
                pass

            def _send(self, code, obj=None):
                body = json.dumps(obj or {}).encode()
                self.send_response(code)
                origin = self.headers.get("Origin", "")
                if origin.startswith(EXT_ORIGINS):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Access-Control-Allow-Headers", "Content-Type, X-SwiftGet-Token")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.send_header("Vary", "Origin")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _guard(self):
                host = self.headers.get("Host", "").rsplit(":", 1)[0]
                origin = self.headers.get("Origin", "")
                if host not in ("127.0.0.1", "localhost") or (origin and not origin.startswith(EXT_ORIGINS)):
                    self._send(403, {"ok": False, "error": "forbidden"})
                    return False
                return True

            def _authed(self):
                return secrets.compare_digest(self.headers.get("X-SwiftGet-Token", ""), outer.cfg["token"])

            def do_OPTIONS(self):
                if self._guard():
                    self._send(204)

            def do_GET(self):
                if not self._guard():
                    return
                if self.path.startswith("/ping"):
                    self._send(200, {"ok": True, "app": APP_NAME, "version": APP_VERSION, "auth": self._authed()})
                else:
                    self._send(404, {"ok": False})

            def do_POST(self):
                if not self._guard():
                    return
                route = self.path.split("?")[0].strip("/")
                if route == "pair":
                    origin = self.headers.get("Origin", "")
                    if not origin.startswith(EXT_ORIGINS) or not outer.pair:
                        return self._send(403, {"ok": False, "error": "hanya extension browser yang boleh"})
                    token = outer.pair(origin)
                    return self._send(200, {"ok": True, "token": token}) if token else self._send(403, {"ok": False, "error": "ditolak"})
                if not self._authed():
                    return self._send(401, {"ok": False, "error": "token salah"})
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > 1_000_000:
                        return self._send(413, {"ok": False})
                    data = json.loads(self.rfile.read(n) or b"{}")
                    if route not in ("add", "media"):
                        return self._send(404, {"ok": False})
                    outer.handler(route, data)
                    self._send(200, {"ok": True})
                except Exception as e:
                    self._send(400, {"ok": False, "error": str(e)})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", int(self.cfg["server_port"])), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
