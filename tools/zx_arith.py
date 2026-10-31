#!/usr/bin/env python3
"""Driller's camera arithmetic, transcribed, and checked against the original.

    .venv/bin/python -I tools/zx_arith.py [--snap build/zx/driller.z80] [--cases N]

The transcription (docs/research/zx-driller.md, "The matrix", "The
transform", "The projection") is what the model can take as the ZX's
behaviour. The check calls the original's own routines in the snapshot
(tools/zx.py) with random inputs and compares every result exactly:

    the matrix       $6EE4 (via $7896)  against matrix()
    the transform    $6E25 then $7915   against transform()
    the projection   $7C9D (via $910E, $91F1) against project()
    the fill         $83FC then $80C0   against fill() (scan())

The tables (the sine table, the scaling diagonal, the projection centre,
the patterns) are read from the snapshot, never written here (decision 6).
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zx  # noqa: E402
from skoolkit.simutils import PC, SP, IXh, IXl  # noqa: E402

SENT = 0x0008  # a sentinel return address no routine here reaches

# The original's addresses (docs/research/zx-driller.md).
SINCOS = 0x8E78      # 72 (sin, cos) pairs of signed bytes, 1.0 = 64
SCALE = 0x88D2       # the scaling diagonal: x, y, z
CENTRE = 0x88D9      # the projection's centre: x, y
PITCH, YAW, ROLL = 0x876C, 0x876D, 0x876E
MATRIX = 0x5E55      # nine signed bytes, row-major
BUILD_MATRIX = 0x6EE4
COMPILE_MULTIPLIES = 0x6E25
NVERTS = 0x8A7F
VERTS_IN = 0x5E63    # relative to the camera: x, y, z words, 6 bytes a vertex
VERTS_OUT = 0x5E9F   # in camera space, likewise
TRANSFORM = 0x7915
PROJECT = 0x7C9D
PROJECTED = 0x8A6B   # x, y bytes a vertex
SCAN = 0x83FC        # a polygon's edges into the edge table (IX: its points)
FILL_SPANS = 0x80C0  # the edge table's rows into the buffer
EDGE_TABLE = 0x8A9F  # the address of the edge table: 3 bytes a row, 105 rows
COLOUR = 0x8917      # the face's colour, 1-15
PATTERNS = 0x891D    # the address of the 15 patterns, 4 bytes each
BUFFER = 0x5CBC
FACE_SCRATCH = 0x6766  # the draw list's space, free outside a redraw


def sb(v):
    return v - 256 if v & 0x80 else v


def s16(v):
    v &= 0xFFFF
    return v - 65536 if v & 0x8000 else v


class Tables:
    """The original's constants, read from a snapshot's memory."""

    def __init__(self, mem):
        self.sin = [sb(mem[SINCOS + 2 * a]) for a in range(72)]
        self.cos = [sb(mem[SINCOS + 2 * a + 1]) for a in range(72)]
        self.scale = [sb(mem[SCALE + i]) for i in range(3)]
        self.xc, self.yc = mem[CENTRE], mem[CENTRE + 1]


def _mul(t, m):
    """t . m, each sum rounded (v + 32) >> 6 to a signed byte ($7896)."""
    return [[sb(((sum(t[i][k] * m[k][j] for k in range(3)) + 32) >> 6) & 0xFF)
             for j in range(3)] for i in range(3)]


def matrix(tab, pitch, yaw, roll):
    """$6EE4: M = S . Rroll . Rpitch . Ryaw, from the identity (1.0 = 64),
    a rotation skipped when its angle is 0. Rows are camera x, y, z."""
    m = [[64, 0, 0], [0, 64, 0], [0, 0, 64]]
    if yaw:
        s, c = tab.sin[yaw], tab.cos[yaw]
        m = _mul([[c, 0, -s], [0, 64, 0], [s, 0, c]], m)
    if pitch:
        s, c = tab.sin[pitch], tab.cos[pitch]
        m = _mul([[64, 0, 0], [0, c, s], [0, -s, c]], m)
    if roll:
        s, c = tab.sin[roll], tab.cos[roll]
        m = _mul([[c, s, 0], [-s, c, 0], [0, 0, 64]], m)
    sx, sy, sz = tab.scale
    return _mul([[sx, 0, 0], [0, sy, 0], [0, 0, sz]], m)


def _product(m, d):
    """One compiled multiply ($6E25's code, finished at $795E): the
    magnitude |m|.|d| >> 6, then the sign."""
    q = (abs(m) * abs(d)) >> 6
    return q if (m >= 0) == (d >= 0) else -q


def transform(m, d):
    """$7915: camera space from a vertex relative to the camera (d, in
    world units, 16-bit signed). Each row's sum wraps at 16 bits."""
    return [s16(sum(_product(m[i][j], d[j]) for j in range(3))) for i in range(3)]


def _proj1(c, v, z):
    """One coordinate of $7C9D: c + trunc(c.v / z), clamped to 0 or 2c
    outside the frustum's side planes."""
    if v < 0:
        if v + z - 1 < 0:
            return 0
    elif v - z >= 0:
        return 2 * c
    q = abs(c * v) // z
    return (c + (q if v >= 0 else -q)) & 0xFF


def project(tab, x, y, z):
    """$7C9D: screen (x, y) from camera space, y upwards from the view's
    bottom edge; z = 0 gives the centre. z is never negative here: the
    clip (frustum planes $7C37, clip $799E) runs first."""
    if z == 0:
        return tab.xc, tab.yc
    return _proj1(tab.xc, x, z), _proj1(tab.yc, y, z)


def scan(points):
    """$83FC: the edge table for a polygon of screen points (x, y), y up:
    {y: (flag, x1, x2)}, flag 1 for one x, 2 for two.

    Each edge, in order and closing back to the first point, is walked
    from its lower end for the rows [y_low, y_high), one x a row: a
    vertical edge's x; otherwise Bresenham with the error starting at
    half the major delta, the steep case writing then stepping x at most
    once a row, the shallow case writing the row's first x then stepping
    x until the error carries into the next row. A row keeps the first
    two distinct x values written to it. A horizontal edge counts only on
    the polygon's top or bottom row, and overwrites that row with both
    its ends."""
    n = len(points)
    ys = [p[1] for p in points]
    ytop, ybottom = max(ys), min(ys)
    table = {}

    def write(y, x):
        e = table.get(y)
        if e is None:
            table[y] = (1, x, 0)
        elif e[0] == 1 and e[1] != x:
            table[y] = (2, e[1], x)

    for i in range(n):
        (x0, y0), (x1, y1) = points[i], points[(i + 1) % n]
        if y0 == y1:
            if (y0 == ytop or y0 == ybottom) and x0 != x1:
                table[y0] = (2, x0, x1)
            continue
        if x0 == x1:
            for y in range(min(y0, y1), max(y0, y1)):
                write(y, x0)
            continue
        step = 1 if x1 > x0 else -1
        adx, ady = abs(x1 - x0), abs(y1 - y0)
        if y1 < y0:  # walk from the lower end
            step, x, y = -step, x1, y1
        else:
            x, y = x0, y0
        if ady >= adx:
            err = ady >> 1
            for _ in range(ady):
                write(y, x)
                err += adx
                if err >= ady:
                    err -= ady
                    x += step
                y += 1
        else:
            err = adx >> 1
            for _ in range(ady):
                write(y, x)
                while True:
                    x += step
                    err += ady
                    if err >= adx:
                        err -= adx
                        break
                y += 1
    return table, ytop, ybottom


def fill(points, pattern, buf):
    """$83FC then $80C0: a polygon into a view buffer (bytearray, 26 bytes
    a row, 105 rows), in pattern (four bytes, by y AND 3). Screen x
    covers pixel column x - 1 (x = 0 is off the view's left); screen y
    is buffer row 104 - y. A row's span is x1..x2 inclusive (one pixel
    for a flag-1 row), written opaquely: the pattern's ink and paper."""
    table, ytop, ybottom = scan(points)
    for y in range(ytop, ybottom - 1, -1):
        e = table.get(y)
        if e is None:
            continue
        flag, a, b = e
        lo, hi = (a, a) if flag == 1 else (min(a, b), max(a, b))
        row = 104 - y
        byte = pattern[y & 3]
        for x in range(max(lo, 1), hi + 1):
            px = x - 1
            mask = 0x80 >> (px & 7)
            i = row * 26 + (px >> 3)
            buf[i] = (buf[i] & ~mask & 0xFF) | (byte & mask)


class Original:
    """The original's routines, called in the snapshot with a sentinel
    return address."""

    def __init__(self, snap):
        self.spec = zx.Spectrum(snap)
        self.mem = self.spec.mem
        self.sp = self.spec.regs[SP]

    def call(self, addr):
        m, r = self.mem, self.spec.regs
        sp = self.sp - 2
        m[sp], m[sp + 1] = SENT & 0xFF, SENT >> 8
        r[SP], r[PC] = sp, addr
        assert self.spec.run_tstates(10 ** 8, stop=SENT) == SENT, f"${addr:04X} didn't return"

    def poke16(self, addr, v):
        self.mem[addr], self.mem[addr + 1] = v & 0xFF, (v >> 8) & 0xFF

    def peek16(self, addr):
        return s16(self.mem[addr] | self.mem[addr + 1] << 8)

    def matrix(self, pitch, yaw, roll):
        self.mem[PITCH], self.mem[YAW], self.mem[ROLL] = pitch, yaw, roll
        self.call(BUILD_MATRIX)
        flat = [sb(self.mem[MATRIX + i]) for i in range(9)]
        return [flat[0:3], flat[3:6], flat[6:9]]

    def transform(self, ds):
        """ds: vertices relative to the camera, after matrix()."""
        self.call(COMPILE_MULTIPLIES)
        self.mem[NVERTS] = len(ds)
        for v, d in enumerate(ds):
            for j in range(3):
                self.poke16(VERTS_IN + 6 * v + 2 * j, d[j])
        self.call(TRANSFORM)
        return [[self.peek16(VERTS_OUT + 6 * v + 2 * i) for i in range(3)] for v in range(len(ds))]

    def project(self, vs):
        self.mem[NVERTS] = len(vs)
        for v, p in enumerate(vs):
            for j in range(3):
                self.poke16(VERTS_OUT + 6 * v + 2 * j, p[j])
        self.call(PROJECT)
        return [(self.mem[PROJECTED + 2 * v], self.mem[PROJECTED + 2 * v + 1]) for v in range(len(vs))]

    def fill(self, points, colour, buf):
        """The polygon through the original's $83FC and $80C0 into a
        buffer (its contents first), returned."""
        m = self.mem
        m[BUFFER:BUFFER + len(buf)] = buf
        edges = self.peek16(EDGE_TABLE) & 0xFFFF
        m[edges:edges + 3 * 105] = bytes(3 * 105)
        for i, (x, y) in enumerate(points):
            m[FACE_SCRATCH + 2 * i], m[FACE_SCRATCH + 2 * i + 1] = x, y
        m[NVERTS] = len(points)
        m[COLOUR] = colour
        r = self.spec.regs
        r[IXh], r[IXl] = FACE_SCRATCH >> 8, FACE_SCRATCH & 0xFF
        self.call(SCAN)
        self.call(FILL_SPANS)
        return bytearray(m[BUFFER:BUFFER + len(buf)])


def check(snap, cases, seed=1):
    rng = random.Random(seed)
    orig = Original(snap)
    tab = Tables(orig.mem)
    failures = 0

    def differ(what, args, got, want):
        nonlocal failures
        failures += 1
        if failures <= 10:
            print(f"{what}{args}: original {got}, transcription {want}")

    angles = [(0, y, 0) for y in range(72)] + [(p, y, 0) for p in range(72) for y in range(0, 72, 7)]
    angles += [(rng.randrange(72), rng.randrange(72), rng.randrange(72)) for _ in range(cases)]
    for a in angles:
        got, want = orig.matrix(*a), matrix(tab, *a)
        if got != want:
            differ("matrix", a, got, want)
    n_vert = 0
    for _ in range(cases):
        a = (rng.randrange(72), rng.randrange(72), rng.randrange(72))
        m = orig.matrix(*a)
        ds = [[rng.randint(-9000, 9000) for _ in range(3)] for _ in range(8)]
        for d, got in zip(ds, orig.transform(ds)):
            n_vert += 1
            want = transform(m, d)
            if got != want:
                differ("transform", (a, d), got, want)
    n_proj = 0
    for _ in range(cases):
        vs = []
        for _ in range(8):
            # Inputs within 16 bits, some beyond the side planes.
            z = rng.choice([0, rng.randint(1, 50), rng.randint(1, 26000)])
            span = max(z, 1) * 5 // 4
            vs.append([rng.randint(-span, span), rng.randint(-span, span), z])
        for v, got in zip(vs, orig.project(vs)):
            n_proj += 1
            want = project(tab, *v)
            if got != want:
                differ("project", tuple(v), got, want)
    patterns = orig.peek16(PATTERNS) & 0xFFFF
    n_fill = 0
    for _ in range(cases):
        points = _convex(rng)
        if rng.random() < 0.5:
            points.reverse()
        colour = rng.randint(1, 15)
        pattern = [orig.mem[patterns + 4 * (colour - 1) + i] for i in range(4)]
        before = bytearray(rng.randrange(256) for _ in range(26 * 105))
        got = orig.fill(points, colour, before)
        want = bytearray(before)
        fill(points, pattern, want)
        n_fill += 1
        if got != want:
            differ("fill", (points, colour), f"{sum(a != b for a, b in zip(got, want))} bytes off", "")
    print(f"zx_arith: {len(angles)} matrices, {n_vert} vertices transformed, "
          f"{n_proj} projected, {n_fill} polygons filled: {failures} differ")
    return failures == 0


def _convex(rng):
    """A random convex polygon of 1-6 screen points, in order, sometimes
    on the view's edges."""
    def coord(top):
        return rng.choice([0, top, rng.randint(0, top), rng.randint(0, top), rng.randint(0, top)])
    pts = sorted({(coord(208), coord(104)) for _ in range(rng.randint(1, 8))})
    if len(pts) < 3:
        return pts

    def half(ps):
        out = []
        for p in ps:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    hull = half(pts)[:-1] + half(pts[::-1])[:-1]
    return hull[:6]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--cases", type=int, default=400)
    args = ap.parse_args()
    return 0 if check(args.snap, args.cases) else 1


if __name__ == "__main__":
    sys.exit(main())
