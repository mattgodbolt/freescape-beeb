"""Checks on the colour study's output (make colour-check).

    python -I tools/colour/check.py SOURCES.json COLOURDIR

- The MODE 2 byte layout is docs/engine.md's: the left pixel's colour bits
  3-0 in bits 7, 5, 3 and 1, the right pixel's in 6, 4, 2 and 0.
- There is a table for each display (bbc-rgb.json, bbc-pal.json and
  bbc-both.json in COLOURDIR), all from one version, with the same face
  colours.
- In each, every area has fifteen patterns, a sky and a ground, each four
  bytes, and every pixel in them is a steady colour, 0-7 (8-15 flash).
- Each table's patterns are what its display's scoring picks: design.choose
  for the colours the area's faces use, patterns.best for the rest.
- In each area, two colours that its faces use and that differ by more
  than design.SAME have different patterns.
- tools/model/colours.py gives what each table holds, for its display named
  and as the default (FREESCAPE_DISPLAY, else PAL).
- tools/pal.py's filters pass DC, and it gives a field of one colour back.
"""

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
import design  # noqa: E402
import patterns as P  # noqa: E402
from tools.model import colours  # noqa: E402

failures = []


def check(ok, what):
    if not ok:
        failures.append(what)


def main(src_path, colour_dir):
    # The byte layout, pixel by pixel.
    for c in range(16):
        left = P.mode2_byte(c, 0)
        right = P.mode2_byte(0, c)
        want_l = sum(((c >> k) & 1) << (2 * k + 1) for k in range(4))
        check(left == want_l and right == want_l >> 1,
              f"MODE 2 byte for colour {c}: {left:02x} {right:02x}")
        check(left & 0x55 == 0 and right & 0xAA == 0,
              f"colour {c} spills into the other pixel")
    check(P.from_bytes(P.to_bytes(list(range(8)))) == list(range(8)),
          "to_bytes and from_bytes disagree")

    # tools/pal.py: its filters pass DC, and a field of one BBC colour
    # comes back as that colour (to the quantisation of a byte, as the
    # shader writes it), away from the picture's edges.
    import pal
    check(abs(pal.CHROMA.sum() - 1) < 1e-12 and abs(pal.LUMA.sum() - 1) < 1e-12,
          "PAL filters don't sum to one")
    for c in range(8):
        field = np.tile(np.array(P.BBC[c], dtype=float) / 255, (16, 128, 1))
        out = pal.decode(field, 0.3, 1)[4:-4, 32:-32]
        err = np.abs(out - field[4:-4, 32:-32]).max() * 255
        check(err < 2.5, f"PAL changes a field of colour {c} by {err:.1f}/255")

    src = json.load(open(src_path))
    tables = {d: json.load(open(os.path.join(colour_dir, f"bbc-{d}.json")))
              for d in colours.DISPLAYS}
    v = tables["pal"]["version"]
    scheme = design.VARIANTS[design.CHOSEN[1]][0]
    cands = P.candidates(scheme)
    check(all(t["version"] == v and t["display"] == d
              for d, t in tables.items()), "the tables' versions disagree")
    check(colours.DISPLAY == os.environ.get("FREESCAPE_DISPLAY", "pal"),
          "colours.DISPLAY isn't FREESCAPE_DISPLAY or PAL")
    for d, bbc in tables.items():
        for a in src["areas"]:
            aid = str(a["id"])
            e = bbc["areas"].get(aid)
            check(e is not None, f"{d}: area {aid} has no patterns")
            if e is None:
                continue
            check(e["faces"] == tables["pal"]["areas"][aid]["faces"],
                  f"{d}: area {aid}'s face colours differ from PAL's")
            pats = e["patterns"] + [e["sky"], e["ground"]]
            check(len(e["patterns"]) == 15, f"{d}: area {aid}: not 15 patterns")
            for p in pats:
                check(len(p) == 4 and all(0 <= b <= 255 for b in p),
                      f"{d}: area {aid}: pattern {p} isn't four bytes")
                check(all(px < 8 for px in P.from_bytes(p)),
                      f"{d}: area {aid}: pattern {p} uses a flashing colour")
            cols = src["colours"][v][aid]
            used = sorted(int(k) for k in
                          src["versions"][v]["areas"][aid]["faces"])
            for i in used:
                for j in used:
                    if i < j and P.de(P.target_of(cols[str(i)]),
                                      P.target_of(cols[str(j)])) > design.SAME:
                        check(e["patterns"][i - 1] != e["patterns"][j - 1],
                              f"{d}: area {aid}: indices {i} and {j} share "
                              "a pattern")
            # What this display's scoring picks.
            ch = design.choose(cols, used, cands, True, d)
            for i in range(1, 16):
                want = ch[i][0] if i in ch else \
                    P.best(P.target_of(cols[str(i)]), cands, d)[0]
                check(want.bytes == e["patterns"][i - 1],
                      f"{d}: area {aid}: index {i} isn't the scoring's pick")
            check(ch["sky"][0].bytes == e["sky"]
                  and ch["ground"][0].bytes == e["ground"],
                  f"{d}: area {aid}: sky or ground isn't the scoring's pick")
            for i in range(1, 16):
                check(list(colours.pattern(a["id"], i, d)) == e["patterns"][i - 1],
                      f"{d}: area {aid}: colours.pattern({i}) disagrees")
            check(list(colours.sky({"id": a["id"]}, d)) == e["sky"]
                  and list(colours.ground(a["id"], d)) == e["ground"],
                  f"{d}: area {aid}: colours.sky or ground disagrees")
            if d == colours.DISPLAY:
                check(all(colours.pattern(a["id"], i) == colours.pattern(
                    a["id"], i, d) for i in range(1, 16)),
                    f"area {aid}: the default isn't {d}'s table")
    for f in failures:
        print("FAIL", f)
    print(f"colour-check: {len(failures)} failures, "
          f"{len(src['areas'])} areas from {v}, tables for "
          f"{', '.join(tables)}; the default is {colours.DISPLAY}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
