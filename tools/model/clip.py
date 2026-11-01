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
from tools.model import maths
from tools.model.view import FX, FY, SUB, VIEW_H, VIEW_W, XC, YC, ZNEAR

# The 2D clip's crossings by a reciprocal (crossing_r); off, by
# crossing_t's division, as the cone's and a line's 3D clip's still are.
RECIP_2D = True

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


def crossing_r(fp, fq):
    """The 2D clip's crossing fraction (RECIP_2D), from its inside end (fp
    >= 0) to its outside end (fq < 0), by a reciprocal rather than a
    division: d = fp - fq, normalised to nine bits dn = d >> s (s =
    bitlen(d) - 9; a shift left when negative), R = 256 + maths.CLIP_M[dn -
    256], about 2^17 / d's nine bits, and t = fp R >> (s + 1), at most
    2^T_BITS - 1. Within about 2^-8 of crossing_t's fraction, and still from
    the inside end, so two faces sharing an edge cut it at the same point."""
    assert fp >= 0 > fq
    d = fp - fq                 # (the 6502's within 16 bits: the guard band)
    s = d.bit_length() - maths.CLIP_RBITS
    dn = d >> s if s >= 0 else d << -s
    r = 256 + maths.CLIP_M[dn - 256]
    k = s + 1
    t = (fp * r) >> k if k >= 0 else (fp * r) << -k
    return min(t, (1 << T_BITS) - 1)


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
        c[other] = lerp(p[other], q[other], (crossing_r if RECIP_2D else crossing_t)(fp, fq))
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

LINE_BITS = 13
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


# A line with an end the projection can't take is clipped in 3D to the near
# plane, then to the planes beyond the view's sides (beyond()'s, which lie
# outside the view), each by a crossing from the inside end. What's left is
# in front of the near plane with |x| and |2y| within z (give or take a
# crossing's rounding), which the projection takes.
SEGMENT_PLANES = [
    (lambda v: v[2] - ZNEAR),
    (lambda v: v[2] + v[0]),
    (lambda v: v[2] - v[0]),
    (lambda v: v[2] - 2 * v[1]),
    (lambda v: v[2] + 2 * v[1]),
]


def segment_clip(a, b):
    """The camera-space segment a-b clipped to SEGMENT_PLANES in turn: [a',
    b'], or [] if nothing's left."""
    for f in SEGMENT_PLANES:
        fa, fb = f(a), f(b)
        if fa < 0 and fb < 0:
            return []
        if fa < 0:
            a = crossing(b, a, fb, fa)
        elif fb < 0:
            b = crossing(a, b, fa, fb)
    return [a, b]


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


# A line from an image (render.IMAGE_LINES): the screen line of an edge's
# plane through the eye runs through the image of any of the edge's points
# in front of the eye, so an edge whose end the projection takes has its
# line through that end's projected image, square to (a, b): through the
# other end's image too when the projection takes both, as a face projected
# whole has that edge, or else toward the edge's vanishing point. With A
# the end's camera-space vertex and d the edge's direction (B - A), N = A x
# d, and with A at (u, v) = (x - XC, y - YC) on the screen, f's gradient
# (-2 Nx, Ny) is Az / FX times (FY dy + v dz, FX dx - u dz): no product of
# 24-bit numbers, and the line passes through the image exactly.
IMAGE_BITS = 14
assert 2 * (1 << IMAGE_BITS) * (1 << 15) < 1 << 31     # (f at a corner fits 32 bits signed)


def image_line(a, b, p):
    """The line through view point p square to (a, b), not both 0: (A, B,
    C) with f(x, y) = A x + B y + C = A (x - px) + B (y - py), A and B a
    and b shifted right together (rounding down) until both fit IMAGE_BITS
    bits, signed; or a unit (A or B +-1) when the other is 0, so that a
    line square to a side crosses it at p exactly."""
    assert a or b
    if not b:
        a, b = (1 if a > 0 else -1), 0
    elif not a:
        a, b = 0, (1 if b > 0 else -1)
    else:
        s = max(0, max(abs(a), abs(b)).bit_length() - IMAGE_BITS)
        a, b = a >> s, b >> s
    x, y = p
    return (a, b, -(a * x + b * y))


def image_gradient(p, d):
    """(a, b) for the line through the image p of an edge's end toward the
    edge's vanishing point, d its direction (B - A) in camera space: (FY dy +
    v dz, FX dx - u dz), (u, v) = p less the view's centre."""
    u, v = p[0] - XC, p[1] - YC
    return (FY * d[1] + v * d[2], FX * d[0] - u * d[2])


RECT = [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT)]
# The rectangle's sides, each from corner k to corner k + 1: the top, the
# right, the bottom and the left. Each vertex of the polygon the cone clips
# carries the label of its edge to the next one: ("side", k), or ("line", j)
# for an edge along the line of the face's edge j.

# A crossing on one of the rectangle's sides is the line's own crossing
# with that side, from the side's corner inside the line (side_crossing):
# one division, and the same point whichever piece of the side is being
# cut. Off, crossing() along the piece, as every other crossing.
SIDE_CROSSINGS = True
# Where the lines of two consecutive edges cross, the polygon takes their
# shared vertex's image when the projection takes that vertex: the point
# they meet at, to the projection's accuracy, and the same point a face
# projected whole has there. Off, crossing() along the edge.
JOINS = True


# The cone's side crossings by a reciprocal (side_d), as the 2D clip's
# crossings are (crossing_r), with no division; off, f(K) / a by division,
# rounded half up.
SIDE_RECIP = True


def side_d(fk, a):
    """f(K) / a, the distance along a side to a line's crossing (0 <= fk <
    a WIDTH): by the 2D clip's reciprocals (maths.CLIP_M), R about 2^17 /
    a's nine bits from its top one an = a >> s, s = bitlen(a) - 9, and fk
    shifted right s + 4 so that its product with R has 16 bits by 9, rounded
    and at most WIDTH (within about 2^-8 of the division's, which is under
    WIDTH); or with SIDE_RECIP off, by division, rounded half up."""
    if not SIDE_RECIP:
        return (2 * fk + a) // (2 * a)
    s = a.bit_length() - maths.CLIP_RBITS
    an = a >> s if s >= 0 else a << -s
    r = 256 + maths.CLIP_M[an - 256]
    t = s + 4
    f = fk >> t if t >= 0 else fk << -t
    assert f < 1 << 16
    return min((f * r + (1 << 12)) >> 13, WIDTH)


assert WIDTH == HEIGHT              # (side_d's bound, whichever side)


def side_crossing(line, k):
    """Where a line crosses side k of the rectangle, which it cuts (its
    corners on either side of it): from the corner K inside the line (f >=
    0), along the side by f(K) / |a| (side_d), a the line's coefficient
    along the side (A along the top and bottom, B down the sides)."""
    c0, c1 = RECT[k], RECT[(k + 1) % 4]
    f0, f1 = line_f(line, c0), line_f(line, c1)
    assert (f0 >= 0) != (f1 >= 0)
    (ka, fk), other = ((c0, f0), c1) if f0 >= 0 else ((c1, f1), c0)
    axis = 0 if k in (0, 2) else 1
    a = abs(line[axis])
    d = side_d(fk, a)
    p = list(ka)
    p[axis] += d if other[axis] > ka[axis] else -d
    return tuple(p)


def _join(j, k, ends, image):
    """The image of the vertex the edges of lines j and k share, clamped to
    the rectangle, if they're consecutive and the projection takes it; else
    None."""
    if ends is None or image is None:
        return None
    if ends[j][1] == ends[k][0]:
        v = ends[j][1]
    elif ends[k][1] == ends[j][0]:
        v = ends[k][1]
    else:
        return None
    p = image(v)
    if p is None:
        return None
    x, y = p
    return (min(max(x, 0), WIDTH), min(max(y, 0), HEIGHT))


def _cone_pass(poly, lines, k, ends, image):
    """Sutherland-Hodgman against line k, on labelled vertices: a crossing on
    a side by side_crossing, one where two consecutive edges' lines meet by
    their vertex's image (_join), any other by crossing() from the inside
    end."""
    line = lines[k]

    def cut(p, q, fp, fq, label):
        kind, j = label
        if kind == "side" and SIDE_CROSSINGS:
            return side_crossing(line, j)
        if kind == "line" and JOINS:
            joined = _join(j, k, ends, image)
            if joined is not None:
                return joined
        return crossing(p, q, fp, fq)

    fs = [line_f(line, p) for p, _ in poly]
    out = []
    n = len(poly)
    for i in range(n):
        (a, la), (b, _) = poly[i], poly[(i + 1) % n]
        fa, fb = fs[i], fs[(i + 1) % n]
        if fa >= 0:
            out.append((a, la))
            if fb < 0:
                out.append((cut(a, b, fa, fb, la), ("line", k)))
        elif fb >= 0:
            out.append((cut(b, a, fb, fa, la), la))
    return out


def corners_out(line):
    """How many of the rectangle's corners are outside a line (f < 0)."""
    return sum(1 for p in RECT if line_f(line, p) < 0)


def cone_clip(lines, ends=None, image=None):
    """The view's rectangle inside every line (the face's edges' planes, in
    its loop's order), repeats dropped: [] if nothing's left. A line with
    the rectangle's every corner inside it cuts nothing and is passed over;
    one with every corner outside leaves nothing. ends[k] is line k's
    edge's two vertices, as indices, and image(v) vertex v's view
    coordinates if the projection takes it, else None (for JOINS; without
    them, no joins)."""
    cutting = []
    for k, line in enumerate(lines):
        out = corners_out(line)
        if out == 4:
            return []
        if out:
            cutting.append(k)
    poly = [(RECT[k], ("side", k)) for k in range(4)]
    for k in cutting:
        poly = _cone_pass(poly, lines, k, ends, image)
        if not poly:
            return []
    return dedupe([p for p, _ in poly])


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
