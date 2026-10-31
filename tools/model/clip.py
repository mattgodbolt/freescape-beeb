"""Clipping (docs/engine.md, section 4, stages 4 and 6).

The near plane in 3D, in camera space (24-bit integers, 64 to the world
unit), before projection; the view's rectangle in 2D, in view coordinates
(sixteenths of a pixel), after it. Both are Sutherland-Hodgman over a convex
polygon, and every new vertex is rounded to the nearest integer, half up, so
the results are integers like their inputs. There is no far plane.

The frustum's side planes are tested exactly, before projection, only to
throw away faces wholly outside one of them: a face so rejected would have
clipped to nothing.

A guard band keeps the projection in range. A vertex far to the side of
a near one (|X| beyond about 25 Z) projects past what 16 bits hold, and a
saturated vertex would bend the 2D clip's edges. So a face with a vertex
outside |X| <= GUARD_X Z or |Y| <= GUARD_Y Z is first clipped against
those planes in 3D, like the near plane. They lie well outside the view,
so this is rare, and as powers of two they're shifts on the 6502.
"""
from tools.model.view import FX, FY, SUB, VIEW_H, VIEW_W, XC, YC, ZNEAR

NEAR, LEFT, RIGHT, TOP, BOTTOM = 1, 2, 4, 8, 16
GUARD_X = 16                # |X| <= 16 Z: sx inside XC +- 16 FX
GUARD_Y = 8                 # |Y| <= 8 Z: sy inside YC +- 8 FY
assert XC + GUARD_X * FX < 1 << 15 and YC + GUARD_Y * FY < 1 << 15
WIDTH = SUB * VIEW_W
HEIGHT = SUB * VIEW_H


def round_div(n, d):
    """n / d to the nearest integer, half up, for any signs."""
    if d < 0:
        n, d = -n, -d
    return (2 * n + d) // (2 * d)


def outcode(v):
    """Which planes a camera-space vertex is outside. The side planes are
    where the exact projection meets the view's edges, so they're only
    tested in front of the near plane."""
    x, y, z = v
    if z < ZNEAR:
        return NEAR
    code = 0
    if XC * z + FX * x < 0:
        code |= LEFT
    if FX * x > (WIDTH - XC) * z:
        code |= RIGHT
    if FY * y > YC * z:
        code |= TOP
    if -FY * y > (HEIGHT - YC) * z:
        code |= BOTTOM
    return code


def near_clip(poly, znear=ZNEAR):
    """A camera-space polygon (a list of (x, y, z)) clipped to z >= znear.
    A two-vertex polygon is a line, clipped as a segment."""
    if len(poly) == 2:
        a, b = poly
        if a[2] < znear and b[2] < znear:
            return []
        if a[2] >= znear and b[2] >= znear:
            return list(poly)
        cut = _near_point(a, b, znear)
        return [cut, b] if a[2] < znear else [a, cut]
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        a_in, b_in = a[2] >= znear, b[2] >= znear
        if a_in:
            out.append(a)
        if a_in != b_in:
            out.append(_near_point(a, b, znear))
    return out


def _near_point(a, b, znear):
    dz = b[2] - a[2]
    t = znear - a[2]
    return (a[0] + round_div((b[0] - a[0]) * t, dz),
            a[1] + round_div((b[1] - a[1]) * t, dz),
            znear)


def outside_guard(v):
    """Whether a camera-space vertex (in front of the near plane) is outside
    the guard band."""
    x, y, z = v
    return abs(x) > GUARD_X * z or abs(y) > GUARD_Y * z


def guard_clip(poly):
    """A camera-space polygon (z >= ZNEAR throughout) clipped to the guard
    band's four planes in 3D. A two-vertex polygon is a line, clipped as a
    segment. New vertices are rounded to the nearest integer, half up."""
    for axis, g in ((0, GUARD_X), (1, GUARD_Y)):
        for sign in (1, -1):
            if not poly:
                return []
            # inside: sign * v[axis] <= g * z; f(v) = g z - sign v[axis] >= 0
            f = [g * v[2] - sign * v[axis] for v in poly]
            if len(poly) == 2:
                (a, b), (fa, fb) = poly, f
                if fa < 0 and fb < 0:
                    return []
                if fa < 0 or fb < 0:
                    cut = _plane_point(a, b, fa, fb)
                    poly = [cut, b] if fa < 0 else [a, cut]
                continue
            out = []
            n = len(poly)
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                fa, fb = f[i], f[(i + 1) % n]
                if fa >= 0:
                    out.append(a)
                if (fa >= 0) != (fb >= 0):
                    out.append(_plane_point(a, b, fa, fb))
            poly = out
    return poly


def _plane_point(a, b, fa, fb):
    """Where segment a-b crosses the plane on which f is zero (f(a) = fa,
    f(b) = fb, of opposite signs)."""
    d = fa - fb
    return tuple(a[k] + round_div((b[k] - a[k]) * fa, d) for k in range(3))


def _clip_edge(poly, axis, bound, keep_below):
    """One side of the rectangle: keep coordinate[axis] <= bound if
    keep_below, else >= bound."""
    def inside(p):
        return p[axis] <= bound if keep_below else p[axis] >= bound

    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        a_in, b_in = inside(a), inside(b)
        if a_in:
            out.append(a)
        if a_in != b_in:
            other = 1 - axis
            cut = [0, 0]
            cut[axis] = bound
            cut[other] = a[other] + round_div((b[other] - a[other]) * (bound - a[axis]),
                                              b[axis] - a[axis])
            out.append(tuple(cut))
    return out


def clip2d(poly, width=WIDTH, height=HEIGHT):
    """A polygon in view coordinates clipped to [0, width] x [0, height].
    Consecutive repeats are dropped; fewer than three vertices left means
    nothing is drawn."""
    for axis, bound, below in ((0, 0, False), (0, width, True), (1, 0, False), (1, height, True)):
        if not poly:
            return []
        poly = _clip_edge(poly, axis, bound, below)
    return dedupe(poly)


def dedupe(poly):
    out = []
    for p in poly:
        if not out or out[-1] != p:
            out.append(p)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def point_square(a):
    """A point in view coordinates as the polygon covering the one pixel
    whose centre is nearest it under the fill rule."""
    x, y = a
    h = SUB // 2
    return [(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]


def line_quad(a, b):
    """A line between two points in view coordinates as the polygon a
    one-pixel line covers under the fill rule: the segment widened by half a
    pixel each way across its major axis."""
    (ax, ay), (bx, by) = a, b
    h = SUB // 2
    if abs(bx - ax) >= abs(by - ay):
        return [(ax, ay - h), (bx, by - h), (bx, by + h), (ax, ay + h)]
    return [(ax - h, ay), (bx - h, by), (bx + h, by), (ax + h, ay)]
