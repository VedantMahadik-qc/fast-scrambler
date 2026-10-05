"""Challenge 01 - try the other image engines (Tessa, Deep Fryer) on the Kerr render.

Both work tile-by-tile / cell-by-cell, so the 8K render is downsized to 1920x1080 first.
Submits everything, then waits and downloads to blackhole/engines/. Re-running skips finished
work; jobs that are still pending are left alone (re-run later to collect them).
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
import atlas  # noqa: E402

BH = HERE / "blackhole"
OUT = BH / "engines"
OUT.mkdir(exist_ok=True)
SIZE = (1920, 1080)

img = OUT / "kerr_1080p.png"
mask = OUT / "kerr_disk_mask_1080p.png"
if not img.exists():
    Image.open(BH / "src" / "kerr.png").convert("RGB").resize(SIZE, Image.LANCZOS).save(img)
    Image.open(BH / "src" / "kerr_disk_mask.png").convert("L").resize(SIZE, Image.LANCZOS).save(mask)

RUNS = {  # name: (engine, params, use mask?)
    "tessa_aer_d0": ("tessa-image-v1", {"machine": "aer", "distortion": 0}, False),
    "tessa_aer_d0.5_XZ": ("tessa-image-v1", {"machine": "aer", "distortion": 0.5, "gate_pauli": "XZ"}, False),
    "tessa_aer_d1.5_ZZ": ("tessa-image-v1", {"machine": "aer", "distortion": 1.5, "gate_pauli": "ZZ"}, False),
    "tessa_fakefez_d0": ("tessa-image-v1", {"machine": "fake_fez", "distortion": 0}, False),
    "tessa_ibm_d0.5_XZ": ("tessa-image-v1", {"machine": "least_busy", "distortion": 0.5, "gate_pauli": "XZ"}, False),
    "fryer_rx0.5": ("deep-fryer-v1", {"gates": [["rx", 0.5]]}, True),
    "fryer_h_rzz0.6": ("deep-fryer-v1", {"gates": [["h", 1.0], ["rzz", 0.6]]}, True),
    "fryer_ry0.6_cx_rz0.4": ("deep-fryer-v1", {"gates": [["ry", 0.6], ["cx", 1.0], ["rz", 0.4]]}, True),
}

jobs_file = OUT / "jobs.json"
state = json.loads(jobs_file.read_text()) if jobs_file.exists() else {"assets": {}, "jobs": {}, "params": {}}
for key, path in (("image", img), ("mask", mask)):
    if key not in state["assets"]:
        state["assets"][key] = atlas.upload(path)

for name, (engine, params, masked) in RUNS.items():
    if name in state["jobs"]:
        continue
    files = {"image": f"asset:{state['assets']['image']}"}
    if masked:
        files["mask"] = f"asset:{state['assets']['mask']}"
    try:
        jid, _ = atlas.submit(engine, params, files)
    except RuntimeError as e:
        print("REJECTED", name, str(e)[:300], flush=True)
        continue
    state["jobs"][name] = jid
    state["params"][name] = {"engine": engine, **params, "mask": mask.name if masked else None}
    jobs_file.write_text(json.dumps(state, indent=2))
    print("queued", name, flush=True)


def fetch(name):
    dest = OUT / f"{name}.png"
    if dest.exists():
        return
    jid = state["jobs"][name]
    try:
        atlas.wait(jid, timeout=900, interval=5, verbose=False)
        res = atlas.result(jid)
        atlas.download_asset(res["outputs"][0]["output_asset_id"], dest)
        print("done", name, flush=True)
    except Exception as e:  # still queued, or failed - report and move on
        print("not done", name, str(e)[:200], flush=True)


with ThreadPoolExecutor(8) as ex:
    list(ex.map(fetch, state["jobs"]))
