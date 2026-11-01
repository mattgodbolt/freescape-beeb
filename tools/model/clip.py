"""Clipping (docs/engine.md, section 4, stages 4 and 6).

The near plane in 3D, in camera space (24-bit integers, 64 to the world
unit), before projection; the view's rectangle in 2D, in view coordinates
(sixteenths of a pixel), after it. Both are Sutherland-Hodgman over a convex
polygon, and every new vertex is an integer like its inputs. There is no
far plane.

A guard band keeps the projection in range. A vertex far to the side of
a near one (|X| beyond about 25 Z) projects past what 16 bits hold, and a
saturated vertex would bend the 2D clip's edges. So a face with a vertex
outside |X| <= GUARD_X Z or |Y| <= GUARD_Y Z is first clipped against
those planes in 3D, like the near plane. They lie well outside the view,
so this is rare, and as powers of two they're shifts on the 6502.

Which faces lie wholly outside the view, and which need the 2D clip, is
decided from the projected vertices against the view's rectangle
(outcode2d): compares on the 6502, where the exact 3D plane tests took
products (docs/research/objects.md, "Decisions proposed").

New vertices: the near clip's are exact, the model's round_div on each
coordinate, since they're a few units from the eye where an error shows
most. The guard band's and the 2D clip's are crossings (the same): one
fraction a crossing, t = floor(2^16 f_P / (f_P - f_Q)) from the edge's
inside end P to its outside end Q (f the plane's signed distance, at
least 0 inside), and each coordinate P + (Q - P) t / 2^16 rounded half
up. One division a crossing instead of one a coordinate, and taken from
the inside end, so the two faces that share an edge cut it at the same
point.
"""
from tools.model.view import FX, FY, SUB, VIEW_H, VIEW_W, XC, YC, ZNEAR

NEAR, LEFT, RIGHT, TOP, BOTTOM = 1, 2, 4, 8, 16
assert FY == 2 * FX                 # (the cone's lines)
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


T_BITS = 16                 # a crossing's fraction


def crossing_t(fp, fq):
    """A crossing's fraction from its inside end (fp >= 0) to its outside
    end (fq < 0): floor(2^T_BITS fp / (fp - fq)), with fp and fp - fq first
    shifted right until fp - fq fits T_BITS bits (so the 6502 divides 16
    bits by 16, and t keeps T_BITS - 1 bits at least), and below
    2^T_BITS."""
    assert fp >= 0 > fq
    d = fp - fq
    s = max(0, d.bit_length() - T_BITS)
    return min(((fp >> s) << T_BITS) // (d >> s), (1 << T_BITS) - 1)


def lerp(p, q, t):
    """p + (q - p) t / 2^T_BITS, rounded half up."""
    return p + (((q - p) * t + (1 << (T_BITS - 1))) >> T_BITS)


def crossing(p, q, fp, fq):
    """The point where segment p-q crosses a plane, p inside (fp >= 0) and q
    outside (fq < 0): every coordinate by lerp from p."""
    t = crossing_t(fp, fq)
    return tuple(lerp(p[k], q[k], t) for k in range(len(p)))


def outcode2d(p, width=None, height=None):
    """Which of the view's edges a projected vertex is beyond: LEFT if x <
    0, RIGHT if x > width, TOP if y < 0, BOTTOM if y > height (the 2D
    clip's inside is the closed rectangle)."""
    width = WIDTH if width is None else width
    height = HEIGHT if height is None else height
    x, y = p
    code = 0
    if x < 0:
        code |= LEFT
    elif x > width:
        code |= RIGHT
    if y < 0:
        code |= TOP
    elif y > height:
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


def beyond(v):
    """Which of the planes x = -z, x = z, 2y = z and 2y = -z a camera-space
    vertex (in front of the near plane) is beyond: LEFT, RIGHT, TOP,
    BOTTOM. They lie outside the view's sides (its edges are at |x| = 0.66 z
    and |y| = 0.33 z), so a face with every vertex beyond one of them can't
    be seen: it's dropped before the guard band and the projection, by
    compares."""
    x, y, z = v
    code = 0
    if x < -z:
        code |= LEFT
    elif x > z:
        code |= RIGHT
    if 2 * y > z:
        code |= TOP
    elif 2 * y < -z:
        code |= BOTTOM
    return code


assert XC < FX and YC < FY // 2     # (beyond's planes are outside the view's)


def outside_guard(v):
    """Whether a camera-space vertex (in front of the near plane) is outside
    the guard band."""
    x, y, z = v
    return abs(x) > GUARD_X * z or abs(y) > GUARD_Y * z


def _clip_plane(poly, f):
    """Sutherland-Hodgman against one plane, f(v) its signed distance (at
    least 0 inside), new vertices by crossing() from the inside end. A
    two-vertex polygon is a line, clipped as a segment."""
    fs = [f(v) for v in poly]
    if len(poly) == 2:
        (a, b), (fa, fb) = poly, fs
        if fa < 0 and fb < 0:
            return []
        if fa < 0:
            return [crossing(b, a, fb, fa), b]
        if fb < 0:
            return [a, crossing(a, b, fa, fb)]
        return list(poly)
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        fa, fb = fs[i], fs[(i + 1) % n]
        if fa >= 0:
            out.append(a)
            if fb < 0:
                out.append(crossing(a, b, fa, fb))
        elif fb >= 0:
            out.append(crossing(b, a, fb, fa))
    return out


GUARD_PLANES = [  # inside: sign * v[axis] <= g * z, so f(v) = g z - sign v[axis]
    (lambda v: GUARD_X * v[2] - v[0]),
    (lambda v: GUARD_X * v[2] + v[0]),
    (lambda v: GUARD_Y * v[2] - v[1]),
    (lambda v: GUARD_Y * v[2] + v[1]),
]


def guard_clip(poly):
    """A camera-space polygon (z >= ZNEAR throughout) clipped to the guard
    band's four planes in 3D, in turn."""
    for f in GUARD_PLANES:
        if not poly:
            return []
        poly = _clip_plane(poly, f)
    return poly


def _clip_edge(poly, axis, bound, keep_below):
    """One side of the rectangle: keep coordinate[axis] <= bound if
    keep_below, else >= bound. A crossing is the bound on the axis and, on
    the other, lerp from the inside end."""
    other = 1 - axis
    fs = [bound - p[axis] if keep_below else p[axis] - bound for p in poly]

    def cut(p, q, fp, fq):
        c = [0, 0]
        c[axis] = bound
        c[other] = lerp(p[other], q[other], crossing_t(fp, fq))
        return tuple(c)

    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        fa, fb = fs[i], fs[(i + 1) % n]
        if fa >= 0:
            out.append(a)
            if fb < 0:
                out.append(cut(a, b, fa, fb))
        elif fb >= 0:
            out.append(cut(b, a, fb, fa))
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


def drawable(poly):
    """Whether a polygon (repeats dropped) is drawn: three or more vertices,
    not all on one line, so nothing degenerate reaches the rasteriser. The
    line is through the first two vertices (which differ): another vertex off
    it is enough."""
    if len(poly) < 3:
        return False
    (x0, y0), (x1, y1) = poly[0], poly[1]
    dx, dy = x1 - x0, y1 - y0
    return any(dx * (y - y0) != dy * (x - x0) for x, y in poly[2:])


# --- The cone ------------------------------------------------------------------
#
# A face with a vertex the projection can't take (nearer than ZNEAR, or
# outside the guard band) is drawn as the view's rectangle clipped, in 2D,
# by its edges' planes through the eye. Seen from the eye, the face covers
# the rays inside every one of those planes, so that intersection is the
# face on the screen with nothing cut away: no near plane, no guard band,
# and no vertex projected. Each plane is a line on the screen, exactly the
# line its edge's two ends would project onto (camera space is exact).
#
# For an edge from A to B of a loop that winds anticlockwise about the
# face's outward normal (objects.py makes every loop so), seen from in
# front, the face is on the side where (A x B) . r <= 0 for the rays r
# through it. A box's edge runs along a world axis k, so B - A is a
# multiple of M's column k and A x B has the direction of A x M[:, k], a
# product of bytes; any other edge's is A x (B - A), each first cut to 16
# bits. On the screen, r = ((x - XC) / FX, -(y - YC) / FY, 1) (z > 0), so
# with FY = 2 FX the plane's line is f(x, y) = A x + B y + C, inside where
# f >= 0, its normal first cut to LINE_BITS bits.

LINE_BITS = 14
BEHIND = 32                 # code3: z <= 0


def code3(v):
    """Which of the half-spaces x < -z, x > z, 2y > z, 2y < -z and z <= 0 a
    camera-space vertex is in, anywhere (in front or not): each misses the
    view's pyramid, so a face with every vertex in one of them can't be
    seen."""
    x, y, z = v
    code = 0
    if x < -z:
        code |= LEFT
    if x > z:
        code |= RIGHT
    if 2 * y > z:
        code |= TOP
    if 2 * y < -z:
        code |= BOTTOM
    if z <= 0:
        code |= BEHIND
    return code


BAND_XS, BAND_YS = 3, 2


def projectable(v):
    """Whether a face with this camera-space vertex can be projected whole:
    in front of the near plane, and with x within 2^(n + BAND_XS) and y
    within 2^(n + BAND_YS) (each as two's complement, from -2^k up to 2^k
    - 1), n the bit length of z. As z >= 2^(n - 1), that's inside the guard
    band, and it's a test on a byte or two of each coordinate."""
    x, y, z = v
    if z < ZNEAR:
        return False
    n = z.bit_length()
    kx, ky = n + BAND_XS, n + BAND_YS
    return -(1 << kx) <= x < (1 << kx) and -(1 << ky) <= y < (1 << ky)


assert 2 << BAND_XS <= GUARD_X and 2 << BAND_YS <= GUARD_Y   # (inside the guard band)


def cut16(v):
    """A vector shifted right (rounding down) until every component fits 16
    bits, signed."""
    s = max(0, max(abs(x) for x in v).bit_length() - 15)
    return tuple(x >> s for x in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def edge_normal_axis(a, col, sign):
    """The plane through the eye and a box's edge from camera-space vertex
    a along M's column col (the world axis's direction), sign +1 up the
    axis and -1 down it."""
    n = cross(a, col)
    return n if sign > 0 else (-n[0], -n[1], -n[2])


def edge_normal(a, b):
    """The plane through the eye and the edge from a to b, any direction."""
    return cross(cut16(a), cut16(tuple(b[k] - a[k] for k in range(3))))


def screen_line(n):
    """A plane through the eye as the screen's line (A, B, C): f(x, y) =
    A x + B y + C, at least 0 on the face's side."""
    s = max(0, max(abs(x) for x in n).bit_length() - LINE_BITS)
    nx, ny, nz = (x >> s for x in n)
    return (-2 * nx, ny, 2 * nx * XC - ny * YC - 2 * FX * nz)


def line_f(line, p):
    a, b, c = line
    return a * p[0] + b * p[1] + c


RECT = [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT)]


def _clip_poly(poly, line):
    """Sutherland-Hodgman against one line, new vertices by crossing() from
    the inside end."""
    fs = [line_f(line, p) for p in poly]
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        fa, fb = fs[i], fs[(i + 1) % n]
        if fa >= 0:
            out.append(a)
            if fb < 0:
                out.append(crossing(a, b, fa, fb))
        elif fb >= 0:
            out.append(crossing(b, a, fb, fa))
    return out


def cone_clip(lines):
    """The view's rectangle inside every line (the face's edges' planes, in
    its loop's order), repeats dropped: [] if nothing's left. A line with
    the rectangle's every corner inside it cuts nothing and is passed over;
    one with every corner outside leaves nothing."""
    cutting = []
    for line in lines:
        fs = [line_f(line, p) for p in RECT]
        if all(f < 0 for f in fs):
            return []
        if any(f < 0 for f in fs):
            cutting.append(line)
    poly = list(RECT)
    for line in cutting:
        poly = _clip_poly(poly, line)
        if not poly:
            return []
    return dedupe(poly)


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
