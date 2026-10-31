#!/usr/bin/env python3
"""A whole view (docs/engine.md, section 4): camera, faces nearest first,
the rasteriser, the writer, and the view's bytes; with a picture at MODE 2's
2:1 pixel aspect, and the work it took (tools/model/counts.py).

    render.py DB.json OUTDIR      every entrance view: OUTDIR/aAAA-eEEE.png
                                  and OUTDIR/counts.json, and the summary
"""
import json
import pathlib
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from dataclasses import dataclass, field

from tools.model import camera as cam
from tools.model import clip, counts, matrix, objects, order, parts, transform
from tools.model.view import VIEW_H, VIEW_W

MAGNIFY = 3


@dataclass
class DrawnFace:
    obj: int             # its object's place in the object pass's list
    id: int
    colour: int
    poly: list           # view coordinates, inside the view
    near_clipped: bool = False
    clipped: bool = False


@dataclass
class View:
    area: dict
    camera: cam.Camera
    matrix: tuple
    faces: list = field(default_factory=list)      # nearest first
    order: list = field(default_factory=list)      # object ids, farthest first
    vertices: list = field(default_factory=list)   # (world vertex, (sx, sy)) projected
    lines: list = None
    bytes: bytes = None
    counts: dict = field(default_factory=dict)


def _area2(poly):
    """Twice the polygon's signed area."""
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))


def draw_faces(cand, m, c, tally, check=False):
    """A candidate's seen faces through transform, near clip, projection and
    2D clip: its drawn faces, and its own vertices it projected, as (world
    vertex, view coordinates)."""
    s = cand.shape
    used = sorted({i for f in cand.faces for i in f.loop})
    if s.corner is not None:
        every = transform.cuboid(m, s.corner, s.size, c)
        cs = {i: every[i] for i in used}
    else:
        cs = {i: transform.transform(m, s.vertices[i], c) for i in used}
    if check:
        mc = transform.mul(m, c)
        for i in used:
            assert cs[i] == transform.transform(m, s.vertices[i], c)
            assert cs[i] == transform.cached(transform.mul(m, s.vertices[i]), mc)
    tally["vertices_transformed"] += len(used)
    projected = {}

    def project(v):
        if v not in projected:
            projected[v] = parts.project(*v)
        return projected[v]

    drawn = []
    for f in cand.faces:
        tally["faces_seen"] += 1
        poly = [cs[i] for i in f.loop]
        near = any(v[2] < clip.ZNEAR for v in poly)
        if near:
            poly = clip.near_clip(poly)
            if not poly:
                tally["faces_rejected"] += 1
                continue
        codes = [clip.outcode(v) for v in poly]
        every_code = 0xFF
        any_code = 0
        for k in codes:
            every_code &= k
            any_code |= k
        if every_code:
            tally["faces_rejected"] += 1
            continue
        flat = [project(v) for v in poly]
        if s.line:
            # Widened, a line can reach past the view even when its ends don't.
            flat = clip.line_quad(flat[0], flat[1])
        elif s.point:
            flat = clip.point_square(flat[0])
        widened = s.line or s.point
        out = clip.clip2d(flat) if any_code or widened else clip.dedupe(flat)
        if len(out) < 3 or not _area2(out):
            tally["faces_rejected"] += 1
            continue
        if near:
            tally["faces_near_clipped"] += 1
        if any_code:
            tally["faces_clipped_2d"] += 1
        drawn.append(DrawnFace(cand.index, s.id, f.colour, out, near, bool(any_code)))
    tally["vertices_projected"] += len(projected)
    world = {cs[i]: s.vertices[i] for i in used}
    return drawn, [(world[v], p) for v, p in projected.items() if v in world]


def recolour(area, objs):
    """The objects with each face's colour index from the version the colours
    follow (decision 8): every version recoloured its faces, so the ZX's
    indices can't be mapped across (docs/research/colour.md). An object the
    followed version has no colours for keeps the ZX's."""
    out = []
    for obj in objs:
        c = parts.face_colours(area, obj["id"])
        if c is None:
            out.append(obj)
        elif obj.get("sensor") is not None:
            out.append(dict(obj, sensor=dict(obj["sensor"], colour=c[0])))
        else:
            out.append(dict(obj, colours=c))
    return out


def render(db, area, camera, state=None, cull=True, check=False, followed=True):
    """The view from camera in area. state maps object ids to shown or not
    (default: the area's start); cull=False skips the coarse cull (to check
    it culls nothing that's drawn); check=True checks the transform's cached
    and corner-and-edge forms against the direct one. The object pass takes
    the area's objects, then the globals, as the original does.
    followed: colour the faces from the version decision 8 follows (the
    ST's), not the database's (the ZX's)."""
    m = matrix.rotation(camera, db["tables"])
    c = camera.position
    v = View(area, camera, m)
    tally = {k: 0 for k in counts.KEYS}
    objs = area["objects"] + db["globals"]
    if followed:
        objs = recolour(area, objs)
    cands = objects.object_pass(objs, m, c, state, cull, tally)
    drawn = []
    for cand in cands:
        faces, projected = draw_faces(cand, m, c, tally, check)
        if faces:
            drawn.append((cand, faces))
            v.vertices.extend(projected)
        else:
            tally["culled_frustum"] += 1
    tally["drawn"] = len(drawn)
    ordered, tally["sort_comparisons"] = order.sort(drawn, lambda d: d[0].shape.box, c)
    v.order = [d[0].shape.id for d in ordered]
    for cand, faces in reversed(ordered):
        v.faces.extend(faces)
    tally["faces_drawn"] = len(v.faces)
    raster_in = [(parts.pattern(area, f.colour), f.poly) for f in v.faces]
    stats = {}
    v.lines = parts.rasterise(raster_in, parts.sky(area), parts.ground(area), None, stats)
    v.bytes = parts.write(v.lines)
    v.counts = counts.finish(tally, v, stats)
    return v


def picture(view, path):
    """The view's bytes as a PNG, each pixel two wide and one high,
    magnified."""
    from PIL import Image
    pal = parts.palette()
    pixels = parts.decode(view.bytes)
    img = Image.new("RGB", (VIEW_W, VIEW_H))
    img.putdata([pal[p] for line in pixels for p in line])
    img = img.resize((2 * MAGNIFY * VIEW_W, MAGNIFY * VIEW_H), Image.NEAREST)
    img.save(path)


def name(area, entrance):
    return "a%03d-e%03d" % (area["id"], entrance["id"])


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        db = json.load(f)
    out = pathlib.Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for area, entrance, camera in cam.entrance_views(db):
        view = render(db, area, camera, check=True)
        picture(view, out / (name(area, entrance) + ".png"))
        rows.append({
            "view": name(area, entrance),
            "area": area["id"],
            "area_name": area["name"].strip(),
            "entrance": entrance["id"],
            "camera": camera.__dict__,
            "order": view.order,
            "counts": view.counts,
        })
    with open(out / "counts.json", "w") as f:
        json.dump({"parts": parts.USING, "views": rows}, f, indent=1)
        f.write("\n")
    print(counts.summary(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
