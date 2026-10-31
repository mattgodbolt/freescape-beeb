"""Swatches: each area's source colours beside its BBC patterns, on an RGB
monitor and through jsbeeb's PAL TV.

    python -I tools/colour/swatches.py SOURCES.json BBC.json OUTDIR

writes OUTDIR/area-NNN.png for every area: a row for each colour index
(1-15), the sky and the ground. Each row shows the source colour (a solid
colour, or the source's own pattern as stripes of its pens), then the BBC
pattern over a block of the screen as an RGB monitor shows it, at MODE 2's
pixel aspect (a pixel twice as wide as it is tall) and magnified, then the
same block through PAL (tools/pal.py, one field), and the figures for both.
Rows for indices that no face in the area uses are dimmed. It also writes
OUTDIR/sheet.png: every area side by side, each used colour as source,
RGB and PAL, to compare areas.
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patterns as P  # noqa: E402

SCALE = 4           # screen pixels a line
BLOCK = (P.PAL_PIXELS, P.PAL_LINES)   # MODE 2 pixels across, lines down
ROW_H = BLOCK[1] * SCALE + 6
GREY = (40, 40, 40)


def block(bs, scale=SCALE, size=BLOCK):
    """An RGB monitor's picture of a pattern over size MODE 2 pixels,
    anchored at (0, 0)."""
    px = P.from_bytes(bs)
    w, h = size
    img = np.array([[P.BBC[px[2 * (y & 3) + (x & 1)]] for x in range(w)]
                    for y in range(h)], dtype=np.uint8)
    img = np.repeat(np.repeat(img, scale, axis=0), 2 * scale, axis=1)
    return Image.fromarray(img)


def pal_image(bs, scale=SCALE, size=BLOCK):
    """The same block through PAL, one field: texels are half a line
    square, so scale // 2 screen pixels each."""
    out = P.pal_block(P.from_bytes(bs))
    w, h = size
    out = out[:2 * h, :4 * w]
    img = (out * 255 + 0.5).astype(np.uint8)
    k = max(1, scale // 2)
    return Image.fromarray(np.repeat(np.repeat(img, k, axis=0), k, axis=1))


def source(mix, scale=SCALE, size=BLOCK):
    """The source colour; a patterned one (the CPC's) as stripes of its
    pens in their shares."""
    w, h = size[0] * 2 * scale, size[1] * scale
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    x = 0
    for r, g, b, share in mix:
        x1 = x + share * w
        d.rectangle([int(x), 0, int(x1), h], fill=(int(r), int(g), int(b)))
        x = x1
    return img


def _figures(mix, bs):
    pat = P.Pattern(P.from_bytes(bs), "")
    P.pal_appearance([pat])
    target = P.target_of(mix)
    hexc = "#" + "".join(f"{int(c):02x}" for c in mix[0][:3]) \
        if len(mix) == 1 else f"{len(mix)}-pen mix"
    return (f"{hexc}  {pat.describe()}  " + " ".join(f"{b:02x}" for b in bs)
            + f"\nRGB dE {P.de(target, pat.mean):.1f} tex {pat.texture:.1f}"
            f"\nPAL dE {P.de(target, pat.pal_mean):.1f} tex "
            f"{pat.pal_texture:.1f} crawl {pat.pal_crawl:.1f}")


def area_image(name, aid, cols, faces, entry):
    font = ImageFont.load_default()
    rows = [(str(i), cols[str(i)], entry["patterns"][i - 1], faces.get(str(i), 0))
            for i in range(1, 16)]
    rows.append(("sky", cols["sky"], entry["sky"], 1))
    rows.append(("gnd", cols["ground"], entry["ground"], 1))
    bw = BLOCK[0] * 2 * SCALE
    W = 40 + 3 * (bw + 8) + 240
    H = 24 + ROW_H * len(rows)
    img = Image.new("RGB", (W, H), GREY)
    d = ImageDraw.Draw(img)
    d.text((6, 6), f"Area {aid}: {name}   source | RGB monitor | PAL TV   "
           f"(patterns chosen for {entry['display']})",
           fill=(230, 230, 230), font=font)
    for r, (label, mix, bs, nfaces) in enumerate(rows):
        y = 24 + r * ROW_H
        x = 40
        tiles = [source(mix), block(bs), pal_image(bs)]
        if not nfaces:
            tiles = [Image.blend(t, Image.new("RGB", t.size, GREY), 0.6)
                     for t in tiles]
        for t in tiles:
            img.paste(t, (x, y))
            x += bw + 8
        d.text((6, y + 4), label, fill=(230, 230, 230), font=font)
        d.multiline_text((x, y + 4), _figures(mix, bs) + f"\nfaces {nfaces}",
                         fill=(230, 230, 230), font=font)
    return img


def sheet(src, bbc, version):
    """Every area in a column: its used colours, then sky and ground, each
    as source, RGB monitor and PAL TV."""
    font = ImageFont.load_default()
    areas = src["areas"]
    s = 2
    size = (4, 4)
    tw = size[0] * 2 * s
    cw = 3 * tw + 6
    rh = size[1] * s + 2
    W = 50 + len(areas) * cw
    H = 30 + 17 * rh
    img = Image.new("RGB", (W, H), GREY)
    d = ImageDraw.Draw(img)
    for i in range(15):
        d.text((4, 30 + i * rh), str(i + 1), fill=(200, 200, 200), font=font)
    d.text((4, 30 + 15 * rh), "sky", fill=(200, 200, 200), font=font)
    d.text((4, 30 + 16 * rh), "ground", fill=(200, 200, 200), font=font)
    for k, a in enumerate(areas):
        aid = str(a["id"])
        e = bbc["areas"][aid]
        cols = src["colours"][version][aid]
        faces = src["versions"][version]["areas"][aid]["faces"]
        x = 50 + k * cw
        d.text((x, 4), aid, fill=(200, 200, 200), font=font)
        for i in range(17):
            y = 30 + i * rh
            if i < 15 and str(i + 1) not in faces:
                continue
            key = str(i + 1) if i < 15 else ("sky" if i == 15 else "ground")
            bs = e["patterns"][i] if i < 15 else e[key]
            img.paste(source(cols[key], s, size), (x, y))
            img.paste(block(bs, s, size), (x + tw, y))
            pal = pal_image(bs, 2 * s, size)
            img.paste(pal, (x + 2 * tw, y))
    return img


def main(src_path, bbc_path, outdir):
    src = json.load(open(src_path))
    bbc = json.load(open(bbc_path))
    v = bbc["version"]
    os.makedirs(outdir, exist_ok=True)
    for a in src["areas"]:
        aid = str(a["id"])
        img = area_image(a["name"], aid, src["colours"][v][aid],
                         src["versions"][v]["areas"][aid]["faces"],
                         dict(bbc["areas"][aid], display=bbc["display"]))
        img.save(os.path.join(outdir, f"area-{a['id']:03d}.png"))
    sheet(src, bbc, v).save(os.path.join(outdir, "sheet.png"))


if __name__ == "__main__":
    main(*sys.argv[1:4])
