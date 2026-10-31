#!/usr/bin/env python3
"""The model against the original: every entrance view the ZX's own redraw
drew (make zxviews, docs/research/zx-driller.md, "The view oracle").

    zxcompare.py DB.json ZXVIEWS_DIR [--out DIR]

For each view in ZXVIEWS_DIR/views.json:

- the camera: the model's placement (camera.from_entrance) against the
  original's; the view is drawn from the original's;
- the objects drawn: the model's draw list against the original's count,
  and against its list, object for object in order with each one's face
  count, where views.json has it (as "list": [[id, faces], ...]);
- the image: the model's view, each face in its colour index, turned into
  the ZX's pixels (each of the model's pixels is two of the ZX's, coloured
  by the database's shade for that index, ink 1 and paper 0, the shade's
  row chosen as the ZX chooses it, by its y counted up from the bottom),
  against the ZX's buffer. Only pixels away from the model's edges are
  compared (a pixel and its eight neighbours the same colour index): the
  original's fill walks edges in integer steps where the model takes pixel
  centres, and its projection truncates where the model rounds to
  sixteenths, so edges may differ by a pixel.

--out writes each view's model and original side by side. Exits 1 if a
camera differs or fewer than MATCH of the compared pixels agree.
"""
import json
import pathlib
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.model import camera as cam
from tools.model import parts, render
from tools.model.view import VIEW_H, VIEW_W

# The share of compared pixels that must agree.
MATCH = 0.99
ZX_W, ZX_ROW = 2 * VIEW_W, 2 * VIEW_W // 8


def index_map(view):
    """The view's colour index at each pixel (0 for the background)."""
    faces = [((f.colour,) * 4, f.poly) for f in view.faces]
    lines = parts.rasterise(faces, (0,) * 4, (0,) * 4)
    out = []
    for runs in lines:
        line = []
        for x0, x1, p in runs:
            line.extend([p[0]] * (x1 - x0))
        out.append(line)
    return out


def compare_lists(view, theirs):
    """How the model's draw list, far to near with each object's face
    count, compares with the original's."""
    faces = {}
    for f in view.faces:
        faces[f.id] = faces.get(f.id, 0) + 1
    ours = [[i, faces[i]] for i in view.order]
    theirs = [list(e) for e in theirs]
    if ours == theirs:
        return "same"
    if [i for i, _ in ours] == [i for i, _ in theirs]:
        return "faces differ"
    if sorted(i for i, _ in ours) == sorted(i for i, _ in theirs):
        return "order differs"
    return "objects differ"


def zx_bit(buf, x, y):
    return (buf[ZX_ROW * y + (x >> 3)] >> (7 - (x & 7))) & 1


def compare_view(db, area, record, buf):
    c = record["camera"]
    camera = cam.Camera(c["x"], c["y"], c["z"], c["yaw"], c["pitch"], c["roll"])
    # The ZX's own colour indices: which faces it draws is part of what's
    # compared (decision 8 colours the engine's from the ST's).
    view = render.render(db, area, camera, followed=False)
    idx = index_map(view)
    shades = db["shades"]
    compared = agree = 0
    model_bits = []
    for y in range(VIEW_H):
        row = []
        for x in range(VIEW_W):
            i = idx[y][x]
            bits = []
            for zx_x in (2 * x, 2 * x + 1):
                b = 0 if i == 0 else (shades[i - 1][(VIEW_H - y) & 3] >> (7 - (zx_x & 7))) & 1
                bits.append(b)
            row.extend(bits)
            interior = all(idx[yy][xx] == i
                           for yy in range(max(0, y - 1), min(VIEW_H, y + 2))
                           for xx in range(max(0, x - 1), min(VIEW_W, x + 2)))
            if interior:
                for zx_x, b in zip((2 * x, 2 * x + 1), bits):
                    compared += 1
                    agree += b == zx_bit(buf, zx_x, y)
        model_bits.append(row)
    return view, camera, compared, agree, model_bits


def picture(model_bits, buf, path):
    from PIL import Image
    img = Image.new("1", (2 * ZX_W + 4, VIEW_H), 0)
    px = img.load()
    for y in range(VIEW_H):
        for x in range(ZX_W):
            px[x, y] = model_bits[y][x]
            px[ZX_W + 4 + x, y] = zx_bit(buf, x, y)
    img.resize((2 * img.width, 2 * VIEW_H)).save(path)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--out")]
    out = None
    if "--out" in argv:
        out = pathlib.Path(argv[argv.index("--out") + 1])
        args = [a for a in args if a != str(out)]
        out.mkdir(parents=True, exist_ok=True)
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(args[0]) as f:
        db = json.load(f)
    zxdir = pathlib.Path(args[1])
    with open(zxdir / "views.json") as f:
        records = json.load(f)["views"]
    areas = {a["id"]: a for a in db["areas"]}
    placed = {(a["id"], e["id"]): c for a, e, c in cam.entrance_views(db)}
    bad_cameras = []
    drawn_differ = []
    lists = {"same": 0, "faces differ": 0, "order differs": 0, "objects differ": 0}
    total_compared = total_agree = 0
    worst = []
    for r in records:
        area = areas[r["area"]]
        buf = (zxdir / (r["name"] + ".bin")).read_bytes()
        view, camera, compared, agree, bits = compare_view(db, area, r, buf)
        if placed[(r["area"], r["entrance"])] != camera:
            bad_cameras.append(r["name"])
        if view.counts["drawn"] != r["drawn"]:
            drawn_differ.append("%s %d/%d" % (r["name"], view.counts["drawn"], r["drawn"]))
        if "list" in r:
            lists[compare_lists(view, r["list"])] += 1
        total_compared += compared
        total_agree += agree
        worst.append((agree / compared if compared else 1.0, r["name"]))
        if out:
            picture(bits, buf, out / (r["name"] + ".png"))
    worst.sort()
    share = total_agree / total_compared
    print("zxcompare: %d views; cameras placed as the original: %d; objects drawn as the "
          "original: %d%s" % (len(records), len(records) - len(bad_cameras),
                              len(records) - len(drawn_differ),
                              " (differ, model/original: %s)" % ", ".join(drawn_differ) if drawn_differ else ""))
    print("zxcompare: pixels away from edges agreeing: %.2f%% of %d; worst views %s"
          % (100 * share, total_compared, ", ".join("%s %.1f%%" % (n, 100 * s) for s, n in worst[:3])))
    if sum(lists.values()):
        print("zxcompare: draw lists against the original's: %s"
              % ", ".join("%s %d" % kv for kv in lists.items()))
    if bad_cameras:
        print("zxcompare: cameras differ:", ", ".join(bad_cameras))
    ok = not bad_cameras and share >= MATCH
    print("zxcompare:", "ok" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
