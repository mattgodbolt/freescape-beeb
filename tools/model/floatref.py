#!/usr/bin/env python3
"""A floating-point reference for the model's geometry (docs/engine.md,
section 5): ScummVM's maths, in floats, for the same views.

    floatref.py DB.json      compare every entrance view's projected
                             vertices; exit 1 if any is out by more than
                             the tolerance

ScummVM draws with OpenGL: exact trigonometry in degrees, a perspective
projection, the roll applied about the view axis after the look
(positionCamera). This does the same in floats, with the model's field of
view (the original's, where ScummVM fits its own), and two more
differences so it can be compared vertex for vertex: it composes the
rotations directly (roll, pitch, yaw) rather than through ScummVM's
look-at, which can't look straight down; and it takes the entrance's yaw
as the original does, where ScummVM's mapping from an entrance's yaw
differs between 180 and 270 degrees (traverseEntrance).

The integer pipeline's error comes from the matrix's bytes (1.0 = 64, and
each product rounded) and the projection's rounding. The check compares the
vertices whose reference projection is inside the view, which are the ones
that place pixels.
"""
import json
import math
import pathlib
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.model import camera as cam
from tools.model import render
from tools.model.view import SUB, VIEW_H, VIEW_W, XC, YC, focal_lengths

# The tolerance for a vertex inside the view: a pixel, in sixteenths.
TOLERANCE = SUB



def rotation(camera):
    """The camera's rotation in floats, 1.0 = 1: roll (pitch (yaw))."""
    def rad(a):
        return math.radians(5 * a)

    y, p, r = rad(camera.yaw), rad(camera.pitch), rad(camera.roll)
    yaw = ((math.cos(y), 0, -math.sin(y)), (0, 1, 0), (math.sin(y), 0, math.cos(y)))
    pitch = ((1, 0, 0), (0, math.cos(p), math.sin(p)), (0, -math.sin(p), math.cos(p)))
    roll = ((math.cos(r), math.sin(r), 0), (-math.sin(r), math.cos(r), 0), (0, 0, 1))

    def mul(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))

    return mul(roll, mul(pitch, yaw))


def project(m, camera, v, focal):
    """A world vertex to view coordinates, in floats, or None behind the
    camera. focal: the focal lengths (x, y), unrounded."""
    d = [v[k] - camera.position[k] for k in range(3)]
    x, y, z = (sum(m[r][k] * d[k] for k in range(3)) for r in range(3))
    if z <= 0:
        return None
    return XC + focal[0] * x / z, YC - focal[1] * y / z


def compare(db):
    """Every entrance view's projected vertices against the reference: a
    list of (view name, world vertex, model's, reference's, error)."""
    out = []
    focal = focal_lengths(db["tables"]["scale"])
    for area, entrance, camera in cam.entrance_views(db):
        view = render.render(db, area, camera)
        m = rotation(camera)
        for world, (sx, sy) in view.vertices:
            ref = project(m, camera, world, focal)
            if ref is None or not (0 <= ref[0] <= SUB * VIEW_W and 0 <= ref[1] <= SUB * VIEW_H):
                continue
            err = max(abs(sx - ref[0]), abs(sy - ref[1]))
            out.append((render.name(area, entrance), world, (sx, sy), ref, err))
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        db = json.load(f)
    rows = compare(db)
    errs = sorted(r[4] for r in rows)
    dx = sorted(abs(r[2][0] - r[3][0]) for r in rows)
    dy = sorted(abs(r[2][1] - r[3][1]) for r in rows)

    def q(v, p):
        return v[min(len(v) - 1, math.ceil(p / 100 * len(v)) - 1)]

    worst = max(rows, key=lambda r: r[4])
    print("floatref: %d vertices inside the view; error in sixteenths of a pixel, "
          "x: median %.1f, p90 %.1f, max %.1f; y: median %.1f, p90 %.1f, max %.1f"
          % (len(rows), q(dx, 50), q(dx, 90), dx[-1], q(dy, 50), q(dy, 90), dy[-1]))
    print("floatref: worst %.1f at %s, vertex %s: model %s, reference (%.1f, %.1f); tolerance %d: %s"
          % (worst[4], worst[0], worst[1], worst[2], worst[3][0], worst[3][1], TOLERANCE,
             "ok" if errs[-1] <= TOLERANCE else "FAIL"))
    return 0 if errs[-1] <= TOLERANCE else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
