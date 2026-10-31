"""What colour each version of Driller gives each face colour index, by area.

    python -I tools/colour/sources.py OUT.json

reads the fetched originals (tools/fetch.d/10-zx.sh and 30-colour.sh), checks
each executable against ScummVM's detection entry (detection.cpp), parses its
database (database.py) and works out, for every area, the colours that the
version shows for indices 1-15, its sky (the background it clears the view
to) and its ground (the floor object's top face). Each colour is a mix: a
list of (r, g, b, share) for the pens of a pattern, or one entry for a solid
colour. Every rule below follows ScummVM's renderer, cited by file:line in
docs/research/colour.md.

It also checks the database is the same in every version: each object's
type, place, size and colour indices against the ZX's.
"""

import hashlib
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "research"))
import database  # noqa: E402
import images  # noqa: E402
import tap  # noqa: E402  (tools/research/tap.py: TZX blocks)

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Each version: where it is, ScummVM's md5 of its first 5000 bytes and its
# size (detection.cpp), and where its database is (games/driller/*.cpp).
VERSIONS = {
    "zx": dict(image="originals/zx/Driller.tzx", member=5,
               md5="396c1789a7da3db5058d18eb8d2d35a3", size=37590,
               db=0x642C, words=False),
    "dos": dict(image="originals/dos/DISK01.IMA", member="DRILLE.EXE",
                md5="eb7e9e0acb72e30cf6e9ed20a6480e7a", size=51944,
                db=0x9B40, words=False),
    "cpc": dict(image="originals/cpc/Driller.dsk", member="DRILL.BIN",
                md5="719f5157391e88b2c391c30576340637", size=35320,
                db=0x5CCB, words=False),
    "st": dict(image="originals/st/Driller.st", member="DRILLER/X.PRG",
               md5="1a79e68e6c2c223c96de0ca2d65149ae", size=293062,
               db=0x29B3C, palettes=0x296FA, words=True),
    # This Amiga release loads its database and palettes from a file of
    # their own, as ScummVM's Amiga demos do (amiga.cpp:365-370); its
    # executable's first 5000 bytes are ScummVM's budget release's.
    # ScummVM has no entry for the data file, so its md5 is the one this
    # study measured (docs/research/colour.md).
    "amiga": dict(image="originals/amiga/Driller.adf", member="DRILLER/data",
                  md5_all="e71031003687571f12fb6303082b0e6f", size=28316,
                  db=0x442, palettes=0, words=True,
                  exe="DRILLER/driller",
                  exe_md5="db1afe151d999f369ae9153d8eeaf254"),
}

# ScummVM's palettes (games/palettes.cpp:26-142).
EGA = [(0x00, 0x00, 0x00), (0x00, 0x00, 0xAA), (0x00, 0xAA, 0x00),
       (0x00, 0xAA, 0xAA), (0xAA, 0x00, 0x00), (0xAA, 0x00, 0xAA),
       (0xAA, 0x55, 0x00), (0xAA, 0xAA, 0xAA), (0x55, 0x55, 0x55),
       (0x55, 0x55, 0xFF), (0x55, 0xFF, 0x55), (0x55, 0xFF, 0xFF),
       (0xFF, 0x55, 0x55), (0xFF, 0x55, 0xFF), (0xFF, 0xFF, 0x55),
       (0xFF, 0xFF, 0xFF)]
ZX = [(0x00, 0x00, 0x00), (0x00, 0x00, 0xD8), (0xD8, 0x00, 0x00),
      (0xD8, 0x00, 0xD8), (0x00, 0xD8, 0x00), (0x00, 0xD8, 0xD8),
      (0xD8, 0xD8, 0x00), (0xD8, 0xD8, 0xD8), (0x00, 0x00, 0x00)]
# The CPC's 32 hardware colour numbers (27 distinct inks).
CPC = [(0x80, 0x80, 0x80), (0x80, 0x80, 0x80), (0x00, 0xFF, 0x80),
       (0xFF, 0xFF, 0x80), (0x00, 0x00, 0x80), (0xFF, 0x00, 0x80),
       (0x00, 0x80, 0x80), (0xFF, 0x80, 0x80), (0xFF, 0x00, 0x80),
       (0xFF, 0xFF, 0x80), (0xFF, 0xFF, 0x00), (0xFF, 0xFF, 0xFF),
       (0xFF, 0x00, 0x00), (0xFF, 0x00, 0xFF), (0xFF, 0x80, 0x00),
       (0xFF, 0x80, 0xFF), (0x00, 0x00, 0x80), (0x00, 0xFF, 0x80),
       (0x00, 0xFF, 0x00), (0x00, 0xFF, 0xFF), (0x00, 0x00, 0x00),
       (0x00, 0x00, 0xFF), (0x00, 0x80, 0x00), (0x00, 0x80, 0xFF),
       (0x80, 0x00, 0x80), (0x80, 0xFF, 0x80), (0x80, 0xFF, 0x00),
       (0x80, 0xFF, 0xFF), (0x80, 0x00, 0x00), (0x80, 0x00, 0xFF),
       (0x80, 0x80, 0x00), (0x80, 0x80, 0xFF)]


def md5(b):
    return hashlib.md5(b).hexdigest()


def load(name):
    """The version's file, checked."""
    v = VERSIONS[name]
    path = os.path.join(ROOT, v["image"])
    img = open(path, "rb").read()
    if name == "zx":
        data = tap.tzx_blocks(img)[v["member"]][1][1:-1]
    elif path.endswith(".zip"):
        data = zipfile.ZipFile(path).read(v["member"])
    elif path.endswith(".dsk"):
        data = images.dsk_read(img, v["member"])
    elif path.endswith(".adf"):
        data = images.adf_read(img, v["member"])
        exe = images.adf_read(img, v["exe"])
        if md5(exe[:5000]) != v["exe_md5"]:
            raise SystemExit(f"{name}: {v['exe']} isn't the expected release")
    else:
        data = images.fat12_read(img, v["member"])
    ok = len(data) == v["size"] and (
        md5(data[:5000]) == v["md5"] if "md5" in v else md5(data) == v["md5_all"])
    if not ok:
        raise SystemExit(f"{name}: {v['member']} in {v['image']} doesn't "
                         f"match ({len(data)} bytes, md5 {md5(data[:5000])})")
    return data


def database_of(name, data):
    v = VERSIONS[name]
    if v["words"]:
        d, high = database.narrow(data, v["db"])
        db = database.parse(d, 0)
        # The area's first word carries COLOR15 cycling in bit 14
        # (8bitBinaryLoader.cpp:631-638).
        for a in db["areas"]:
            a["cycling"] = bool(high.get(a["offset"], 0) & 0x40)
    else:
        db = database.parse(data, v["db"])
    return db


def palettes_16bit(data, off, n_areas):
    """{area id: 16 RGB} as loadPalettes reads them: Driller has two more
    than its areas (games/palettes.cpp:187-231)."""
    out = {}
    for i in range(n_areas + 2):
        p = off + 34 * i
        label = int.from_bytes(data[p:p + 2], "big")
        if label == 255:
            break
        words = [int.from_bytes(data[p + 2 + 2 * c:p + 4 + 2 * c], "big")
                 for c in range(16)]
        out.setdefault(label, [(((w >> 8) & 15) * 17, ((w >> 4) & 15) * 17,
                                (w & 15) * 17) for w in words])
    return out


def mix(pairs):
    """A mix from [(rgb, count)], merged and normalised to shares."""
    tot = {}
    for rgb, n in pairs:
        tot[tuple(rgb)] = tot.get(tuple(rgb), 0) + n
    s = sum(tot.values())
    return [[*rgb, n / s] for rgb, n in sorted(tot.items(), key=lambda x: -x[1])]


def cpc_pens(byte):
    """The four mode 1 pixels' pens, left first (freescape.cpp:86-97)."""
    return [((byte >> (3 - i)) & 1) << 1 | ((byte >> (7 - i)) & 1)
            for i in range(4)]


def colours_zx(db, area):
    paper, ink = ZX[area["colours"][2] % 9], ZX[area["colours"][3] % 9]
    out = {}
    for i, entry in enumerate(db["colour_map"], 1):
        bits = sum(bin(b).count("1") for b in entry)
        out[i] = mix([(ink, bits), (paper, 32 - bits)])
    # The view is cleared to the sky index's first colour, paper unless the
    # entry is solid ink (gfx.cpp:466-493, 1314-1344; driller.cpp:290-304).
    sky = area["flags"] & 15
    out["sky"] = mix([(ZX[0], 1)]) if sky == 0 else [out[sky][0][:3] + [1.0]] \
        if db["colour_map"][sky - 1] == [255] * 4 else mix([(paper, 1)])
    return out


def colours_dos(db, area):
    out = {}
    for i, entry in enumerate(db["colour_map"], 1):
        if any(b not in (0, 0xFF) for b in entry):
            raise SystemExit(f"dos: colour map entry {i} isn't EGA planes")
        # Byte k is plane k (gfx.cpp:594-609, mapEGAColor).
        c = sum(1 << k for k, b in enumerate(entry) if b == 0xFF)
        out[i] = mix([(EGA[c], 1)])
    out["sky"] = mix([(EGA[0], 1)])  # driller.cpp:295-297
    return out


def colours_cpc(db, area):
    inks = [CPC[c & 31] for c in area["colours"]]
    out = {}
    for i, entry in enumerate(db["colour_map"], 1):
        pens = [p for b in entry for p in cpc_pens(b)]
        out[i] = mix([(inks[p], 1) for p in pens])
    out["sky"] = mix([(inks[0], 1)])  # pen 0, driller.cpp:298-304
    return out


def colours_16bit(pal, area):
    # The Amiga data file has no palette for area 32: ScummVM gives its
    # demos, which lack it too, area 31's (games/palettes.cpp:233-238).
    p = pal[area["id"]] if area["id"] in pal else pal[31]
    out = {i: mix([(p[i], 1)]) for i in range(1, 16)}
    out["sky"] = mix([((0, 0, 0), 1)])  # driller.cpp:295-297
    return out


def compare(ref, other):
    """Differences between two databases, object by object."""
    diffs = []
    rmap = {a["id"]: a for a in ref["areas"]}
    for a in other["areas"]:
        r = rmap.get(a["id"])
        if r is None:
            diffs.append((a["id"], None, "area missing from the ZX"))
            continue
        for k in ("flags", "nobj", "scale", "gas", "name"):
            if a[k] != r[k]:
                diffs.append((a["id"], None, f"area {k}: zx {r[k]} here {a[k]}"))
        # Entrances have ids of their own (ScummVM keeps them apart).
        ro = {(o["t"] == 0, o["id"]): o for o in r["objects"]}
        for o in a["objects"]:
            q = ro.get((o["t"] == 0, o["id"]))
            if q is None:
                diffs.append((a["id"], o["id"], "object missing from the ZX"))
                continue
            for k in ("t", "flags", "pos", "size", "colours", "ords"):
                if o[k] != q[k]:
                    diffs.append((a["id"], o["id"],
                                  f"{k}: zx {q[k]} here {o[k]}"))
    return diffs


def face_summary(ref, other):
    """Face by face, how the other version's colour indices differ from
    the ZX's, over the objects both have with the same type; and how many
    faces a remap of the ZX's indices, one an area, would get wrong (each
    ZX index taking the colour index most of its faces have here)."""
    s = {"objects": 0, "geometry": 0, "faces": 0, "index_differs": 0,
         "drawn_differs": 0, "remap_wrong": 0, "remap_faces": 0}
    rmap = {a["id"]: a for a in ref["areas"]}
    for a in other["areas"]:
        ro = {(o["t"] == 0, o["id"]): o for o in rmap[a["id"]]["objects"]}
        votes = {}
        for o in a["objects"]:
            q = ro.get((o["t"] == 0, o["id"]))
            if q is None or q["t"] != o["t"]:
                continue
            s["objects"] += 1
            if any(o[k] != q[k] for k in ("pos", "size", "ords")):
                s["geometry"] += 1
            for x, y in zip(q["colours"], o["colours"]):
                s["faces"] += 1
                s["index_differs"] += x != y
                s["drawn_differs"] += (x == 0) != (y == 0)
                if x:
                    votes.setdefault(x, {})
                    votes[x][y] = votes[x].get(y, 0) + 1
        for v in votes.values():
            s["remap_faces"] += sum(v.values())
            s["remap_wrong"] += sum(v.values()) - max(v.values())
    return s


def main(out_path):
    result = {"versions": {}, "areas": [], "colours": {}, "compare": {},
              "faces_compare": {}}
    dbs = {}
    for name, v in VERSIONS.items():
        data = load(name)
        db = database_of(name, data)
        dbs[name] = db
        info = {"file": v["image"], "member": v["member"], "size": len(data),
                "md5_5000": md5(data[:5000]), "md5": md5(data),
                "db_offset": v["db"], "colour_map": db["colour_map"],
                "areas": {}}
        for a in db["areas"]:
            faces = {}
            for o in a["objects"]:
                for c in o["colours"]:
                    if c:
                        faces[c] = faces.get(c, 0) + 1
            info["areas"][a["id"]] = {
                "colours": a["colours"], "flags": a["flags"],
                "cycling": a.get("cycling", False),
                # How many faces have each colour index, in this version's
                # own database.
                "faces": dict(sorted(faces.items())),
                # Each object's colour nibbles, by object id.
                "objects": {o["id"]: o["colours"] for o in a["objects"]
                            if o["colours"]}}
        if v["words"]:
            pal = palettes_16bit(data, v["palettes"], db["n_areas"])
            info["palettes"] = {k: p for k, p in pal.items()}
        result["versions"][name] = info
        if name == "zx":
            cols = {a["id"]: colours_zx(db, a) for a in db["areas"]}
        elif name == "dos":
            cols = {a["id"]: colours_dos(db, a) for a in db["areas"]}
        elif name == "cpc":
            cols = {a["id"]: colours_cpc(db, a) for a in db["areas"]}
        else:
            cols = {a["id"]: colours_16bit(pal, a) for a in db["areas"]}
        result["colours"][name] = cols

    for a in dbs["zx"]["areas"]:
        f = database.floor_of(a)
        result["areas"].append({"id": a["id"], "name": a["name"],
                                "floor": None if f is None else f["id"]})
    for name in VERSIONS:
        if name != "zx":
            result["compare"][name] = compare(dbs["zx"], dbs[name])
            result["faces_compare"][name] = face_summary(dbs["zx"], dbs[name])
    # The ground is the floor object's top face, in each version's own
    # colour index for it.
    for name, cols in result["colours"].items():
        for a in result["areas"]:
            c = cols[a["id"]]
            objs = result["versions"][name]["areas"][a["id"]]["objects"]
            top = objs[a["floor"]][database.CUBE_TOP] if a["floor"] else 0
            c["ground_index"] = top
            c["ground"] = c[top] if top else c["sky"]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
