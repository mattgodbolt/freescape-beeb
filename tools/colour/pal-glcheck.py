"""tools/pal.py against jsbeeb's own PAL shader, run by Chrome's WebGL.

    python -I tools/colour/pal-glcheck.py JSBEEB_CHECKOUT WORKDIR

makes a test picture (MODE 2 pixels of random colours, then the colour
study's patterns, lines doubled as jsbeeb doubles them), has
pal-glcheck.mjs render it through the shader for several subcarrier phases
and line parities, and compares the bytes with tools/pal.py's. The shader
runs in single precision and writes bytes, so the two may differ by a
step or two of 255; it prints the largest difference and the share of
bytes that differ at all, and fails beyond MAX_DIFF.

Not part of `make check`: it needs a jsbeeb source checkout with its
node_modules (Playwright) and Chrome.
"""

import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import pal  # noqa: E402
import patterns as P  # noqa: E402

MAX_DIFF = 3  # of 255


def picture(rows=48):
    rng = np.random.default_rng(8)
    lines = rows // 2
    px = rng.integers(0, 8, size=(lines, 256))
    # The right half: the study's two-colour patterns, eight pixels each.
    cands = P.candidates("pair")
    for k in range(128, 256, 2):
        p = cands[(k * 7) % len(cands)].pixels
        for y in range(lines):
            px[y, k:k + 2] = p[2 * (y % 4):2 * (y % 4) + 2]
    rgb = np.array(P.BBC, dtype=np.uint8)[px]
    return pal.expand(rgb, 4, 2)


def main(checkout, work):
    os.makedirs(work, exist_ok=True)
    fb = picture()
    h, w, _ = fb.shape
    cases = [{"phase": p, "line": l} for p, l in
             ((0.0, 0), (0.25, 1), (0.6180339, 0), (0.9, 17))]
    inp = os.path.join(work, "pal-in.json")
    outp = os.path.join(work, "pal-out.json")
    with open(inp, "w") as f:
        json.dump({"width": w, "height": h, "rgb": fb.reshape(-1).tolist(),
                   "cases": cases}, f)
    subprocess.run(["node", os.path.join(HERE, "pal-glcheck.mjs"), checkout,
                    inp, outp], check=True)
    got = json.load(open(outp))
    worst = 0
    for c, res in zip(cases, got["results"]):
        gl = np.array(res, dtype=int).reshape(h, w, 3)
        ours = pal.decode(fb / 255.0, c["phase"], c["line"])
        ours = (ours * 255 + 0.5).astype(int)
        d = np.abs(gl - ours)
        worst = max(worst, int(d.max()))
        print(f"phase {c['phase']} line {c['line']}: largest difference "
              f"{d.max()}, bytes differing {np.mean(d > 0):.2%}, "
              f"mean {d.mean():.3f}")
    print(f"pal-glcheck: largest difference {worst} of 255 "
          f"(allowed {MAX_DIFF}) on {got['renderer']}")
    return 0 if worst <= MAX_DIFF else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
