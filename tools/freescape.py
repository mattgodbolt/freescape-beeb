#!/usr/bin/env python3
"""Driller's database, straight off the ZX retail tape, as JSON.

    freescape.py TAPE OUT.json      write the database (make data)
    freescape.py --check OUT.json   check a written database against
                                    the counts below; exit 1 if any fail

The tape is untrusted data: run this with python -I, and nothing here
executes what it reads.

The layout follows ScummVM's 8-bit loader (load8bitBinary, load8bitArea,
load8bitObject in loaders/8bitBinaryLoader.cpp, and games/driller/zx.cpp
for the ZX retail offsets), checked against John Elliott's Driller notes
and Castle Master II's annotated Z80 (docs/research/freescape.md,
section 2). Nothing is converted: every field is the byte the original
holds, in its own units (cells for positions and sizes, 5 degree steps
for angles, colour indices 0-15), and the model decides what they mean
(docs/research/model.md).
"""
import hashlib
import json
import struct
import sys

# The data block: TZX block 5, a turbo block holding the game's code and
# data, which the loader puts at LOAD in the Spectrum's memory.
BLOCK = 5
LOAD = 0x6B12

# ScummVM's detection entry for the ZX retail data (detection.cpp): the md5
# of the first 5000 bytes, and the length.
SCUMMVM_MD5_5000 = "396c1789a7da3db5058d18eb8d2d35a3"
SCUMMVM_LENGTH = 37590

# Offsets in the block (games/driller/zx.cpp, GF_ZX_RETAIL).
DATABASE = 0x642C
GLOBALS = 0x1C93
N_GLOBALS = 8

# Tables in the Spectrum's memory the model needs (docs/research/freescape.md,
# section 4, and docs/research/zx-driller.md): the sine table, 72 entries of (sin, cos) as signed bytes
# with 1.0 = 64; and the step and turn tables, each a count and then that
# many bytes (steps in world units, turns in 5 degree units).
SINCOS = 0x8E78
STEPS = 0x88BE
TURNS = 0x88C9
# The matrix's scaling diagonal (x, y, z), signed bytes with 1.0 = 64, and
# the projection's centre (x, y) in ZX pixels (docs/research/zx-driller.md).
SCALE = 0x88D2
CENTRE = 0x88D9

KINDS = {
    0: "entrance", 1: "cuboid", 2: "sensor", 3: "rectangle",
    4: "pyramid_e", 5: "pyramid_w", 6: "pyramid_u", 7: "pyramid_d",
    8: "pyramid_n", 9: "pyramid_s",
    10: "line", 11: "triangle", 12: "quad", 13: "pentagon", 14: "hexagon",
    15: "group",
}
# Each type's fixed record length; bytes past it are FCL
# (Castle Master II's L6b2c_expected_object_size_by_type).
FIXED_LENGTH = [9, 12, 14, 10, 16, 16, 16, 16, 16, 16, 16, 19, 22, 25, 28]

# The counts measured when the research parsed it (BRIEF.md), which the
# check holds the parse to.
EXPECTED = {
    "areas": 29, "records": 669, "geometric": 576, "cuboids": 277,
    "rectangles": 162, "pyramids": 101, "entrances": 65, "sensors": 28,
    "groups": 0,
}


# --- The tape ---------------------------------------------------------------

def tzx_blocks(buf):
    """Each data-carrying block of a TZX file, as (id, data), the data
    including its flag and checksum bytes."""
    if buf[:8] != b"ZXTape!\x1a":
        raise ValueError("not a TZX file")
    p = 10
    out = []
    while p < len(buf):
        bid = buf[p]
        p += 1
        if bid == 0x10:      # standard speed data
            n = struct.unpack_from("<H", buf, p + 2)[0]
            out.append((bid, buf[p + 4:p + 4 + n]))
            p += 4 + n
        elif bid == 0x11:    # turbo speed data
            n = int.from_bytes(buf[p + 15:p + 18], "little")
            out.append((bid, buf[p + 18:p + 18 + n]))
            p += 18 + n
        elif bid == 0x14:    # pure data
            n = int.from_bytes(buf[p + 7:p + 10], "little")
            out.append((bid, buf[p + 10:p + 10 + n]))
            p += 10 + n
        elif bid == 0x12:
            p += 4
        elif bid == 0x13:
            p += 1 + 2 * buf[p]
        elif bid == 0x20:
            p += 2
        elif bid in (0x21, 0x30):
            p += 1 + buf[p]
        elif bid in (0x22, 0x25):
            pass
        elif bid == 0x24:
            p += 2
        elif bid == 0x32:
            p += 2 + struct.unpack_from("<H", buf, p)[0]
        elif bid == 0x35:
            p += 0x14 + struct.unpack_from("<I", buf, p + 0x10)[0]
        else:
            raise ValueError("TZX block id %02x at %x not handled" % (bid, p - 1))
    return out


def data_block(tape):
    """The game's data block: its body without the flag and checksum, which
    must check (the XOR of every byte, flag and checksum included, is 0)."""
    _, data = tzx_blocks(tape)[BLOCK]
    x = 0
    for b in data:
        x ^= b
    if x != 0:
        raise ValueError("block %d's checksum fails" % BLOCK)
    return data[1:-1]


# --- The database -------------------------------------------------------------

def s8(b):
    return b - 256 if b >= 128 else b


def n_colours(t):
    if t in (0, 2, 15):
        return 0
    if t == 1 or 4 <= t <= 9:
        return 6
    return 2


def n_ordinates(t):
    if 4 <= t <= 9:
        return 4
    if 10 <= t <= 14:
        return 3 * (t - 8)
    return 0


def parse_object(d, p, base):
    """One object record at d[p]; base is the database's offset, so each
    record's offset is given within the database."""
    raw = d[p]
    t = raw & 0x1F
    length = d[p + 8]
    o = {
        "offset": p - base,
        "raw": raw,
        "type": t,
        "kind": KINDS.get(t, "t%d" % t),
        "destroyed": bool(raw & 0x20),
        "invisible": bool(raw & 0x40),
        "initially_invisible": bool(raw & 0x80),
        "id": d[p + 7],
        "length": length,
    }
    if length < 9:
        raise ValueError("object at %x is %d bytes" % (p, length))
    end = p + length
    if t == 15:
        # Groups are a different record (ScummVM's load8bitGroup); Driller
        # has none, and the check says so.
        o["group"] = d[p + 1:end].hex()
        return o, end
    o["pos"] = list(d[p + 1:p + 4])
    o["size"] = list(d[p + 4:p + 7])
    q = p + 9
    if t == 0:
        # An entrance's three size bytes are its angles, in 5 degree units:
        # pitch, yaw and roll (ScummVM's Entrance rotation x, y, z).
        o["rotation"] = o.pop("size")
    elif t == 2:
        o["sensor"] = {
            "colour": d[q] & 0x0F,
            "interval": d[q + 1],
            "range": d[q + 2] | (d[q + 3] << 8),
            "axes": d[q + 4],
        }
        q += 5
    else:
        colours = []
        for _ in range(n_colours(t) // 2):
            colours += [d[q] & 0x0F, d[q] >> 4]
            q += 1
        o["colours"] = colours
        k = n_ordinates(t)
        ords = list(d[q:q + k])
        q += k
        if 4 <= t <= 9:
            o["apex"] = ords
        elif k:
            o["vertices"] = [ords[i:i + 3] for i in range(0, k, 3)]
    if q > end:
        raise ValueError("object at %x overruns its length" % p)
    if t < len(FIXED_LENGTH) and q - p != FIXED_LENGTH[t]:
        raise ValueError("object at %x: fixed part %d, not %d" % (p, q - p, FIXED_LENGTH[t]))
    o["fcl"] = d[q:end].hex()
    return o, end


def parse_conditions(d, r):
    """A count and then that many conditions, each a length and FCL bytes."""
    n = d[r]
    r += 1
    out = []
    for _ in range(n):
        ln = d[r]
        out.append(d[r + 1:r + 1 + ln].hex())
        r += 1 + ln
    return out, r


def parse_area(d, p, base):
    flags = d[p]
    a = {
        "offset": p - base,
        "flags": flags,
        # ScummVM's reading of the flags byte (load8bitArea): sky colour in
        # the low nibble, ground colour in the high one, 0 for none.
        "sky": flags & 0x0F,
        "ground": flags >> 4,
        "n_objects": d[p + 1],
        "id": d[p + 2],
        "conditions_offset": d[p + 3] | (d[p + 4] << 8),
        "scale": d[p + 5],
        # The four colour bytes: usual background, background under fire,
        # paper and ink (on the ZX, attribute colours 0-7).
        "colours": list(d[p + 6:p + 10]),
        # Driller's gas pocket: x and z in cells, and its radius.
        "gas": list(d[p + 10:p + 13]),
        "name": d[p + 13:p + 25].decode("latin-1"),
    }
    q = p + 25
    objects = []
    for _ in range(a["n_objects"]):
        o, q = parse_object(d, q, base)
        objects.append(o)
    a["objects"] = objects
    a["objects_end"] = q - p
    a["conditions"], r = parse_conditions(d, p + a["conditions_offset"])
    a["length"] = r - p
    return a


def parse_database(d, off):
    db = {
        "n_areas": d[off],
        "length": d[off + 1] | (d[off + 2] << 8),
        "start_area": d[off + 3],
        "start_entrance": d[off + 4],
        "unknown_5": d[off + 5],
        # ScummVM: the tank's energy and shield, then the jet's.
        "initial": list(d[off + 6:off + 10]),
        # The 15 shade patterns, colour indices 1-15: four bytes each, one
        # a pixel row, repeating every four rows (index 0 is "not drawn").
        "shades": [list(d[off + 0x0A + 4 * i:off + 0x0E + 4 * i]) for i in range(15)],
        "demo_offset": d[off + 0x46] | (d[off + 0x47] << 8),
        "global_conditions_offset": d[off + 0x48] | (d[off + 0x49] << 8),
        "timer": d[off + 0xB4:off + 0xBC].decode("latin-1"),
        "initial_step_index": d[off + 0xC2],
        "initial_turn_index": d[off + 0xC3],
    }
    db["global_conditions"], _ = parse_conditions(d, off + db["global_conditions_offset"])
    offsets = [d[off + 0xC8 + 2 * i] | (d[off + 0xC9 + 2 * i] << 8) for i in range(db["n_areas"])]
    db["areas"] = [parse_area(d, off + o, off) for o in offsets]
    return db


def counted_table(d, addr):
    p = addr - LOAD
    return list(d[p + 1:p + 1 + d[p]])


def tables(d):
    p = SINCOS - LOAD
    pairs = [(s8(d[p + 2 * i]), s8(d[p + 2 * i + 1])) for i in range(72)]
    return {
        "sin": [s for s, _ in pairs],
        "cos": [c for _, c in pairs],
        "steps": counted_table(d, STEPS),
        "turns": counted_table(d, TURNS),
        "scale": [s8(d[SCALE - LOAD + i]) for i in range(3)],
        "centre": list(d[CENTRE - LOAD:CENTRE - LOAD + 2]),
    }


def globals_(d):
    q = GLOBALS
    out = []
    for _ in range(N_GLOBALS):
        o, q = parse_object(d, q, DATABASE)
        o["offset"] = None
        out.append(o)
    return out


def load(tape):
    d = data_block(tape)
    return {
        "source": {
            "tape_block": BLOCK,
            "length": len(d),
            "md5_5000": hashlib.md5(d[:5000]).hexdigest(),
            "load": LOAD,
            "database": DATABASE,
        },
        "tables": tables(d),
        "globals": globals_(d),
        **parse_database(d, DATABASE),
    }


# --- The checks -------------------------------------------------------------

def counts(db):
    objs = [o for a in db["areas"] for o in a["objects"]]
    return {
        "areas": len(db["areas"]),
        "records": len(objs),
        "geometric": sum(1 for o in objs if o["type"] not in (0, 2, 15)),
        "cuboids": sum(1 for o in objs if o["type"] == 1),
        "rectangles": sum(1 for o in objs if o["type"] == 3),
        "pyramids": sum(1 for o in objs if 4 <= o["type"] <= 9),
        "entrances": sum(1 for o in objs if o["type"] == 0),
        "sensors": sum(1 for o in objs if o["type"] == 2),
        "groups": sum(1 for o in objs if o["type"] == 15),
    }


def check(db):
    """Every failure, as a list of strings (empty when it all holds)."""
    import math
    bad = []
    src = db["source"]
    if src["md5_5000"] != SCUMMVM_MD5_5000 or src["length"] != SCUMMVM_LENGTH:
        bad.append("the block isn't ScummVM's ZX retail data (md5 %s, %d bytes)"
                   % (src["md5_5000"], src["length"]))
    if db["n_areas"] != len(db["areas"]):
        bad.append("area count")
    for a in db["areas"]:
        if a["objects_end"] != a["conditions_offset"]:
            bad.append("area %d: objects end at +%d, conditions start at +%d"
                       % (a["id"], a["objects_end"], a["conditions_offset"]))
    c = counts(db)
    for k, v in EXPECTED.items():
        if c[k] != v:
            bad.append("%s: %d, expected %d" % (k, c[k], v))
    t = db["tables"]
    # The sine table is round(64 sin) and round(64 cos) of each 5 degrees,
    # which also confirms the block's load address.
    for i in range(72):
        a = math.radians(5 * i)
        if (t["sin"][i], t["cos"][i]) != (round(64 * math.sin(a)), round(64 * math.cos(a))):
            bad.append("sine table entry %d" % i)
    if t["steps"][db["initial_step_index"]] != 250 or t["turns"][db["initial_turn_index"]] != 3:
        bad.append("the initial step and turn aren't the manual's 250 and 15 degrees")
    ids = {}
    for a in db["areas"]:
        if a["id"] in ids:
            bad.append("area id %d repeated" % a["id"])
        ids[a["id"]] = a
    if db["start_area"] not in ids:
        bad.append("no start area")
    elif not any(o["type"] == 0 and o["id"] == db["start_entrance"]
                 for o in ids[db["start_area"]]["objects"]):
        bad.append("no start entrance")
    return bad


def main(argv):
    if len(argv) == 3 and argv[1] == "--check":
        with open(argv[2]) as f:
            db = json.load(f)
        bad = check(db)
        for b in bad:
            print("freescape.py:", b, file=sys.stderr)
        c = counts(db)
        print("data: %d areas, %d records, %d geometric (%d cuboids, %d rectangles, "
              "%d pyramids), %d entrances, %d sensors, %d groups: %s"
              % (c["areas"], c["records"], c["geometric"], c["cuboids"], c["rectangles"],
                 c["pyramids"], c["entrances"], c["sensors"], c["groups"],
                 "FAIL" if bad else "ok"))
        return 1 if bad else 0
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], "rb") as f:
        db = load(f.read())
    with open(argv[2], "w") as f:
        json.dump(db, f, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
