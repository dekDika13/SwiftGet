"""Bangun & kemas SwiftGet: python packaging/build.py [--no-package]

Hasil akhir ada di dist/release/:
  Windows : SwiftGet-Setup-<versi>.exe (installer, butuh Inno Setup) + SwiftGet-<versi>-windows-portable.zip
  macOS   : SwiftGet-<versi>-macos-<arsitektur>.dmg (seret ke Applications)
  Linux   : SwiftGet-<versi>-linux-<arsitektur>.tar.gz
Harus dijalankan di OS target.
"""
import platform, re, shutil, subprocess, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUT = DIST / "release"
VERSION = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text("utf-8"), re.M).group(1)
WIN, MAC = sys.platform.startswith("win"), sys.platform == "darwin"
ARCH = platform.machine().lower().replace("amd64", "x86_64")


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)))
    subprocess.check_call(cmd, **kw)


def version_file() -> Path:
    a, b, c = (VERSION.split(".") + ["0", "0"])[:3]
    p = ROOT / "build" / "version_info.txt"
    p.parent.mkdir(exist_ok=True)
    p.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a},{b},{c},0), prodvers=({a},{b},{c},0), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),
  kids=[StringFileInfo([StringTable('040904B0', [StringStruct('CompanyName', 'SwiftGet'),
    StringStruct('FileDescription', 'SwiftGet Download Manager'), StringStruct('FileVersion', '{VERSION}'),
    StringStruct('InternalName', 'SwiftGet'), StringStruct('OriginalFilename', 'SwiftGet.exe'),
    StringStruct('ProductName', 'SwiftGet'), StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding="utf-8")
    return p


def pyinstaller():
    sep = ";" if WIN else ":"
    icon = ROOT / "assets" / ("icon.ico" if WIN else "icon.icns" if MAC else "icon.png")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "SwiftGet",
           "--icon", str(icon), "--add-data", f"{ROOT / 'extension'}{sep}extension",
           "--add-data", f"{ROOT / 'pyproject.toml'}{sep}.",
           "--collect-submodules", "yt_dlp", "--collect-all", "yt_dlp_ejs", "--collect-all", "imageio_ffmpeg",
           "--hidden-import", "PySide6.QtSvg"]
    if WIN:
        cmd += ["--version-file", str(version_file())]
    if MAC:
        cmd += ["--osx-bundle-identifier", "com.swiftget.app"]
    run(cmd + [str(ROOT / "run.py")], cwd=ROOT)


def package_windows():
    app = DIST / "SwiftGet"
    shutil.make_archive(str(OUT / f"SwiftGet-{VERSION}-windows-portable"), "zip", DIST, "SwiftGet")
    iscc = shutil.which("iscc") or next((p for p in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                                                       r"C:\Program Files\Inno Setup 6\ISCC.exe") if Path(p).exists()), None)
    if not iscc:
        print("! Inno Setup tidak ditemukan; installer dilewati (unduh di https://jrsoftware.org/isdl.php)")
        return
    run([iscc, f"/DAppVersion={VERSION}", f"/O{OUT}", str(ROOT / "packaging" / "windows" / "swiftget.iss")], cwd=ROOT)
    assert app.exists()


def package_macos():
    app = DIST / "SwiftGet.app"
    subprocess.call(["codesign", "--force", "--deep", "--sign", "-", str(app)])   # ad-hoc agar bisa jalan di Apple Silicon
    stage = DIST / "dmg"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()
    shutil.copytree(app, stage / "SwiftGet.app", symlinks=True)
    (stage / "Applications").symlink_to("/Applications")
    run(["hdiutil", "create", "-volname", "SwiftGet", "-srcfolder", str(stage), "-ov", "-format", "UDZO",
         str(OUT / f"SwiftGet-{VERSION}-macos-{ARCH}.dmg")])


def package_linux():
    with tarfile.open(OUT / f"SwiftGet-{VERSION}-linux-{ARCH}.tar.gz", "w:gz") as t:
        t.add(DIST / "SwiftGet", arcname="SwiftGet")


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    pyinstaller()
    if "--no-package" not in sys.argv:
        (package_windows if WIN else package_macos if MAC else package_linux)()
    print("\nSelesai. Hasil di:", OUT)
    for f in sorted(OUT.iterdir()):
        print("  ", f.name)
