#!/usr/bin/env python3
"""Polar forms for a level camera, as portalc's polar branch has them
(docs/research/rtw-sources.md, section 1.2), modelled on its integer tables
and measured against exact trigonometry on Driller's views
(docs/research/projection.md, "Polar forms and logs").

    polar.py errors       vertices on the view, the 61 level entrance views
                          at their own yaw and seven more
    polar.py walk STEP    excess flips in walks, STEP world units a frame
    polar.py turn SUB     excess flips turning 5/SUB degrees a frame
    polar.py clip         Doom's clipper in logs on Driller's own edges

Needs build/data/driller.json (make data). A model for measuring, not the
engine's: camera space for the clip comes from exact trigonometry, and the
projection takes each vertex's offset from the eye back out of it.
"""
import dataclasses
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.model import camera as cam, clip, matrix, objects, parts, render, transform  # noqa: E402
from tools.model import maths as M  # noqa: E402

DB = json.loads((ROOT / "build/data/driller.json").read_text())
FX, FY, XC, YC = M.FX, M.FY, M.XC, M.YC


class Polar:
    """portalc's tables with S steps an octant (its 128; 288 makes Driller's
    5 degrees 32 steps), tb bits of the ratio minor / major, L bits of a
    log's fraction, lm bits of mantissa into the log table and E bits of
    exp's mantissa. Columns (a2c) in sixteenths, at each step's middle."""

    def __init__(self, S=128, tb=8, L=8, lm=8, E=8):
        self.S, self.tb, self.L, self.lm, self.E = S, tb, L, lm, E
        n = 1 << tb
        steps = 4 * S / math.pi                     # steps a radian
        self.atan = [math.floor(math.atan((i + 0.5) / n) * steps) for i in range(n)]
        self.lhyp = [round((1 << L) * 0.5 * math.log2(1 + ((i + 0.5) / n) ** 2)) for i in range(n)]
        self.logf = [round((1 << L) * math.log2(1 + j / (1 << lm))) for j in range(1 << lm)]
        self.expf = [round((1 << E) * (2 ** (f / (1 << L)) - 1)) for f in range(1 << L)]
        self.rad = 1 / steps

    def log2(self, x):
        """2^L log2 x, x >= 1: the lm bits under its leading one, rounded,
        index the fraction (a rounding that carries is the next octave)."""
        k = x.bit_length() - 1
        if k <= self.lm:
            j = (x << (self.lm - k)) - (1 << self.lm)
        else:
            j = ((x >> (k - self.lm - 1)) + 1) // 2 - (1 << self.lm)
        if j == 1 << self.lm:
            return (k + 1) << self.L
        return (k << self.L) + self.logf[j]

    def exp2(self, l):
        """2^(l / 2^L), to the nearest integer."""
        n, f = l >> self.L, l & ((1 << self.L) - 1)
        m = (1 << self.E) + self.expf[f]
        s = n - self.E
        return m << s if s >= 0 else (m + (1 << (-s - 1))) >> -s

    def polar(self, dx, dz):
        """(the angle in steps from +z towards +x, floored; 2^L log2 r) for
        an integer offset, not (0, 0): the ratio from the logs, atan and
        lhyp from it, the octant folded as portalc folds it."""
        ax, az = abs(dx), abs(dz)
        steep = ax > az
        maj, mnr = (ax, az) if steep else (az, ax)
        lmaj = self.log2(maj)
        r, equal = 0, False
        if mnr:
            l = self.log2(mnr) - lmaj + (self.tb << self.L)
            r = self.exp2(l) if l >= 0 else 0
            equal = r >= 1 << self.tb
        phi = self.S if equal else self.atan[r]
        lh = (1 << self.L) // 2 if equal else self.lhyp[r]
        a = self.S if equal else (2 * self.S - 1 - phi if steep else phi)
        if dx >= 0 and dz >= 0:
            ang = a
        elif dx >= 0:
            ang = 4 * self.S - 1 - a
        elif dz < 0:
            ang = 4 * self.S + a
        else:
            ang = 8 * self.S - 1 - a
        return ang % (8 * self.S), lmaj + lh

    def project(self, dx, dy, dz, yaw):
        """(sx, sy) for an offset from the eye (world units, integers) and
        the eye's yaw in steps."""
        ang, lr = self.polar(dx, dz)
        v = (ang - yaw + 4 * self.S) % (8 * self.S) - 4 * self.S
        vm = (v + 0.5) * self.rad
        sx = XC + round(FX * math.tan(vm))              # a2c
        lz = lr - round(-(1 << self.L) * math.log2(math.cos(vm)))   # lsec
        if dy == 0:
            return sx, YC
        p = self.exp2(self.log2(abs(dy)) + round((1 << self.L) * math.log2(FY)) - lz)
        return sx, YC - p if dy > 0 else YC + p


TABLES = {
    "portalc's tables": Polar(S=128, tb=8, L=8, lm=8, E=8),
    "2,304 steps, 8-bit": Polar(S=288, tb=8, L=8, lm=8, E=8),
    "2,304 steps, 10-bit": Polar(S=288, tb=10, L=10, lm=10, E=12),
    "2,304 steps, 12-bit": Polar(S=288, tb=12, L=12, lm=12, E=16),
    "4,608 steps, 12-bit": Polar(S=576, tb=12, L=12, lm=12, E=16),
}

# --- the model's views with exact trigonometry, a level camera -------------

STATE = {"yaw": 0.0, "polar": None}
_TRANSFORM, _CUBOID, _ROTATION = transform.transform, transform.cuboid, matrix.rotation


def exact_rot(v, c):
    a = math.radians(STATE["yaw"])
    dx, dy, dz = v[0] - c[0], v[1] - c[1], v[2] - c[2]
    return (round(64 * (dx * math.cos(a) - dz * math.sin(a))), 64 * dy,
            round(64 * (dx * math.sin(a) + dz * math.cos(a))))


def _transform(m, v, c):
    return exact_rot(v, c)


def _cuboid(m, lo, size, c):
    return [exact_rot(tuple(lo[k] + (size[k] if i >> k & 1 else 0) for k in range(3)), c)
            for i in range(8)]


def exact_proj(X, Y, Z):
    return XC + (2 * FX * X + Z) // (2 * Z), YC - (2 * FY * Y + Z) // (2 * Z)


def polar_proj(X, Y, Z):
    a = math.radians(STATE["yaw"])
    dx = (X * math.cos(a) + Z * math.sin(a)) / 64
    dz = (-X * math.sin(a) + Z * math.cos(a)) / 64
    p = STATE["polar"]
    rx, rz = round(dx), round(dz)
    if abs(dx - rx) > 0.02 or abs(dz - rz) > 0.02:
        # a vertex the clip made: in 64ths of a unit
        rx, rz, dy = round(64 * dx), round(64 * dz), Y
    else:
        dy = Y // 64
    return p.project(rx, dy, rz, round(STATE["yaw"] / 360 * 8 * p.S))


def byte_matrix(yaw):
    """The model's matrix at any yaw: its sines rounded to 1/64."""
    s, c = round(64 * math.sin(math.radians(yaw))), round(64 * math.cos(math.radians(yaw)))
    return ((c, 0, -s), (0, 64, 0), (s, 0, c))


def view(area, camera, yaw, proj, trig=True):
    """The view, the yaw in degrees: by exact trigonometry, or the byte
    matrix at that yaw."""
    STATE["yaw"] = yaw
    if trig:
        transform.transform, transform.cuboid, matrix.rotation = _transform, _cuboid, _ROTATION
    else:
        transform.transform, transform.cuboid = _TRANSFORM, _CUBOID
        matrix.rotation = lambda c, tables: byte_matrix(yaw)
    parts.project = proj
    try:
        return render.render(DB, area, camera)
    finally:
        transform.transform, transform.cuboid, matrix.rotation = _TRANSFORM, _CUBOID, _ROTATION


def level_views():
    return [(a, e, c) for a, e, c in cam.entrance_views(DB) if c.pitch == 0 and c.roll == 0]


def errors():
    seen = []

    def rec(X, Y, Z):
        seen.append((X, Y, Z))
        return exact_proj(X, Y, Z)

    rows = {k: [0, 0.0, 0] for k in TABLES}
    for a, e, c in level_views():
        for dyaw in (0, 1.25, 2.5, 3.75, 10, 20, 33.75, 45):
            seen.clear()
            view(a, c, 5 * c.yaw + dyaw, rec)
            for X, Y, Z in seen:
                ex, ey = XC + FX * X / Z, YC - FY * Y / Z
                if not (0 <= ex <= 16 * 104 and 0 <= ey <= 16 * 104):
                    continue
                for k, p in TABLES.items():
                    STATE["polar"] = p
                    sx, sy = polar_proj(X, Y, Z)
                    err = max(abs(sx - ex), abs(sy - ey))
                    r = rows[k]
                    r[0], r[1], r[2] = max(r[0], err), r[1] + err, r[2] + 1
    for k, (w, s, n) in rows.items():
        print(f"{k:24} on the view: worst {w:6.2f}, mean {s / n:5.2f} sixteenths ({n} vertices)")


def flips(imgs):
    out = [0] * (2 * len(imgs[0]))
    for a, b in zip(imgs, imgs[1:]):
        for i, (x, y) in enumerate(zip(a, b)):
            d = x ^ y
            if d:
                out[2 * i] += bool(d & 0xAA)
                out[2 * i + 1] += bool(d & 0x55)
    return out


def differ(a, b):
    return sum(bool((x ^ y) & 0xAA) + bool((x ^ y) & 0x55) for x, y in zip(a, b))


def flicker(sequences, label):
    """sequences: (area, [(camera, yaw in degrees)]): each method's excess
    flips against exact trigonometry with exact division."""
    methods = [(k, True, p) for k, p in TABLES.items()]
    methods += [("byte matrix, exact division", False, exact_proj),
                ("byte matrix, the model's projection", False, M.project)]
    tot = {k: [0, 0] for k, _, _ in methods}
    own = nframes = 0
    for area, frames in sequences:
        ref = [view(area, c, yaw, exact_proj).bytes for c, yaw in frames]
        fr = flips(ref)
        own += sum(fr)
        nframes += len(frames)
        for k, polar, p in methods:
            imgs = []
            for c, yaw in frames:
                if polar:
                    STATE["polar"] = p
                    imgs.append(view(area, c, yaw, polar_proj).bytes)
                else:
                    imgs.append(view(area, c, yaw, p, trig=False).bytes)
            tot[k][0] += sum(max(0, a - b) for a, b in zip(flips(imgs), fr))
            tot[k][1] += sum(differ(a, b) for a, b in zip(imgs, ref))
    print(f"{label}: {nframes} frames; exact trigonometry's own flips {own / nframes:.2f} a frame")
    for k, (ex, d) in tot.items():
        print(f"  {k:36} excess flips {ex / nframes:6.3f} a frame, pixels unlike exact's {d / nframes:6.2f}")


def walks(step, frames=40):
    seqs = []
    for a, e, c0 in level_views():
        yaw = 5 * c0.yaw
        r = math.radians(yaw)
        for d in ((math.sin(r), 0, math.cos(r)), (math.cos(r), 0, -math.sin(r)), (0, 1, 0)):
            fr = []
            for t in range(frames):
                q = [round(c0.position[k] + d[k] * step * t) for k in range(3)]
                if all(0 <= v < 65536 for v in q):
                    fr.append((dataclasses.replace(c0, x=q[0], y=q[1], z=q[2]), yaw))
            seqs.append((a, fr))
    flicker(seqs, f"walks, {step} world units a frame")


def turns(sub, frames=40):
    seqs = []
    for a, e, c0 in level_views():
        for sgn in (1, -1):
            fr = []
            for t in range(frames):
                yaw = 5 * c0.yaw + sgn * 5 * t / sub
                fr.append((dataclasses.replace(c0, yaw=round(yaw / 5) % 72), yaw))
            seqs.append((a, fr))
    flicker(seqs, f"turns, 5/{sub} degrees a frame")


def crossings(area, c0, yaw):
    """(A, B) offsets from the eye (world units) of each edge of a face the
    camera sees that crosses a side of the view, A the end inside."""
    STATE["yaw"] = yaw
    c = c0.position
    objs = render.recolour(area, area["objects"] + DB["globals"])
    out = []
    for cand in objects.object_pass(objs, matrix.rotation(c0, DB["tables"]), c, None, True, {}):
        s = cand.shape
        for f in cand.faces:
            if len(f.loop) < 3:
                continue
            rel = [tuple(s.vertices[i][k] - c[k] for k in range(3)) for i in f.loop]
            cs = [exact_rot(s.vertices[i], c) for i in f.loop]
            if any(v[2] < clip.ZNEAR for v in cs):
                continue
            for i in range(len(cs)):
                j = (i + 1) % len(cs)
                ina = abs(FX * cs[i][0]) <= XC * cs[i][2]
                inb = abs(FX * cs[j][0]) <= XC * cs[j][2]
                if ina != inb:
                    out.append((rel[i], rel[j]) if ina else (rel[j], rel[i]))
    return out


def clipped():
    """Doom's clipper in logs (portalc's howitworks.md, "Ends off the
    view"): log depth = log r + log|sin(a - w)| - log|sin(b - w)| +
    log cos(b - yaw), at the steps' middles as portalc takes them."""
    half = math.atan(XC / FX)
    for name, p in TABLES.items():
        T, L = 8 * p.S, 1 << p.L
        rad = 2 * math.pi / T
        edge, own = [], []
        for area, e, c0 in level_views():
            for dyaw in (0, 2.5, 10, 20, 33.75):
                yaw = 5 * c0.yaw + dyaw
                yaw_st = round(yaw / 360 * T)
                phi = yaw_st * rad
                for A, B in crossings(area, c0, yaw):
                    ex, ez = B[0] - A[0], B[2] - A[2]
                    if ex == 0 and ez == 0:
                        continue
                    side = 1 if B[0] * math.cos(phi) - B[2] * math.sin(phi) > 0 else -1
                    b_st = yaw_st + side * math.ceil(half / rad)
                    b = b_st * rad
                    den = ex * math.cos(b) - ez * math.sin(b)
                    if abs(den) < 1e-9:
                        continue
                    s = -(A[0] * math.cos(b) - A[2] * math.sin(b)) / den
                    if not 0 <= s <= 1:
                        continue
                    depth = (A[0] + s * ex) * math.sin(phi) + (A[2] + s * ez) * math.cos(phi)
                    if depth <= 4:
                        continue
                    a_st, lr = p.polar(A[0], A[2])
                    w_st, _ = p.polar(ex, ez)

                    def lsin(st):
                        return -L * math.log2(max(1e-12, abs(math.sin(st * rad))))
                    aw = a_st - w_st
                    lz = (lr - round((lsin(aw - 0.5) + lsin(aw + 0.5)) / 2)
                          + round(lsin(b_st - w_st - 0.5)) - round(-L * math.log2(math.cos(b - phi))))
                    rel = abs(2 ** (lz / L) / depth - 1)
                    edge.append(rel * YC)
                    cy = A[1] + s * (B[1] - A[1])
                    ry = FY * cy / depth
                    if abs(ry) <= YC:
                        own.append(abs(FY * cy / 2 ** (lz / L) - ry))
        edge.sort()
        own.sort()

        def q(v, f):
            return v[min(len(v) - 1, int(f * len(v)))]
        print(f"{name:24} {len(edge)} crossings; the crossing's own row ({len(own)} on the view): "
              f"median {q(own, .5):.2f}, p99 {q(own, .99):.2f}, worst {own[-1]:.2f}; "
              f"a row at the view's edge: worst {edge[-1]:.2f} sixteenths")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "errors":
        errors()
    elif what == "walk":
        walks(float(sys.argv[2]))
    elif what == "turn":
        turns(int(sys.argv[2]))
    elif what == "clip":
        clipped()
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
