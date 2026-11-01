#!/usr/bin/env python3
"""A whole view (docs/engine.md, section 4): camera, faces nearest first,
the rasteriser, the writer, and the view's bytes; with a picture at MODE 2's
2:1 pixel aspect, and the work it took (tools/model/counts.py).

    render.py DB.json OUTDIR      every entrance view: OUTDIR/aAAA-eEEE.png
                                  and OUTDIR/counts.json, and the summary
    render.py --diff MODULE.FLAG DB.json [ZXVIEWS]
                                  a model flag's picture: every entrance view
                                  and a four-step walk from each (as
                                  tools/objectcases.py walks) rendered with
                                  the flag on and off, the pixels and draw
                                  orders that differ; and with the ZX
                                  oracle's views (make model-zx's
                                  build/zx/views/), each way's agreement
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
    horizon: tuple = None                          # the rasteriser's, or None
    bytes: bytes = None
    counts: dict = field(default_factory=dict)


# A face the projection can't take whole goes through the cone (clip.py);
# off, the near clip, the guard band and the 2D clip as before (decisions
# 15, 17 and 24), to measure the one against the other.
CONE = True
# The cone takes no line for an edge with both ends at or behind the eye:
# the face's image (what's in front of the eye) is inside that edge's
# plane already, wherever it is. Off, every edge's line.
BEHIND_EDGES = True


def edge_lines(s, m, loop, cs, image=None):
    """The screen lines of a face's edges' planes through the eye (clip.py,
    "The cone"): a box's edges along M's columns, any other's from its
    ends; and each line's edge, its two vertices' indices. An edge with
    both ends at or behind the eye (z <= 0) has none: the face's image is
    inside its plane already (BEHIND_EDGES). They're made in FRONT_FIRST's
    order, and none after one with every corner of the view outside it,
    which leaves nothing of the face (clip.cone_clip). With IMAGE_LINES, an
    edge with an end the projection takes (image(i) not None) has its line
    through that end's image (clip.image_line): through both ends' images
    when it takes both, or a box's edge toward its vanishing point."""
    box = s.corner is not None or (s.obj["type"] == objects.RECTANGLE and not s.line)
    n = len(loop)
    edges = [(loop[j], loop[(j + 1) % n]) for j in range(n)]
    if BEHIND_EDGES:
        edges = [(i, k) for i, k in edges if cs[i][2] > 0 or cs[k][2] > 0]
    if FRONT_FIRST:
        edges.sort(key=lambda e: not (cs[e[0]][2] > 0 and cs[e[1]][2] > 0))
    lines = []
    ends = []
    for i, k in edges:
        line = _image_line(s, m, cs, i, k, box, image) if IMAGE_LINES and image else None
        if line is None:
            if box:
                d = [s.vertices[k][a] - s.vertices[i][a] for a in range(3)]
                axis = next(a for a in range(3) if d[a])
                col = (m[0][axis], m[1][axis], m[2][axis])
                normal = clip.edge_normal_axis(cs[i], col, 1 if d[axis] > 0 else -1)
            else:
                normal = clip.edge_normal(cs[i], cs[k])
            line = clip.screen_line(normal)
        lines.append(line)
        ends.append((i, k))
        if clip.corners_out(line) == 4:
            break
    return lines, ends


def _image_line(s, m, cs, i, k, box, image):
    """Edge i -> k's line from its ends' images (edge_lines, IMAGE_LINES), or
    None for the plane's own line: when the projection takes neither end; a
    generic edge with one end taken; or an edge whose images give no
    direction (both at one point, or the edge pointing at the eye)."""
    ti, tk = clip.projectable(cs[i]), clip.projectable(cs[k])
    if ti and tk:
        p, q = image(i), image(k)
        a, b = p[1] - q[1], q[0] - p[0]
    elif (ti or tk) and box:
        d = [s.vertices[k][a] - s.vertices[i][a] for a in range(3)]
        axis = next(a for a in range(3) if d[a])
        sign = 1 if d[axis] > 0 else -1
        p = image(i if ti else k)
        a, b = clip.image_gradient(p, tuple(sign * m[r][axis] for r in range(3)))
    else:
        return None
    if not (a or b):
        return None
    return clip.image_line(a, b, p)


# The cone's lines from the images of their edges' ends where the projection
# takes them (clip.image_line); off, every line from its edge's plane.
IMAGE_LINES = True


# The lines of edges with both ends in front come first, then the rest, each
# in the loop's order: a floor's far edge, say, before its sides, whose
# lines then mostly cut nothing it hasn't. With side crossings and joins
# the same point whatever the order, it changes only the general crossings,
# which it makes rare. Off, the loop's order.
FRONT_FIRST = True


def _cone_face(s, m, f, poly, cs, project, image, tally):
    """One face with the cone on: (its polygon, whether it went through the
    cone or a 3D clip, whether it crossed the view's edges), or None if
    nothing of it is drawn. A polygon the projection takes whole is
    projected; any other polygon goes through the cone. A line or a point
    with an end the projection can't take is first clipped in 3D to the
    near plane and the planes beyond the view's sides (clip.segment_clip),
    so that it can."""
    if not (s.line or s.point):
        if not all(clip.projectable(v) for v in poly):
            every_code = 0xFF
            for v in poly:
                every_code &= clip.code3(v)
            if every_code:
                out = []
            else:
                lines, ends = edge_lines(s, m, f.loop, cs, image)
                # the lines made (not one of counts.KEYS: tools/objectcases.py's)
                tally["cone_lines"] = tally.get("cone_lines", 0) + len(lines)
                out = clip.cone_clip(lines, ends, image)
            return (out, True, True) if clip.drawable(out) else None
    near = not all(clip.projectable(v) for v in poly)
    if near:
        if s.point:
            return None
        poly = clip.segment_clip(poly[0], poly[1])
        assert all(clip.projectable(v) for v in poly)
        if not poly:
            return None
    if s.line or s.point:
        # (a line's or a point's ends, each projected as it's drawn)
        tally["vertices_numbered"] = tally.get("vertices_numbered", 0) + len(poly)
    flat = [project(v) for v in poly]
    # Wholly beyond one of the view's edges, it isn't drawn; beyond any,
    # it's clipped (clip.outcode2d).
    every_code = 0xFF
    any_code = 0
    for p in flat:
        k = clip.outcode2d(p)
        every_code &= k
        any_code |= k
    if every_code:
        return None
    if s.line:
        # Widened, a line can reach past the view even when its ends don't.
        flat = clip.line_quad(flat[0], flat[1])
    elif s.point:
        flat = clip.point_square(flat[0])
    widened = s.line or s.point
    out = clip.clip2d(flat) if any_code or widened else clip.dedupe(flat)
    return (out, near, bool(any_code)) if clip.drawable(out) else None


def draw_faces(cand, m, c, tally, check=False):
    """A candidate's seen faces: those the projection can take whole
    projected, and clipped to the view in 2D if they cross its edges; the
    rest, through the cone (clip.py), the view's rectangle clipped to their
    edges' planes through the eye; lines and points clipped in 3D, then
    widened. Its drawn faces, and its own vertices it projected, as (world
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
    numbered = set()            # (a polygon object's vertices projected, by index)

    def project(v):
        if v not in projected:
            projected[v] = parts.project(*v)
        return projected[v]

    def image(i):
        """Vertex i's view coordinates, if the projection takes it (the
        cone's joins), else None."""
        if not clip.projectable(cs[i]):
            return None
        numbered.add(i)
        return project(cs[i])

    drawn = []
    for f in cand.faces:
        tally["faces_seen"] += 1
        poly = [cs[i] for i in f.loop]
        if CONE:
            if not (s.line or s.point) and all(clip.projectable(v) for v in poly):
                numbered.update(f.loop)
            face = _cone_face(s, m, f, poly, cs, project, image, tally)
            if face is None:
                tally["faces_rejected"] += 1
                continue
            out, near, clipped = face
            if near:
                tally["faces_near_clipped"] += 1
            if clipped:
                tally["faces_clipped_2d"] += 1
            drawn.append(DrawnFace(cand.index, s.id, f.colour, out, near, clipped))
            continue
        near = any(v[2] < clip.ZNEAR for v in poly)
        if near:
            poly = clip.near_clip(poly)
            if not poly:
                tally["faces_rejected"] += 1
                continue
        # Wholly beyond a plane outside the view's sides, it can't be seen.
        every_beyond = 0xFF
        for v in poly:
            every_beyond &= clip.beyond(v)
        if every_beyond:
            tally["faces_rejected"] += 1
            continue
        if any(clip.outside_guard(v) for v in poly):
            # (decision 17: so that no vertex projects past 16 bits)
            poly = clip.guard_clip(poly)
            tally["faces_guard_clipped"] += 1
            if not poly:
                tally["faces_rejected"] += 1
                continue
        flat = [project(v) for v in poly]
        # Wholly beyond one of the view's edges, the face isn't drawn; beyond
        # any, it's clipped (clip.outcode2d).
        every_code = 0xFF
        any_code = 0
        for p in flat:
            k = clip.outcode2d(p)
            every_code &= k
            any_code |= k
        if every_code:
            tally["faces_rejected"] += 1
            continue
        if s.line:
            # Widened, a line can reach past the view even when its ends don't.
            flat = clip.line_quad(flat[0], flat[1])
        elif s.point:
            flat = clip.point_square(flat[0])
        widened = s.line or s.point
        out = clip.clip2d(flat) if any_code or widened else clip.dedupe(flat)
        if not clip.drawable(out):
            tally["faces_rejected"] += 1
            continue
        if near:
            tally["faces_near_clipped"] += 1
        if any_code:
            tally["faces_clipped_2d"] += 1
        drawn.append(DrawnFace(cand.index, s.id, f.colour, out, near, bool(any_code)))
    tally["vertices_projected"] += len(projected)
    # (not one of counts.KEYS: tools/objectcases.py's)
    tally["vertices_numbered"] = tally.get("vertices_numbered", 0) + len(numbered)
    world = {cs[i]: s.vertices[i] for i in used}
    return drawn, [(world[v], p) for v, p in projected.items() if v in world]


HORIZON_MAX = 30000         # the rasteriser's |hx|, |hy| at most (src/raster.6502's RS_HMAX)


def horizon(m):
    """The floor's horizon (decision 8a as amended): where an infinite
    horizontal plane below the eye meets the sky, from the matrix alone. A
    view ray (X / FX, -Y / FY, 1), X and Y from the view's centre, is level
    when it's square to the camera's up, M's second column (m01, m11, m21):
    with FY = 2 FX that's 2 m01 X - m11 Y + m21 FY = 0, sky where it's
    positive. As the rasteriser takes it (raster.Horizon): a point, on the
    centre line across the line's steeper axis, and the direction (m11, 2
    m01), sky to its left, halved if it doesn't fit signed bytes; or None
    for sky everywhere, and a level horizon off the top for ground
    everywhere, when the line misses the view by more than the rasteriser
    takes."""
    from tools.model.view import FY, XC, YC
    m01, m11, m21 = m[0][1], m[1][1], m[2][1]
    a, b, c = 2 * m01, -m11, m21 * FY
    dx, dy = -b, a
    if not -128 <= dy <= 127:
        dx, dy = dx >> 1, dy >> 1
    if abs(b) >= abs(a) and b:
        x, y = 0, clip.round_div(-c, b)
    elif a:
        x, y = clip.round_div(-c, a), 0
    else:
        x = y = HORIZON_MAX         # (up is along the view: one side everywhere)
    if abs(x + XC) > HORIZON_MAX or abs(y + YC) > HORIZON_MAX:
        if c > 0:
            return None
        return ((XC, -HORIZON_MAX), (1, 0))
    return ((XC + x, YC + y), (dx, dy))


# The floor as the horizon: measured, and not taken (docs/research/objects.md,
# "The floor as the horizon"): it shows ground where the original shows the
# void past the platform's edge, and the objects a thick floor hides.
FLOOR_AS_HORIZON = False


def floor_slot(area, objs):
    """The index in objs of the area's floor (colours.floor), or None."""
    fid = parts.floor(area)
    if fid is None:
        return None
    for i, o in enumerate(objs):
        if o["id"] == fid and o["type"] != 0:
            return i
    return None


def floor_as_horizon(area, objs, m):
    """The objects with the area's floor not drawn, and the horizon that
    stands for it (decision 8a as amended): the ground below the horizon
    is the floor's top face's pattern (colours.ground). Without a floor,
    the objects as they are and no horizon (sky everywhere)."""
    i = floor_slot(area, objs) if FLOOR_AS_HORIZON else None
    if i is None:
        return objs, None
    objs = list(objs)
    objs[i] = dict(objs[i], initially_invisible=True)
    return objs, horizon(m)


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
    objs, sky_ground = floor_as_horizon(area, objs, m)
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
    v.horizon = sky_ground
    v.lines = parts.rasterise(raster_in, parts.sky(area), parts.ground(area), sky_ground, stats)
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


def walk_views(db, steps=4, step=25):
    """Every entrance view, then a walk of steps frames along its yaw, step
    world units a frame (tools/objectcases.py's WALK_STEPS, WALK_STEP):
    (area, name, camera)."""
    sin, cos = db["tables"]["sin"], db["tables"]["cos"]
    for area, e, c in cam.entrance_views(db):
        yield area, name(area, e), c
        x, z = c.x, c.z
        for k in range(1, steps + 1):
            x += (step * sin[c.yaw]) // 64
            z += (step * cos[c.yaw]) // 64
            yield area, "%s-w%d" % (name(area, e), k), cam.Camera(x, c.y, z, c.yaw, c.pitch, c.roll)


class _Flag:
    """MODULE.FLAG, set in every copy of its module that renders: this
    module's own flags in this copy too, which run as a script is __main__,
    not the tools.model.render that zxcompare renders through."""

    def __init__(self, flag):
        import importlib
        mod_name, attr = flag.rsplit(".", 1)
        mods = [importlib.import_module("tools.model." + mod_name)]
        if mod_name == "render" and sys.modules[__name__] is not mods[0]:
            mods.append(sys.modules[__name__])
        self.mods, self.attr = mods, attr
        self.was = getattr(mods[0], attr)

    def set(self, value):
        for mod in self.mods:
            setattr(mod, self.attr, value)


def flag_diff(db, flag):
    """The views of walk_views rendered with MODULE.FLAG (a tools/model
    module's boolean) on and then off: (views, pixels, the pixels that
    differ, the views with any, the most in one and which, the views whose
    draw order differs)."""
    f = _Flag(flag)
    views = pixels = differ = touched = worst = orders = 0
    worst_name = None
    try:
        for area, label, camera in walk_views(db):
            f.set(True)
            on = render(db, area, camera)
            f.set(False)
            off = render(db, area, camera)
            a, b = parts.decode(on.bytes), parts.decode(off.bytes)
            n = sum(1 for la, lb in zip(a, b) for pa, pb in zip(la, lb) if pa != pb)
            views += 1
            pixels += VIEW_W * VIEW_H
            differ += n
            touched += n > 0
            orders += on.order != off.order
            if n > worst:
                worst, worst_name = n, label
    finally:
        f.set(f.was)
    return views, pixels, differ, touched, worst, worst_name, orders


def flag_zx(db, flag, zxdir):
    """The ZX oracle's agreement (tools/model/zxcompare.py: the pixels away
    from edges compared and agreeing, over its views) with MODULE.FLAG on
    and off: ((compared, agreeing) on, (compared, agreeing) off)."""
    from tools.model import zxcompare
    flag = _Flag(flag)
    zxdir = pathlib.Path(zxdir)
    with open(zxdir / "views.json") as f:
        records = json.load(f)["views"]
    areas = {a["id"]: a for a in db["areas"]}
    out = []
    try:
        for on in (True, False):
            flag.set(on)
            compared = agree = 0
            for r in records:
                buf = (zxdir / (r["name"] + ".bin")).read_bytes()
                _, _, c, a, _ = zxcompare.compare_view(db, areas[r["area"]], r, buf)
                compared += c
                agree += a
            out.append((compared, agree))
    finally:
        flag.set(flag.was)
    return out


def main(argv):
    if len(argv) in (4, 5) and argv[1] == "--diff":
        with open(argv[3]) as f:
            db = json.load(f)
        views, pixels, differ, touched, worst, who, orders = flag_diff(db, argv[2])
        print("%s: %d views, %d of %d pixels differ, in %d views (most %d, %s); "
              "the draw order differs in %d" % (argv[2], views, differ, pixels, touched, worst, who, orders))
        if len(argv) == 5:
            (c1, a1), (c0, a0) = flag_zx(db, argv[2], argv[4])
            print("%s: against the ZX oracle, pixels away from edges agreeing %d of %d on, %d of %d off"
                  % (argv[2], a1, c1, a0, c0))
        return 0
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
