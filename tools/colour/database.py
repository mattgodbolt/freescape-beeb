"""Driller's database, as far as the colour study needs it.

A small parser after ScummVM's load8bitBinary, load8bitArea and
load8bitObject (loaders/8bitBinaryLoader.cpp). It reads the colour map,
each area's header and each object's type, place, size and colour
nibbles, and skips the rest.

The 16-bit versions (Amiga, ST) store the same database with every byte
widened to a big-endian word, and pointers as two such words counting
words (readField and readPtr, 8bitBinaryLoader.cpp:38-75). narrow() turns
one back into the 8-bit layout, keeping the words whose high byte is set,
so one parser reads every version.
"""

import struct

TYPES = {0: "entrance", 1: "cube", 2: "sensor", 3: "rect", 4: "pyrE",
         5: "pyrW", 6: "pyrU", 7: "pyrD", 8: "pyrN", 9: "pyrS", 10: "line",
         11: "tri", 12: "quad", 13: "pent", 14: "hex", 15: "group"}

# Face order of a cuboid's six colours (gfx.cpp:973-1095, renderCube): -X, +X, -Y,
# +Y, -Z, +Z. The top face is +Y.
CUBE_TOP = 3


def ncolours(t):
    """Colour nibbles for type t (GeometricObject::numberOfColoursForObjectOfType)."""
    if t in (0, 2, 15):
        return 0
    if t == 1 or 4 <= t <= 9:
        return 6
    return 2


def nords(t):
    if 4 <= t <= 9:
        return 4
    if 10 <= t <= 14:
        return 3 * (t - 8)
    return 0


def narrow(words_bytes, off, end=None):
    """The 16-bit database at off as 8-bit bytes, and {byte index: high byte}
    for each word whose high byte isn't zero."""
    end = len(words_bytes) if end is None else end
    n = (end - off) // 2
    words = struct.unpack_from(f">{n}H", words_bytes, off)
    high = {i: w >> 8 for i, w in enumerate(words) if w >> 8}
    return bytes(w & 0xFF for w in words), high


def parse_object(d, p):
    raw = d[p]
    t = raw & 0x1F
    o = {"type": TYPES.get(t, f"t{t}"), "t": t, "flags": raw & 0xE0,
         "pos": list(d[p + 1:p + 4]), "size": list(d[p + 4:p + 7]),
         "id": d[p + 7], "len": d[p + 8], "colours": []}
    if o["len"] < 9:
        raise ValueError(f"object at {p:#x}: length {o['len']}")
    q = p + 9
    if t == 2:
        o["sensor_colour"] = d[q] & 0xF
    for _ in range(ncolours(t) // 2):
        o["colours"] += [d[q] & 0xF, d[q] >> 4]
        q += 1
    o["ords"] = list(d[q:q + nords(t)])
    return o, p + o["len"]


def parse_area(d, p):
    a = {"flags": d[p], "nobj": d[p + 1], "id": d[p + 2],
         "cptr": d[p + 3] | (d[p + 4] << 8), "scale": d[p + 5],
         # +6..+9: usual background, under-fire background, paper, ink
         # (8bitBinaryLoader.cpp:667-670).
         "colours": list(d[p + 6:p + 10]),
         "gas": list(d[p + 10:p + 13]),
         "name": d[p + 13:p + 25].decode("latin-1").strip(),
         "offset": p}
    q = p + 25
    objs = []
    for _ in range(a["nobj"]):
        o, q = parse_object(d, q)
        objs.append(o)
    a["objects"] = objs
    return a


def parse(d, off):
    """The database at off in d (8-bit layout)."""
    db = {"n_areas": d[off], "size": d[off + 1] | (d[off + 2] << 8),
          "start_area": d[off + 3], "start_entrance": d[off + 4],
          # +0A: the colour map, 15 entries of four bytes, one a row.
          "colour_map": [list(d[off + 0xA + 4 * i:off + 0xE + 4 * i])
                         for i in range(15)]}
    offs = [d[off + 0xC8 + 2 * i] | (d[off + 0xC9 + 2 * i] << 8)
            for i in range(db["n_areas"])]
    db["areas"] = [parse_area(d, off + o) for o in offs]
    return db


def floor_of(area):
    """The area's floor: the widest cuboid whose top face is coloured and
    whose base is at y = 0, or None. Driller has no ground plane; its
    platforms stand on such an object (docs/research/colour.md)."""
    best = None
    for o in area["objects"]:
        if o["t"] != 1 or o["flags"] & 0xC0 or o["pos"][1] != 0:
            continue
        if not o["colours"][CUBE_TOP]:
            continue
        a = o["size"][0] * o["size"][2]
        if best is None or a > best[0]:
            best = (a, o)
    return None if best is None else best[1]
