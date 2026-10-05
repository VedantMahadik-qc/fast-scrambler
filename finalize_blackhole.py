"""Challenge 01 - submission images for the black-hole entry.

Writes to submission_blackhole/ (disk mask) or submission_blackhole_<mask>/:
  hero.png           the chosen blur-v1 output, untouched (full 8K)
  hero_4k.png/.jpg   same, downsized to 3840x2160 for forms with upload limits
  before_after.png   source render | disk mask | quantum-scrambled result
  detail.png         close-up of the disk, before vs after
  poster_4x3.jpg     4:3 centre crop of the result, for poster/thumbnail use

usage: python finalize_blackhole.py [variant]   default disk_rx0.9_r0.5 (round 1, the entry)
                                                or e.g. sky_rx0.9_r0.5, horizon_rx0.9_r0.5 (round 2)
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BH = HERE / "blackhole"

RENDER = "kerr"
VARIANT = sys.argv[1] if len(sys.argv) > 1 else "disk_rx0.9_r0.5"
MASK_NOTES = {
    "disk": "accretion disk + photon ring; stars and shadow untouched",
    "horizon": "disk mask fading outward: full effect at the shadow's edge",
    "sky": "inverse of the disk: everything except the disk and photon ring",
}
BG, INK, DIM = (6, 5, 12), (230, 225, 240), (150, 140, 175)


def font(px):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            pass
    return ImageFont.load_default()


def tile(img, title, sub, w):
    h = round(img.height * w / img.width)
    t = Image.new("RGB", (w, h + 76), BG)
    t.paste(img.convert("RGB").resize((w, h), Image.LANCZOS), (0, 0))
    d = ImageDraw.Draw(t)
    d.text((4, h + 10), title, fill=INK, font=font(26))
    d.text((4, h + 44), sub, fill=DIM, font=font(19))
    return t


def sheet(tiles, header=None, gap=24, pad=32):
    hh = 64 if header else 0
    s = Image.new("RGB", (sum(t.width for t in tiles) + gap * (len(tiles) - 1) + 2 * pad,
                          max(t.height for t in tiles) + 2 * pad + hh), BG)
    if header:
        ImageDraw.Draw(s).text((pad, pad - 6), header, fill=INK, font=font(32))
    x = pad
    for t in tiles:
        s.paste(t, (x, pad + hh))
        x += t.width + gap
    return s


# Round 2 results live in blackhole/round2/ (keyed by variant), round 1 in blackhole/out/.
r2 = json.loads((BH / "round2" / "jobs.json").read_text())
if VARIANT in r2["params"]:
    params, hero_path = r2["params"][VARIANT], BH / "round2" / f"{RENDER}_{VARIANT}.png"
else:
    params = json.loads((BH / "jobs.json").read_text())["params"][f"{RENDER}_{VARIANT}"]
    hero_path = BH / "out" / f"{RENDER}_{VARIANT}.png"
mask_kind = VARIANT.split("_")[0]
# The disk version is the main entry; other masks get their own folder so nothing is overwritten.
SUB = HERE / ("submission_blackhole" if mask_kind == "disk" else f"submission_blackhole_{mask_kind}")
SUB.mkdir(exist_ok=True)
caption = f"blur-v1  style={params['style']}  strength={params['strength']}  reach={params['reach']}"
print("hero:", RENDER, VARIANT, "|", caption)

src = Image.open(BH / "src" / f"{RENDER}.png").convert("RGB")
mask = Image.open(BH / "src" / f"{RENDER}_{mask_kind}_mask.png").convert("L")
hero = Image.open(hero_path).convert("RGB")
if hero.size != src.size:
    hero = hero.resize(src.size, Image.LANCZOS)
shutil.copyfile(hero_path, SUB / "hero.png")
hero_4k = hero.resize((3840, 2160), Image.LANCZOS)
hero_4k.save(SUB / "hero_4k.png")
hero_4k.save(SUB / "hero_4k.jpg", quality=93, subsampling=0)  # small enough for any upload form
pw = hero.height * 4 // 3
px = (hero.width - pw) // 2
hero.crop((px, 0, px + pw, hero.height)).resize((2400, 1800), Image.LANCZOS).save(SUB / "poster_4x3.jpg", quality=92)

W = 720
sheet([
    tile(src, "1. Source render", "Kerr black hole, spin a = 0.9, from my own simulation, 7680x4320", W),
    tile(mask, "2. Mask", MASK_NOTES[mask_kind], W),
    tile(hero, "3. Result", caption, W),
], header="One image, one engine - Quantum Blur (blur-v1) on a simulated Kerr black hole"
).save(SUB / "before_after.png")

# Disk close-up around the bright approaching side of the disk.
cx, cy = src.width // 2, src.height // 2
box = (cx - 1600, cy - 900, cx + 1600, cy + 900)
sheet([
    tile(src.crop(box), "Before", "central 3200x1800 crop", 900),
    tile(hero.crop(box), "After", f"{mask_kind} mask, {caption}", 900),
]).save(SUB / "detail.png")
print("wrote", SUB)
