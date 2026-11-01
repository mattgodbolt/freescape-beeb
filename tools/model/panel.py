"""The panel below the view: Driller's instruments, the ST's console redrawn
for MODE 2's 128 pixels (docs/research/panel.md).

The screen is Driller's 192 lines (decision 43): the view's 104 lines, a
character row above it and ten below. Everything outside the view is the
panel: a picture that never changes (tools/mkpanel.py makes it from the
ST's console at build time: Driller's art is never committed) and, over
it, cells that the logic's values choose.

A cell is two MODE 2 bytes across, four pixels, and its style's lines
down. What it shows is a glyph: four pixels a line, one bit each (bit 3
the leftmost), from one of the glyph tables below; each pixel is the
style's ink or paper for its line, each a MODE 2 byte (a solid colour or a
pattern's byte for the line). A field is a run of cells across (two bytes
apart) or down (the style's lines apart), all of one style and table.

    glyph_tables()        every table's glyphs, each a list of line nibbles
    cells(values)         each field's glyph numbers, from the panel's values
    render(cells, base)   the screen's bytes (SCREEN to &7FFF) with them drawn

The values (values_of) are the logic's variables the original's panel
shows ($B72B, docs/research/zx-logic.md): the score, the energy and
shield, the step and the turn, the position over the area's scale, the
heading and pitch, the vehicle, the area's name and its message, whether
the crosshair is up and whether it's shooting mode; and the frames a
second the disc measures itself. tools/livecheck.mjs holds the disc's
cells to cells() of the transcription's state after every pass, and its
screen to render() of the cells it shows.
"""
import json
import pathlib

from . import view

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "panel"

DEFS = view.read_defs()
SCREEN = DEFS["SCREEN"]
SCREEN_ROW = DEFS["SCREEN_ROW"]
SCREEN_COLS = DEFS["SCREEN_COLS"]
SCREEN_ROWS = DEFS["SCREEN_ROWS"]
VIEW_ADDR = DEFS["VIEW_ADDR"]
VIEW_COL0 = DEFS["VIEW_COL0"]
VIEW_BYTES = DEFS["VIEW_BYTES"]
VIEW_TOP = DEFS["VIEW_ROW0"] * 8
VIEW_END = VIEW_TOP + DEFS["VIEW_H"]
PIX_LEFT = DEFS["PIX_LEFT"]
PIX_RIGHT = DEFS["PIX_RIGHT"]
WIDTH = SCREEN_COLS * 2             # pixels across
LINES = SCREEN_ROWS * 8
SCREEN_BYTES = 0x8000 - SCREEN


def address(x, y):
    """The byte holding pixel x (even: the left of its byte) on line y."""
    return SCREEN + (y // 8) * SCREEN_ROW + (x // 2) * 8 + y % 8


def in_view(x, y):
    return VIEW_TOP <= y < VIEW_END and VIEW_COL0 <= x // 2 < VIEW_COL0 + VIEW_BYTES


def mode2_left(c):
    return ((c & 8) << 4) | ((c & 4) << 3) | ((c & 2) << 2) | ((c & 1) << 1)


def mode2_byte(left, right):
    return mode2_left(left) | (mode2_left(right) >> 1)


def colours_of(b):
    """A MODE 2 byte's two logical colours, left then right."""
    left = sum(((b >> (2 * i + 1)) & 1) << i for i in range(4))
    right = sum(((b >> (2 * i)) & 1) << i for i in range(4))
    return left, right


# --- The font ---------------------------------------------------------------
#
# Three pixels by five lines, a pixel's gap to the right and none below:
# MODE 2's pixels are twice as wide as tall, so a glyph is about as wide as
# it is tall, and four pixels a character gives 32 across, as the ZX's
# panel font gives its 256 pixels. Capitals, figures and what the panel
# says. tools/mkpanel.py writes the static text (the credit, the labels) in
# it too, closed up where a glyph is narrower ("I", ".", ":").

FONT_H = 5
FONT = {
    " ": ["...", "...", "...", "...", "..."],
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"],
    "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "##."],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", "##.", ".##"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "Z": ["###", "..#", ".#.", "#..", "###"],
    ".": ["...", "...", "...", "...", ".#."],
    ":": ["...", ".#.", "...", ".#.", "..."],
    "-": ["...", "...", "###", "...", "..."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
    "(": ["..#", ".#.", ".#.", ".#.", "..#"],
    ")": ["#..", ".#.", ".#.", ".#.", "#.."],
    "'": [".#.", ".#.", "...", "...", "..."],
    "^": [".#.", "#.#", ".#.", "...", "..."],    # a degree sign
}
# Glyphs narrower than three pixels, closed up in static text: the columns
# each keeps.
NARROW = {"I": (1,), ".": (1,), ":": (1,), "'": (1,), "(": (1, 2), ")": (0, 1), " ": (0, 1)}
NARROW_FONT = {"I": ["#", "#", "#", "#", "#"]}


def glyph_nibbles(rows):
    """A glyph's rows of '#' and '.' (three across, or four) as nibbles,
    bit 3 the leftmost pixel."""
    out = []
    for r in rows:
        r = r.ljust(4, ".")
        out.append(sum(8 >> i for i, ch in enumerate(r) if ch == "#"))
    return out


def text_pixels(text, narrow=True):
    """Static text as rows of pixels (1 ink, 0 paper), FONT_H lines: each
    glyph and a pixel's gap, closed up where narrow."""
    rows = [[] for _ in range(FONT_H)]
    for i, ch in enumerate(text):
        g = NARROW_FONT.get(ch) if narrow else None
        g = g or FONT[ch]
        keep = range(len(g[0]))
        if narrow and ch in NARROW and ch not in NARROW_FONT:
            keep = NARROW[ch]
        for y in range(FONT_H):
            rows[y] += [1 if g[y][k] == "#" else 0 for k in keep]
            if i < len(text) - 1:
                rows[y].append(0)
    return rows


def text_width(text, narrow=True):
    return len(text_pixels(text, narrow)[0])


# --- The glyph tables ---------------------------------------------------------
#
# A table's glyph g starts at line g * stride of the table's lines: the font
# and the bars are glyphs one after another (stride their height); a tape
# down the screen is one long column read from any line (stride 1).

STEPS = 72                  # a turn, in the logic's 5-degree steps

# The characters the font table holds, in order: a cell's value is its
# character's place here.
CHARSET = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.:-+/()'^"


def font_table():
    return [glyph_nibbles(FONT[ch]) for ch in CHARSET]


# The bars: a cell of a bar four pixels long, n of them lit from the left.
BAR_H = 6


def bar_table():
    return [[(0xF0 >> n) & 0xF] * BAR_H for n in range(5)]


# The heading: a tape a pixel to the step, round the full turn, N at 0 (the
# logic's yaw 0 looks along +z; turning right adds to it), E, S and W a
# quarter apart, a tick between each, dashes between those, as the ST's
# compass has them (SPRCOG). Seen through a window HEADING_CELLS cells
# wide, its middle at the logic's yaw.
HEADING_H = 5
HEADING_CELLS = 3


def heading_tape():
    """The tape: HEADING_H lines of STEPS pixels (1 lit)."""
    rows = [[0] * STEPS for _ in range(HEADING_H)]
    for q, ch in enumerate("NESW"):
        g = FONT[ch]
        for y in range(HEADING_H):
            for k in range(3):
                if g[y][k] == "#":
                    rows[y][(q * STEPS // 4 + k - 1) % STEPS] = 1
        mid = q * STEPS // 4 + STEPS // 8
        for y in (1, 2, 3):
            rows[y][mid % STEPS] = 1
        for d in (STEPS // 16 + 1, 3 * STEPS // 16):
            rows[2][(q * STEPS // 4 + d) % STEPS] = 1
    return rows


def heading_table():
    """Glyph g: the tape's four pixels from pixel g on."""
    tape = heading_tape()
    return [[sum(8 >> k for k in range(4) if tape[y][(g + k) % STEPS]) for y in range(HEADING_H)]
            for g in range(STEPS)]


def heading_cells(yaw):
    """The window's cells: its middle pixel the tape's pixel yaw."""
    left = yaw - 2 * HEADING_CELLS
    return [(left + 4 * i) % STEPS for i in range(HEADING_CELLS)]


# The pitch: a tape down the screen, two lines to the step round the full
# turn, a tick at every step and the angle from level every six (30
# degrees, folded at 90 as the ST's strip folds its own), in two columns of
# cells: the tens and the units with the ticks. The window is PITCH_CELLS
# cells of PITCH_H lines, a character row each; the logic's pitch is at its
# line PITCH_MID.
PITCH_H = 8
PITCH_CELLS = 4
PITCH_MID = 16
PITCH_LINES = 2 * STEPS


def pitch_tape():
    """Two columns of PITCH_LINES + PITCH_H lines (the window can run past
    the end, so the start repeats there), each line a nibble."""
    cols = [[0] * PITCH_LINES for _ in range(2)]
    for p in range(STEPS):
        cols[1][2 * p] |= 1 if p % 3 else 0
        if p % 6 == 0:
            cols[1][2 * p] |= 1
            cols[1][(2 * p + 1) % PITCH_LINES] |= 1
            angle = min(p * 5 % 360, 360 - p * 5 % 360)
            if angle > 90:
                angle = 180 - angle
            text = f"{angle:02d}"
            for c in range(2):
                g = glyph_nibbles(FONT[text[c]])
                for y in range(FONT_H):
                    line = (2 * p - FONT_H // 2 + y) % PITCH_LINES
                    cols[c][line] |= g[y] & 0xE
    return [col + col[:PITCH_H] for col in cols]


def pitch_cells(pitch):
    """Each column's cells: the tape's line at the top of each."""
    top = 2 * pitch - PITCH_MID
    return [(top + PITCH_H * j) % PITCH_LINES for j in range(PITCH_CELLS)]


# Lights: a cell two lines high, three pixels lit or none.
LIGHT_H = 2


def light_table():
    return [[0, 0], [0xE, 0xE]]


TABLES = {
    "font": (FONT_H, FONT_H, font_table),
    "bar": (BAR_H, BAR_H, bar_table),
    "heading": (HEADING_H, HEADING_H, heading_table),
    "pitch0": (PITCH_H, 1, lambda: [[v] for v in pitch_tape()[0]]),
    "pitch1": (PITCH_H, 1, lambda: [[v] for v in pitch_tape()[1]]),
    "light": (LIGHT_H, LIGHT_H, light_table),
}


def table_lines(name):
    """A table as one run of line nibbles: glyph g's lines start at g * stride."""
    _h, _stride, make = TABLES[name]
    return [v for g in make() for v in g]


# --- The fields ---------------------------------------------------------------
#
# Each: its name, the pixel its first cell starts at (even: a byte's left)
# and its first line, its cells, whether they go across or down, its
# table, and its ink: a logical colour, or None for the bars' (the ST's
# bars' own, line by line: tools/mkpanel.py). The paper is the picture
# under the cell, which tools/mkpanel.py makes one colour a line under each
# cell. Every cell lies inside a character row, so its lines are one byte
# apart (tools/mkpanel.py checks). docs/research/panel.md has the layout.
YELLOW, RED, GREEN, WHITE, BLACK = 3, 1, 2, 7, 0

FIELDS = [
    # name       x    y    n  across  table      ink
    ("score",    88, 123,  7, True,  "font",    YELLOW),
    ("message",  62, 171, 14, True,  "font",    YELLOW),
    ("name",     62, 178, 14, True,  "font",    YELLOW),
    ("shield",    6, 170,  6, True,  "bar",     None),
    ("energy",    6, 178,  6, True,  "bar",     None),
    ("heading",  24, 136,  3, True,  "heading", YELLOW),
    ("pitch0",   38, 128,  4, False, "pitch0",  YELLOW),
    ("pitch1",   42, 128,  4, False, "pitch1",  YELLOW),
    ("step",     24, 146,  3, True,  "font",    YELLOW),
    ("turn",     24, 153,  3, True,  "font",    YELLOW),
    ("x",         4, 136,  4, True,  "font",    YELLOW),
    ("z",         4, 144,  4, True,  "font",    YELLOW),
    ("y",         4, 152,  4, True,  "font",    YELLOW),
    ("vehicle",  56, 155,  5, True,  "font",    YELLOW),
    ("fps",      38, 187,  4, True,  "font",    YELLOW),
    ("cross",    80, 115,  1, True,  "light",   YELLOW),
    ("shoot",    86, 115,  1, True,  "light",   WHITE),
]
# The bars' inks by line, the ST's own bars' (its console's): the first
# cell its red end's, the rest its yellow's.
BAR_RED = 1
BAR_CELLS = 6
BAR_MAX = 63                # the energy and shield the bars show whole

# The vehicle's picture, over the monitor: the ST's own (its sprites of
# the jet and of the probe, tools/mkpanel.py), drawn as tiles a byte across
# and a character row down where the two differ: field "picture", whose
# cells are tiles (panel.json's "tiles", at its "tile_places"), each
# picture its tiles (panel.json's "pictures"). Its name goes under it (field
# "vehicle"): the ST's AIRBORNE, MOBILE and EXTENSION in five cells.
VEHICLE_NAMES = ["JET", "PROBE", "EXT 1", "EXT 2", "EXT 3"]
JET, PROBE = 0, 1
# The free camera's disc shows its entrance where the message goes: " ENTRANCE
# nn  ", or "     DEMO nn  " while its demo turns (entrance_message).
ENTRANCE_WORDS = ("ENTRANCE", "    DEMO")


def entrance_message(entrance, demo):
    tens = f"{entrance // 10}" if entrance >= 10 else " "
    return f" {ENTRANCE_WORDS[1 if demo else 0]} {tens}{entrance % 10}  "


def field(name):
    return next(f for f in FIELDS if f[0] == name)


def cell_places(f):
    """Each cell of field f: (pixel, line) of its top left."""
    name, x, y, n, across, table, _ink = f
    h = TABLES[table][0]
    return [(x + 4 * i, y) if across else (x, y + h * i) for i in range(n)]


def cell_bytes(f):
    """The screen's offsets (from SCREEN) each cell of field f covers, by
    line then byte."""
    h = TABLES[f[5]][0]
    return [[(address(x, y + k) - SCREEN, address(x + 2, y + k) - SCREEN) for k in range(h)]
            for x, y in cell_places(f)]


def tile_bytes(place):
    """A tile's screen offsets: a byte column of a character row, (row, byte)."""
    r, c = place
    return [r * SCREEN_ROW + 8 * c + k for k in range(8)]


# --- The values ---------------------------------------------------------------
#
# values_of: the panel's values from the original's variables, by their ZX
# addresses (the logic's mirror and the transcription's state alike):
# what the original's $B72B reads.
ZX = {"Score": 0x8872, "Energy": 0x8875, "Shield": 0x8878, "Step": 0x876A,
      "Turn": 0x876F, "PlayerX": 0x8762, "PlayerY": 0x8764, "PlayerZ": 0x8766,
      "Pitch": 0x876C, "Yaw": 0x876D, "InJet": 0x877A, "ExtLevel": 0x8772,
      "AreaScale": 0x8779, "AreaId": 0x8862, "RigPlaced": 0x877B,
      "CrossOn": 0x88A2, "ShootMode": 0x88AC}
NEUTRAL_FROM = 19           # areas from this id have no gas ($B773)
CLEARED = 3                 # RigPlaced's value for a rig that's drilled ($B787)
NO_COMPASS = (13, 18)       # areas whose compass the original doesn't turn ($B83E)


def values_of(mem, area_name, over=False):
    """The panel's values from the original's memory (anything indexable by
    its addresses): as $B72B shows them. The area's name is the one the
    view shows (its entry's), and over whether the game is over."""
    def w(a):
        return mem[a] | (mem[a + 1] << 8)
    scale = mem[ZX["AreaScale"]] or 1
    area = mem[ZX["AreaId"]]
    if over:
        message = "over"
    elif not (area - NEUTRAL_FROM) & 0x80:          # (the sign of the byte, as JP M)
        message = "neutral"
    elif mem[ZX["RigPlaced"] + ((area - 1) & 0xFF)] == CLEARED:
        message = "cleared"
    else:
        message = "build"
    return {
        "score": mem[ZX["Score"]] | (mem[ZX["Score"] + 1] << 8) | (mem[ZX["Score"] + 2] << 16),
        "energy": mem[ZX["Energy"]], "shield": mem[ZX["Shield"]],
        "step": mem[ZX["Step"]], "turn": mem[ZX["Turn"]],
        "x": w(ZX["PlayerX"]) // scale, "y": w(ZX["PlayerY"]) // scale,
        "z": w(ZX["PlayerZ"]) // scale,
        "yaw": mem[ZX["Yaw"]], "pitch": mem[ZX["Pitch"]],
        "compass": area not in NO_COMPASS,
        "vehicle": JET if mem[ZX["InJet"]] else min(max(mem[ZX["ExtLevel"]], 1), 4),
        "message": message, "name": area_name,
        "cross": mem[ZX["CrossOn"]] != 0, "shoot": mem[ZX["ShootMode"]] != 0,
    }


def number(v, digits):
    """v as the original's $9390 writes it: digits places, leading zeros,
    the low ones if it's longer."""
    return f"{v % 10 ** digits:0{digits}d}"


def text_cells(text, n):
    text = text.upper()
    if len(text) > n:
        raise ValueError(f"{text!r} is wider than {n} cells")
    return [CHARSET.index(ch) for ch in text.ljust(n)]


def centred(text, n):
    text = text.strip()
    pad = n - len(text)
    return " " * (pad // 2) + text + " " * (pad - pad // 2)


def bar_lit(v):
    """The pixels a bar lights for v: BAR_CELLS * 4 for BAR_MAX or more,
    none for 0, at least one for 1."""
    return (min(v, BAR_MAX) * 3 + 7) >> 3


def bar_cells(v):
    lit = bar_lit(v)
    return [max(0, min(4, lit - 4 * i)) for i in range(BAR_CELLS)]


def cells(values, before=None, build=None):
    """Each field's cells, from the panel's values (values_of), and the
    cells shown before (for the heading, which stays as it was where the
    original's compass doesn't turn; none before: it turns anyway)."""
    v = values
    build = build or load_build()
    message = v.get("message_text") or centred(build["messages"][v["message"]], 14)
    out = {
        "score": text_cells(number(v["score"], 7), 7),
        "message": text_cells(message, 14),
        "name": text_cells(centred(v["name"] or "", 14), 14),
        "shield": bar_cells(v["shield"]),
        "energy": bar_cells(v["energy"]),
        "heading": heading_cells(v["yaw"] % STEPS),
        "step": text_cells(number(v["step"], 3), 3),
        "turn": text_cells(number(5 * v["turn"] & 0xFF, 2) + "^", 3),
        "x": text_cells(number(v["x"], 4), 4),
        "z": text_cells(number(v["z"], 4), 4),
        "y": text_cells(number(v["y"], 4), 4),
        "vehicle": text_cells(centred(VEHICLE_NAMES[v["vehicle"]], 5), 5),
        "picture": build["pictures"][JET if v["vehicle"] == JET else PROBE],
        "fps": text_cells(v.get("fps", "    "), 4),
        "cross": [1 if v["cross"] else 0],
        "shoot": [1 if v["shoot"] else 0],
    }
    if not v.get("compass", True) and before:
        out["heading"] = before["heading"]
    if v["name"] is None:           # (no area yet: the name stays as it was)
        out["name"] = before["name"] if before else text_cells("", 14)
    pitch = pitch_cells(v["pitch"] % STEPS)
    out["pitch0"] = pitch
    out["pitch1"] = pitch
    return out


# The order of the cells on the disc: the fields' in FIELDS's order, then
# the picture's tiles.
def flat(cell_values):
    return [g for f in FIELDS for g in cell_values[f[0]]] + list(cell_values["picture"])


def unflat(values, build=None):
    build = build or load_build()
    out, i = {}, 0
    for f in FIELDS:
        out[f[0]] = list(values[i:i + f[3]])
        i += f[3]
    out["picture"] = list(values[i:i + len(build["tile_places"])])
    return out


# --- Rendering --------------------------------------------------------------

def load_build():
    """mkpanel's output: the picture (SCREEN to &7FFF, both buffers alike,
    the view's bytes 0), the inks' bytes by field, cell and line, the glyph
    tables, the vehicle's tiles and the messages."""
    return json.loads((BUILD / "panel.json").read_text())


def masks(nibble):
    """A glyph line's four pixels as two MODE 2 byte masks."""
    pair = (0, PIX_RIGHT, PIX_LEFT, 0xFF)
    return pair[nibble >> 2], pair[nibble & 3]


def render(cell_values, build=None):
    """The screen's bytes, SCREEN to &7FFF, with each field's cells drawn
    over the picture: each pixel the field's ink where its glyph is lit,
    else the picture's; and the vehicle's tiles."""
    build = build or load_build()
    out = bytearray(bytes.fromhex(build["picture"]))
    for f in FIELDS:
        name, table = f[0], f[5]
        h, stride, _make = TABLES[table]
        lines = build["tables"][table]
        for i, place in enumerate(cell_bytes(f)):
            g = cell_values[name][i]
            ink = build["inks"][name][i]
            for k, pair in enumerate(place):
                for a, m in zip(pair, masks(lines[g * stride + k])):
                    out[a] ^= (out[a] ^ ink[k]) & m
    for place, t in zip(build["tile_places"], cell_values["picture"]):
        for a, b in zip(tile_bytes(place), bytes.fromhex(build["tiles"][t])):
            out[a] = b
    return bytes(out)
