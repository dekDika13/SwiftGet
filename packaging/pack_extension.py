"""Kemas extension untuk toko: python packaging/pack_extension.py
Hasil: dist/extension/swiftget-chrome-edge.zip (Chrome Web Store, Edge Add-ons, Brave) dan swiftget-firefox.zip (addons.mozilla.org)."""
import json, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "extension", ROOT / "dist" / "extension"


def build(name, edit):
    m = json.loads((SRC / "manifest.json").read_text("utf-8"))
    edit(m)
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT / name, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m, indent=2, ensure_ascii=False))
        for f in SRC.rglob("*"):
            if f.is_file() and f.name != "manifest.json":
                z.write(f, f.relative_to(SRC).as_posix())
    print("dibuat:", OUT / name)


def chromium(m):
    m["background"] = {"service_worker": "background.js"}
    m.pop("browser_specific_settings", None)


def firefox(m):
    m["background"] = {"scripts": ["background.js"]}


if __name__ == "__main__":
    build("swiftget-chrome-edge.zip", chromium)
    build("swiftget-firefox.zip", firefox)
