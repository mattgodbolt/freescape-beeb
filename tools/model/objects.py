"""The objects: their geometry, and the object pass (docs/engine.md, section 4,
stage 2).

Geometry is in integer world units, an object's cell coordinates times CELL.
Each drawable object becomes a Shape: its vertices, its faces (a colour and
a loop of vertex indices, with the plane that decides which side sees it),
its header box (the box the sort compares) and its bounds (the box the
coarse cull tests).

Which faces are seen (docs/research/model.md, "What is drawn"):

- A cuboid: the original's side bits ($6B7C and $6FC2; CM2's L8431 and
  L9661): the face on an axis's low side when the camera is strictly below
  the box on that axis, the high side's when strictly above. Colours -x, +x,
  -y, +y, -z, +z.
- A rectangle: the same test on its one zero axis; colour 0 is seen from the
  low side, colour 1 from the high side (ScummVM's renderRectangle windings).
- A pyramid: ScummVM's renderPyramid's eight vertices and six faces, each
  seen when the camera is strictly on the outer side of its plane.
- A polygon: colour 1 seen from the side its vertex order winds
  anticlockwise, colour 0 from the other (ScummVM's renderPolygon windings).
- A line, or a rectangle with two zero sizes: always seen, in colour 0, as
  Castle Master II draws lines (ScummVM's last-drawn colour 1 is the same in
  every Driller line).
- A sensor: a point at its corner, in its colour, seen while the camera is
  on a side its axis bits watch and nearer than its range (the original's
  $7592, docs/research/model.md). ScummVM draws none.
- Colour 0 is "not drawn"; a face of no area is never seen. Entrances and
  groups aren't drawn.

The original decides a pyramid's and a flat shape's faces from the turn of
their first three projected points; these plane tests are its exact form,
on the world's integers, and differ from it only for a face seen edge-on or
so small its projected points fall in line.
"""
import math
from dataclasses import dataclass, field

from tools.model.view import CELL, FX, FY, XC, YC

CUBOID, SENSOR, RECTANGLE = 1, 2, 3
PYRAMIDS = range(4, 10)
LINE = 10
POLYGONS = range(10, 15)

# ScummVM's renderPyramid: each type's base corners (0-3) and apex corners
# (4-7), relative to the origin, as functions of the size (sx, sy, sz) and
# the apex ordinates (o0, o1, o2, o3).
_PYRAMID_VERTICES = {
    4: lambda sx, sy, sz, o: [(0, 0, sz), (0, sy, sz), (0, sy, 0), (0, 0, 0),
                              (sx, o[0], o[3]), (sx, o[2], o[3]), (sx, o[2], o[1]), (sx, o[0], o[1])],
    5: lambda sx, sy, sz, o: [(sx, 0, 0), (sx, sy, 0), (sx, sy, sz), (sx, 0, sz),
                              (0, o[0], o[1]), (0, o[2], o[1]), (0, o[2], o[3]), (0, o[0], o[3])],
    6: lambda sx, sy, sz, o: [(0, 0, 0), (sx, 0, 0), (sx, 0, sz), (0, 0, sz),
                              (o[0], sy, o[1]), (o[2], sy, o[1]), (o[2], sy, o[3]), (o[0], sy, o[3])],
    7: lambda sx, sy, sz, o: [(sx, sy, 0), (0, sy, 0), (0, sy, sz), (sx, sy, sz),
                              (o[2], 0, o[1]), (o[0], 0, o[1]), (o[0], 0, o[3]), (o[2], 0, o[3])],
    8: lambda sx, sy, sz, o: [(0, sy, 0), (sx, sy, 0), (sx, 0, 0), (0, 0, 0),
                              (o[0], o[3], sz), (o[2], o[3], sz), (o[2], o[1], sz), (o[0], o[1], sz)],
    9: lambda sx, sy, sz, o: [(0, 0, sz), (sx, 0, sz), (sx, sy, sz), (0, sy, sz),
                              (o[0], o[1], 0), (o[2], o[1], 0), (o[2], o[3], 0), (o[0], o[3], 0)],
}
# Its faces, in colour order: four sides, the base, the apex.
_PYRAMID_FACES = [(4, 5, 1, 0), (5, 6, 2, 1), (6, 7, 3, 2), (7, 4, 0, 3), (0, 1, 2, 3), (7, 6, 5, 4)]

# A cuboid's vertex i is at the low corner plus, for each axis k with bit k
# of i set, the size on that axis. Its faces in colour order.
_CUBOID_FACES = [(0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)]


@dataclass
class Face:
    colour: int
    loop: tuple          # vertex indices
    normal: tuple = None  # outward plane normal; None for a line (always seen)
    d: int = 0           # the plane: normal . p == d

    def seen_from(self, c):
        if self.normal is None:
            return True
        n = self.normal
        return n[0] * c[0] + n[1] * c[1] + n[2] * c[2] > self.d


@dataclass
class Shape:
    obj: dict
    vertices: list
    faces: list
    box: tuple           # header box, world units: ((x0, y0, z0), (x1, y1, z1))
    bounds: tuple        # the box around the header box and every vertex
    line: bool = False
    point: bool = False   # a sensor
    corner: tuple = None  # a cuboid's low corner and size, for the
    size: tuple = None    # corner-and-edges transform

    @property
    def id(self):
        return self.obj["id"]


def newell(points):
    """The normal of a planar loop, by Newell's method: twice its area,
    pointing the way the loop winds anticlockwise. Exact for integers."""
    nx = ny = nz = 0
    n = len(points)
    for i in range(n):
        x0, y0, z0 = points[i]
        x1, y1, z1 = points[(i + 1) % n]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return (nx, ny, nz)


def _loop(vertices, loop):
    """The loop without repeated corners (a pyramid's apex can be a point or
    an edge)."""
    out = []
    for i in loop:
        if not out or vertices[out[-1]] != vertices[i]:
            out.append(i)
    while len(out) > 1 and vertices[out[0]] == vertices[out[-1]]:
        out.pop()
    return tuple(out)


def _plane_face(colour, vertices, loop, flip=False):
    loop = _loop(vertices, loop)
    if len(loop) < 3:
        return None
    n = newell([vertices[i] for i in loop])
    if n == (0, 0, 0):
        return None
    if flip:
        n = (-n[0], -n[1], -n[2])
        loop = tuple(reversed(loop))
    v = vertices[loop[0]]
    return Face(colour, loop, n, n[0] * v[0] + n[1] * v[1] + n[2] * v[2])


def _axis_face(colour, loop, axis, sign, plane):
    n = [0, 0, 0]
    n[axis] = sign
    return Face(colour, tuple(loop), tuple(n), sign * plane)


def _box(lo, hi):
    return (tuple(lo), tuple(hi))


def shape(obj):
    """The object's Shape, or None if it isn't drawn at all."""
    t = obj["type"]
    if t == SENSOR:
        lo = tuple(CELL * p for p in obj["pos"])
        colour = obj["sensor"]["colour"]
        if not colour:
            return None
        return Shape(obj, [lo], [Face(colour, (0,))], _box(lo, lo), _box(lo, lo), point=True)
    if t not in (CUBOID, RECTANGLE) and t not in PYRAMIDS and t not in POLYGONS:
        return None
    lo = tuple(CELL * p for p in obj["pos"])
    size = tuple(CELL * s for s in obj["size"])
    hi = tuple(lo[k] + size[k] for k in range(3))
    colours = obj["colours"]
    faces = []
    line = False
    corner = None
    if t == CUBOID:
        vertices = [tuple(lo[k] + (size[k] if i >> k & 1 else 0) for k in range(3)) for i in range(8)]
        for f, loop in enumerate(_CUBOID_FACES):
            axis, high = f // 2, f % 2
            others = [k for k in range(3) if k != axis]
            if colours[f] and all(size[k] for k in others):
                faces.append(_axis_face(colours[f], loop, axis, 1 if high else -1, hi[axis] if high else lo[axis]))
        corner = (lo, size)
    elif t == RECTANGLE and sum(1 for s in size if s == 0) == 1:
        axis = size.index(0)
        u, v = [k for k in range(3) if k != axis]
        vertices = []
        for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1)):
            p = list(lo)
            p[u] += size[u] * du
            p[v] += size[v] * dv
            vertices.append(tuple(p))
        # Each face's loop winds anticlockwise about its outward normal, as
        # every face's does (clip.py's cone takes it so): (0, 1, 2, 3)
        # does about e_u x e_v, which is +x, -y, +z for the zero axis.
        ccw_side = 0 if axis == 1 else 1
        for f in (0, 1):
            if colours[f]:
                loop = (0, 1, 2, 3) if f == ccw_side else (0, 3, 2, 1)
                faces.append(_axis_face(colours[f], loop, axis, 1 if f else -1, lo[axis]))
    elif t == RECTANGLE:
        # Two zero sizes: ScummVM makes it a line from the origin to the
        # far corner (GeometricObject's constructor). Three is nothing.
        if size == (0, 0, 0):
            return None
        vertices = [lo, hi]
        line = True
    elif t in PYRAMIDS:
        o = [CELL * a for a in obj["apex"]]
        rel = _PYRAMID_VERTICES[t](size[0], size[1], size[2], o)
        vertices = [tuple(lo[k] + r[k] for k in range(3)) for r in rel]
        for f, loop in enumerate(_PYRAMID_FACES):
            if colours[f]:
                face = _plane_face(colours[f], vertices, loop)
                if face:
                    faces.append(face)
    else:
        vertices = [tuple(CELL * c for c in v) for v in obj["vertices"]]
        if t == LINE:
            line = True
        else:
            loop = tuple(range(len(vertices)))
            for f in (0, 1):
                if colours[f]:
                    face = _plane_face(colours[f], vertices, loop, flip=(f == 0))
                    if face:
                        faces.append(face)
    if line:
        if vertices[0] == vertices[1] or not colours[0]:
            return None
        faces = [Face(colours[0], (0, 1))]
    if not faces:
        return None
    blo = tuple(min([lo[k]] + [v[k] for v in vertices]) for k in range(3))
    bhi = tuple(max([hi[k]] + [v[k] for v in vertices]) for k in range(3))
    s = Shape(obj, vertices, faces, _box(lo, hi), _box(blo, bhi), line)
    if corner:
        s.corner, s.size = corner
    return s


# --- The object pass ----------------------------------------------------------

def sides(box, c):
    """The original's six side bits ($5E62): bit 0 if the camera is below
    the box's x minimum, bit 1 if above its x maximum, then y, then z."""
    lo, hi = box
    bits = 0
    for k in range(3):
        if lo[k] - c[k] > 0:
            bits |= 1 << (2 * k)
        if hi[k] - c[k] < 0:
            bits |= 2 << (2 * k)
    return bits


def sensor_watching(s, c):
    """Whether a sensor is drawn from c: the camera on a side its axis bits
    watch, and the Manhattan distance from its corner less than its range
    (the original's $7592)."""
    o = s.obj["sensor"]
    if not sides(s.box, c) & o["axes"]:
        return False
    v = s.vertices[0]
    return sum(abs(v[k] - c[k]) for k in range(3)) < o["range"]


def shown(obj, state=None):
    """Whether the object is shown: not destroyed and not invisible. At an
    area's start that's "not initially invisible" (ScummVM's resetArea and
    GeometricObject's constructor); state, if given, maps an id to
    visible-or-not for objects the logic has changed."""
    if state is not None and obj["id"] in state:
        return state[obj["id"]]
    return not obj["initially_invisible"]


# The coarse cull's cone: the narrowest round cone about the view's axis
# holding the whole view, whatever the roll; its half-angle's sine, scaled
# to the matrix's 64, plus a margin for the matrix's rounding.
_CONE_TAN = math.hypot(XC / FX, YC / FY)
CONE_SIN = _CONE_TAN / math.hypot(1, _CONE_TAN)
CULL_K = math.ceil(64 * CONE_SIN) + 3


def coarse_cull(bounds, m, c):
    """True if the box is wholly behind the camera, by compares: on an axis
    every direction in the view's cone goes up (the matrix's ahead row has
    that component at least CULL_K), and the box is no higher than the
    camera on it; or every direction goes down and the box is no lower."""
    ahead = m[2]
    lo, hi = bounds
    for k in range(3):
        if ahead[k] >= CULL_K and hi[k] <= c[k]:
            return True
        if ahead[k] <= -CULL_K and lo[k] >= c[k]:
            return True
    return False


@dataclass
class Candidate:
    """An object past the object pass: its shape and the faces the camera
    sees."""
    index: int           # its place in the object pass's list
    shape: Shape
    faces: list = field(default_factory=list)


def object_pass(objects, m, c, state=None, cull=True, tally=None):
    """Every object to transform, in the given order (the original's: the
    area's objects, then the globals): shown, drawable, not culled, with at
    least one face the camera sees. tally, a dict, counts what happened to
    the rest."""
    if tally is None:
        tally = {}
    for key in ("records", "not_drawn", "hidden", "culled_coarse", "no_faces", "considered"):
        tally.setdefault(key, 0)
    out = []
    for i, obj in enumerate(objects):
        tally["records"] += 1
        s = shape(obj)
        if s is None:
            tally["not_drawn"] += 1
            continue
        if not shown(obj, state):
            tally["hidden"] += 1
            continue
        if cull and coarse_cull(s.bounds, m, c):
            tally["culled_coarse"] += 1
            continue
        if s.point and not sensor_watching(s, c):
            tally["no_faces"] += 1
            continue
        faces = [f for f in s.faces if f.seen_from(c)]
        if not faces:
            tally["no_faces"] += 1
            continue
        tally["considered"] += 1
        out.append(Candidate(i, s, faces))
    return out
