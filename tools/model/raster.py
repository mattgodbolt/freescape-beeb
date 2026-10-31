"""The rasteriser: faces, nearest first, into each line's runs.

docs/engine.md, stages 8 and 9, and section 9's interface. This is the
specification the 6502's src/raster.6502 matches byte for byte (through
writer.py's bytes; tools/rastercheck.mjs compares them).

rasterise(faces, sky, ground, horizon=None, stats=None):

- faces: nearest first, each (pattern, polygon): a pattern is four bytes,
  one for each value of line AND 3; a polygon is convex, its vertices view
  coordinates inside [0, 16 VIEW_W] x [0, 16 VIEW_H], in either winding.
- sky, ground: patterns; horizon: ((px, py), (dx, dy)) in view coordinates,
  sky to the left of the direction as seen on the screen (a pixel centre on
  the line is ground), or None for sky everywhere.
- Returns, for each line 0 .. VIEW_H - 1, its runs (x0, x1, pattern) in
  pixels, in order, covering [0, VIEW_W) exactly. A run is the pixels of one
  source (a face, or the sky or ground) that touch, so two faces of the same
  pattern side by side are two runs, as the 6502 writes them.
- stats, a dict, gets the counts the cost model uses (Counts).

The rules:

- View coordinates are sixteenths of a pixel (SUB), x right and y down from
  the view's top left; pixel (px, py) has its centre at (16 px + 8, 16 py + 8).
- The fill rule: a face covers a pixel when the pixel's centre is inside it.
  A centre exactly on an edge counts for top and left edges, not for bottom
  and right ones. Per line that is: each non-horizontal edge is crossed by
  the lines whose centres are in [top, bottom) of it, at
  p = ceil((x - 8) / 16) of its x there, and the face covers [p_left, p_right).
- Faces come nearest first. Each pixel takes the first face that covers it,
  which is the painter's image for the same order taken back to front.
- What no face covers is background: sky on one side of the horizon and
  ground on the other (horizon_split), or all sky when there is no horizon.
"""

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _defs(path=ROOT / "src" / "defs.6502"):
    """The plain constants of src/defs.6502 (NAME = expression), evaluated, so
    the view's size and place are written down once, there (as
    tools/model/view.py reads them too)."""
    out = {}
    for line in path.read_text().splitlines():
        line = line.split(";", 1)[0].split("\\", 1)[0].strip()
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", line)
        if not m:
            continue
        expr = m.group(2)
        expr = re.sub(r"&([0-9A-Fa-f]+)", r"0x\1", expr)
        expr = expr.replace(" DIV ", " // ").replace(" MOD ", " % ")
        try:
            out[m.group(1)] = eval(expr, {"__builtins__": {}}, dict(out))
        except (NameError, SyntaxError, TypeError):
            pass
    return out


DEFS = _defs()
VIEW_W = DEFS["VIEW_W"]
VIEW_H = DEFS["VIEW_H"]
SUB = DEFS["SUB"]
HALF = SUB // 2


def ceil_div(n, d):
    """ceil(n / d) for integers, d > 0."""
    return -((-n) // d)


def pixel_of(num, den):
    """The first pixel whose centre is at or right of x = num / den
    (sixteenths): ceil((x - 8) / 16)."""
    return ceil_div(num - HALF * den, SUB * den)


def first_line(y):
    """The first line whose centre is at or below y (sixteenths)."""
    return ceil_div(y - HALF, SUB)


def edge_crossings_exact(x0, y0, x1, y1):
    """The fill rule's exact boundaries: (line, p) for each line whose centre
    is in [top, bottom) of the edge, p = ceil((x - 8) / 16) of its x there.
    A horizontal edge crosses none. (The reference the DDA is held to.)"""
    if y0 == y1:
        return
    if y0 > y1:
        x0, y0, x1, y1 = x1, y1, x0, y0
    dx, dy = x1 - x0, y1 - y0
    for k in range(max(first_line(y0), 0), min(first_line(y1), VIEW_H)):
        c = SUB * k + HALF
        yield k, pixel_of(x0 * dy + dx * (c - y0), dy)


# The gradient's reciprocal (portalc's, docs/research/rtw-sources.md 1.5):
# dy, normalised to a byte n in [128, 255] at a power of two and rounded up,
# has 256 + RECIPF[n - 128] <= 65536 / n.
RECIPF = [65536 // n - 256 for n in range(128, 256)]


def normalise(dy):
    """(n, s) with n in [128, 255] and n * 2^s >= dy: exact when s <= 0,
    dy's top byte rounded up otherwise."""
    s = dy.bit_length() - 8
    if s <= 0:
        return dy << -s, s
    n = -((-dy) >> s)
    if n == 256:
        return 128, s + 1
    return n, s


def edge_crossings(x0, y0, x1, y1):
    """The lines an edge crosses (those whose centres are in [top, bottom) of
    it, as the fill rule has it) and its pixel boundary on each: (line, p).
    A horizontal edge crosses none.

    The boundary is the exact one, (x + 7) >> 4, for a vertical edge, and
    otherwise a DDA in 8.8 fixed point (decision 21), as the 6502 steps it.
    With dy normalised to n at 2^s (normalise) and r = 256 + f(n), its
    reciprocal, the gradient is g = |dx| r >> (8 + s) pixels a line, and
    the first line's offset from the top vertex g t0 >> 4, t0 the line's
    distance below it in sixteenths. An edge no taller than a line crosses
    one line at most, so it has no gradient, and its offset is
    |dx| t0 r >> (12 + s) (which g needn't fit 16 bits for). X starts at
    16 (x0 - 8) + 255 plus or minus the offset, steps by g a line, and p is
    X >> 8. Every term rounds toward x0, so an edge never passes its far
    vertex and p stays inside the view; edge_crossings_exact is what it
    approximates, within a pixel."""
    if y0 == y1:
        return
    if y0 > y1:
        x0, y0, x1, y1 = x1, y1, x0, y0
    k0, k1 = max(first_line(y0), 0), min(first_line(y1), VIEW_H)
    if k0 >= k1:
        return
    if x0 == x1:
        p = (x0 + SUB // 2 - 1) >> 4
        for k in range(k0, k1):
            yield k, p
        return
    dx, dy = x1 - x0, y1 - y0
    adx = abs(dx)
    n, s = normalise(dy)
    r = 256 + RECIPF[n - 128]
    t0 = SUB * k0 + HALF - y0
    if dy > SUB:
        g = (adx * r) >> (8 + s)
        off = (g * t0) >> 4
    else:
        g = 0
        off = (adx * t0 * r) >> (12 + s)
    if dx < 0:
        g, off = -g, -off
    x = (x0 - HALF) * 16 + 255 + off
    for k in range(k0, k1):
        yield k, x >> 8
        x += g


def face_spans(vertices, crossings=None):
    """A convex polygon's span on each line it covers: {line: (x0, x1)}, x1
    exclusive, only lines where x0 < x1. Either winding; a degenerate
    polygon (no area) covers nothing. crossings is edge_crossings unless
    given (edge_crossings_exact, for the reference)."""
    crossings = crossings or edge_crossings
    cross = {}
    n = len(vertices)
    for i in range(n):
        (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
        for k, p in crossings(x0, y0, x1, y1):
            cross.setdefault(k, []).append(p)
    spans = {}
    for k, ps in cross.items():
        lo, hi = max(min(ps), 0), min(max(ps), VIEW_W)
        if lo < hi:
            spans[k] = (lo, hi)
    return spans


@dataclass(frozen=True)
class Horizon:
    """A point on the horizon and its direction, in view coordinates; the sky
    is to the left of the direction as seen on the screen (y down), so a
    level horizon pointing right has sky above."""
    x: int
    y: int
    dx: int
    dy: int

    def __post_init__(self):
        if self.dx == 0 and self.dy == 0:
            raise ValueError("a horizon needs a direction")


@dataclass
class Background:
    sky: tuple
    ground: tuple
    horizon: Horizon | None = None


def is_ground(h, cx, cy):
    """Whether a point is ground: on the horizon or on its right as seen on
    the screen, dx (cy - hy) - dy (cx - hx) >= 0."""
    return h.dx * (cy - h.y) - h.dy * (cx - h.x) >= 0


def horizon_split(bg, line):
    """The background on a line: (left, right, split), meaning pixels below
    split take left and the rest take right, split in [0, VIEW_W].

    A pixel is ground when its centre is on the horizon or on the ground's
    side of it (is_ground), and sky otherwise. A level horizon puts a whole
    line on one side. Otherwise the split is where the horizon crosses the
    line's centre, at x: pointing down the screen, the sky is right of it
    and the ground is the pixels whose centres are at or left of x, so the
    split is floor((x - 8) / 16) + 1; pointing up, the ground is right of
    it, from ceil((x - 8) / 16)."""
    h = bg.horizon
    if h is None:
        return bg.sky, bg.ground, VIEW_W
    c = SUB * line + HALF
    if h.dy == 0:
        return bg.sky, bg.ground, 0 if is_ground(h, 0, c) else VIEW_W
    # x = hx + dx (c - hy) / dy, and (x - 8) / 16 = n / d.
    num, den = h.x * h.dy + h.dx * (c - h.y), h.dy
    if den < 0:
        num, den = -num, -den
    n, d = num - HALF * den, SUB * den
    if h.dy > 0:
        return bg.ground, bg.sky, min(max(n // d + 1, 0), VIEW_W)
    return bg.sky, bg.ground, min(max(ceil_div(n, d), 0), VIEW_W)


@dataclass
class Counts:
    """What the rasteriser did, for the cost model (docs/research/raster.md):
    the 6502 does the same work, so these predict its cycles."""
    faces: int = 0          # faces looked at (before every line was full)
    edges: int = 0          # edges set up: non-horizontal, crossing a line
    edge_lines: int = 0     # (edge, line) steps
    face_rows: int = 0      # (face, line) for every line a face's range takes
    face_lines: int = 0     # (face, line) with a span, on a line not yet full
    pieces: int = 0         # visible pieces of faces written
    bg_pieces: int = 0      # background pieces written
    whole: int = 0          # whole bytes written through the row runs
    joins: int = 0          # bytes two runs share, written combined
    gaps_peak: int = 0      # most gaps alive at once, over all lines
    line_gaps_peak: int = 0 # most gaps on one line at once
    full_lines: int = 0     # lines faces filled before the background
    overflow: bool = False  # a span didn't fit the pools (rasterise)

    @property
    def runs(self):
        return self.pieces + self.bg_pieces

    @property
    def bytes(self):
        return self.whole + self.joins


def _piece_bytes(counts, lo, hi):
    """A piece's whole bytes: those both of whose pixels it covers."""
    n = (hi >> 1) - ((lo + 1) >> 1)
    if n > 0:
        counts.whole += n


def rasterise(faces, sky, ground, horizon=None, stats=None):
    """The interface (the module's docstring): faces nearest first to each
    line's runs."""
    bg = Background(tuple(sky), tuple(ground),
                    None if horizon is None else Horizon(*horizon[0], *horizon[1]))
    lines, counts = spans([(tuple(p), [tuple(v) for v in vs]) for p, vs in faces], bg)
    if stats is not None:
        stats.update(counts.__dict__, runs=counts.runs, bytes=counts.bytes,
                     # the stand-in's names for three of them (counts.py)
                     face_lines_open=counts.face_lines, face_runs=counts.pieces,
                     lines_full=counts.full_lines)
    return lines


def spans(faces, bg, capacity=None, crossings=None):
    """faces: [(pattern, [(x, y), ...]), ...] nearest first, vertices inside
    [0, 16 VIEW_W] x [0, 16 VIEW_H]; bg: a Background. Returns (lines,
    counts): lines[y] = [(x0, x1, pattern), ...] in order, covering
    [0, VIEW_W).

    The algorithm is stage 8's, as the 6502 runs it: each line keeps its
    gaps (the runs nothing covers yet) in order, and each face's span on a
    line takes what it overlaps of them. A line with no gaps is full, and
    faces stop once every line is.

    capacity, if given, is how many gaps each of the 6502's four pools
    holds (one for each value of line AND 3), counting every gap a frame
    makes: a line's first face makes the gaps it leaves, and a span inside
    a gap splits it into two. A span whose gaps don't fit isn't drawn on
    that line, and counts.overflow says so. crossings is the edges' rule
    (edge_crossings unless given; edge_crossings_exact for the check against
    the brute force)."""
    counts = Counts()
    gaps = [[[0, VIEW_W]] for _ in range(VIEW_H)]
    touched = [False] * VIEW_H
    used = [0] * 4
    covered = [[] for _ in range(VIEW_H)]       # (x0, x1, pattern, source)
    open_lines = VIEW_H
    alive = VIEW_H
    for f, (pattern, vertices) in enumerate(faces):
        if open_lines == 0:
            break
        counts.faces += 1
        n = len(vertices)
        if n >= 3:
            ys = [y for _, y in vertices]
            counts.face_rows += max(0, min(first_line(max(ys)), VIEW_H) - max(first_line(min(ys)), 0))
        for i in range(n):
            (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
            k = list(edge_crossings(x0, y0, x1, y1))
            if k:
                counts.edges += 1
                counts.edge_lines += len(k)
        for y, (a, b) in sorted(face_spans(vertices, crossings).items()):
            line = gaps[y]
            if not line:
                continue
            counts.face_lines += 1
            out, pieces, splits = [], [], 0
            for g in line:
                s, e = g
                if e <= a or s >= b:
                    out.append(g)
                    continue
                lo, hi = max(a, s), min(b, e)
                pieces.append((s, e, lo, hi))
                if s < lo:
                    out.append([s, lo])
                if hi < e:
                    out.append([hi, e])
                splits += s < lo and hi < e
            need = len(out) if not touched[y] else splits
            if capacity is not None and used[y & 3] + need > capacity:
                counts.overflow = True
                continue
            used[y & 3] += need
            touched[y] = True
            for s, e, lo, hi in pieces:
                covered[y].append((lo, hi, pattern, f))
                counts.pieces += 1
                _piece_bytes(counts, lo, hi)
                # A byte the piece shares with a neighbour already there is
                # written now; one it shares with the gap waits for the
                # gap's filling.
                if lo == s and s & 1:
                    counts.joins += 1
                if hi == e and e & 1:
                    counts.joins += 1
            alive += len(out) - len(line)
            gaps[y] = out
            counts.line_gaps_peak = max(counts.line_gaps_peak, len(out))
            if not out:
                open_lines -= 1
            counts.gaps_peak = max(counts.gaps_peak, alive)
    counts.full_lines = VIEW_H - open_lines
    lines = []
    for y in range(VIEW_H):
        left, right, split = horizon_split(bg, y)
        runs = list(covered[y])
        for s, e in gaps[y]:
            for lo, hi, pat, src in ((s, min(e, split), left, "L"),
                                     (max(s, split), e, right, "R")):
                if lo < hi:
                    runs.append((lo, hi, pat, src))
                    counts.bg_pieces += 1
                    _piece_bytes(counts, lo, hi)
                    if lo == s and s & 1:
                        counts.joins += 1
                    if hi == e and e & 1:
                        counts.joins += 1
            if s < split < e and split & 1:
                counts.joins += 1
        runs.sort()
        lines.append([(x0, x1, pat) for x0, x1, pat, _ in runs])
    return lines, counts


def reference(faces, bg):
    """The same image by brute force, every pixel of the view against every
    face's edge functions (not spans), and the background pixel by pixel
    (not by split): the model's check on spans."""
    import numpy as np

    cx = (SUB * np.arange(VIEW_W) + HALF)[None, :].astype(np.int64)
    cy = (SUB * np.arange(VIEW_H) + HALF)[:, None].astype(np.int64)
    owner = np.full((VIEW_H, VIEW_W), -1, dtype=np.int64)
    for f, (pattern, vertices) in enumerate(faces):
        n = len(vertices)
        area = sum(vertices[i][0] * vertices[(i + 1) % n][1] -
                   vertices[(i + 1) % n][0] * vertices[i][1] for i in range(n))
        if area == 0:
            continue
        sign = 1 if area > 0 else -1        # > 0: clockwise on the screen
        inside = np.ones((VIEW_H, VIEW_W), dtype=bool)
        for i in range(n):
            (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
            dx, dy = (x1 - x0) * sign, (y1 - y0) * sign
            if dx == 0 and dy == 0:
                continue
            # Clockwise on the screen, inside is where e > 0. A centre on the
            # edge counts for a left edge (going up, dy < 0) or a top edge
            # (going right, dy = 0 and dx > 0).
            e = dx * (cy - y0) - dy * (cx - x0)
            tie = dy < 0 or (dy == 0 and dx > 0)
            inside &= (e > 0) | ((e == 0) & tie)
        owner[(owner < 0) & inside] = f

    lines = []
    for py in range(VIEW_H):
        runs = []
        for px in range(VIEW_W):
            f = int(owner[py, px])
            if f >= 0:
                src = (f, faces[f][0])
            elif bg.horizon is not None and is_ground(bg.horizon, SUB * px + HALF, SUB * py + HALF):
                src = ("G", bg.ground)
            else:
                src = ("S", bg.sky)
            if runs and runs[-1][3] == src:
                runs[-1][1] = px + 1
            else:
                runs.append([px, px + 1, src[1], src])
        lines.append([(x0, x1, pat) for x0, x1, pat, _ in runs])
    return lines
