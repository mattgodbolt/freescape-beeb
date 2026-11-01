#!/usr/bin/env python3
"""The panel's picture and tables (src/panel.6502), from the Atari ST's
console (decision 8: the ST's colours), at build time.

    mkpanel.py OUTDIR

reads Driller's ST executable from the fetched disc image (tools/colour/
sources.py checks it: ScummVM's budget release, whose console is the NEO
picture at CONSOLE in X.PRG, games/driller/atari.cpp) and writes into
OUTDIR:

    panel.6502   for the assembly (src/panel.6502 includes it): the
                 picture outside the view, packed; the glyph tables, the
                 styles and the cells' places (tools/model/panel.py's)
    panel.json   the picture and the styles' bytes, for the model
                 (tools/model/panel.py's render) and the check
    picture.png  the picture at MODE 2's pixels, and picture4x.png at four
                 by two, as an RGB monitor shows it (tools/pal.py shows it
                 through PAL: --texels 4 --rows 2)

The ST's console is 320 pixels by 200 lines around a 248 by 102 view; the
BBC's screen is 128 MODE 2 pixels (each two of the ST's across: both are
pixels of a PAL line's 52 microseconds, at 4 and 8 MHz) by 192 lines
around a 104 by 104 view. So the console is cut, not scaled: the panel
below the view keeps the ST's instruments where the ST has them and drops
the mouse's buttons, which a BBC has no use for (docs/research/panel.md
has the layout); the frames beside the view are the ST's nearest it; the
row above the view carries the credit (decision 6).

Derived from the originals, so built, never committed (decision 6).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "colour"))

from tools.model import panel  # noqa: E402

CONSOLE = 0x1371A           # the console's NEO picture in X.PRG (atari.cpp)
ST_W, ST_H = 320, 200


_DATA = []


def st_data():
    """X.PRG, checked (tools/colour/sources.py)."""
    if not _DATA:
        import sources
        _DATA.append(sources.load("st"))
    return _DATA[0]


# The vehicle's monitor: five pictures of the vehicle (the ST's own
# sprites, VEHICLES in X.PRG, each four words of 16 pixels by 43 lines,
# VEHICLE_STRIDE apart: the jet, then the probe at each extension), drawn at
# VEHICLE_AT, their columns VEHICLE_COLS showing (atari.cpp, amiga.cpp).
VEHICLES = 0x24CAE
VEHICLE_STRIDE = 0x580
VEHICLE_H = 43
VEHICLE_AT = (104, 126)
VEHICLE_COLS = (8, 61)


def st_sprite(at, words, height):
    """An ST sprite's colour numbers (0 is clear), as decodeAmigaSprite
    reads them: each 16 pixels four plane words."""
    data = st_data()
    rows = []
    for y in range(height):
        row = []
        for col in range(words):
            o = at + (y * words + col) * 8
            planes = [int.from_bytes(data[o + 2 * k:o + 2 * k + 2], "big") for k in range(4)]
            for bit in range(16):
                row.append(sum(1 << k for k in range(4) if planes[k] & (0x8000 >> bit)))
        rows.append(row)
    return rows


def vehicle(img, frame):
    """The console with vehicle picture frame drawn on it (ScummVM fills
    the sprite black first, so its clear pixels are black)."""
    out = [row[:] for row in img]
    spr = st_sprite(VEHICLES + frame * VEHICLE_STRIDE, 4, VEHICLE_H)
    x0, y0 = VEHICLE_AT
    for y in range(VEHICLE_H):
        for sx in range(*VEHICLE_COLS):
            out[y0 + y][x0 + sx - VEHICLE_COLS[0]] = spr[y][sx]
    return out


def st_console():
    """The console: its 16 colours (RGB, the ST's three bits a gun) and
    its pixels' colour numbers, 200 lines of 320."""
    data = st_data()
    head = data[CONSOLE:CONSOLE + 128]
    if head[0:4] != bytes(4):
        raise SystemExit("X.PRG: no NEO picture at the console's offset")
    words = [int.from_bytes(head[4 + 2 * i:6 + 2 * i], "big") for i in range(16)]
    if any(w & 0xF888 for w in words):
        raise SystemExit("X.PRG: the console's palette isn't the ST's 512 colours")
    pal = [tuple(((w >> s) & 7) * 255 // 7 for s in (8, 4, 0)) for w in words]
    px = data[CONSOLE + 128:CONSOLE + 128 + 32000]
    img = []
    for y in range(ST_H):
        row = []
        for g in range(ST_W // 16):
            o = y * 160 + g * 8
            planes = [int.from_bytes(px[o + 2 * k:o + 2 * k + 2], "big") for k in range(4)]
            for bit in range(16):
                row.append(sum(1 << k for k in range(4) if planes[k] & (0x8000 >> bit)))
        img.append(row)
    return pal, img


# --- The cut ------------------------------------------------------------------
#
# BBC line y of the panel (from the view's end) is the ST's line y + PANEL_DY:
# the ST's panel is two lines taller, and its top two are the bevel's edge.
# Across, each band keeps two runs of the ST's columns, side by side: the
# upper band (the instruments, the vehicle's monitor, the score) drops the
# arrows the mouse clicks; the lower (the shield and energy, the message
# box) drops the information button and what's round it.
PANEL_DY = 8
SPLIT = 164                 # the BBC line the lower band starts on
BANDS = (                   # (first BBC line, BBC pixel where the cut is, ST column it goes on from)
    (panel.VIEW_END, 79, 222),
    (SPLIT, 59, 182),
)
SIDE_ST = (6, 142)          # the ST's MODE 2 columns the left and right frames start from
SIDE_W = panel.VIEW_COL0 * 2


def luma(rgb):
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def compose(pal, img):
    """The BBC's screen as ST colour numbers (None in the view): each MODE 2
    pixel the brighter of the two ST pixels it covers."""
    def pair(x, y):
        a, b = img[y][x], img[y][x + 1]
        return a if luma(pal[a]) >= luma(pal[b]) else b

    out = [[None] * panel.WIDTH for _ in range(panel.LINES)]
    for y in range(panel.LINES):
        for x in range(panel.WIDTH):
            if panel.in_view(x, y):
                continue
            if y < panel.VIEW_TOP:
                out[y][x] = 0
            elif y < panel.VIEW_END:
                sy = 16 + round((y - panel.VIEW_TOP) * 101 / (panel.VIEW_END - panel.VIEW_TOP - 1))
                col = SIDE_ST[0] + x if x < SIDE_W else SIDE_ST[1] + x - (panel.WIDTH - SIDE_W)
                out[y][x] = pair(2 * col, sy)
            else:
                first, cut, st = [b for b in BANDS if b[0] <= y][-1]
                sx = 2 * x if x < cut else st + 2 * (x - cut)
                out[y][x] = pair(sx, y + PANEL_DY)
    return out


# --- What the BBC's panel changes ---------------------------------------------
#
# Over the cut: the boxes the fields are drawn in, cleared of the ST's
# placeholders (its score's empty holes, its step and turn boxes, its pitch
# strip's ticks, the save and load buttons where the position goes); the
# labels and the credit in the panel's own font; markers for the heading's
# and the pitch's middles. Colours are the ST's (0 black, 2 yellow, 7
# orange); text is in a logical colour (TEXT_INK), drawn solid.
BLACK, YELLOW, DARK_RED, ORANGE, PURPLE = 0, 2, 4, 7, 11
FILLS = [                   # ST colour, x0, y0, x1, y1 (inclusive)
    (BLACK, 88, 121, 115, 128),         # the score's box
    (BLACK, 5, 169, 56, 184),           # the shield's and energy's box
    (BLACK, 0, 134, 19, 158),           # the position's, for the save and load buttons
    (BLACK, 23, 142, 36, 159),          # the step's and turn's, under the heading
    (BLACK, 38, 129, 47, 158),          # the pitch's tape, and beside it ...
    (PURPLE, 46, 129, 46, 158),         # ... its bar ...
    (ORANGE, 46, 143, 47, 143),         # ... and its middle
    (PURPLE, 24, 134, 35, 140),         # the heading's tape
    (BLACK, 24, 133, 35, 133),          # over and under it
    (BLACK, 24, 141, 35, 141),
    (YELLOW, 30, 133, 30, 133),         # its middle
    (YELLOW, 30, 141, 30, 141),
    (DARK_RED, 80, 115, 91, 116),       # the lights
    (BLACK, 0, 186, 71, 191),           # the strip along the bottom
    (BLACK, 54, 154, 76, 159),          # the vehicle's name, under its picture
    (BLACK, 0, 0, panel.WIDTH - 1, 7),  # the row over the view
]
CREDIT = "DRILLER (C) INCENTIVE SOFTWARE 1987"
LABELS = [                  # text, x (or None: centred), line, logical colour
    (CREDIT, None, 1, 3),
    ("TECH DEMO", 2, 187, 1),
    ("FPS", 55, 187, 1),
    ("SHIELD", 33, 171, 1),
    ("ENERGY", 33, 178, 1),
    ("X", 0, 137, 1),
    ("Y", 0, 144, 1),
    ("Z", 0, 151, 1),
]


def paint(pic):
    """FILLS over the cut. Text goes in after the patterns (texts())."""
    for c, x0, y0, x1, y1 in FILLS:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                pic[y][x] = c


def texts(rows):
    """LABELS into the picture's pixels (logical colours, rows of WIDTH)."""
    for text, x, y, ink in LABELS:
        px = panel.text_pixels(text)
        w = len(px[0])
        if x is None:
            x = (panel.WIDTH - w) // 2
        if x + w > panel.WIDTH:
            raise SystemExit(f"{text!r} runs off the screen")
        for k, row in enumerate(px):
            for i, lit in enumerate(row):
                if lit:
                    rows[y + k][x + i] = ink


# --- The ST's colours in MODE 2 ---------------------------------------------
#
# Each of the console's sixteen colours is a MODE 2 pattern (docs/engine.md,
# section 2), chosen as the colour study chooses a face's (tools/colour/
# patterns.py, decision 8) for the display the build is for (decision 8b),
# from solid colours and pairs: a third colour's texture costs more than it
# gives on a panel's small shapes.

def st_patterns(pal):
    import patterns
    from tools.model import colours
    display = colours.DISPLAY
    cands = patterns.candidates("pair")
    out = []
    for rgb in pal:
        p, _d = patterns.best(patterns.target_of([[*rgb, 1.0]]), cands, display)
        out.append(p.pixels)
    return out


def logical(pic, pats):
    """Each pixel's logical colour: its ST colour's pattern's, at its place
    (patterns are anchored to the screen: pixel x AND 1 of line y AND 3);
    None in the view."""
    return [[None if c is None else pats[c][2 * (y & 3) + (x & 1)]
             for x, c in enumerate(row)] for y, row in enumerate(pic)]


def screen_bytes(rows):
    """The screen's bytes, SCREEN to &7FFF, from logical colours; the view 0."""
    out = bytearray(panel.SCREEN_BYTES)
    for y in range(panel.LINES):
        for x in range(0, panel.WIDTH, 2):
            a, b = rows[y][x], rows[y][x + 1]
            if a is not None:
                out[panel.address(x, y) - panel.SCREEN] = panel.mode2_byte(a, b)
    return bytes(out)


def to_rgb(screen):
    """The screen's bytes as logical colours' RGB, LINES rows of WIDTH."""
    rgb = [tuple(255 * ((c >> b) & 1) for b in range(3)) for c in range(8)]
    rows = []
    for y in range(panel.LINES):
        row = []
        for x in range(0, panel.WIDTH, 2):
            left, right = panel.colours_of(screen[panel.address(x, y) - panel.SCREEN])
            row += [rgb[left & 7], rgb[right & 7]]
        rows.append(row)
    return rows


def save_rgb(rows, path, scale=(1, 1)):
    from PIL import Image
    im = Image.new("RGB", (len(rows[0]), len(rows)))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            im.putpixel((x, y), c)
    if scale != (1, 1):
        im = im.resize((im.width * scale[0], im.height * scale[1]), Image.NEAREST)
    im.save(path)


# --- The fields' inks ---------------------------------------------------------

def inks(cut, pats):
    """Each field's ink, a byte for each cell and line: a logical colour
    solid; the bars the ST's own bar's colours line by line (the first
    BAR_RED cells its red end's, the rest its yellow's), each its pattern's
    byte for the line."""
    def pattern_byte(c, y):
        p = pats[c]
        return panel.mode2_byte(p[2 * (y & 3)], p[2 * (y & 3) + 1])

    out = {}
    for f in panel.FIELDS:
        name, x, y, n, across, table, ink = f
        h = panel.TABLES[table][0]
        cells = []
        for i, (cx, cy) in enumerate(panel.cell_places(f)):
            if ink is not None:
                cells.append([panel.mode2_byte(ink, ink)] * h)
                continue
            # (the ST's bar: its red end at BAR_ST_RED, the rest at BAR_ST_YELLOW)
            sx = BAR_ST_RED if i < panel.BAR_RED else BAR_ST_YELLOW
            cells.append([pattern_byte(cut[cy + k][sx], cy + k) for k in range(h)])
        out[name] = cells
    return out


BAR_ST_RED, BAR_ST_YELLOW = 8, 20   # pixels of the cut inside the ST's bar's red end and the rest


def check_layout():
    """Every cell on the screen, off the view, on a byte, and on no other."""
    seen = {}
    for f in panel.FIELDS:
        h = panel.TABLES[f[5]][0]
        for i, (x, y) in enumerate(panel.cell_places(f)):
            if x % 2:
                raise SystemExit(f"{f[0]}: cell {i} isn't on a byte")
            for k in range(h):
                for px in range(x, x + 4):
                    if not (0 <= px < panel.WIDTH and 0 <= y + k < panel.LINES) or panel.in_view(px, y + k):
                        raise SystemExit(f"{f[0]}: cell {i} is off the panel")
                    if (px, y + k) in seen:
                        raise SystemExit(f"{f[0]}: cell {i} is over {seen[(px, y + k)]}")
                    seen[(px, y + k)] = f[0]


def picture(pal, img, pats):
    """The cut, painted, in MODE 2: (the cut's ST colours, the screen's bytes)."""
    cut = compose(pal, img)
    pic = [row[:] for row in cut]
    paint(pic)
    rows = logical(pic, pats)
    texts(rows)
    return cut, screen_bytes(rows)


# --- Packing --------------------------------------------------------------
#
# The picture is unpacked once, at the start, into both buffers
# (src/panel.6502's panel_unpack): a stream of tokens, each a run of bytes
# given (a byte below &80: one more than that many follow) or a run copied
# from those already unpacked (a byte &80 + n - MATCH_MIN, then how far
# back, 1 to 256, 256 as 0: n bytes). Dithered colours repeat every four
# lines, so in the screen's order a flat area repeats every four bytes.
MATCH_MIN = 3
MATCH_MAX = 0x7F + MATCH_MIN
LITERAL_MAX = 0x80


def pack(data):
    """data as tokens (greedy: the longest match within 256 back)."""
    out = bytearray()
    lit = bytearray()

    def flush():
        while lit:
            run = lit[:LITERAL_MAX]
            out.append(len(run) - 1)
            out.extend(run)
            del lit[:LITERAL_MAX]

    i = 0
    n = len(data)
    while i < n:
        best, best_d = 0, 0
        for d in range(1, min(256, i) + 1):
            k = 0
            while k < MATCH_MAX and i + k < n and data[i + k] == data[i + k - d]:
                k += 1
            if k > best:
                best, best_d = k, d
        if best >= MATCH_MIN:
            flush()
            out.append(0x80 + best - MATCH_MIN)
            out.append(best_d & 0xFF)
            i += best
        else:
            lit.append(data[i])
            i += 1
    flush()
    return bytes(out)


def unpack(stream, n):
    """pack's inverse, as panel_unpack does it, to n bytes."""
    out = bytearray()
    i = 0
    while len(out) < n:
        t = stream[i]
        i += 1
        if t < 0x80:
            out.extend(stream[i:i + t + 1])
            i += t + 1
        else:
            d = stream[i] or 256
            i += 1
            for _ in range(t - 0x80 + MATCH_MIN):
                out.append(out[-d])
    return bytes(out)


def tiles(screens, width):
    """The places where the screens differ, in tiles width bytes by a
    character row, and the different tiles."""
    places, unique = [], {}
    for r in range(panel.SCREEN_ROWS):
        for c in range(0, panel.SCREEN_COLS, width):
            a = r * panel.SCREEN_ROW + 8 * c
            got = [s[a:a + 8 * width] for s in screens]
            if len(set(got)) > 1:
                places.append((r, c))
                for g in got:
                    unique.setdefault(g, len(unique))
    return places, unique


def papers(screen):
    """Each glyph cell's paper, a byte a line: the picture under it, which
    must be one byte a line across the cell (paint() sees to it)."""
    out = {}
    for f in panel.FIELDS:
        cells = []
        for i, place in enumerate(panel.cell_bytes(f)):
            line = []
            for a, b in place:
                if screen[a] != screen[b]:
                    raise SystemExit(f"{f[0]}: cell {i}'s paper isn't one colour across a line")
                line.append(screen[a])
            cells.append(line)
        out[f[0]] = cells
    return out


# --- The ZX's own words ------------------------------------------------------
#
# The message under the area's name: the original's three ($B76C), from its
# memory, and the disc's own for the game's end.
ZX_MESSAGES = {"neutral": 0x8C12, "cleared": 0x8BF6, "build": 0x8C04}
MESSAGE_LEN = 14


def messages(snap):
    sys.path.insert(0, str(ROOT / "tools"))
    from logic.oracle import Original
    mem = Original(snap).memory()
    out = {k: bytes(mem[a:a + MESSAGE_LEN]).decode("ascii") for k, a in ZX_MESSAGES.items()}
    out["over"] = "GAME OVER"
    for m in out.values():
        panel.text_cells(m, MESSAGE_LEN)        # (each in the font)
    return out


# --- The assembly's data ------------------------------------------------------

def equb(name, values, per=16):
    out = [f".{name}"] if name else []
    values = list(values)
    for i in range(0, len(values), per):
        out.append("    EQUB " + ", ".join(str(v) for v in values[i:i + per]))
    return out


def assembly(build, packed):
    """panel.6502: constants, then section PanelData (the tables the panel's
    code reads), then section PanelPack (the packed picture, loaded once)."""
    fields = panel.FIELDS
    # the glyph cells, field by field, then the tiles
    cells = []                  # (address, kind)
    kinds = []                  # (table, ink lines, paper lines)
    first = {}
    for f in fields:
        first[f[0]] = len(cells)
        for i, (x, y) in enumerate(panel.cell_places(f)):
            k = (f[5], tuple(build["inks"][f[0]][i]), tuple(build["papers"][f[0]][i]))
            if k not in kinds:
                kinds.append(k)
            cells.append((panel.address(x, y), kinds.index(k)))
    glyphs = len(cells)
    for r, c in build["tile_places"]:
        cells.append((panel.SCREEN + r * panel.SCREEN_ROW + 8 * c, 0))
    names = build["names"]
    L = [
        "\\ Generated by tools/mkpanel.py from Driller's ST console and ZX data",
        "\\ (decision 6): never committed. src/panel.6502 documents the layout.",
        f"PANEL_CELLS = {len(cells)}",
        f"PANEL_GLYPHS = {glyphs}",
        f"PANEL_KINDS = {len(kinds)}",
        f"PANEL_PACKED = {len(packed)}",
        f"PANEL_LOWEST = &{min(a for a, _k in cells):04X}",
        f"PANEL_TILES = {len(build['tiles'])}",
        f"PANEL_AREAS = {len(names)}",
        f"PANEL_MESSAGE = {MESSAGE_LEN}",
        f"PANEL_HEADING_SPAN = {2 * panel.HEADING_CELLS}",
        f"PANEL_PITCH_MID = {panel.PITCH_MID}",
        f"PANEL_PITCH_LINES = {panel.PITCH_LINES}",
        f"PANEL_PITCH_H = {panel.PITCH_H}",
        f"PANEL_BAR_MAX = {panel.BAR_MAX}",
        f"PANEL_NEUTRAL_FROM = {panel.NEUTRAL_FROM}",
        f"PANEL_CLEARED = {panel.CLEARED}",
        f"PANEL_NO_COMPASS = {{{', '.join(str(a) for a in panel.NO_COMPASS)}}}",
        f"PANEL_JET = {panel.JET}",
        f"PANEL_MAX_H = {max(panel.TABLES[t][0] for t, _i, _p in kinds)}",
    ]
    for f in fields:
        L.append(f"PF_{f[0].upper()} = {first[f[0]]} : PN_{f[0].upper()} = {f[3]}")
    L.append(f"PF_PICTURE = {glyphs} : PN_PICTURE = {len(build['tile_places'])}")
    for ch, name in ((" ", "SPACE"), ("0", "DIGIT0"), (".", "DOT"), ("^", "DEGREE")):
        L.append(f"PC_{name} = {panel.CHARSET.index(ch)}")
    # the free camera's message's words (src/live.6502's entrance_text)
    for name, text in (("ENTRANCE", panel.ENTRANCE_WORDS[0]), ("DEMO", panel.ENTRANCE_WORDS[1])):
        L.append(f"PANEL_{name} = {{{', '.join(str(c) for c in panel.text_cells(text, len(text)))}}}")
    L += ["", "SECTION PanelData"]
    L += equb("pc_lo", (a & 0xFF for a, _k in cells))
    L += equb("pc_hi", (a >> 8 for a, _k in cells))
    L += equb("pc_kind", (k for _a, k in cells[:glyphs]))
    L += equb("pk_h", (panel.TABLES[t][0] for t, _i, _p in kinds))
    L += equb("pk_stride", (panel.TABLES[t][1] for t, _i, _p in kinds))
    L.append(".pk_tlo")
    L += [f"    EQUB LO(pt_{t})" for t, _i, _p in kinds]
    L.append(".pk_thi")
    L += [f"    EQUB HI(pt_{t})" for t, _i, _p in kinds]
    lines = []                  # each kind's ink and paper lines, shared where alike
    for _t, ink, paper in kinds:
        for run in (ink, paper):
            if run not in lines:
                lines.append(run)
    for part, idx in (("i", 1), ("p", 2)):
        L.append(f".pk_{part}lo")
        L += [f"    EQUB LO(pl_{lines.index(k[idx])})" for k in kinds]
        L.append(f".pk_{part}hi")
        L += [f"    EQUB HI(pl_{lines.index(k[idx])})" for k in kinds]
    for i, run in enumerate(lines):
        L += equb(f"pl_{i}", run)
    for t in panel.TABLES:
        L += equb(f"pt_{t}", build["tables"][t])
    L += equb("pv_data", (b for t in build["tiles"] for b in bytes.fromhex(t)))
    L += equb("pv_jet", build["pictures"][panel.JET])
    L += equb("pv_probe", build["pictures"][panel.PROBE])
    for k in ("neutral", "cleared", "build", "over"):
        L += equb(f"pm_{k}", panel.text_cells(panel.centred(build["messages"][k], MESSAGE_LEN), MESSAGE_LEN))
    L += equb("pm_vehicle", (c for v in panel.VEHICLE_NAMES for c in panel.text_cells(panel.centred(v, 5), 5)))
    L += equb("pa_names", (c for n in names
                           for c in panel.text_cells(panel.centred(n, MESSAGE_LEN), MESSAGE_LEN)))
    L += ["ENDSECTION", "", "SECTION PanelPack"]
    L += equb("panel_packed", packed)
    L += ["ENDSECTION"]
    return "\n".join(L) + "\n"


SAMPLE = {                  # values for the previews
    "score": 1234567, "energy": 48, "shield": 50, "step": 250, "turn": 3,
    "x": 1888, "y": 104, "z": 2272, "yaw": 34, "pitch": 70, "vehicle": 2,
    "message": "build", "name": "AMETHYST", "cross": True, "shoot": False,
    "fps": "12.5",
}
JET_FRAME, PROBE_FRAME = 0, 1       # the ST's vehicle pictures the panel shows


def check(req):
    """For tools/livecheck.mjs (mkpanel.py --check < request > answer): the
    model's panel for what the disc showed and what it was given.

    req["shown"]: the cells the disc's buffers showed at flips (each the
    flat list, tools/model/panel.py's flat()); answered with the bytes
    render() makes at the cells' offsets ("offsets", from SCREEN), and the
    picture whole ("picture"), for everything else outside the view.

    req["valued"]: each time the disc set the panel's values
    (panel_values), in order: the original's variables as {"mem": [[ZX
    address, byte], ...]} (the transcription's state, or the free disc's
    own), the area whose name shows ("area": its index in the records'
    directory), whether the game's over ("over"), and with the free camera
    its position, yaw and pitch ("cam"); answered with the cells cells()
    gives, each after the last (the heading stays where the compass
    doesn't turn)."""
    build = panel.load_build()
    offsets = []
    for f in panel.FIELDS:
        for place in panel.cell_bytes(f):
            for pair in place:
                offsets += pair
    for place in build["tile_places"]:
        offsets += panel.tile_bytes(place)
    shown = []
    for s in req["shown"]:
        screen = panel.render(panel.unflat(s, build), build)
        shown.append(bytes(screen[o] for o in offsets).hex())
    valued, before = [], None
    for v in req["valued"]:
        mem = dict(v["mem"])
        names = build["names"]
        values = panel.values_of(mem, names[v["area"]] if v["area"] < len(names) else None, bool(v["over"]))
        if v.get("cam"):
            scale = mem[panel.ZX["AreaScale"]] or 1
            x, y, z, yaw, pitch = v["cam"]
            values.update(x=x // scale, y=y // scale, z=z // scale, yaw=yaw, pitch=pitch, compass=True)
        cells = panel.cells(values, before, build)
        before = cells
        valued.append(panel.flat(cells))
    return {"offsets": offsets, "picture": build["picture"], "shown": shown, "valued": valued,
            "fields": [[f[0], f[3]] for f in panel.FIELDS] + [["picture", len(build["tile_places"])]],
            "names": build["names"], "messages": build["messages"]}


def main(argv):
    if len(argv) == 2 and argv[1] == "--check":
        json.dump(check(json.load(sys.stdin)), sys.stdout)
        return 0
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    out, snap, areas_json, data_json = Path(argv[1]), argv[2], argv[3], argv[4]
    out.mkdir(parents=True, exist_ok=True)
    check_layout()
    pal, img = st_console()
    pats = st_patterns(pal)
    cut, screen = picture(pal, vehicle(img, PROBE_FRAME), pats)
    jet = picture(pal, vehicle(img, JET_FRAME), pats)[1]
    places, unique = tiles([jet, screen], 1)
    tile_list = sorted(unique, key=unique.get)

    def tiles_of(s):
        return [unique[s[r * panel.SCREEN_ROW + 8 * c:r * panel.SCREEN_ROW + 8 * c + 8]]
                for r, c in places]
    db = json.loads(Path(data_json).read_text())
    by_id = {a["id"]: a for a in db["areas"]}
    layout = json.loads(Path(areas_json).read_text())
    names = [by_id[a["id"]]["name"].strip() for a in layout["areas"]]
    build = {
        "picture": screen.hex(), "inks": inks(cut, pats), "papers": papers(screen),
        "tables": {name: panel.table_lines(name) for name in panel.TABLES},
        "tile_places": places, "tiles": [t.hex() for t in tile_list],
        "pictures": [tiles_of(jet), tiles_of(screen)], "messages": messages(snap),
        "names": names, "charset": panel.CHARSET,
    }
    packed = pack(screen)
    if unpack(packed, len(screen)) != screen:
        raise SystemExit("the picture doesn't unpack to itself")
    (out / "panel.json").write_text(json.dumps(build) + "\n")
    (out / "panel.6502").write_text(assembly(build, packed))
    save_rgb(to_rgb(screen), out / "picture.png")
    sample = panel.render(panel.cells(SAMPLE, build=build), build)
    save_rgb(to_rgb(sample), out / "sample.png")
    save_rgb(to_rgb(sample), out / "sample4x.png", (4, 2))
    print(f"panel: the picture {len(packed)} bytes packed; {len(places)} tiles' places, "
          f"{len(tile_list)} tiles")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
