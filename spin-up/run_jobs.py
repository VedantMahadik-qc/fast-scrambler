"""Challenge 04 'Spin-up': quantum keyframes for the video, all at 1920x1080.

  teleblur/  telablur-v1: Schwarzschild render -> Kerr render, strength 0.1 .. 0.9
  blur/      blur-v1 (rx, reach 0.5) on the Kerr render, masked to the accretion disk,
             strength 0.15 .. 0.9

Sources are the user's own black-hole renders from Challenge 01 (7680x4320, downsized).
Resumable: re-running only submits keyframes that are missing.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # atlas.py lives at the repo root
import atlas  # noqa: E402

SRC = HERE.parent / "01_one_image" / "blackhole" / "src"
IN = HERE / "inputs"
IN.mkdir(exist_ok=True)
for name in ("schwarzschild", "kerr", "kerr_disk_mask"):
    dst = IN / f"{name}_1080.png"
    if not dst.exists():
        im = Image.open(SRC / f"{name}.png")
        im.resize((1920, 1080), Image.LANCZOS).save(dst)

TELE = [round(0.1 * k, 2) for k in range(1, 10)]
BLUR = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9]
jobs_file = HERE / "jobs.json"
jobs = json.loads(jobs_file.read_text()) if jobs_file.exists() else {}

assets = jobs.setdefault("_assets", {})
for name in ("schwarzschild", "kerr", "kerr_disk_mask"):
    if name not in assets:
        assets[name] = atlas.upload(IN / f"{name}_1080.png")

todo = []
for s in TELE:
    key, out = f"teleblur_{s:.2f}", HERE / "teleblur" / f"tele_{s:.2f}.png"
    if not out.exists():
        todo.append((key, out, "telablur-v1", {"strength": s, "size": 1024, "downscale": True},
                     {"image1": f"asset:{assets['schwarzschild']}", "image2": f"asset:{assets['kerr']}"}))
for s in BLUR:
    key, out = f"blur_{s:.2f}", HERE / "blur" / f"blur_{s:.2f}.png"
    if not out.exists():
        todo.append((key, out, "blur-v1", {"style": "rx", "strength": s, "reach": 0.5, "size": 1024, "downscale": True},
                     {"image": f"asset:{assets['kerr']}", "mask": f"asset:{assets['kerr_disk_mask']}"}))

for key, out, eng, params, files in todo:
    if key not in jobs:
        jobs[key] = {"engine": eng, "params": params, "job": atlas.submit(eng, params, files)[0]}
        print("submitted", key, jobs[key]["job"], flush=True)
jobs_file.write_text(json.dumps(jobs, indent=2))


def fetch(item):
    key, out, *_ = item
    jid = jobs[key]["job"]
    try:
        atlas.wait(jid, timeout=3600, interval=5, verbose=False)
        res = atlas.result(jid)
        atlas.download_asset(res["outputs"][0]["output_asset_id"], out)
        print("done", key, flush=True)
    except Exception as e:  # keep the rest going; re-run to resubmit
        print("FAILED", key, str(e)[:300], flush=True)
        jobs.pop(key, None)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(fetch, todo))
jobs_file.write_text(json.dumps(jobs, indent=2))
