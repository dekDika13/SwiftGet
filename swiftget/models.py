"""Model data unduhan dan penyimpanan SQLite."""
from __future__ import annotations
import json, os, sqlite3, threading, time
from dataclasses import dataclass, field, fields, asdict
from urllib.parse import urlparse

ACTIVE = ("preparing", "downloading", "processing", "verifying")


@dataclass
class Task:
    id: int = 0
    url: str = ""
    kind: str = "file"          # file | media
    filename: str = ""
    save_dir: str = ""
    auto_dir: bool = True
    category: str = "Lainnya"
    status: str = "queued"      # queued scheduled preparing downloading processing verifying paused completed error
    total: int = 0
    downloaded: int = 0
    connections: int = 8
    referer: str = ""
    cookies: str = ""
    user_agent: str = ""
    headers: dict = field(default_factory=dict)
    etag: str = ""
    resumable: bool = False
    chunks: list = field(default_factory=list)
    error: str = ""
    added: float = field(default_factory=time.time)
    finished: float = 0.0
    start_at: float = 0.0
    order: float = 0.0
    media_opts: dict = field(default_factory=dict)
    checksum: str = ""
    title: str = ""
    final_path: str = ""
    resolver: str = ""
    dup: str = "number"         # cara menangani nama yang sama: number | replace
    # --- runtime (tidak disimpan) ---
    speed: float = field(default=0.0, repr=False)
    eta: float = field(default=-1.0, repr=False)
    note: str = field(default="", repr=False)

    RUNTIME = ("speed", "eta", "note")

    def to_dict(self):
        d = asdict(self)
        for k in self.RUNTIME:
            d.pop(k, None)
        return d

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    @property
    def name(self) -> str:
        if self.filename:
            return self.filename
        if self.title:
            return self.title
        return os.path.basename(urlparse(self.url).path) or self.url

    @property
    def path(self) -> str:
        return self.final_path or os.path.join(self.save_dir, self.filename)

    @property
    def host(self) -> str:
        return urlparse(self.url).netloc

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE

    def progress(self) -> float:
        if self.status == "completed":
            return 1.0
        return min(1.0, self.downloaded / self.total) if self.total > 0 else -1.0


class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS downloads(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)")
            self.conn.commit()

    def insert(self, t: Task) -> int:
        with self.lock:
            cur = self.conn.execute("INSERT INTO downloads(data) VALUES('{}')")
            t.id = cur.lastrowid
            self.conn.execute("UPDATE downloads SET data=? WHERE id=?", (json.dumps(t.to_dict()), t.id))
            self.conn.commit()
        return t.id

    def update(self, t: Task):
        with self.lock:
            self.conn.execute("UPDATE downloads SET data=? WHERE id=?", (json.dumps(t.to_dict()), t.id))
            self.conn.commit()

    def delete(self, tid: int):
        with self.lock:
            self.conn.execute("DELETE FROM downloads WHERE id=?", (tid,))
            self.conn.commit()

    def load_all(self):
        with self.lock:
            rows = self.conn.execute("SELECT id,data FROM downloads ORDER BY id").fetchall()
        out = []
        for i, data in rows:
            try:
                t = Task.from_dict(json.loads(data))
                t.id = i
                out.append(t)
            except Exception:
                continue
        return out
