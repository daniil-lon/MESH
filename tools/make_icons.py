"""Generate maskable (dark, full-bleed) icons and apple-touch icons.

Strategy: extract the white logo from the existing icon by per-pixel
"whiteness" (min channel), then composite it onto a dark indigo gradient
that fills the whole square (maskable safe for rounded/circular masks).
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "icons"

TOP = (30, 27, 75)      # #1e1b4b
BOTTOM = (76, 29, 149)  # #4c1d95


def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = round(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = round(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = round(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def logo_mask(src, size):
    small = src.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size))
    mp = mask.load()
    sp = small.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = sp[x, y]
            if a < 20:
                mp[x, y] = 0
                continue
            mn = min(r, g, b)
            v = int((mn - 90) / (205 - 90) * 255)
            mp[x, y] = max(0, min(255, v)) if a > 200 else 0
    return mask


def make_maskable(src, size, out):
    bg = gradient(size)
    white = Image.new("RGB", (size, size), (255, 255, 255))
    bg.paste(white, (0, 0), logo_mask(src, size))
    bg.save(out, "PNG")
    print("wrote", out.name, out.stat().st_size, "bytes")


def main():
    src = Image.open(ICONS / "icon-512.png").convert("RGBA")
    make_maskable(src, 192, ICONS / "maskable-192.png")
    make_maskable(src, 512, ICONS / "maskable-512.png")
    for size in (120, 152, 167, 180):
        make_maskable(src, size, ICONS / f"apple-touch-icon-{size}.png")


if __name__ == "__main__":
    main()
