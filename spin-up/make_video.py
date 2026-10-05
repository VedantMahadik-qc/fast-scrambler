"""Render 'Spin-up' (Challenge 04): quantum keyframes cut to Superposition.

  python make_video.py            -> spin-up.mp4 (1920x1080, 30 fps)
  python make_video.py --stills   -> stills/ (a frame every 2 s, for checking)

Act 1  (intro + build)  Teleblur morph, Schwarzschild -> Kerr, crossfaded keyframes, slow push-in
Act 2  (drop 1)         Quantum Blur scramble, a cut on every kick, strength rising through the drop
Act 3  (break, build 2) the QRC reservoir's generated sequence, slow then accelerating
       (final drop)     the reservoir's sequence cut on every kick and snare
End                     settle on the full scramble, fade
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
# Soundtrack + drum timing come from the Superposition project
# (github.com/VedantMahadik-qc/superposition, folder 02_audible/superposition).
import os  # noqa: E402
SUP = Path(os.environ.get("SUPERPOSITION_DIR", HERE.parent.parent / "superposition" / "02_audible" / "superposition"))
sys.path.insert(0, str(SUP.parent))
from synth import midi_notes  # noqa: E402

W, H, FPS = 1920, 1080, 30
S = dict(build=6.857, drop1=20.571, quantum=27.429, brk=34.286, build2=41.143,
         gap=46.975, drop2=47.78, end=60.58, track=74.58)
AUDIO = Path(os.environ.get("SUPERPOSITION_WAV", SUP / "submission" / "superposition.wav"))
TOTAL = S["track"] + 5.0

FONTS = Path("C:/Windows/Fonts")
F = lambda n, s: ImageFont.truetype(str(FONTS / n), s)  # noqa: E731
INK, DIM, HOT, TEAL = (236, 236, 244), (150, 150, 175), (255, 64, 129), (0, 210, 200)

TELE = [0.1 * k for k in range(1, 10)]
BLUR = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9]


def load(p):
    return np.asarray(Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS), np.float32)


FR = {"schwarzschild": load(HERE / "inputs" / "schwarzschild_1080.png"),
      "kerr": load(HERE / "inputs" / "kerr_1080.png")}
for s in TELE:
    FR[f"tele_{s:.2f}"] = load(HERE / "teleblur_masked" / f"tele_{s:.2f}.png")
for s in BLUR:
    FR[f"blur_{s:.2f}"] = load(HERE / "blur" / f"blur_{s:.2f}.png")
ACT1 = ["schwarzschild"] + [f"tele_{s:.2f}" for s in TELE] + ["kerr"]
DREAM = json.loads((HERE / "qrc" / "sequence.json").read_text())
TOKENS = DREAM["tokens"]

drums = midi_notes(SUP / "midi" / "superposition_hype_fixed.mid")["drums"]
KICKS = sorted(s for s, d, p, v in drums if p == 36)
HITS = sorted(s for s, d, p, v in drums if p in (36, 38))


def label(name):
    if name == "schwarzschild":
        return "source: Schwarzschild (no spin)"
    if name == "kerr":
        return "source: Kerr, spin a = 0.9"
    if name.startswith("tele_"):
        return f"telablur-v1 · strength {float(name[5:]):.1f}"
    return f"blur-v1 · rx · disk mask · strength {float(name[5:]):.2f}"


def zoom(a, z, cx=0.5, cy=0.5):
    if z <= 1.0001:
        return a
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    w, h = W / z, H / z
    x0, y0 = (W - w) * cx, (H - h) * cy
    return np.asarray(im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h)), np.float32)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def since(times, t):
    """Seconds since the last event at or before t (large if none)."""
    i = np.searchsorted(times, t, side="right") - 1
    return t - times[i] if i >= 0 else 1e9, i


def frame_at(t):
    """-> (image array, caption title, caption body, current token or None)."""
    if t < S["drop1"]:                                  # act 1: spin-up
        u = max(0.0, t - 4.0) / (S["drop1"] - 4.0) * (len(ACT1) - 1)   # hold the still hole under the title
        i = min(int(u), len(ACT1) - 2)
        f = ease(u - i)
        a = FR[ACT1[i]] * (1 - f) + FR[ACT1[i + 1]] * f
        name = ACT1[i + (f > 0.5)]
        return zoom(a, 1.0 + 0.12 * t / S["drop1"]), "1 · SPIN-UP", "Quantum Teleblur morphs a still black hole into a spinning one", name
    if t < S["brk"]:                                    # act 2: scramble on the kicks
        dk, k = since(KICKS, t)
        first = np.searchsorted(KICKS, S["drop1"] - 1e-3)
        n = max(0, k - first)
        name = f"blur_{BLUR[min(len(BLUR) - 1, n // 4)]:.2f}"
        a = FR[name] * (1 + 0.35 * np.exp(-dk * 9))   # flash on the kick
        return zoom(a, 1.06 + 0.05 * np.exp(-dk * 7)), "2 · SCRAMBLE", "Quantum Blur breaks only the accretion disk, harder with every bar", name
    if t < S["gap"]:                                    # act 3a: the reservoir dreams, accelerating
        u = (t - S["brk"]) / (S["gap"] - S["brk"])
        rate = 2.0 + 10.0 * u ** 2                      # tokens per second
        pos = 2.0 * (t - S["brk"]) + 10.0 / 3.0 * (S["gap"] - S["brk"]) * u ** 3
        i = int(pos) % len(TOKENS)
        f = ease((pos - int(pos)) * 3) if rate < 5 else 0.0
        a = FR[TOKENS[i]] * (1 - f) + FR[TOKENS[(i + 1) % len(TOKENS)]] * f
        return zoom(a, 1.04), "3 · DREAM", "a quantum reservoir (qrc-image-v1) trained on these frames generates its own sequence", TOKENS[i]
    if t < S["drop2"]:
        return np.zeros((H, W, 3), np.float32), None, None, None
    if t < S["end"]:                                    # final drop: reservoir cut on kicks + snares
        dh, h = since(HITS, t)
        first = np.searchsorted(HITS, S["drop2"] - 1e-3)
        name = TOKENS[(40 + h - first) % len(TOKENS)]
        a = FR[name] * (1 + 0.3 * np.exp(-dh * 10))
        return zoom(a, 1.05 + 0.06 * np.exp(-dh * 8)), "3 · DREAM", "the reservoir's sequence, cut to the final drop", name
    f = ease((t - S["end"]) / 3.0)                      # settle
    a = FR["blur_0.90"] * (1 - 0.55 * ease((t - S["track"] + 4) / 4))
    return zoom(a, 1.05 - 0.05 * f), "", "", "blur_0.90"


def overlay(img, t, title, body, token):
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    if t < 5.5:                                         # opening title, alpha-blended below the hole
        a = int(255 * ease(t / 1.0) * ease((5.5 - t) / 0.8))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.text((W // 2, 880), "SPIN-UP", font=F("segoeuib.ttf", 130), fill=INK + (a,), anchor="mm")
        ld.text((W // 2, 975), "a black hole, spun up and scrambled by quantum circuits",
                font=F("segoeuil.ttf", 42), fill=DIM + (a,), anchor="mm")
        im = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")
        d = ImageDraw.Draw(im)
    elif title:
        d.rectangle([0, 0, W, 130], fill=(0, 0, 0))
        d.text((60, 40), title, font=F("segoeuib.ttf", 46), fill=HOT if "DREAM" in title or "SCRAMBLE" in title else INK)
        d.text((60 + d.textlength(title, font=F("segoeuib.ttf", 46)) + 28, 52), body, font=F("segoeuil.ttf", 32), fill=DIM)
    if token and t >= 5.5 and t < S["track"]:
        d.rectangle([0, H - 70, W, H], fill=(0, 0, 0))
        d.text((60, H - 52), label(token), font=F("consola.ttf", 30), fill=TEAL)
        d.text((W - 60, H - 52), "Moth_Hack 2026 · Challenge 04", font=F("consola.ttf", 26), fill=(90, 90, 115), anchor="ra")
    if S["brk"] <= t < S["end"] and title and "DREAM" in title:   # token strip of the generated sequence
        y = H - 104
        for k, tok in enumerate(TOKENS[:96]):
            x = 60 + k * 18
            c = TEAL if tok.startswith("tele") else HOT if tok.startswith("blur") else INK
            d.rectangle([x, y, x + 12, y + 18], fill=c if tok == token else tuple(v // 3 for v in c))
    if t >= S["track"]:                                 # closing card
        a = ease((t - S["track"]) / 1.0)
        d.rectangle([0, 0, W, H], fill=(int(9 * a), int(9 * a), int(18 * a)))
        cc = lambda col: tuple(int(v * a) for v in col)  # noqa: E731
        d.text((W // 2, 400), "SPIN-UP", font=F("segoeuib.ttf", 120), fill=cc(INK), anchor="mm")
        d.text((W // 2, 520), "telablur-v1  ·  blur-v1  ·  qrc-image-v1   on Moth Atlas", font=F("segoeui.ttf", 40), fill=cc(HOT), anchor="mm")
        d.text((W // 2, 590), "source renders: my own Schwarzschild + Kerr black-hole simulation", font=F("segoeuil.ttf", 32), fill=cc(DIM), anchor="mm")
        d.text((W // 2, 640), "music: Superposition (Blur Jazz + Retrocausal Echo)", font=F("segoeuil.ttf", 32), fill=cc(DIM), anchor="mm")
        d.text((W // 2, 760), "Moth_Hack 2026 · Challenge 04: Moving image", font=F("consola.ttf", 30), fill=cc(DIM), anchor="mm")
    return im


def main():
    stills = "--stills" in sys.argv
    n = int(TOTAL * FPS)
    if stills:
        (HERE / "stills").mkdir(exist_ok=True)
        for f in range(0, n, FPS * 2):
            t = f / FPS
            overlay(*frame_at(t)[:1], t, *frame_at(t)[1:]).save(HERE / "stills" / f"s{f:05d}.jpg", quality=88)
        return
    out = HERE / "spin-up.mp4"
    # Pad the track with silence to the video length up front: ffmpeg's apad filter with a
    # piped video input never ends on the old local ffmpeg build.
    from scipy.io import wavfile
    sr, x = wavfile.read(AUDIO)
    padded = HERE / "_audio_padded.wav"
    wavfile.write(padded, sr, np.pad(x, ((0, max(0, int(TOTAL * sr) - len(x))), (0, 0)))[: int(TOTAL * sr)])
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(padded),
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-strict", "-2", "-b:a", "256k", "-shortest", str(out)],
                          stdin=subprocess.PIPE)
    for f in range(n):
        t = f / FPS
        if f % 300 == 0:
            print(f"frame {f}/{n}", flush=True)
        img, title, body, token = frame_at(t)
        ff.stdin.write(overlay(img, t, title, body, token).tobytes())
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("ffmpeg failed")
    print("wrote", out, f"{n / FPS:.1f}s")


if __name__ == "__main__":
    main()
