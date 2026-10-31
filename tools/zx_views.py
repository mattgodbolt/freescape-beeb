#!/usr/bin/env python3
"""Every entrance view, drawn by Driller's own redraw (the ZX oracle).

    .venv/bin/python -I tools/zx_views.py [--snap build/zx/driller.z80] [--out build/zx/views] [--check]

For each of the database's entrances (type 0 objects, in area order), from
the in-play snapshot (make zx): tools/zx.py's render_view puts the camera
at the entrance with the game's own code, on the probe at the start's
extension, and calls the redraw. Writes, in --out:

    a<area>_e<entrance>.bin   the view: 104 rows of 26 bytes, bit 7 left,
                              set = ink (the rows the game shows)
    a<area>_e<entrance>.png   the same, ink white, at twice the size
    views.json                per view: the camera, whether the area's
                              draw clears the buffer, the objects drawn,
                              and the redraw's T-states, as the 48K runs
                              it ("tstates": memory contention and the
                              game's interrupt included) and as its
                              instructions alone ("tstates_bare"), each in
                              all and by stage

--check: the start view equals the buffer the game drew itself at boot
(in the snapshot), every view is drawn again identically, and the JSON
matches.
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research"))
import zx  # noqa: E402
from fsdump import parse_db  # noqa: E402

DATABASE = 0xCF3E   # the database, as loaded (docs/research/freescape.md)
START = (1, 19)     # the start's area and entrance (the database's header)


EXTENSION = 0x8772  # the probe's vertical extension, 1-4 (2 at the start)


def entrances(snap):
    """(area, entrance id, the camera the entrance gives) for every
    entrance, in the database's order. The camera is the placement
    docs/research/zx-driller.md gives (GoToEntrance, $9D1C): the cell's
    centre, the eye 64*L*scale - 32 units above the cell's floor on the
    probe, and the entrance's angles."""
    spec = zx.Spectrum(snap)
    mem = bytes(spec.mem[0:0x10000])
    level = mem[EXTENSION]
    db = parse_db(mem, DATABASE)
    out = []
    for a in db["areas"]:
        for o in a["objects"]:
            if o["t"] == 0:
                (ex, ey, ez), rot = o["pos"], o["rot5"]
                cam = [64 * ex + 32, 64 * (ey + level * a["scale"] - 1) + 32, 64 * ez + 32, *rot]
                out.append((a["id"], o["id"], cam))
    return out


def render(snap, area, ent, cam):
    """The view from an entrance, placed by the game's own code
    (GoToEntrance) where that finds the entrance, and from cam otherwise.

    The game's lookup ($A8BA) takes the first object with the id, of any
    type, so an entrance whose id an earlier object shares can't be
    reached by it, and id 0 means "keep the position". Those are placed
    from cam ("placed": "formula"). Where the game places it, it must
    agree with cam ("placed": "game")."""
    v = zx.render_view(snap, area, ent) if ent else None
    if v is not None and v["camera"] == cam:
        placed = "game"
        bare = zx.render_view(snap, area, ent, contended=False, interrupts=False)
    else:
        placed = "formula"
        v = zx.render_view(snap, area, 0, cam)
        bare = zx.render_view(snap, area, 0, cam, contended=False, interrupts=False)
        v["entrance"] = bare["entrance"] = ent
    assert bare["view"] == v["view"], f"area {area} entrance {ent}: the timing changed the image"
    v["placed"] = placed
    return v, bare


def record(v, bare):
    return {
        "area": v["area"], "entrance": v["entrance"],
        "name": f"a{v['area']}_e{v['entrance']}",
        "camera": dict(zip(("x", "y", "z", "pitch", "yaw", "roll"), v["camera"])),
        "placed": v["placed"], "clears": v["clears"], "drawn": v["drawn"],
        "tstates": v["tstates"], "stages": v["stages"],
        "tstates_bare": bare["tstates"], "stages_bare": bare["stages"],
    }


def summary(views):
    ts = sorted(r["tstates"] for r in views)
    bare = sorted(r["tstates_bare"] for r in views)
    return {"views": len(views),
            "tstates": {"median": statistics.median(ts), "min": ts[0], "max": ts[-1]},
            "tstates_bare": {"median": statistics.median(bare), "min": bare[0], "max": bare[-1]}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--out", default="build/zx/views")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = args.out
    if args.check:
        failures = 0
        spec = zx.Spectrum(args.snap)
        own = bytes(spec.mem[zx.BUFFER:zx.BUFFER + zx.ROW_BYTES * zx.VIEW_H])
        if zx.render_view(args.snap, *START)["view"] != own:
            print("zx_views: the start view isn't the one the game drew at boot")
            failures += 1
        with open(os.path.join(out, "views.json")) as f:
            saved = json.load(f)["views"]
        ents = {(a, e): cam for a, e, cam in entrances(args.snap)}
        if len(saved) != len(ents):
            print(f"zx_views: {len(saved)} views saved, {len(ents)} entrances")
            failures += 1
        for r in saved:
            v, bare = render(args.snap, r["area"], r["entrance"], ents[r["area"], r["entrance"]])
            with open(os.path.join(out, r["name"] + ".bin"), "rb") as f:
                if f.read() != v["view"] or record(v, bare) != r:
                    print(f"zx_views: {r['name']} drew differently")
                    failures += 1
        print(f"zx_views: {len(saved)} views checked, {failures} failures")
        return 1 if failures else 0

    os.makedirs(out, exist_ok=True)
    views = []
    for area, ent, cam in entrances(args.snap):
        v, bare = render(args.snap, area, ent, cam)
        r = record(v, bare)
        with open(os.path.join(out, r["name"] + ".bin"), "wb") as f:
            f.write(v["view"])
        zx.view_image(v["view"], 2).save(os.path.join(out, r["name"] + ".png"))
        views.append(r)
    s = summary(views)
    with open(os.path.join(out, "views.json"), "w") as f:
        json.dump({"summary": s, "views": views}, f, indent=1)
    t = s["tstates"]
    print(f"zx_views: {len(views)} views in {out}; redraw T-states median {t['median']}, "
          f"range {t['min']}-{t['max']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
