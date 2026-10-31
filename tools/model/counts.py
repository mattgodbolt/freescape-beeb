#!/usr/bin/env python3
"""The work a view takes, counted (docs/engine.md, section 6). These drive the
cost model, so each is defined by what the 6502 would do for it.

    counts.py COUNTS.json      print the summary of a run of render.py

Per view:

- records: object records the object pass walks, the area's and then the
  globals. not_drawn: entrances, groups, empty shapes. hidden: invisible or
  destroyed. culled_coarse: wholly behind the camera, by compares.
  no_faces: no face the camera sees has a colour (or a sensor not
  watching). considered: transformed.
  culled_frustum: considered, but no face survives the clip. drawn: objects
  with a face drawn, which the sort orders. sort_comparisons: pairs it
  compared.
- vertices_transformed: distinct vertices of the faces seen, of considered
  objects. vertices_projected: distinct camera-space vertices projected,
  those the near clip makes included.
- faces_seen: faces of considered objects the camera sees. faces_rejected:
  of those, wholly outside the near plane or one side of the view, or
  clipped to nothing. faces_near_clipped, faces_clipped_2d: drawn faces
  that needed each clip. faces_drawn: faces into the rasteriser.
- face_lines: lines each drawn face covers a pixel on, summed (the fill
  rule's, before anything hides it). face_lines_open: of those, lines not
  yet full when the face came. face_runs: runs the faces put in the span
  buffer (the stand-in rasteriser's counts, absent from another).
- runs: runs on all lines, background included, the writer's input.
  joins: bytes where two runs meet, which take a mask. bytes: the view's.
"""
import json
import math
import pathlib
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from tools.model.standin.raster import span
from tools.model.view import VIEW_BYTES, VIEW_H

KEYS = [
    "records", "not_drawn", "hidden", "culled_coarse", "no_faces", "considered",
    "culled_frustum", "drawn", "sort_comparisons",
    "vertices_transformed", "vertices_projected",
    "faces_seen", "faces_rejected", "faces_near_clipped", "faces_clipped_2d", "faces_drawn",
    "face_lines", "face_lines_open", "face_runs", "lines_full",
    "runs", "joins", "bytes",
]


def face_lines(poly):
    """Lines a polygon covers a pixel on, by the fill rule."""
    ys = [p[1] for p in poly]
    lo = max(0, -((-(min(ys) - 8)) // 16))
    hi = min(VIEW_H - 1, (max(ys) - 8) // 16)
    return sum(1 for y in range(lo, hi + 1) if span(poly, y))


def finish(tally, view, stats):
    t = dict(tally)
    t["face_lines"] = sum(face_lines(f.poly) for f in view.faces)
    for k in ("face_lines_open", "face_runs", "lines_full"):
        t[k] = stats.get(k)
    t["runs"] = sum(len(line) for line in view.lines)
    t["joins"] = sum(1 for line in view.lines for x0, _, _ in line[1:] if x0 & 1)
    t["bytes"] = VIEW_BYTES * VIEW_H
    return {k: t[k] for k in KEYS}


def percentile(values, p):
    """The nearest-rank percentile: the smallest value at least p% of them
    don't exceed."""
    v = sorted(values)
    return v[max(0, math.ceil(p / 100 * len(v)) - 1)]


def median(values):
    v = sorted(values)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def summary(rows):
    lines = ["%d views: median, 90th percentile (nearest rank) and maximum" % len(rows),
             "%-22s %8s %8s %8s  %s" % ("count", "median", "p90", "max", "busiest")]
    for k in KEYS:
        vals = [r["counts"][k] for r in rows if r["counts"][k] is not None]
        if not vals:
            continue
        top = max(rows, key=lambda r: r["counts"][k] if r["counts"][k] is not None else -1)
        med = median(vals)
        lines.append("%-22s %8s %8d %8d  %s" % (
            k, ("%g" % med), percentile(vals, 90), max(vals), top["view"]))
    return "\n".join(lines)


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        rows = json.load(f)["views"]
    print(summary(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
