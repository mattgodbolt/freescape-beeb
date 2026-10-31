#!/usr/bin/env python3
"""Driller's areas as the engine's records (docs/research/objects.md).

    mkareas.py DB.json OUT.6502 OUT.json

Reads build/data/driller.json and writes, into build/gen/:

- OUT.6502: the records for the assembler: the model's constants the
  object pipeline needs (CULL_K, the projection's, ZNEAR), the working
  copy's arrays (section ObjArea), the tables that stay resident (section
  ObjConst: the face loops, the area directory, the copy's descriptors,
  the globals' record), and each area's packed record in sideways RAM
  (sections AreaBank4 onwards, saved as AREAS4 ...).
- OUT.json: the layout, for tools/objectcheck.mjs: each area's bank and
  address, and which of the model's objects each working slot holds.

Nothing of Driller's is committed: this runs at build time (decision 6).
The faces' colours are the model's, from the version the colours follow
(render.recolour, decision 8), so the records need `make colours` first.

The layout is the object pass's (stage 2), structure of arrays indexed by
a slot: the globals in slots 0 .. G_OBJ - 1, copied once, and the area's
after them, copied on entering it (src/area.6502). Only objects the model
can draw get a slot (tools/model/objects.py's shape() isn't None); the
pass walks the area's slots, then the globals', which is the model's order
with the undrawable ones left out.

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
- a plane test (PLANE, tval the plane's index): the reduced normal's one
  or two non-zero components and a point of the plane, 64 times a vertex's
  cells, on those axes.
- ALWAYS, for a line and a sensor's point.
"""
import json
import math
import pathlib
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.model import clip, objects, render, view

CUBOID, RECT, GENERIC, SENSOR = 0, 1, 2, 3
F_LINE = 0x20
F_HIDDEN = 0x80                      # initially invisible (ob_flags), hidden (ob_state)
AX_LO, AX_HI = 0, 1                  # + 2 * axis
PLANE, ALWAYS = 6, 7
BANKS = [4, 5, 6, 7]                 # decision 5
BANK_SIZE = 0x4000
BANK_ORG = 0x8000

# The working copy's arrays: (name, index space, what it holds). The
# packed records hold them in this order, each as long as its space's count.
SPACES = ["obj", "face", "plane", "gv", "sensor"]
ARRAYS = [
    ("ob_flags", "obj"), ("ob_id", "obj"),
    ("ob_blx", "obj"), ("ob_bly", "obj"), ("ob_blz", "obj"),
    ("ob_bhx", "obj"), ("ob_bhy", "obj"), ("ob_bhz", "obj"),
    ("ob_lx", "obj"), ("ob_ly", "obj"), ("ob_lz", "obj"),
    ("ob_hx", "obj"), ("ob_hy", "obj"), ("ob_hz", "obj"),
    ("ob_f0", "obj"), ("ob_nf", "obj"), ("ob_nv", "obj"), ("ob_aux", "obj"),
    ("fa_col", "face"), ("fa_test", "face"), ("fa_tval", "face"),
    ("fa_loop", "face"), ("fa_nv", "face"), ("fa_vmask", "face"),
    ("pl_a", "plane"), ("pl_na", "plane"), ("pl_b", "plane"), ("pl_nb", "plane"),
    ("pl_ral", "plane"), ("pl_rah", "plane"), ("pl_rbl", "plane"), ("pl_rbh", "plane"),
    ("gv_x", "gv"), ("gv_y", "gv"), ("gv_z", "gv"),
    ("sn_axes", "sensor"), ("sn_rl", "sensor"), ("sn_rh", "sensor"),
]

class Loops:
    """The face loops, shared by every area: each distinct loop once."""

    def __init__(self):
        self.table = []
        self.at = {}

    def add(self, loop):
        loop = tuple(loop)
        if loop not in self.at:
            # A loop that's a run of another's needn't be stored again.
            for start in range(len(self.table) - len(loop) + 1):
                if tuple(self.table[start:start + len(loop)]) == loop:
                    self.at[loop] = start
                    break
            else:
                self.at[loop] = len(self.table)
                self.table.extend(loop)
        return self.at[loop]


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


class Record:
    """One area's (or the globals') arrays, before packing."""

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


def build(db):
    loops = Loops()
    # Shared loops first, in a fixed order, so the cuboids' are where the
    # 6502 can find them by face.
    for loop in objects._CUBOID_FACES:
        loops.add(loop)
    zero = {s: 0 for s in SPACES}
    globals_rec = Record(zero)
    # The globals are copied once, so they must be coloured alike in every
    # area.
    the_globals = coloured(db, db["areas"][0])[1]
    for area in db["areas"]:
        assert coloured(db, area)[1] == the_globals, "the globals' colours vary by area"
    for i, o in enumerate(the_globals):
        add_object(globals_rec, loops, i, o)
    g = {s: globals_rec.count(s) for s in SPACES}
    areas = []
    for area in db["areas"]:
        rec = Record(g)
        n_area = len(area["objects"])
        for i, o in enumerate(coloured(db, area)[0]):
            add_object(rec, loops, i, o)
        # The model's object-pass index of a global in this area.
        rec.globals_index = [n_area + i for i in globals_rec.slots]
        areas.append((area, rec))
    return loops, globals_rec, areas


def outcode_shifts(a, b):
    """For the side test A p > B z with z >= ZNEAR, src/clip.6502's
    oc_side compares p with w = z >> SHI and fractions of it, each rounded
    down, before it multiplies: p >= w is outside, p < w/2 inside, p < 5w/8
    (w/2 + w/8) inside and p >= 6w/8 (that plus w/8) outside. SHI is the
    least shift with the ratio B 2^SHI / A in [5/8, 6/8); these assert that
    each test holds however its shifts round down, for every z >= ZNEAR."""
    shi = 0
    while 5 * a > 8 * (b << shi):
        shi += 1
    w = 8 << shi                    # z per unit of the eighths
    assert 5 * a <= 8 * (b << shi) < 6 * a, "the side's ratio isn't in [5/8, 6/8)"
    # p >= w: w >= z / 2^shi - 1, so A p > B z if z (A - B 2^shi) > A 2^shi
    assert view.ZNEAR * (a - (b << shi)) > a << shi
    # p >= w/2 + 2 (w/2 >> 2), at least 6 z / w - 3: A p > B z if
    # z (6 A - B w) > 3 A w
    assert view.ZNEAR * (6 * a - b * w) > 3 * a * w
    return shi + 1, shi


def packed(rec):
    counts = [rec.count(s) for s in SPACES]
    out = list(counts)
    for name, _ in ARRAYS:
        out.extend(rec.arrays[name])
    return out


def emit(db, loops, globals_rec, areas, out6502, outjson):
    g = {s: globals_rec.count(s) for s in SPACES}
    maxima = {s: max(g[s] + rec.count(s) for _, rec in areas) for s in SPACES}
    L = []
    w = L.append
    w("\\ Generated by tools/mkareas.py from build/data/driller.json: not committed.")
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
    w("")
    w("\\ The side planes (tools/model/clip.py's outcode): a vertex is outside")
    w("\\ one when A p > B z, p its distance across (x or y, the side's way).")
    w("\\ It is when p >= z >> SHI and isn't when p < z >> SLO, so only")
    w("\\ between those does the clip multiply (src/clip.6502).")
    width, height = view.SUB * view.VIEW_W, view.SUB * view.VIEW_H
    for side, a, b in (("L", view.FX, view.XC), ("R", view.FX, width - view.XC),
                       ("T", view.FY, view.YC), ("B", view.FY, height - view.YC)):
        slo, shi = outcode_shifts(a, b)
        w("OC_%s_A = %d : OC_%s_B = %d : OC_%s_SLO = %d : OC_%s_SHI = %d" % (
            side, a, side, b, side, slo, side, shi))
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
    w("\\ The working copy: the globals' entries, then the area's.")
    w("SECTION ObjArea")
    for name, space in ARRAYS:
        w(".%-10s SKIP N_%s" % (name, space.upper()))
    w(".ar_counts  SKIP %d       ; the area's counts, as its record has them" % len(SPACES))
    w("ENDSECTION")
    w("")
    w("SECTION ObjConst")
    w("\\ Every face's loop of vertices (indices into its object's), shared.")
    w(".lp_table")
    for i in range(0, len(loops.table), 16):
        w("    EQUB " + ", ".join(str(v) for v in loops.table[i:i + 16]))
    w("\\ The copy's descriptors: each array's destination for an area, and")
    w("\\ which of the record's counts it's as long as.")
    w(".ad_dest_lo")
    w("    EQUB " + ", ".join("LO(%s + G_%s)" % (n, s.upper()) for n, s in ARRAYS))
    w(".ad_dest_hi")
    w("    EQUB " + ", ".join("HI(%s + G_%s)" % (n, s.upper()) for n, s in ARRAYS))
    w("\\ ... and the globals' destinations, the arrays' first entries.")
    w(".ad_gdest_lo")
    w("    EQUB " + ", ".join("LO(%s)" % n for n, _ in ARRAYS))
    w(".ad_gdest_hi")
    w("    EQUB " + ", ".join("HI(%s)" % n for n, _ in ARRAYS))
    w(".ad_space")
    w("    EQUB " + ", ".join(str(SPACES.index(s)) for _, s in ARRAYS))
    w("AD_COUNT = %d" % len(ARRAYS))
    w("\\ The original's sine table (tables.sin, tables.cos): 72 steps of 5")
    w("\\ degrees, signed bytes, 1.0 = 64.")
    w(".sin_table")
    w("    EQUB " + ", ".join(str(v & 255) for v in db["tables"]["sin"]))
    w(".cos_table")
    w("    EQUB " + ", ".join(str(v & 255) for v in db["tables"]["cos"]))
    w("\\ The globals' record, copied once to the working copy's first entries.")
    w(".globals_record")
    gp = packed(globals_rec)
    for i in range(0, len(gp), 16):
        w("    EQUB " + ", ".join(str(v) for v in gp[i:i + 16]))
    # The areas, packed into banks in order.
    placed = []
    bank_i, at = 0, 0
    for area, rec in areas:
        p = packed(rec)
        if at + len(p) > BANK_SIZE:
            bank_i, at = bank_i + 1, 0
        assert bank_i < len(BANKS), "the areas don't fit in the banks"
        placed.append((area, rec, BANKS[bank_i], BANK_ORG + at, p))
        at += len(p)
    w("\\ The area directory: each area's bank, record and Driller's id.")
    w(".ar_bank")
    w("    EQUB " + ", ".join(str(b) for _, _, b, _, _ in placed))
    w(".ar_lo")
    w("    EQUB " + ", ".join("LO(&%04X)" % a for _, _, _, a, _ in placed))
    w(".ar_hi")
    w("    EQUB " + ", ".join("HI(&%04X)" % a for _, _, _, a, _ in placed))
    w(".ar_id")
    w("    EQUB " + ", ".join(str(area["id"]) for area, _, _, _, _ in placed))
    w("ENDSECTION")
    w("")
    banks_used = sorted({b for _, _, b, _, _ in placed})
    for b in banks_used:
        w("SECTION AreaBank%d, org = &%04X, guard = &%04X, filename = \"AREAS%d\"" % (
            b, BANK_ORG, BANK_ORG + BANK_SIZE, b))
        for area, rec, bank, addr, p in placed:
            if bank != b:
                continue
            w(".area_%d     \\ %s" % (area["id"], area["name"].strip()))
            w("    ASSERT P%% = &%04X" % addr)
            for i in range(0, len(p), 16):
                w("    EQUB " + ", ".join(str(v) for v in p[i:i + 16]))
        w("ENDSECTION")
    pathlib.Path(out6502).write_text("\n".join(L) + "\n")
    layout = {
        "spaces": SPACES,
        "globals": {"counts": g, "slots": globals_rec.slots, "bytes": len(gp)},
        "maxima": maxima,
        "loops": len(loops.table),
        "areas": [{
            "index": i, "id": area["id"], "name": area["name"].strip(), "bank": bank,
            "address": addr, "bytes": len(p),
            "counts": {s: rec.count(s) for s in SPACES},
            "slots": rec.slots, "globals_index": rec.globals_index,
        } for i, (area, rec, bank, addr, p) in enumerate(placed)],
        "banks": {str(b): sum(len(p) for _, _, bank, _, p in placed if bank == b) for b in banks_used},
    }
    pathlib.Path(outjson).write_text(json.dumps(layout, indent=1) + "\n")
    return layout


def main(argv):
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        db = json.load(f)
    loops, globals_rec, areas = build(db)
    layout = emit(db, loops, globals_rec, areas, argv[2], argv[3])
    total = sum(a["bytes"] for a in layout["areas"])
    print("areas: %d records, %d bytes in banks %s; globals %d bytes; loops %d; maxima %s" % (
        len(layout["areas"]), total, layout["banks"], layout["globals"]["bytes"],
        layout["loops"], layout["maxima"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
