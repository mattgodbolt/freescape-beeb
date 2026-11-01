#!/usr/bin/env python3
"""Driller's areas as the engine's records (docs/research/objects.md): the
model of what src/area.6502 builds as an area is entered.

    mkareas.py DB.json TAPE OUT.6502 OUT.json

Reads build/data/driller.json and the tape it came from, and writes, into
build/gen/:

- OUT.6502: for the assembler: the model's constants the object pipeline
  needs (CULL_K, the projection's, ZNEAR), the working copy's arrays
  (section ObjArea), the tables that stay resident (section ObjConst: the
  face loops, the sine table), and what the conversion reads that isn't in
  the ZX's database (section AreaConv: each face's colour in the version
  the colours follow, decision 8; and the globals' records as the tape has
  them, for a build without the player logic), with the database's layout
  as the conversion walks it.
- OUT.json: for the checks: which of the model's objects each working slot
  holds, and every area's working copy as this builds it, which
  tools/areacheck.mjs holds src/area.6502's to, byte for byte.

Nothing of Driller's is committed: this runs at build time (decision 6).
The faces' colours are the model's, from the version the colours follow
(render.recolour, decision 8), so the records need `make colours` first.

The working copy is the object pass's (stage 2), structure of arrays
indexed by a slot: the globals in slots 0 .. G_OBJ - 1, built once, and the
area's after them, built on entering it (src/area.6502), from the records
of Driller's database where the player logic keeps them (LOGIC_BANK). Only
objects the model can draw get a slot (tools/model/objects.py's shape()
isn't None); the pass walks the area's slots, then the globals', which is
the model's order with the undrawable ones left out.

Everything a frame compares is a byte: positions are cells (an object's
world position over CELL), so the coarse cull, the side bits and the sort
compare cells against the camera's cell (docs/research/objects.md, "Cells").

Kinds:
- cuboid: its box; its eight vertices are the box's corners, vertex i
  having bit k set for the high side on axis k.
- rect: a rectangle with one zero size; its box; its four vertices in the
  model's order; ob_aux is the zero axis.
- generic: pyramids, polygons and lines (a rectangle with two zero sizes
  among them); its vertices in gv_* from slot ob_aux.
- sensor: a point at its box's corner; ob_aux indexes sn_*.

Each face has a colour, a vertex loop (an offset into the shared lp_table
and a length), the mask of the object's vertices it uses, and a test of
whether the camera sees it:
- an axis test, for a face in a plane x, y or z = P (cells): from below
  (the camera's coordinate less than 64 P, test AX_LO + 2 axis, tval P)
  the face is seen when the camera's floor cell is less than P; from above
  (AX_HI + 2 axis, tval 255 - P) when the camera's ceiling cell is more
  than P, which is 255 - ceil < tval. One compare either way.
- a plane test (PLANE, tval the plane's index): the reduced normal's two
  non-zero components and a point of the plane, 64 times a vertex's cells,
  on those axes.
- ALWAYS, for a line and a sensor's point.

ob_ix is each slot's place in the player logic's index of the area's
objects (src/logic/index.6502's ix_*: the area's records, then the
globals'), where the logic's flags say what's hidden.

How the 6502 gets there, where it isn't the model's way (src/area.6502),
is asserted here on every object, so a database it can't convert fails the
build with a reason: a slanted face's plane is the cross product at its
loop's first corner, reduced; a pyramid's side loses its apex corner when
the apex edge has shrunk to a point, and its apex face goes when any edge
of it has; every loop is one the conversion knows (lp_table's fixed
order).
"""
import json
import math
import pathlib
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools import freescape
from tools.model import clip, objects, render, view

CUBOID, RECT, GENERIC, SENSOR = 0, 1, 2, 3
F_LINE = 0x20
F_HIDDEN = 0x80                      # initially invisible (ob_flags), hidden (ob_state)
AX_LO, AX_HI = 0, 1                  # + 2 * axis
PLANE, ALWAYS = 6, 7

# The working copy's arrays: (name, index space).
SPACES = ["obj", "face", "plane", "gv", "sensor"]
ARRAYS = [
    ("ob_flags", "obj"), ("ob_id", "obj"),
    ("ob_blx", "obj"), ("ob_bly", "obj"), ("ob_blz", "obj"),
    ("ob_bhx", "obj"), ("ob_bhy", "obj"), ("ob_bhz", "obj"),
    ("ob_lx", "obj"), ("ob_ly", "obj"), ("ob_lz", "obj"),
    ("ob_hx", "obj"), ("ob_hy", "obj"), ("ob_hz", "obj"),
    ("ob_f0", "obj"), ("ob_nf", "obj"), ("ob_nv", "obj"), ("ob_aux", "obj"),
    ("ob_ix", "obj"),
    ("fa_col", "face"), ("fa_test", "face"), ("fa_tval", "face"),
    ("fa_loop", "face"), ("fa_nv", "face"), ("fa_vmask", "face"),
    ("pl_a", "plane"), ("pl_na", "plane"), ("pl_b", "plane"), ("pl_nb", "plane"),
    ("pl_ral", "plane"), ("pl_rah", "plane"), ("pl_rbl", "plane"), ("pl_rbh", "plane"),
    ("gv_x", "gv"), ("gv_y", "gv"), ("gv_z", "gv"),
    ("sn_axes", "sensor"), ("sn_rl", "sensor"), ("sn_rh", "sensor"),
]

# The database's layout, as tools/freescape.py parses it and src/area.6502
# walks it: the database's offset of each area's record, a word an area
# from DB_AREAS; an area's object count and its first object's record; an
# object's record (parse_object): its type and flags, cell, size, id and
# length, then its colours (a nibble a face), a sensor's range and axes, a
# pyramid's apex ordinates or a polygon's vertices.
DB_AREAS = 0xC8
AREA_N_OBJECTS, AREA_FIRST = 1, 25
REC = {"POS": 1, "SIZE": 4, "ID": 7, "LEN": 8, "COLOURS": 9, "RANGE": 11, "AXES": 13,
       "APEX": 12, "VERTS": 10}
FETCH_N = max(freescape.FIXED_LENGTH)   # the bytes of a record the conversion reads

# The loops the conversion picks, in a fixed order that puts each where it
# finds it by a constant: the cuboid's faces (face f's at 4 f); a polygon's
# loop forward and backward (an n-gon's backward is the last n), whose
# runs are a rectangle's, a line's and a point's too; a pyramid's sides,
# whole and with the apex corner gone (their apex edge a point), and its
# apex.
FORWARD = tuple(range(6))
BACKWARD = tuple(reversed(FORWARD))
PYRAMID_SIDES = objects._PYRAMID_FACES[:4]
PYRAMID_TRIANGLES = [side[:1] + side[2:] for side in PYRAMID_SIDES]
PYRAMID_BASE, PYRAMID_APEX = objects._PYRAMID_FACES[4:]


class Loops:
    """The face loops, shared by every area: each distinct loop once, all
    of them added before any object's (frozen): an object's loop must be
    one of them, or a run of one."""

    def __init__(self):
        self.table = []
        self.at = {}
        self.frozen = False

    def add(self, loop):
        loop = tuple(loop)
        if loop not in self.at:
            # A loop that's a run of another's needn't be stored again.
            for start in range(len(self.table) - len(loop) + 1):
                if tuple(self.table[start:start + len(loop)]) == loop:
                    self.at[loop] = start
                    break
            else:
                assert not self.frozen, "a loop the conversion doesn't know: %r" % (loop,)
                self.at[loop] = len(self.table)
                self.table.extend(loop)
        return self.at[loop]


def known_loops():
    loops = Loops()
    for loop in objects._CUBOID_FACES:
        loops.add(loop)
    for loop in [FORWARD, BACKWARD] + PYRAMID_SIDES + PYRAMID_TRIANGLES + [PYRAMID_BASE, PYRAMID_APEX]:
        loops.add(loop)
    for f, loop in enumerate(objects._CUBOID_FACES):
        assert loops.at[loop] == 4 * f
    for n in range(3, 7):
        assert loops.add(FORWARD[:n]) == loops.at[FORWARD]
        assert loops.add(BACKWARD[6 - n:]) == loops.at[BACKWARD] + 6 - n
    for loop in ((0,), (0, 1), (0, 1, 2, 3), (0, 3, 2, 1)):
        loops.add(loop)
    loops.frozen = True
    return loops


def cells(world):
    for v in world:
        assert v % view.CELL == 0, world
    out = tuple(v // view.CELL for v in world)
    for v in out:
        # Cells are compared as unsigned bytes against the camera's,
        # clamped to 0-254 (docs/research/objects.md).
        assert 0 <= v <= 254, out
    return out


def reduced(n):
    g = 0
    for x in n:
        g = math.gcd(g, abs(x))
    return tuple(x // g for x in n)


def first_corner(shape, loop):
    """The 6502's plane for a face: the cross product at its loop's first
    corner, of edges whose components are signed bytes."""
    v0, v1, v2 = (cells(shape.vertices[i]) for i in loop[:3])
    u = [v1[k] - v0[k] for k in range(3)]
    w = [v2[k] - v1[k] for k in range(3)]
    assert all(-128 <= x <= 127 for x in u + w), "an edge longer than a signed byte"
    return (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])


def conversion_faces(obj, shape):
    """The faces, (colour, loop), as src/area.6502 picks a pyramid's or a
    polygon's: by its colours, the shrunk apex edges and the first corner's
    cross product, not by objects.shape()'s Newell normals."""
    t = obj["type"]
    c = obj["colours"]
    out = []

    def face(colour, loop):
        if colour and any(first_corner(shape, loop)):
            out.append((colour, tuple(loop)))

    if t in objects.PYRAMIDS:
        v = shape.vertices
        shrunk = [v[4 + f] == v[4 + (f + 1) % 4] for f in range(4)]
        for f in range(4):
            face(c[f], PYRAMID_TRIANGLES[f] if shrunk[f] else PYRAMID_SIDES[f])
        face(c[4], PYRAMID_BASE)
        if not any(shrunk):
            face(c[5], PYRAMID_APEX)
    else:
        n = len(shape.vertices)
        face(c[0], BACKWARD[6 - n:])
        face(c[1], FORWARD[:n])
    return out


class Record:
    """One area's (or the globals') arrays."""

    def __init__(self, base):
        self.base = base            # the globals' counts, which this record's indices follow
        self.arrays = {name: [] for name, _ in ARRAYS}
        self.slots = []             # the model's object-pass index for each slot

    def count(self, space):
        return len(self.arrays[next(n for n, s in ARRAYS if s == space)])


def face_test(rec, kind, shape, face):
    """The face's test and tval (and its plane, if it has one)."""
    if face.normal is None:
        return ALWAYS, 255
    n = reduced(face.normal)
    if kind == GENERIC:
        assert reduced(first_corner(shape, face.loop)) == n, "a face's first corner isn't its plane's"
    nz = [k for k in range(3) if n[k]]
    v = cells(shape.vertices[face.loop[0]])
    if len(nz) == 1:
        k = nz[0]
        # n_k c_k > n_k v_k: from above if n_k > 0, else from below.
        p = v[k]
        if n[k] > 0:
            return AX_HI + 2 * k, 255 - p
        return AX_LO + 2 * k, p
    assert kind == GENERIC, "a box's face with a slanted plane"
    assert len(nz) == 2, "a plane with three non-zero normal components: %r" % (n,)
    a, b = nz
    for x in (n[a], n[b]):
        assert -128 <= x <= 127
    p = rec.count("plane")
    ra = view.CELL * v[a]
    rb = view.CELL * v[b]
    for name, val in (("pl_a", a), ("pl_na", n[a] & 255), ("pl_b", b), ("pl_nb", n[b] & 255),
                      ("pl_ral", ra & 255), ("pl_rah", ra >> 8),
                      ("pl_rbl", rb & 255), ("pl_rbh", rb >> 8)):
        rec.arrays[name].append(val)
    return PLANE, rec.base["plane"] + p


def add_object(rec, loops, index, obj):
    s = objects.shape(obj)
    if s is None:
        return
    t = obj["type"]
    if t == objects.CUBOID:
        kind = CUBOID
    elif t == objects.RECTANGLE and not s.line:
        kind = RECT
    elif s.point:
        kind = SENSOR
    else:
        kind = GENERIC
    box = cells(s.box[0]), cells(s.box[1])
    bounds = cells(s.bounds[0]), cells(s.bounds[1])
    if kind in (CUBOID, RECT, SENSOR):
        assert box == bounds
    nv = len(s.vertices)
    assert nv <= 8
    flags = kind | (F_LINE if s.line else 0) | (F_HIDDEN if not objects.shown(obj) else 0)
    if kind == CUBOID:
        lo, hi = box
        for i, v in enumerate(s.vertices):
            assert cells(v) == tuple(hi[k] if i >> k & 1 else lo[k] for k in range(3))
        aux = 0
    elif kind == RECT:
        aux = obj["size"].index(0)
        lo, hi = box
        u, w = [k for k in range(3) if k != aux]
        for (du, dw), v in zip(((0, 0), (1, 0), (1, 1), (0, 1)), s.vertices):
            want = list(lo)
            want[u] = hi[u] if du else lo[u]
            want[w] = hi[w] if dw else lo[w]
            assert cells(v) == tuple(want)
    elif kind == GENERIC:
        aux = rec.base["gv"] + rec.count("gv")
        for v in s.vertices:
            c = cells(v)
            rec.arrays["gv_x"].append(c[0])
            rec.arrays["gv_y"].append(c[1])
            rec.arrays["gv_z"].append(c[2])
        if not s.line:
            assert conversion_faces(obj, s) == [(f.colour, f.loop) for f in s.faces], \
                "object %d's faces aren't the conversion's" % obj["id"]
    else:
        assert cells(s.vertices[0]) == box[0]
        aux = rec.base["sensor"] + rec.count("sensor")
        sn = obj["sensor"]
        assert 0 < sn["range"] < 0x10000
        rec.arrays["sn_axes"].append(sn["axes"])
        rec.arrays["sn_rl"].append(sn["range"] & 255)
        rec.arrays["sn_rh"].append(sn["range"] >> 8)
    f0 = rec.count("face")
    for f in s.faces:
        test, tval = face_test(rec, kind, s, f)
        if kind in (CUBOID, RECT):
            assert test < PLANE
        mask = 0
        for i in f.loop:
            mask |= 1 << i
        rec.arrays["fa_col"].append(f.colour)
        rec.arrays["fa_test"].append(test)
        rec.arrays["fa_tval"].append(tval)
        rec.arrays["fa_loop"].append(loops.add(f.loop))
        rec.arrays["fa_nv"].append(len(f.loop))
        rec.arrays["fa_vmask"].append(mask)
    nf = rec.count("face") - f0
    assert 1 <= nf <= 8
    vals = {
        "ob_flags": flags, "ob_id": obj["id"],
        "ob_blx": bounds[0][0], "ob_bly": bounds[0][1], "ob_blz": bounds[0][2],
        "ob_bhx": bounds[1][0], "ob_bhy": bounds[1][1], "ob_bhz": bounds[1][2],
        "ob_lx": box[0][0], "ob_ly": box[0][1], "ob_lz": box[0][2],
        "ob_hx": box[1][0], "ob_hy": box[1][1], "ob_hz": box[1][2],
        "ob_f0": rec.base["face"] + f0, "ob_nf": nf, "ob_nv": nv, "ob_aux": aux,
        "ob_ix": index,
    }
    for name, v in vals.items():
        assert 0 <= v <= 255, (name, v)
        rec.arrays[name].append(v)
    rec.slots.append(index)


def coloured(db, area):
    """The area's objects and the globals with their faces' colours as the
    model draws them: render.recolour's, from the version the colours
    follow (decision 8)."""
    n = len(area["objects"])
    objs = render.recolour(area, area["objects"] + db["globals"])
    return objs[:n], objs[n:]


def colour_stream(objs):
    """The colour bytes the conversion takes in place of the records' own,
    in the records' layout, for each record in order that has any: a byte
    for each two faces (the first in the low nibble), and a sensor's
    colour."""
    out = []
    for o in objs:
        t = o["type"]
        if t == objects.SENSOR:
            out.append(o["sensor"]["colour"])
        elif freescape.n_colours(t):
            c = o["colours"]
            assert len(c) == freescape.n_colours(t)
            out.extend(c[i] | c[i + 1] << 4 for i in range(0, len(c), 2))
    return out


def stream_bytes(t):
    """How many colour bytes a record of type t takes from the stream."""
    return 1 if t == objects.SENSOR else freescape.n_colours(t) // 2


def build(db):
    loops = known_loops()
    zero = {s: 0 for s in SPACES}
    globals_rec = Record(zero)
    # The globals are built once, so they must be coloured alike in every
    # area.
    the_globals = coloured(db, db["areas"][0])[1]
    for area in db["areas"]:
        assert coloured(db, area)[1] == the_globals, "the globals' colours vary by area"
    for i, o in enumerate(the_globals):
        add_object(globals_rec, loops, i, o)
    globals_rec.stream = colour_stream(the_globals)
    g = {s: globals_rec.count(s) for s in SPACES}
    areas = []
    for area in db["areas"]:
        rec = Record(g)
        n_area = len(area["objects"])
        objs = coloured(db, area)[0]
        for i, o in enumerate(objs):
            add_object(rec, loops, i, o)
        rec.stream = colour_stream(objs)
        # The model's object-pass index of a global in this area, and the
        # logic's index of it: the area's records, then the globals'.
        rec.globals_index = [n_area + i for i in globals_rec.slots]
        areas.append((area, rec))
    return loops, globals_rec, areas


def tape_bytes(db, tape):
    """The database's bytes and the globals' records, from the tape, held
    to driller.json's parse of them."""
    block = freescape.data_block(tape)
    data = block[freescape.DATABASE:freescape.DATABASE + db["length"]]
    assert data[0] == len(db["areas"])
    for i, area in enumerate(db["areas"]):
        assert data[DB_AREAS + 2 * i] | data[DB_AREAS + 2 * i + 1] << 8 == area["offset"]
        assert data[area["offset"] + AREA_N_OBJECTS] == len(area["objects"])
        if area["objects"]:
            assert area["objects"][0]["offset"] == area["offset"] + AREA_FIRST
    glen = sum(o["length"] for o in db["globals"])
    gbytes = block[freescape.GLOBALS:freescape.GLOBALS + glen]
    p = 0
    for o in db["globals"]:
        parsed, end = freescape.parse_object(gbytes, p, 0)
        parsed["offset"] = None
        assert parsed == o, "the tape's globals aren't driller.json's"
        p = end
    return data, gbytes


def equb_lines(values, per=16):
    values = list(values)
    return ["    EQUB " + ", ".join(str(v) for v in values[i:i + per]) for i in range(0, len(values), per)]


def blist(name, values):
    return "%s = {%s}" % (name, ", ".join(str(v) for v in values))


def pyramid_sources():
    """Each pyramid type's vertices, coordinate by coordinate, as offsets
    into its record: its size's bytes, its apex ordinates', or AC_ZERO, a
    zero byte past the bytes read (objects._PYRAMID_VERTICES, probed)."""
    size = [1001, 1002, 1003]
    apex = [1004, 1005, 1006, 1007]
    where = {0: FETCH_N}
    for k in range(3):
        where[size[k]] = REC["SIZE"] + k
    for k in range(4):
        where[apex[k]] = REC["APEX"] + k
    out = []
    for t in objects.PYRAMIDS:
        for v in objects._PYRAMID_VERTICES[t](*size, apex):
            out.extend(where[c] for c in v)
    return out


def emit(db, loops, globals_rec, areas, gbytes, out6502, outjson):
    g = {s: globals_rec.count(s) for s in SPACES}
    maxima = {s: max(g[s] + rec.count(s) for _, rec in areas) for s in SPACES}
    L = []
    w = L.append
    w("\\ Generated by tools/mkareas.py from build/data/driller.json and the tape: not committed.")
    w("\\ The records' layout is documented there and in docs/research/objects.md.")
    w("")
    w("\\ The model's constants (tools/model/view.py, objects.py, clip.py).")
    w("CELL        = %d" % view.CELL)
    w("CULL_K      = %d" % objects.CULL_K)
    w("ZNEAR       = %d" % view.ZNEAR)
    w("\\ The guard band (decision 17): |X| <= 2^GUARD_XS Z, |Y| <= 2^GUARD_YS Z.")
    for name, slope in (("GUARD_XS", clip.GUARD_X), ("GUARD_YS", clip.GUARD_Y)):
        assert slope & (slope - 1) == 0, "the guard band's slopes are shifts"
        w("%-11s = %d" % (name, slope.bit_length() - 1))
    w("\\ The band a face is projected whole inside (clip.projectable).")
    w("BAND_XS     = %d" % clip.BAND_XS)
    w("BAND_YS     = %d" % clip.BAND_YS)
    w("\\ The cone (render.CONE), and its lines' precision (clip.LINE_BITS).")
    w("CONE        = %s" % ("TRUE" if render.CONE else "FALSE"))
    w("LINE_BITS   = %d" % clip.LINE_BITS)
    w("\\ The cone's pieces (render.BEHIND_EDGES, render.FRONT_FIRST, clip.SIDE_CROSSINGS,")
    w("\\ clip.JOINS), the 2D clip's crossings by a reciprocal (clip.RECIP_2D), the")
    w("\\ cone's side crossings so (clip.SIDE_RECIP) but a unit line's (clip.UNIT_SIDES), and")
    w("\\ its lines from images (render.IMAGE_LINES), their precision (clip.IMAGE_BITS).")
    for name, on in (("BEHIND_EDGES", render.BEHIND_EDGES), ("FRONT_FIRST", render.FRONT_FIRST),
                     ("SIDE_CROSSINGS", clip.SIDE_CROSSINGS), ("JOINS", clip.JOINS),
                     ("RECIP_2D", clip.RECIP_2D), ("SIDE_RECIP", clip.SIDE_RECIP),
                     ("UNIT_SIDES", clip.UNIT_SIDES), ("IMAGE_LINES", render.IMAGE_LINES)):
        w("%-11s = %s" % (name, "TRUE" if on else "FALSE"))
    w("IMAGE_BITS  = %d" % clip.IMAGE_BITS)
    w("")
    w("VIEW_FX    = %d             ; the focal lengths, sixteenths" % view.FX)
    w("VIEW_FY     = %d" % view.FY)
    w("")
    w("K_CUBOID = %d : K_RECT = %d : K_GENERIC = %d : K_SENSOR = %d" % (CUBOID, RECT, GENERIC, SENSOR))
    w("K_MASK = 3 : F_LINE = &%02X : F_HIDDEN = &%02X" % (F_LINE, F_HIDDEN))
    w("T_AXLO = %d : T_AXHI = %d : T_PLANE = %d : T_ALWAYS = %d" % (AX_LO, AX_HI, PLANE, ALWAYS))
    w("")
    w("\\ The largest any area needs, globals included, and the globals' own.")
    for s in SPACES:
        w("%-11s = %d" % ("N_" + s.upper(), max(1, maxima[s])))
        w("%-11s = %d" % ("G_" + s.upper(), g[s]))
    w("AR_COUNT    = %d" % len(areas))
    w("LP_SIZE     = %d" % len(loops.table))
    w("ASSERT N_OBJ <= 255 AND N_FACE <= 255 AND N_PLANE <= 255 AND N_GV <= 255 AND LP_SIZE <= 256")
    w("")
    w("\\ The database's layout (tools/freescape.py's parse), as src/area.6502 walks it.")
    w("AREA_DB_LEN = %d          ; the database's bytes" % db["length"])
    w("DB_AREAS    = &%02X          ; each area's record's offset, a word an area" % DB_AREAS)
    w("AREA_N_OBJECTS = %d : AREA_FIRST = %d" % (AREA_N_OBJECTS, AREA_FIRST))
    w(" : ".join("REC_%s = %d" % (k, v) for k, v in REC.items()))
    w("FETCH_N     = %d          ; the most of a record's bytes read: its fixed part's most" % FETCH_N)
    w("AC_ZERO     = FETCH_N     ; a zero byte past them")
    w("\\ The bytes of a record's fixed part by its type's low nibble (a group's its")
    w("\\ first nine; tools/freescape.py's FIXED_LENGTH).")
    w(blist("AC_FIXED", freescape.FIXED_LENGTH + [REC["LEN"] + 1]))
    w("G_RECORDS   = %d           ; the globals' records" % len(db["globals"]))
    w("\\ The logic's index (src/logic/index.6502) needs this many places at most.")
    w("IX_MOST     = %d" % (max(len(a["objects"]) for a in db["areas"]) + len(db["globals"])))
    w("\\ Colour bytes each record type takes from the colour stream (AreaConv).")
    w(blist("AC_COLOURS", [stream_bytes(t) for t in range(15)]))
    w("\\ The globals' places in the logic's index, by slot (the area's records come first).")
    w(blist("G_IX", globals_rec.slots))
    w("")
    w("\\ Where the conversion finds each loop in lp_table: the cuboid's face f at")
    w("\\ 4 f; an n-gon's forward at LP_FWD, backward at LP_BACK + 6 - n; a")
    w("\\ pyramid's side f at LP_SIDE[f], or LP_TRI[f] with its apex corner gone.")
    w("LP_FWD = %d : LP_BACK = %d : LP_POINT = %d : LP_LINE = %d : LP_RECT = %d : LP_RECT_BACK = %d" % (
        loops.at[FORWARD], loops.at[BACKWARD], loops.at[(0,)], loops.at[(0, 1)], loops.at[(0, 1, 2, 3)],
        loops.at[(0, 3, 2, 1)]))
    w("LP_BASE = %d : LP_APEX = %d" % (loops.at[PYRAMID_BASE], loops.at[PYRAMID_APEX]))
    w(blist("LP_SIDE", [loops.at[s] for s in PYRAMID_SIDES]))
    w(blist("LP_TRI", [loops.at[s] for s in PYRAMID_TRIANGLES]))
    w(blist("CUBE_VMASK", [sum(1 << i for i in f) for f in objects._CUBOID_FACES]))
    w("\\ A pyramid's vertices (types 4-9), each coordinate an offset into its record.")
    w(blist("PYR_REC", pyramid_sources()))
    w("")
    w("\\ The working copy: the globals' entries, then the area's.")
    w("SECTION ObjArea")
    for name, space in ARRAYS:
        w(".%-10s SKIP N_%s" % (name, space.upper()))
    w(".ar_counts  SKIP %d       ; the area's counts, objects, faces, planes, vertices, sensors" % len(SPACES))
    w("ENDSECTION")
    w("")
    w("SECTION ObjConst")
    w("\\ Every face's loop of vertices (indices into its object's), shared.")
    w(".lp_table")
    L.extend(equb_lines(loops.table))
    w("\\ The original's sine table (tables.sin, tables.cos): 72 steps of 5")
    w("\\ degrees, signed bytes, 1.0 = 64.")
    w(".sin_table")
    w("    EQUB " + ", ".join(str(v & 255) for v in db["tables"]["sin"]))
    w(".cos_table")
    w("    EQUB " + ", ".join(str(v & 255) for v in db["tables"]["cos"]))
    w("ENDSECTION")
    w("")
    w("SECTION AreaConv")
    w("\\ Each area's colour stream (its records' colours in the version the")
    w("\\ colours follow), by its index in the database, and the globals'.")
    w(".ac_streams_lo")
    w("    EQUB " + ", ".join("LO(ac_stream_%d)" % i for i in range(len(areas))))
    w(".ac_streams_hi")
    w("    EQUB " + ", ".join("HI(ac_stream_%d)" % i for i in range(len(areas))))
    w(".ac_stream_globals")
    L.extend(equb_lines(globals_rec.stream))
    for i, (area, rec) in enumerate(areas):
        w(".ac_stream_%d     \\ %s" % (i, area["name"].strip()))
        L.extend(equb_lines(rec.stream))
    w("\\ The globals' records as the tape has them, for a build without the logic,")
    w("\\ which keeps its own (src/logic/vars.6502's Globals).")
    w(".ac_tape_globals")
    L.extend(equb_lines(gbytes))
    w("ENDSECTION")
    pathlib.Path(out6502).write_text("\n".join(L) + "\n")

    def hidden(objs):
        return [0 if objects.shown(o) else 1 for o in objs]

    streams = len(globals_rec.stream) + sum(len(rec.stream) for _, rec in areas)
    copy = sum(maxima[s] for _, s in ARRAYS) + len(SPACES)
    layout = {
        "spaces": SPACES,
        "arrays": ARRAYS,
        "globals": {"counts": g, "slots": globals_rec.slots, "arrays": globals_rec.arrays,
                    "hidden": hidden(db["globals"])},
        "maxima": maxima,
        "copy_bytes": copy,
        "stream_bytes": streams,
        "tape_globals_bytes": len(gbytes),
        "loops": len(loops.table),
        "areas": [{
            "index": i, "id": area["id"], "name": area["name"].strip(),
            "records": len(area["objects"]),
            "counts": {s: rec.count(s) for s in SPACES},
            "slots": rec.slots, "globals_index": rec.globals_index,
            "arrays": rec.arrays, "hidden": hidden(area["objects"]),
        } for i, (area, rec) in enumerate(areas)],
    }
    pathlib.Path(outjson).write_text(json.dumps(layout, indent=1) + "\n")
    return layout


def main(argv):
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        db = json.load(f)
    with open(argv[2], "rb") as f:
        _, gbytes = tape_bytes(db, f.read())
    loops, globals_rec, areas = build(db)
    layout = emit(db, loops, globals_rec, areas, gbytes, argv[3], argv[4])
    print("areas: %d; the working copy %d bytes; colour streams %d bytes; the tape's globals %d bytes; "
          "loops %d; maxima %s" % (
              len(layout["areas"]), layout["copy_bytes"], layout["stream_bytes"],
              layout["tape_globals_bytes"], layout["loops"], layout["maxima"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
