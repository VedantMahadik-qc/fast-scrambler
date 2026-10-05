"""Challenge 04 'Spin-up', act 3: a quantum reservoir dreams its own sequence of the keyframes.

qrc-image-v1 is trained on the keyframes in story order (Schwarzschild -> Teleblur morph ->
Kerr -> Quantum Blur scramble) and generates new frames as a GIF. Every GIF frame is one of the
vocabulary images, so each is matched back to its full-resolution keyframe; the generated
token sequence (qrc/sequence.json) is what the video plays at 1080p.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # atlas.py lives at the repo root
import atlas  # noqa: E402

OUT = HERE / "qrc"
OUT.mkdir(exist_ok=True)


def keyframes():
    """Story order: name -> 1080p path."""
    frames = [("schwarzschild", HERE / "inputs" / "schwarzschild_1080.png")]
    frames += [(f"tele_{s:.2f}", HERE / "teleblur_masked" / f"tele_{s:.2f}.png") for s in [0.1 * k for k in range(1, 10)]]
    frames += [("kerr", HERE / "inputs" / "kerr_1080.png")]
    frames += [(f"blur_{s:.2f}", HERE / "blur" / f"blur_{s:.2f}.png") for s in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9)]
    return [(n, p) for n, p in frames if p.exists()]


def main(length=96, fps=8, variation=1.0):
    frames = keyframes()
    thumbs = {n: Image.open(p).convert("RGB").resize((320, 180), Image.LANCZOS) for n, p in frames}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, im in thumbs.items():
            b = io.BytesIO()
            im.save(b, "PNG")
            z.writestr(f"{n}.png", b.getvalue())
    vocab = OUT / "vocabulary.zip"
    vocab.write_bytes(buf.getvalue())
    names = [n for n, _ in frames]
    # Story order, there and back, so the reservoir learns spin-up and collapse.
    seq = [f"{n}.png" for n in names + names[-2:0:-1]]
    params = {"training_sequence": seq, "length": length, "fps": fps, "quality": "moderate",
              "variation": variation, "periodic": True, "seed": 2026}
    jid, res, paths = atlas.run("qrc-image-v1", params, {"vocabulary": vocab}, out_dir=OUT, prefix="dream_")
    gif = Image.open(paths["result"])
    ref = {n: np.asarray(im, np.float32) for n, im in thumbs.items()}
    tokens = []
    for fr in ImageSequence.Iterator(gif):
        a = np.asarray(fr.convert("RGB").resize((320, 180)), np.float32)
        tokens.append(min(ref, key=lambda n: np.abs(ref[n] - a).mean()))
    (OUT / "sequence.json").write_text(json.dumps({"job": jid, "params": params, "tokens": tokens}, indent=2))
    print("frames", len(tokens), "distinct", len(set(tokens)))
    print(" ".join(t.replace("tele_", "T").replace("blur_", "B") for t in tokens))


if __name__ == "__main__":
    main()
