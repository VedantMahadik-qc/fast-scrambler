"""Challenge 01 - round 1: my own black-hole renders through blur-v1, with every parameter recorded.

Sources (7680x4320 frames from my black-hole simulation, in blackhole/src/):
  schwarzschild.png  non-spinning black hole
  kerr.png           Kerr black hole, a = 0.9

Builds a "disk" mask per render (accretion disk + photon ring, dilated and feathered) so the
non-local scramble can be confined to the matter around the horizon while the stars stay crisp.
Submits all variants, waits, downloads to blackhole/out/. Re-running skips finished work.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
import atlas  # noqa: E402

BH = HERE / "blackhole"
SRC = BH / "src"
OUT = BH / "out"
SRC.mkdir(parents=True, exist_ok=True)
OUT.mkdir(exist_ok=True)

RENDERS = ("schwarzschild", "kerr")


def p(strength, reach, style="rx"):
    return {"strength": strength, "reach": reach, "style": style, "size": 1024, "downscale": True}


VARIANTS = {  # name: (params, use disk mask?)
    "rx0.833_r0": (p(0.833, 0.0), False),
    "rx0.833_r0.25": (p(0.833, 0.25), False),
    "rx0.833_r0.5": (p(0.833, 0.5), False),
    "ry0.2_r0": (p(0.2, 0.0, "ry"), False),
    "disk_rx0.9_r0.5": (p(0.9, 0.5), True),
    "disk_rx0.9_r1.0": (p(0.9, 1.0), True),
}


def disk_mask(img):
    """White where the disk/ring glows (grown outward and feathered), black on stars and sky."""
    small = img.convert("L").resize((img.width // 8, img.height // 8), Image.BOX)
    lum = np.asarray(small, np.float32)
    core = Image.fromarray(((lum > 60) * 255).astype(np.uint8))
    core = core.filter(ImageFilter.MinFilter(3))       # drop isolated bright stars
    grown = core.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(8))
    return grown.resize(img.size, Image.BICUBIC)


jobs_file = BH / "jobs.json"
state = json.loads(jobs_file.read_text()) if jobs_file.exists() else {"assets": {}, "jobs": {}, "params": {}}

for name in RENDERS:
    src = SRC / f"{name}.png"
    mask = SRC / f"{name}_disk_mask.png"
    if not mask.exists():
        disk_mask(Image.open(src)).save(mask)
    for key, path in ((name, src), (f"{name}_mask", mask)):
        if key not in state["assets"]:
            state["assets"][key] = atlas.upload(path)
    for v, (params, masked) in VARIANTS.items():
        key = f"{name}_{v}"
        if key in state["jobs"]:
            continue
        files = {"image": f"asset:{state['assets'][name]}"}
        if masked:
            files["mask"] = f"asset:{state['assets'][f'{name}_mask']}"
        jid, _ = atlas.submit("blur-v1", params, files)
        state["jobs"][key] = jid
        state["params"][key] = {**params, "mask": f"{name}_disk_mask.png" if masked else None}
        jobs_file.write_text(json.dumps(state, indent=2))
        print("queued", key, flush=True)


def fetch(key):
    dest = OUT / f"{key}.png"
    if dest.exists():
        return
    jid = state["jobs"][key]
    atlas.wait(jid, timeout=1800, interval=5, verbose=False)
    res = atlas.result(jid)
    atlas.download_asset(res["outputs"][0]["output_asset_id"], dest)
    print("done", key, flush=True)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(fetch, state["jobs"]))
