"""Konfigurasi, lokasi data, dan kategori file."""
from __future__ import annotations
import json, os, secrets, sys
from pathlib import Path

APP_NAME = "SwiftGet"
def _read_version() -> str:
    """Versi dibaca dari pyproject.toml (satu-satunya sumber). Saat di-build, pyproject.toml ikut dibundel."""
    import re
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    try:
        m = re.search(r'^version\s*=\s*"([^"]+)"', (base / "pyproject.toml").read_text("utf-8"), re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    try:                                              # terpasang lewat "pip install ." tanpa pyproject.toml di sebelahnya
        from importlib.metadata import version
        return version("swiftget")
    except Exception:
        return "0.0.0"


APP_VERSION = _read_version()

# Isi dengan URL halaman toko setelah extension dipublikasikan, maka tombol "Pasang" langsung membuka toko (1 klik).
EXT_STORE = {"chrome": "", "edge": "", "brave": "", "firefox": ""}


def resource_dir() -> Path:
    """Folder sumber daya (extension, aset): folder proyek, atau isi bundel saat sudah di-build."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def export_extension() -> Path:
    """Salin extension ke folder yang mudah ditemukan (~/SwiftGet Extension) dan selalu disegarkan sesuai versi aplikasi."""
    import shutil
    src, dst = resource_dir() / "extension", Path.home() / "SwiftGet Extension"
    shutil.copytree(src, dst, dirs_exist_ok=True)
    return dst


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


OTHER = "Lainnya"
CATEGORIES = {
    "Video": {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg", "ts", "3gp", "m3u8"},
    "Musik": {"mp3", "m4a", "flac", "wav", "aac", "ogg", "opus", "wma", "aiff"},
    "Dokumen": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "epub", "csv", "rtf", "odt", "md", "mobi"},
    "Arsip": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz", "zst"},
    "Program": {"exe", "msi", "dmg", "pkg", "deb", "rpm", "apk", "appimage", "iso", "img", "jar", "bat", "sh", "ipa"},
    "Gambar": {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "tiff", "heic", "psd", "ico"},
}
CATEGORY_NAMES = list(CATEGORIES) + [OTHER]
ALL_EXTS = set().union(*CATEGORIES.values())


def categorize(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return OTHER


DEFAULTS = {
    "download_dir": str(Path.home() / "Downloads" / "SwiftGet"),
    "auto_categorize": True,
    "max_concurrent": 3,
    "connections": 8,
    "media_connections": 1,
    "speed_limit_kbps": 0,
    "retries": 5,
    "timeout": 30,
    "proxy": "",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "theme": "glass",
    "native_glass": False,
    "clipboard_monitor": True,
    "minimize_to_tray": True,
    "notify": True,
    "after_queue": "nothing",  # nothing | quit | sleep | shutdown
    "server_enabled": True,
    "server_port": 6277,
    "token": "",
    "extension_ask": True,  # tampilkan dialog saat extension mengirim unduhan
    "ffmpeg_path": "",
    "cookies_browser": "",
    "video_compat": True,      # True = H.264+AAC (bisa diputar di mana saja), False = kualitas asli VP9/AV1
    "autostart": False,
    "paired_origins": [],
    "onboarded": False,
    "embed_metadata": True,
    "embed_thumbnail": False,
}


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        try:
            self.data.update(json.loads(self.path.read_text("utf-8")))
        except Exception:
            pass
        if not self.data.get("token"):
            self.data["token"] = secrets.token_urlsafe(24)
            self.save()

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def get(self, k, default=None):
        return self.data.get(k, default)

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")
        os.replace(tmp, self.path)
