"""Bangun aplikasi mandiri: python packaging/build.py   (jalankan di OS target)"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sep = ";" if sys.platform.startswith("win") else ":"
icon = ROOT / "assets" / ("icon.ico" if sys.platform.startswith("win") else "icon.icns" if sys.platform == "darwin" else "icon.png")
cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "SwiftGet",
       "--icon", str(icon), "--add-data", f"{ROOT / 'extension'}{sep}extension",
       "--collect-submodules", "yt_dlp", "--collect-all", "imageio_ffmpeg", "--collect-data", "yt_dlp", "--hidden-import", "PySide6.QtSvg",
       str(ROOT / "run.py")]
sys.exit(subprocess.call(cmd, cwd=ROOT))
