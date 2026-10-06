"""Membuat ikon aplikasi & extension: python packaging/make_icons.py (butuh Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def draw(size):
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gp = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            gp[x, y] = (int(59 + (14 - 59) * t), int(130 + (165 - 130) * t), int(246 + (233 - 246) * t), 255)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.235), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = max(2, int(S * 0.078))
    pts = lambda *p: [(S * a / 64, S * b / 64) for a, b in p]
    for seg in (pts((32, 15), (32, 39)), pts((21, 29), (32, 40), (43, 29)), pts((20, 48), (44, 48))):
        d.line(seg, fill="white", width=w, joint="curve")
        for x, y in (seg[0], seg[-1]):
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill="white")
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    for s in (16, 32, 48, 128):
        draw(s).save(ROOT / "extension" / "icons" / f"{s}.png")
    big = draw(512)
    big.save(ROOT / "assets" / "icon.png")
    big.save(ROOT / "assets" / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    try:
        big.save(ROOT / "assets" / "icon.icns")
    except Exception as e:
        print("ICNS dilewati:", e)
    print("ikon dibuat")
