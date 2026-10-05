"""Challenge 01 - second, focused blur-v1 round on the Kerr render.

Round 1 (blackhole.py) showed that masking is what makes the scramble read as a picture.
This round varies the mask itself and the brightness/block structure of the disk scramble:
  disk     - accretion disk + photon ring (round 1's mask)
  horizon  - disk mask x radial falloff: full effect at the shadow, fading outward
  sky      - inverse of the disk mask: scramble the lensed starfield, keep the disk sharp
Reuses round 1's uploaded render and disk mask; results go to blackhole/round2/.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
import atlas  # noqa: E402

BH = HERE / "blackhole"
OUT = BH / "round2"
OUT.mkdir(exist_ok=True)
round1 = json.loads((BH / "jobs.json").read_text())["assets"]


def p(strength, reach, style="rx", **kw):
    return {"strength": strength, "reach": reach, "style": style, "size": 1024, "downscale": True, **kw}


VARIANTS = {  # name: (params, mask)
    "disk_rx0.6_r0.5": (p(0.6, 0.5), "disk"),
    "disk_rx0.75_r0.5": (p(0.75, 0.5), "disk"),
    "disk_rx0.9_r0.25": (p(0.9, 0.25), "disk"),
    "disk_ry0.3_r0.5": (p(0.3, 0.5, "ry"), "disk"),
    "disk_rx0.9_r0.5_tiled": (p(0.9, 0.5, downscale=False), "disk"),
    "disk_rx0.9_r0.5_size256": (p(0.9, 0.5, size=256), "disk"),
    "horizon_rx0.9_r0.5": (p(0.9, 0.5), "horizon"),
    "sky_rx0.9_r0.5": (p(0.9, 0.5), "sky"),
}

disk = Image.open(BH / "src" / "kerr_disk_mask.png").convert("L")
masks = {"disk": BH / "src" / "kerr_disk_mask.png",
         "horizon": BH / "src" / "kerr_horizon_mask.png",
         "sky": BH / "src" / "kerr_sky_mask.png"}
if not masks["horizon"].exists():
    # Radial falloff centred on the disk's centroid, reaching zero just past the outer disk.
    d = np.asarray(disk, np.float32) / 255
    ys, xs = np.nonzero(d > 0.5)
    cy, cx = ys.mean(), xs.mean()
    ring_r = np.percentile(np.hypot(xs - cx, (ys - cy) * 1.0), 60)
    yy, xx = np.mgrid[0:d.shape[0], 0:d.shape[1]]
    fall = np.clip(1.15 - np.hypot(xx - cx, yy - cy) / (2.2 * ring_r), 0, 1) ** 1.5
    Image.fromarray((d * fall * 255).astype(np.uint8)).save(masks["horizon"])
if not masks["sky"].exists():
    ImageOps.invert(disk).save(masks["sky"])
if "--masks-only" in sys.argv:
    sys.exit(print("masks written"))

jobs_file = OUT / "jobs.json"
state = json.loads(jobs_file.read_text()) if jobs_file.exists() else {"assets": {}, "jobs": {}, "params": {}}
state["assets"].setdefault("kerr", round1["kerr"])
state["assets"].setdefault("disk", round1["kerr_mask"])
for m in ("horizon", "sky"):
    if m not in state["assets"]:
        state["assets"][m] = atlas.upload(masks[m])

for name, (params, m) in VARIANTS.items():
    if name in state["jobs"]:
        continue
    jid, _ = atlas.submit("blur-v1", params, {"image": f"asset:{state['assets']['kerr']}",
                                               "mask": f"asset:{state['assets'][m]}"})
    state["jobs"][name] = jid
    state["params"][name] = {**params, "mask": masks[m].name}
    jobs_file.write_text(json.dumps(state, indent=2))
    print("queued", name, flush=True)


def fetch(name):
    dest = OUT / f"kerr_{name}.png"
    if dest.exists():
        return
    try:
        atlas.wait(state["jobs"][name], timeout=900, interval=5, verbose=False)
        res = atlas.result(state["jobs"][name])
        atlas.download_asset(res["outputs"][0]["output_asset_id"], dest)
        print("done", name, flush=True)
    except Exception as e:
        print("not done", name, str(e)[:150], flush=True)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(fetch, state["jobs"]))
