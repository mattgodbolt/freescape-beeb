#!/usr/bin/env python3
"""The object pipeline's cases: what the model makes of each camera, stage by
stage, for tools/objectcheck.mjs to hold the 6502 to.

    objectcases.py DB.json AREAS.json OUT.json [--quick]

AREAS.json is tools/mkareas.py's layout (which slot holds which of the
model's objects). For each camera, the area's index in the records'
directory, the camera, and from the model (tools/model/):

- matrix: M (stage 1);
- cands: the object pass's candidates in order (stage 2), each its slot,
  the mask of its seen faces (bit j for its shape's face j), the mask of
  the vertices they use, those vertices in camera space (stage 3), and the
  faces it draws, each a colour and a polygon in view coordinates
  (stages 4-6);
- order: the drawn objects' slots, farthest first (stage 7);
- out: the faces as the rasteriser takes them, nearest first.

This is tools/model/render.py's render() up to the rasteriser, called
through the same functions, so the two can't drift: render_geometry()
below is its first half, and check_render() asserts it agrees with
render() on every entrance view.

The projection is the model's (tools/model/maths.py, through parts.py),
and the faces' colours the followed version's (render.recolour), as
render() has them.

Also the matrices: every yaw at every pitch (roll 0), every roll at a few
of those, and random triples.
"""
import json
import pathlib
import random
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.model import camera as cam
from tools.model import clip, matrix, objects, order, parts, render, transform

def render_geometry(db, area, camera, state=None):
    """render.render()'s stages 1-7, with what each stage made."""
    m = matrix.rotation(camera, db["tables"])
    c = camera.position
    tally = {k: 0 for k in render.counts.KEYS}
    objs = render.recolour(area, area["objects"] + db["globals"])
    cands = objects.object_pass(objs, m, c, state, True, tally)
    drawn = []
    per = []
    for cand in cands:
        faces, _ = render.draw_faces(cand, m, c, tally)
        per.append(faces)
        if faces:
            drawn.append((cand, faces))
    ordered, _ = order.sort(drawn, lambda d: d[0].shape.box, c)
    out = []
    for cand, faces in reversed(ordered):
        out.extend(faces)
    return m, cands, per, ordered, out


def check_render(db):
    """render_geometry agrees with render() on every entrance view."""
    for area, _, camera in cam.entrance_views(db):
        v = render.render(db, area, camera)
        _, _, _, ordered, out = render_geometry(db, area, camera)
        assert [d[0].shape.id for d in ordered] == v.order
        assert [(f.colour, f.poly) for f in out] == [(f.colour, f.poly) for f in v.faces]


def slot_map(layout, a_index, n_area):
    """The model's object-pass index to the working copy's slot."""
    g = layout["globals"]["counts"]["obj"]
    out = {}
    for s, i in enumerate(layout["globals"]["slots"]):
        out[n_area + i] = s
    for s, i in enumerate(layout["areas"][a_index]["slots"]):
        out[i] = g + s
    return out


def case(db, layout, a_index, area, camera, name):
    m, cands, per, ordered, out = render_geometry(db, area, camera)
    slots = slot_map(layout, a_index, len(area["objects"]))
    c = camera.position
    rows = []
    for cand, faces in zip(cands, per):
        s = cand.shape
        mask = 0
        for j, f in enumerate(s.faces):
            if any(f is g for g in cand.faces):
                mask |= 1 << j
        used = sorted({i for f in cand.faces for i in f.loop})
        vmask = sum(1 << i for i in used)
        verts = {str(i): list(transform.transform(m, s.vertices[i], c)) for i in used}
        # The vertices a polygon's faces can't be projected whole at (the
        # vertex pass's vp_off): its used vertices clip.projectable refuses.
        off = None
        if not (s.line or s.point):
            off = sum(1 << i for i in used if not clip.projectable(tuple(verts[str(i)])))
        rows.append({
            "slot": slots[cand.index], "mask": mask, "vmask": vmask, "verts": verts, "off": off,
            "faces": [[f.colour, [list(p) for p in f.poly]] for f in faces],
        })
    # The area's floor object (decision 8a), for the cycles' accounting.
    floor = None
    fid = parts.colours.floor(area) if hasattr(parts.colours, "floor") else None
    for i, o in enumerate(area["objects"]):
        if o["id"] == fid and o["type"] != 0 and i in slots:
            floor = slots[i]
            break
    return {
        "name": name, "area": a_index,
        "camera": [camera.x, camera.y, camera.z, camera.yaw, camera.pitch, camera.roll],
        "matrix": [v for row in m for v in row],
        "floor": floor,
        "cands": rows,
        "order": [slots[d[0].index] for d in ordered],
        "out": [[f.colour, [list(p) for p in f.poly]] for f in out],
    }


WALK_STEPS = 4                      # frames of a walk from each entrance, as the
WALK_STEP = 25                      # original steps (step sin / 64, floored); world units


def cameras(db, layout, quick=False):
    """Every entrance view, each followed by a short walk forward from it
    (the camera moved, the angles kept: the transform's cache holds), then
    the extra cameras: at a spread of entrances, every yaw, every pitch and
    every roll with the others the entrance's, and random angles."""
    index = {a["id"]: i for i, a in enumerate(layout["areas"])}
    views = list(cam.entrance_views(db))
    sin, cos = db["tables"]["sin"], db["tables"]["cos"]
    out = []
    for area, e, c in views:
        name = "a%03d-e%03d" % (area["id"], e["id"])
        out.append((index[area["id"]], area, c, name))
        x, z = c.x, c.z
        for k in range(1, WALK_STEPS + 1):
            x += (WALK_STEP * sin[c.yaw]) // 64
            z += (WALK_STEP * cos[c.yaw]) // 64
            moved = cam.Camera(x, c.y, z, c.yaw, c.pitch, c.roll)
            out.append((index[area["id"]], area, moved, "%s-w%d" % (name, k)))
    rng = random.Random(1987)
    picks = views[::max(1, len(views) // (3 if quick else 8))]
    for area, e, c in picks:
        base = "a%03d-e%03d" % (area["id"], e["id"])
        a = index[area["id"]]
        steps = range(0, cam.STEPS, 9 if quick else 1)
        for yaw in steps:
            out.append((a, area, cam.Camera(c.x, c.y, c.z, yaw, c.pitch, c.roll), base + "-y%d" % yaw))
        for pitch in steps:
            out.append((a, area, cam.Camera(c.x, c.y, c.z, c.yaw, pitch, c.roll), base + "-p%d" % pitch))
        for roll in steps:
            out.append((a, area, cam.Camera(c.x, c.y, c.z, c.yaw, c.pitch, roll), base + "-r%d" % roll))
        for k in range(4 if quick else 24):
            yaw, pitch, roll = (rng.randrange(cam.STEPS) for _ in range(3))
            out.append((a, area, cam.Camera(c.x, c.y, c.z, yaw, pitch, roll), base + "-x%d" % k))
    return out


def matrices(db, quick=False):
    rng = random.Random(64)
    triples = []
    step = 7 if quick else 1
    for yaw in range(0, cam.STEPS, step):
        for pitch in range(0, cam.STEPS, step):
            triples.append((yaw, pitch, 0))
    for yaw, pitch in ((0, 0), (5, 3), (18, 9), (40, 66)):
        for roll in range(cam.STEPS):
            triples.append((yaw, pitch, roll))
    for _ in range(200 if quick else 3000):
        triples.append(tuple(rng.randrange(cam.STEPS) for _ in range(3)))
    out = []
    for yaw, pitch, roll in triples:
        m = matrix.rotation(cam.Camera(0, 0, 0, yaw, pitch, roll), db["tables"])
        out.append([yaw, pitch, roll, [v for row in m for v in row]])
    return out


def main(argv):
    quick = "--quick" in argv
    argv = [a for a in argv if a != "--quick"]
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        db = json.load(f)
    with open(argv[2]) as f:
        layout = json.load(f)
    check_render(db)
    views = [case(db, layout, a, area, c, name) for a, area, c, name in cameras(db, layout, quick)]
    result = {"parts": parts.USING, "matrices": matrices(db, quick), "views": views}
    with open(argv[3], "w") as f:
        json.dump(result, f, separators=(",", ":"))
    print("objectcases: %d views, %d matrices" % (len(views), len(result["matrices"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
