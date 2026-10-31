#!/usr/bin/env python3
"""The rasteriser's test scenes, with the model's bytes for each.

    rasterscenes.py OUT.json
    rasterscenes.py --driller DB.json OUT.json    Driller's entrance views

Random convex polygons in sixteenths, scenes shaped like Driller's (boxes
with vertical sides seen by a level camera), and the edge cases: slivers,
single pixels, shared edges and T-junctions, a face over the whole view,
many faces on one line, horizontal edges, vertices on pixel centres,
degenerate polygons, and horizons at any angle and off the view.

Each scene's image is checked here against the model's brute-force
reference (tools/model/raster.py), so a scene whose spans disagree with
the fill rule fails before the 6502 sees it. tools/rastercheck.mjs then runs
the 6502 on each and compares its bytes with these.
"""

import json
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "model"))

from raster import (VIEW_W, VIEW_H, SUB, HALF, Background, Horizon,  # noqa: E402
                    spans, reference)
import writer  # noqa: E402

XMAX, YMAX = SUB * VIEW_W, SUB * VIEW_H
MAX_VERTICES = 16


def _raster_constant(name):
    """A constant of src/raster.6502, where the 6502's limits are set."""
    src = (Path(__file__).resolve().parents[1] / "src" / "raster.6502").read_text()
    m = re.search(rf"^{name}\s*=\s*(\d+)", src, re.M)
    return int(m.group(1))


# The 6502's pools' size, and its horizon: a point within HMAX of 0 and a
# direction in signed bytes.
POOL_NODES = _raster_constant("POOL_NODES")
PATTERNS = _raster_constant("RS_PATTERNS")
HMAX, DMAX = _raster_constant("RS_HMAX"), 127


def hull(points):
    """The convex hull of integer points, clockwise on the screen (y down),
    without collinear points: Andrew's monotone chain."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def clamp(p):
    return (min(max(p[0], 0), XMAX), min(max(p[1], 0), YMAX))


def pattern(rng):
    """Four random bytes: every face its own, so a wrong face shows."""
    return [rng.randrange(256) for _ in range(4)]


def jumble(rng, vertices):
    """Either winding, from any vertex."""
    v = list(vertices)
    if rng.random() < 0.5:
        v.reverse()
    k = rng.randrange(len(v)) if v else 0
    return v[k:] + v[:k]


def random_polygon(rng, centre=None, radius=None):
    cx, cy = centre or (rng.randint(-200, XMAX + 200), rng.randint(-200, YMAX + 200))
    r = radius or math.exp(rng.uniform(math.log(6), math.log(1100)))
    pts = []
    for _ in range(rng.randint(3, 12)):
        a = rng.uniform(0, 2 * math.pi)
        d = r * rng.uniform(0.4, 1.0)
        pts.append(clamp((round(cx + d * math.cos(a)), round(cy + d * math.sin(a)))))
    return jumble(rng, hull(pts))


def random_horizon(rng, near=True):
    if rng.random() < 0.15:
        return None
    if rng.random() < 0.4:
        dx, dy = rng.choice([(64, 0), (-64, 0), (1, 0), (127, 0)])
    else:
        a = rng.uniform(0, 2 * math.pi)
        dx, dy = round(DMAX * math.cos(a)), round(DMAX * math.sin(a))
        if dx == 0 and dy == 0:
            dx = 1
    span = 2400 if near else HMAX
    hx = rng.randint(-span, span) if near else rng.randint(-HMAX, HMAX)
    hy = rng.randint(-span, span) if near else rng.randint(-HMAX, HMAX)
    return Horizon(hx, hy, dx, dy)


def scene(name, faces, horizon=None, rng=None, sky=None, ground=None):
    rng = rng or random.Random(name)
    # Patterns are reused once there are more faces than the 6502's table
    # holds, the sky's and ground's besides.
    own = [p for p, _ in faces]
    room = PATTERNS - 2
    faces = [(own[i % room], v) for i, (_, v) in enumerate(faces)]
    return {
        "name": name,
        "sky": sky or pattern(rng),
        "ground": ground or pattern(rng),
        "horizon": horizon,
        "faces": faces,
    }


def random_scenes():
    out = []
    for i in range(48):
        rng = random.Random(1000 + i)
        n = [1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 35, 40][i % 12]
        faces = [(pattern(rng), random_polygon(rng)) for _ in range(n)]
        out.append(scene(f"random{i:02d}-{n}", faces, random_horizon(rng, i % 3 != 2), rng))
    return out


def box_faces(rng, x0, x1, ytop0, ytop1, ybot0, ybot1, top=None):
    """A box's side, as a level camera sees it: vertical sides at x0 and x1,
    its top and bottom edges slanting from (x0, ytop0) to (x1, ytop1) and so
    on; with top, the box's top face above it to the far edge's heights."""
    faces = [(pattern(rng), jumble(rng, hull([(x0, ytop0), (x1, ytop1), (x1, ybot1), (x0, ybot0)])))]
    if top:
        (fx0, fy0), (fx1, fy1) = top
        faces.append((pattern(rng), jumble(rng, hull([(fx0, fy0), (fx1, fy1), (x1, ytop1), (x0, ytop0)]))))
    return [(p, v) for p, v in faces if len(v) >= 3]


def driller(i, pan=0, horizon_y=None, sky=None, name=None):
    """Boxes on the ground, a level camera: most edges vertical. pan moves
    them across (a turn), horizon_y moves the horizon (a pitch), sky
    changes its pattern; each gives the same boxes and patterns otherwise."""
    rng = random.Random(2000 + i)
    hy = rng.choice([SUB * 52, SUB * 40 + 3, SUB * 60 + 8, SUB * 30])
    if horizon_y is not None:
        hy = horizon_y
    faces = []
    for _ in range([3, 6, 10, 14][i % 4]):
        x0 = rng.randint(0, XMAX - 32)
        x1 = min(XMAX, x0 + rng.randint(16, 900))
        yb0 = rng.randint(hy, YMAX)
        yb1 = min(YMAX, max(hy, yb0 + rng.randint(-200, 200)))
        h = rng.randint(32, 1200)
        yt0, yt1 = max(0, yb0 - h), max(0, yb1 - h + rng.randint(-100, 100))
        top = None
        if rng.random() < 0.4 and yt0 > 40 and yt1 > 40:
            shift = rng.randint(-200, 200)
            top = (clamp((x0 + shift, yt0 - rng.randint(8, 120))),
                   clamp((x1 + shift, yt1 - rng.randint(8, 120))))
            top = None if (top[0][1] >= yt0 or top[1][1] >= yt1) else top
        faces += box_faces(rng, x0, x1, yt0, yt1, yb0, yb1, top)
    # The ground cuboid's face: below the horizon, across the view.
    if i % 2:
        faces.append((pattern(rng), [(0, hy + 40), (XMAX, hy + 40), (XMAX, YMAX), (0, YMAX)]))
    if pan:
        faces = [(p, hull([clamp((x + pan, y)) for x, y in v])) for p, v in faces]
        faces = [(p, v) for p, v in faces if len(v) >= 3]
    return scene(name or f"driller{i:02d}", faces, Horizon(XMAX // 2, hy, 64, 0), rng, sky=sky)


def driller_scenes():
    return [driller(i) for i in range(16)]


def sequences():
    """Frames in turn, alternately into each screen, which keeps what was
    drawn into it: what the 6502 leaves alone must be what's wanted."""
    out = {
        "still": [driller(7) for _ in range(6)],
        "pan": [driller(3, pan=24 * t) for t in range(8)],
        "rise": [driller(5, horizon_y=SUB * 40 + 19 * t) for t in range(8)],
        "alternate": [driller(1 if t % 4 < 2 else 2) for t in range(8)],
        "recolour": [driller(9, sky=[0x0f, 0x3c, 0xf0, 0xc3] if t >= 3 else None) for t in range(6)],
        "empty": [scene("empty", []) for _ in range(4)],
        "turning": [scene("turning", [], Horizon(832, 832, round(127 * math.cos(t / 9)), round(127 * math.sin(t / 9))),
                          random.Random(7)) for t in range(6)],
    }
    # The pitch moves the boxes, but the sky and ground stay as they were.
    for f in out["rise"]:
        f["sky"], f["ground"] = out["rise"][0]["sky"], out["rise"][0]["ground"]
    return [{"name": k, "frames": v} for k, v in out.items()]


def edge_scenes():
    out = []
    rng = random.Random(3000)
    level = Horizon(XMAX // 2, SUB * 52 + 8, 64, 0)
    out.append(scene("empty-sky", []))
    for y in (-50000 // 2, -1, 0, 7, 8, 9, 16 * 30 + 8, YMAX - 1, YMAX, YMAX + 9, 30000):
        out.append(scene(f"level-{y}", [], Horizon(rng.randint(-500, 2000), y, 64, 0), rng))
    for hy in (800, 808, 816):
        out.append(scene(f"upside-down-{hy}", [], Horizon(800, hy, -64, 0), rng))
    for k in range(24):
        a = 2 * math.pi * k / 24
        dx, dy = round(DMAX * math.cos(a)), round(DMAX * math.sin(a))
        out.append(scene(f"tilt-{k:02d}", [], Horizon(XMAX // 2 + 37 * k - 400, YMAX // 2 - 29 * k + 300, dx, dy), rng))
    for hx, hy, dx, dy in ((832, 832, 0, 64), (832, 832, 0, -64), (8, 8, 1, 1), (24, 0, -1, 1),
                           (-HMAX, -HMAX, 127, 127), (HMAX, -HMAX, -1, 127), (HMAX, HMAX, 127, -1),
                           (-HMAX, 0, 127, -127), (5000, 832, 0, 1), (-5000, 832, 0, -1),
                           (836, 8, 127, -126), (840, 840, 3, -127),
                           # through pixel centres, where a tie is ground
                           (8, 8, 2, 1), (8, 1656, 2, -1), (1656, 8, -1, 1), (1656, 1656, -2, -1),
                           (808, 8, 0, 1), (808, 8, 0, -1), (8, 808, 1, 0), (8, 808, -1, 0)):
        out.append(scene(f"horizon-{hx}-{hy}-{dx}-{dy}", [], Horizon(hx, hy, dx, dy), rng))

    whole = [(0, 0), (XMAX, 0), (XMAX, YMAX), (0, YMAX)]
    out.append(scene("whole-view", [(pattern(rng), whole)], level, rng))
    out.append(scene("whole-view-twice", [(pattern(rng), jumble(rng, whole)), (pattern(rng), whole)], level, rng))
    out.append(scene("whole-behind-small", [(pattern(rng), [(400, 400), (900, 420), (600, 1000)]),
                                            (pattern(rng), whole)], level, rng))
    # Gaps on the top line, then a face over them all from the first: its span
    # fills the line's first gap and goes on through the rest (and the same
    # on other lines, and with the first gap not at the left).
    for name, y0 in (("top-line", 0), ("second-line", 16), ("last-line", YMAX - 40)):
        faces = [(pattern(rng), [(80 * i + 100, y0), (80 * i + 140, y0), (80 * i + 120, y0 + 30)]) for i in range(8)]
        faces.append((pattern(rng), [(60, y0), (1500, y0), (1500, min(YMAX, y0 + 400)), (60, min(YMAX, y0 + 400))]))
        faces.append((pattern(rng), [(0, y0), (XMAX, y0), (XMAX, min(YMAX, y0 + 40)), (0, min(YMAX, y0 + 40))]))
        out.append(scene(name, faces, level, rng))
    # Every line but the last full after the first face: the faces must go
    # on until the last is, and stop after.
    last = SUB * (VIEW_H - 1) + HALF
    out.append(scene("all-but-one-line", [(pattern(rng), [(0, 0), (XMAX, 0), (XMAX, last), (0, last)]),
                                          (pattern(rng), [(300, last - 40), (1300, last - 40), (900, YMAX)]),
                                          (pattern(rng), whole), (pattern(rng), whole)], level, rng))

    # Slivers: thin in x, thin in y, and diagonal, some under a pixel wide.
    faces = []
    for i in range(20):
        x = 30 + 80 * i
        faces.append((pattern(rng), jumble(rng, [(x, 10), (x + 1 + i, 1600), (x + i // 2, 1650)])))
    out.append(scene("slivers-vertical", faces, level, rng))
    faces = []
    for i in range(20):
        y = 30 + 80 * i
        faces.append((pattern(rng), jumble(rng, [(10, y), (1600, y + 1 + i), (1650, y + i // 2)])))
    out.append(scene("slivers-horizontal", faces, level, rng))
    faces = [(pattern(rng), jumble(rng, [(0 + 40 * i, 0), (40 * i + 3, 0), (1664, 1664 - 40 * i)])) for i in range(30)]
    out.append(scene("slivers-diagonal", faces, Horizon(100, 100, 50, 77), rng))

    # Single pixels: squares and diamonds around pixel centres, and squares
    # whose edges go through centres (which the top-left rule settles).
    faces = []
    for i in range(40):
        cx, cy = 16 * (2 * i + 5) + 8, 16 * (i + 20) + 8
        k = i % 4
        if k == 0:
            v = [(cx - 1, cy - 1), (cx + 1, cy - 1), (cx + 1, cy + 1), (cx - 1, cy + 1)]
        elif k == 1:
            v = [(cx, cy - 2), (cx + 2, cy), (cx, cy + 2), (cx - 2, cy)]
        elif k == 2:
            v = [(cx, cy), (cx + 16, cy), (cx + 16, cy + 16), (cx, cy + 16)]
        else:
            v = [(cx - 8, cy - 8), (cx + 8, cy - 8), (cx + 8, cy + 8), (cx - 8, cy + 8)]
        faces.append((pattern(rng), jumble(rng, v)))
    out.append(scene("single-pixels", faces, level, rng))

    # Shared edges: a grid of quads with jittered corners, split into
    # triangles both ways; every pixel of it is one face's, never the sky's.
    for name, split in (("shared-grid", None), ("shared-triangles", 1), ("shared-triangles-2", 2)):
        g = {}
        for i in range(7):
            for j in range(7):
                g[i, j] = clamp((i * 260 + rng.randint(-60, 60) * (0 < i < 6) + 50,
                                 j * 250 + rng.randint(-60, 60) * (0 < j < 6) + 60))
        faces = []
        for i in range(6):
            for j in range(6):
                a, b, c, d = g[i, j], g[i + 1, j], g[i + 1, j + 1], g[i, j + 1]
                quad = hull([a, b, c, d])
                if split is None or len(quad) < 4:
                    faces.append((pattern(rng), jumble(rng, quad)))
                elif (i + j + split) % 2:
                    faces += [(pattern(rng), jumble(rng, [a, b, c])), (pattern(rng), jumble(rng, [a, c, d]))]
                else:
                    faces += [(pattern(rng), jumble(rng, [a, b, d])), (pattern(rng), jumble(rng, [b, c, d]))]
        rng.shuffle(faces)
        out.append(scene(name, [(p, v) for p, v in faces if len(hull(v)) >= 3], level, rng))
    # A fan around a centre, and T-junctions: one long edge, the faces on
    # its other side meeting it at points along it.
    c = (830, 811)
    ring = [clamp((round(c[0] + 700 * math.cos(2 * math.pi * k / 17)),
                   round(c[1] + 700 * math.sin(2 * math.pi * k / 17)))) for k in range(17)]
    out.append(scene("fan", [(pattern(rng), jumble(rng, [c, ring[k], ring[(k + 1) % 17]])) for k in range(17)], level, rng))
    faces = [(pattern(rng), [(100, 200), (1500, 1300), (100, 1300)])]
    for k in range(6):
        t0, t1 = k / 6, (k + 1) / 6
        p0 = (round(100 + 1400 * t0), round(200 + 1100 * t0))
        p1 = (round(100 + 1400 * t1), round(200 + 1100 * t1))
        faces.append((pattern(rng), jumble(rng, [p0, (1600, 150 + 30 * k), p1])))
    out.append(scene("t-junctions", faces, level, rng))

    # Many faces on one line: strips side by side, touching and apart.
    faces = [(pattern(rng), jumble(rng, [(40 * i + 5, 700), (40 * i + 30 + (i % 3) * 5, 690), (40 * i + 33, 900), (40 * i, 910)]))
             for i in range(41)]
    out.append(scene("many-on-a-line", faces, level, rng))
    faces = [(pattern(rng), jumble(rng, [(16 * 2 * i, 0), (16 * 2 * i + 16 + (i % 2), 0), (16 * 2 * i + 16, YMAX), (16 * 2 * i, YMAX)]))
             for i in range(40)]
    out.append(scene("comb", faces, level, rng))
    faces = [(pattern(rng), jumble(rng, [(41 * i, 300 + 7 * i), (41 * i + 41, 300 + 7 * i), (41 * i + 41, 1400 - 9 * i), (41 * i, 1400 - 9 * i)]))
             for i in range(40)]
    out.append(scene("abutting-strips", faces, level, rng))

    # Horizontal edges on, just above and just below line centres.
    faces = []
    for i, dy in enumerate((-1, 0, 1, 7, 8, 9, 15, 16)):
        y0, y1 = 16 * (3 + 12 * i) + dy, 16 * (10 + 12 * i) + dy
        faces.append((pattern(rng), jumble(rng, [(100 + i * 9, y0), (1500 - i * 7, y0), (1400, y1), (200, y1)])))
    out.append(scene("horizontal-edges", faces, level, rng))
    # Vertices exactly on pixel centres, and edges through rows of centres.
    faces = []
    for i in range(12):
        v = [(16 * rng.randrange(VIEW_W) + 8, 16 * rng.randrange(VIEW_H) + 8) for _ in range(rng.randint(3, 7))]
        h = hull(v)
        if len(h) >= 3:
            faces.append((pattern(rng), jumble(rng, h)))
    out.append(scene("on-centres", faces, Horizon(808, 808, 64, 64), rng))
    faces = [(pattern(rng), jumble(rng, [(8 + 32 * i, 8), (8 + 32 * i + 16 * (i + 1), 8 + 16 * (i + 1) * 3), (8 + 32 * i, 8 + 16 * (i + 1) * 3)]))
             for i in range(16)]
    out.append(scene("centre-edges", faces, level, rng))

    # Degenerate polygons: collinear, repeated vertices, a point, a segment.
    faces = [(pattern(rng), [(100, 100), (500, 500), (900, 900)]),
             (pattern(rng), [(300, 100), (300, 100), (300, 100)]),
             (pattern(rng), [(200, 1000), (1200, 1000)]),
             (pattern(rng), [(600, 200), (600, 200), (1000, 600), (1000, 600), (600, 1000)]),
             (pattern(rng), [(10, 10), (1500, 10), (1500, 10), (1500, 1500)]),
             (pattern(rng), [(10, 300), (800, 300), (1600, 300), (800, 300)]),
             (pattern(rng), [(1200, 200), (1300, 300), (1400, 400), (1300, 500), (1200, 400), (1200, 300)])]
    out.append(scene("degenerate", faces, level, rng))
    # Many vertices: near-circles, near the view's corners and edges.
    faces = []
    for k, (cx, cy, r) in enumerate(((0, 0, 500), (XMAX, YMAX, 700), (832, 832, 300), (XMAX, 0, 900), (200, 1400, 250))):
        pts = [clamp((round(cx + r * math.cos(2 * math.pi * j / MAX_VERTICES + k)),
                      round(cy + r * math.sin(2 * math.pi * j / MAX_VERTICES + k)))) for j in range(MAX_VERTICES)]
        h = hull(pts)
        if len(h) >= 3:
            faces.append((pattern(rng), jumble(rng, h)))
    out.append(scene("circles", faces, Horizon(0, 1664, 90, -90), rng))
    # Gaps a pixel wide between faces, at odd and even pixels.
    faces = []
    for i in range(25):
        x = 16 * (4 * i + i % 2) + 8
        faces.append((pattern(rng), jumble(rng, [(x, 100 + 13 * i), (x + 40 + i, 100), (x + 40, 1500), (x, 1500 - 20 * i)])))
    out.append(scene("narrow-gaps", faces, Horizon(-400, 900, 127, 3), rng))
    return out


def build(s):
    """The model's image of a scene, checked against the brute force."""
    bg = Background(tuple(s["sky"]), tuple(s["ground"]),
                    None if s["horizon"] is None else Horizon(*s["horizon"]))
    faces = [(tuple(p), [tuple(v) for v in vs]) for p, vs in s["faces"]]
    for p, vs in faces:
        assert len(vs) <= MAX_VERTICES, s["name"]
        assert all(0 <= x <= XMAX and 0 <= y <= YMAX for x, y in vs), s["name"]
    if bg.horizon:
        h = bg.horizon
        assert abs(h.x) <= HMAX and abs(h.y) <= HMAX and abs(h.dx) <= DMAX and abs(h.dy) <= DMAX, s["name"]
    want = writer.view_bytes(reference(faces, bg))
    got = writer.view_bytes(spans(faces, bg)[0])
    if got != want:
        y = next(i for i in range(VIEW_H) if got[i] != want[i])
        raise SystemExit(f"{s['name']}: spans disagree with the reference on line {y}")
    # What the 6502 draws, its pools as big as they are.
    lines, counts = spans(faces, bg, POOL_NODES)
    return {
        "name": s["name"],
        "sky": s["sky"],
        "ground": s["ground"],
        "horizon": None if bg.horizon is None else [bg.horizon.x, bg.horizon.y, bg.horizon.dx, bg.horizon.dy],
        "faces": [{"pattern": list(p), "vertices": [list(v) for v in vs]} for p, vs in faces],
        "view": [row.hex() for row in writer.view_bytes(lines)],
        "counts": {**counts.__dict__, "runs": counts.runs, "bytes": counts.bytes},
    }


def driller_views(db_path, out):
    """Every Driller entrance view's faces, from the whole-view model
    (tools/model/render.py), as scenes: what the rasteriser gets in the
    game. The model has no horizon yet, so a level camera's goes through the
    view's centre. Derived from the originals, so built, never committed."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.model import camera as cam, parts, render, view

    db = json.loads(Path(db_path).read_text())
    scenes = []
    for area, entrance, camera in cam.entrance_views(db):
        v = render.render(db, area, camera)
        level = getattr(camera, "pitch", 0) == 0 and getattr(camera, "roll", 0) == 0
        scenes.append(build({
            "name": render.name(area, entrance),
            "sky": list(parts.sky(area)), "ground": list(parts.ground(area)),
            "horizon": [view.XC, view.YC, 64, 0] if level else None,
            "faces": [(list(parts.pattern(area, f.colour)), [list(p) for p in f.poly]) for f in v.faces],
        }))
    Path(out).write_text(json.dumps({"scenes": scenes}) + "\n")
    print(f"{len(scenes)} of Driller's entrance views, each the same as the model's brute force")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--driller":
        return driller_views(sys.argv[2], sys.argv[3])
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    def built(s):
        if isinstance(s["horizon"], Horizon):
            h = s["horizon"]
            s["horizon"] = [h.x, h.y, h.dx, h.dy]
        return build(s)

    scenes = [built(s) for s in edge_scenes() + driller_scenes() + random_scenes()]
    seqs = [{"name": q["name"], "frames": [built(s) for s in q["frames"]]} for q in sequences()]
    Path(sys.argv[1]).write_text(json.dumps({"scenes": scenes, "sequences": seqs}) + "\n")
    print(f"{len(scenes)} scenes and {len(seqs)} sequences of frames, each the same as the model's brute force")


if __name__ == "__main__":
    main()
