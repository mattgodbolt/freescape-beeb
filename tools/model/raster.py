"""The rasteriser: faces, nearest first, into each line's runs.

docs/engine.md, stages 8 and 9, and section 9's interface. This is the
specification the 6502's src/raster.6502 matches byte for byte (through
writer.py's bytes; tools/rastercheck.mjs compares them).

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

The output is, for each line 0 .. VIEW_H - 1, its runs (x0, x1, pattern)
in pixels, in order, covering [0, VIEW_W) exactly. A run is the pixels of
one source (a face, or the sky or ground) that touch, so two faces of the
same pattern side by side are two runs, as the 6502 writes them.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _defs(path=ROOT / "src" / "defs.6502"):
    """The plain constants of src/defs.6502 (NAME = expression), evaluated, so
    the view's size and place are written down once, there."""
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


def edge_crossings(x0, y0, x1, y1):
    """The lines an edge crosses and its pixel boundary on each: (line, p) for
    each line whose centre is in [top, bottom) of the edge. A horizontal edge
    crosses none."""
    if y0 == y1:
        return
    if y0 > y1:
        x0, y0, x1, y1 = x1, y1, x0, y0
    dx, dy = x1 - x0, y1 - y0
    for k in range(max(first_line(y0), 0), min(first_line(y1), VIEW_H)):
        c = SUB * k + HALF
        yield k, pixel_of(x0 * dy + dx * (c - y0), dy)


def face_spans(vertices):
    """A convex polygon's span on each line it covers: {line: (x0, x1)}, x1
    exclusive, only lines where x0 < x1. Either winding; a degenerate
    polygon (no area) covers nothing."""
    cross = {}
    n = len(vertices)
    for i in range(n):
        (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
        for k, p in edge_crossings(x0, y0, x1, y1):
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


def horizon_split(bg, line):
    """The background on a line: (left, right, split), meaning pixels below
    split take left and the rest take right, split in [0, VIEW_W].

    A pixel is sky when its centre is strictly to the sky's side of the
    horizon and ground when strictly on the ground's. A centre exactly on it
    goes by the fill rule, to the side the horizon is a top or left edge of:
    the side to its right, or below it when it's level. So for a horizon
    that isn't level it's the same boundary as an edge's, p = ceil((x - 8) /
    16) of where the horizon crosses the line's centre: right of it is sky
    when the horizon points down the screen and ground when it points up."""
    h = bg.horizon
    if h is None:
        return bg.sky, bg.ground, VIEW_W
    c = SUB * line + HALF
    if h.dy == 0:
        # The whole line is on one side: the sign of the cross product,
        # dx (c - hy), and on the line itself the ground when dx > 0 (it is
        # the ground's top edge) and the sky when dx < 0 (the sky's).
        s = h.dx * (c - h.y)
        sky = s < 0 or (s == 0 and h.dx < 0)
        return bg.sky, bg.ground, VIEW_W if sky else 0
    # x where the horizon crosses the centre line: hx + dx (c - hy) / dy.
    num, den = h.x * h.dy + h.dx * (c - h.y), h.dy
    if den < 0:
        num, den = -num, -den
    split = min(max(pixel_of(num, den), 0), VIEW_W)
    if h.dy > 0:
        return bg.ground, bg.sky, split
    return bg.sky, bg.ground, split


@dataclass
class Counts:
    """What the rasteriser did, for the cost model (docs/research/raster.md):
    the 6502 does the same work, so these predict its cycles."""
    faces: int = 0          # faces looked at (before every line was full)
    edges: int = 0          # edges set up: non-horizontal, crossing a line
    edge_lines: int = 0     # (edge, line) steps
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


def rasterise(faces, bg, capacity=None):
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
    that line, and counts.overflow says so."""
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
        for i in range(n):
            (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
            k = list(edge_crossings(x0, y0, x1, y1))
            if k:
                counts.edges += 1
                counts.edge_lines += len(k)
        for y, (a, b) in sorted(face_spans(vertices).items()):
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
    face's edge functions (not spans): the model's check on rasterise."""
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
        left, right, split = horizon_split(bg, py)
        runs = []
        for px in range(VIEW_W):
            f = int(owner[py, px])
            src = (f, faces[f][0]) if f >= 0 else \
                (("L", left) if px < split else ("R", right))
            if runs and runs[-1][3] == src:
                runs[-1][1] = px + 1
            else:
                runs.append([px, px + 1, src[1], src])
        lines.append([(x0, x1, pat) for x0, x1, pat, _ in runs])
    return lines
