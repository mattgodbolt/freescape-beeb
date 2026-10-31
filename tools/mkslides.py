#!/usr/bin/env python3
"""The slideshow's data: every Driller entrance view's rasteriser input, as
the model computes it, packed into sideways RAM banks for src/slides.6502.

    mkslides.py DB.json OUTDIR [--banks 5,6,7]

For each entrance view (tools/model/camera.py's entrance_views, in the
database's order) the whole-view model (tools/model/render.py) gives the
faces nearest first, each a pattern and a polygon in view coordinates
inside the view, and the area's sky and ground; that is the rasteriser's
input (src/raster.6502, RasterIn). Each view becomes a record:

    TEXT_LINES lines of TEXT_COLS characters: the area's name, the
        entrance, the view's number (what the slideshow shows beside it)
    nfaces, nvertices, npatterns, sky, ground (pattern numbers)
    horizon (0: none), hx (2), hy (2), hdx, hdy
    fn[nfaces], fv[nfaces], fc[nfaces]
    vxl[nvertices], vxh[nvertices], vyl[nvertices], vyh[nvertices]
    pat[4 npatterns]

which src/slides.6502's slide_load copies into RasterIn. This packing and
that routine are the only places that know the rasteriser's input layout.
Records are laid end to end in the banks, a record never crossing one.

Writes into OUTDIR:
    S<bank>       each bank's records, from &8000
    slides.6502   for the assembly: each view's bank and address, the banks
                  used, and the most faces, vertices and patterns a view has
                  (src/slides.6502 ASSERTs them against the rasteriser's
                  limits)
    views.json    each view's name and the model's view bytes, line by line
                  (tools/slidecheck.mjs compares the BBC's with them), and the
                  model's counts

Each record is checked here: unpacked and rasterised by the model with the
6502's pool size, it must give the render's bytes.

Derived from the originals (make data, make colours), so built, never
committed (decision 6).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.model import camera as cam, parts, raster, render, view, writer  # noqa: E402

BANK_ORG = 0x8000
BANK_SIZE = 0x4000
# A MODE 2 character is 8 pixels, four bytes, across.
TEXT_COLS = view.read_defs()["SCREEN_COLS"] // 4
TEXT_LINES = 3


def _raster_constant(name):
    """A constant of src/raster.6502, where the 6502's limits are set."""
    src = (ROOT / "src" / "raster.6502").read_text()
    return int(re.search(rf"^{name}\s*=\s*(\d+)", src, re.M).group(1))


POOL_NODES = _raster_constant("POOL_NODES")


def centred(text):
    text = text.strip()
    if len(text) > TEXT_COLS:
        raise SystemExit(f"{text!r} is wider than {TEXT_COLS} characters")
    return text.center(TEXT_COLS).encode("ascii")


def record(lines, faces, sky, ground, horizon):
    """A view's record: its text lines, then the rasteriser's input (the
    module's docstring). faces: [(pattern, [(x, y), ...]), ...] nearest
    first; horizon: None or (x, y, dx, dy)."""
    patterns = []

    def pid(p):
        if p not in patterns:
            patterns.append(p)
        return patterns.index(p)

    sky_id, ground_id = pid(tuple(sky)), pid(tuple(ground))
    fn, fv, fc, xs, ys = [], [], [], [], []
    for p, poly in faces:
        fn.append(len(poly))
        fv.append(len(xs))
        fc.append(pid(tuple(p)))
        for x, y in poly:
            xs.append(x)
            ys.append(y)
    # (counts in a byte each: the copy takes up to 255 bytes an array)
    assert len(faces) < 256 and len(xs) < 256 and 4 * len(patterns) < 256
    h = (1, *horizon) if horizon else (0, 0, 0, 0, 0)
    out = bytearray(b"".join(lines))
    out += bytes([len(faces), len(xs), len(patterns), sky_id, ground_id, h[0]])
    out += (h[1] & 0xFFFF).to_bytes(2, "little") + (h[2] & 0xFFFF).to_bytes(2, "little")
    out += bytes([h[3] & 0xFF, h[4] & 0xFF])
    out += bytes(fn) + bytes(fv) + bytes(fc)
    out += bytes(x & 0xFF for x in xs) + bytes(x >> 8 for x in xs)
    out += bytes(y & 0xFF for y in ys) + bytes(y >> 8 for y in ys)
    for p in patterns:
        out += bytes(p)
    stats = {"faces": len(faces), "vertices": len(xs), "patterns": len(patterns)}
    return bytes(out), stats


def unpack(rec):
    """record's raster input back as faces, background: what the 6502 gets."""
    at = TEXT_LINES * TEXT_COLS
    n, v, p, sky, ground, has = rec[at:at + 6]
    hx, hy = (int.from_bytes(rec[at + k:at + k + 2], "little", signed=True) for k in (6, 8))
    hdx, hdy = (b - 256 if b > 127 else b for b in rec[at + 10:at + 12])
    at += 12
    fn, fv, fc = rec[at:at + n], rec[at + n:at + 2 * n], rec[at + 2 * n:at + 3 * n]
    at += 3 * n
    vxl, vxh, vyl, vyh = (rec[at + k * v:at + (k + 1) * v] for k in range(4))
    at += 4 * v
    pats = [tuple(rec[at + 4 * k:at + 4 * k + 4]) for k in range(p)]
    assert at + 4 * p == len(rec)
    xs = [lo | hi << 8 for lo, hi in zip(vxl, vxh)]
    ys = [lo | hi << 8 for lo, hi in zip(vyl, vyh)]
    faces = [(pats[fc[f]], [(xs[i], ys[i]) for i in range(fv[f], fv[f] + fn[f])]) for f in range(n)]
    horizon = raster.Horizon(hx, hy, hdx, hdy) if has else None
    return faces, raster.Background(pats[sky], pats[ground], horizon)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("db")
    ap.add_argument("out")
    ap.add_argument("--banks", default="5,6,7", help="the sideways RAM banks to fill, in order")
    a = ap.parse_args(argv)
    banks = [int(b) for b in a.banks.split(",")]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    db = json.loads(Path(a.db).read_text())
    every = list(cam.entrance_views(db))
    images = {b: bytearray() for b in banks}
    slides = []
    bank = 0
    for i, (area, entrance, camera) in enumerate(every):
        v = render.render(db, area, camera)
        name = area["name"].strip()
        lines = [centred(name), centred(f"entrance {entrance['id']}"), centred(f"view {i + 1} of {len(every)}")]
        faces = [(parts.pattern(area, f.colour), f.poly) for f in v.faces]
        rec, stats = record(lines, faces, parts.sky(area), parts.ground(area), None)

        # The record, unpacked as the 6502 reads it and rasterised with the
        # 6502's pools, must give the render's bytes.
        got, counts = raster.spans(*unpack(rec), POOL_NODES)
        if counts.overflow or writer.write(got) != v.bytes:
            raise SystemExit(f"{render.name(area, entrance)}: the packed input doesn't draw the render's view")

        while len(images[banks[bank]]) + len(rec) > BANK_SIZE:
            bank += 1
            if bank == len(banks):
                raise SystemExit(f"the views don't fit banks {banks}")
        b = banks[bank]
        slides.append({
            "name": render.name(area, entrance),
            "area": name,
            "entrance": entrance["id"],
            "bank": b,
            "addr": BANK_ORG + len(images[b]),
            "bytes": len(rec),
            **stats,
            "text": [s.decode("ascii") for s in lines],
            "view": [row.hex() for row in writer.view_bytes(v.lines)],
            "counts": {"runs": counts.runs, "face_rows": counts.face_rows, "edges": counts.edges},
        })
        images[b] += rec

    used = [b for b in banks if images[b]]
    for b in used:
        (out / f"S{b}").write_bytes(bytes(images[b]))
    inc = [
        "\\ The slideshow's directory and banks: made by tools/mkslides.py from",
        "\\ Driller's data (decision 6), never committed; included by src/slides.6502.",
        f"SLIDES = {len(slides)}",
        f"SLIDE_TEXT_COLS = {TEXT_COLS}",
        f"SLIDE_TEXT_LINES = {TEXT_LINES}",
        f"SLIDE_MAX_FACES = {max(s['faces'] for s in slides)}",
        f"SLIDE_MAX_VERTICES = {max(s['vertices'] for s in slides)}",
        f"SLIDE_MAX_PATTERNS = {max(s['patterns'] for s in slides)}",
        "SLIDE_BANK = {" + ", ".join(str(s["bank"]) for s in slides) + "}",
        "SLIDE_ADDR = {" + ", ".join("&%04X" % s["addr"] for s in slides) + "}",
        "SLIDE_BANKS = {" + ", ".join(str(b) for b in used) + "}",
        "SLIDE_BANK_ORG = &%04X" % BANK_ORG,
    ]
    for b in used:
        inc += [
            f"SECTION Slides{b}, org = &{BANK_ORG:04X}, guard = &{BANK_ORG + BANK_SIZE:04X}, filename = \"S{b}\"",
            f"    INCBIN \"S{b}\"",
            "ENDSECTION",
        ]
    (out / "slides.6502").write_text("\n".join(inc) + "\n")
    (out / "views.json").write_text(json.dumps({"display": parts.colours.DISPLAY, "slides": slides}, indent=1) + "\n")
    sizes = ", ".join(f"bank {b} {len(images[b])}" for b in used)
    print(f"{len(slides)} views packed ({sizes} bytes), each drawing the render's bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
