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

The tables (the sine table, the scaling diagonal, the projection centre)
are read from the snapshot, never written here (decision 6).
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zx  # noqa: E402
from skoolkit.simutils import PC, SP  # noqa: E402

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
    print(f"zx_arith: {len(angles)} matrices, {n_vert} vertices transformed, "
          f"{n_proj} projected: {failures} differ")
    return failures == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--cases", type=int, default=400)
    args = ap.parse_args()
    return 0 if check(args.snap, args.cases) else 1


if __name__ == "__main__":
    sys.exit(main())
