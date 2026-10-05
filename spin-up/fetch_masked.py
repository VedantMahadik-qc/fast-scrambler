"""Collect the masked Teleblur sweep (mask = both renders' disk masks, dilated) into teleblur_masked/."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # atlas.py lives at the repo root
import atlas  # noqa: E402

jobs = {k: v for k, v in json.loads((HERE / "jobs_masked.json").read_text()).items() if not k.startswith("_")}


def fetch(key):
    out = HERE / "teleblur_masked" / f"tele_{key.rsplit('_', 1)[1]}.png"
    if out.exists():
        return
    try:
        atlas.wait(jobs[key]["job"], timeout=3600, interval=5, verbose=False)
        atlas.download_asset(atlas.result(jobs[key]["job"])["outputs"][0]["output_asset_id"], out)
        print("done", key, flush=True)
    except Exception as e:
        print("FAILED", key, str(e)[:300], flush=True)


with ThreadPoolExecutor(9) as ex:
    list(ex.map(fetch, jobs))
