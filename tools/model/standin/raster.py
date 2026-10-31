"""Stand-in for tools/model/raster.py: a simple scan converter over a span
buffer, front to back with coverage (docs/engine.md, section 4, stages 8 and
9; section 9's interface).

rasterise(faces, sky, ground, horizon=None, stats=None):

- faces: nearest first, each (pattern, polygon): a pattern is four bytes, one
  for each value of line AND 3; a polygon is convex, its vertices view
  coordinates (sixteenths) inside [0, 16 VIEW_W] x [0, 16 VIEW_H], in either
  winding.
- sky, ground: patterns; horizon: ((px, py), (dx, dy)) in view coordinates,
  sky to the left of the direction as seen on the screen (a pixel centre on
  the line is ground), or None for sky everywhere.
- Returns, for each line 0 to VIEW_H - 1, its runs (x0, x1, pattern) in
  pixels, in order, covering [0, VIEW_W) exactly.

The fill rule: a pixel is covered when its centre is inside the polygon; a
centre exactly on an edge counts for top and left edges and not for bottom
and right ones. A face's run on a line is clipped against what's already
there, and only the uncovered parts go in. Runs aren't merged.
"""
from tools.model.view import SUB, VIEW_H, VIEW_W

HALF = SUB // 2


def _ceil_div(n, d):
    return -((-n) // d)


def span(poly, line):
    """The pixels [x0, x1) a convex polygon covers on a line, or None."""
    yc = SUB * line + HALF
    cross = []
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if y0 == y1:
            continue
        if min(y0, y1) <= yc < max(y0, y1):
            d = y1 - y0
            num = x0 * d + (x1 - x0) * (yc - y0)
            if d < 0:
                num, d = -num, -d
            cross.append((num, d))
    if len(cross) < 2:
        return None
    # The leftmost and rightmost crossings, compared exactly.
    na, da = nb, db = cross[0]
    for n_, d_ in cross[1:]:
        if n_ * da < na * d_:
            na, da = n_, d_
        if n_ * db > nb * d_:
            nb, db = n_, d_
    # The first pixel whose centre is at or right of each crossing.
    x0 = max(0, _ceil_div(na - HALF * da, SUB * da))
    x1 = min(VIEW_W, _ceil_div(nb - HALF * db, SUB * db))
    return (x0, x1) if x0 < x1 else None


def _rows(poly):
    ys = [p[1] for p in poly]
    lo = max(0, _ceil_div(min(ys) - HALF, SUB))
    hi = min(VIEW_H - 1, (max(ys) - HALF) // SUB)
    return range(lo, hi + 1)


def _insert(runs, x0, x1, pattern):
    """Add [x0, x1) to a line's sorted runs where nothing covers it; return
    the number of pieces that went in."""
    pieces = []
    at = x0
    for r0, r1, _ in runs:
        if r1 <= at:
            continue
        if r0 >= x1:
            break
        if r0 > at:
            pieces.append((at, r0, pattern))
        at = max(at, r1)
        if at >= x1:
            break
    if at < x1:
        pieces.append((at, x1, pattern))
    if pieces:
        runs.extend(pieces)
        runs.sort(key=lambda r: r[0])
    return len(pieces)


def _background(line, x0, x1, sky, ground, horizon):
    """The runs filling an uncovered [x0, x1) of a line."""
    if horizon is None:
        return [(x0, x1, sky)]
    (px, py), (dx, dy) = horizon
    yc = SUB * line + HALF

    def is_ground(x):
        return dx * (yc - py) - dy * (SUB * x + HALF - px) >= 0

    out = []
    x = x0
    while x < x1:
        g = is_ground(x)
        e = x + 1
        while e < x1 and is_ground(e) == g:
            e += 1
        out.append((x, e, ground if g else sky))
        x = e
    return out


def rasterise(faces, sky, ground, horizon=None, stats=None):
    lines = [[] for _ in range(VIEW_H)]
    covered = [0] * VIEW_H
    face_lines = open_lines = pieces = 0
    for pattern, poly in faces:
        if len(poly) < 3:
            continue
        for y in _rows(poly):
            s = span(poly, y)
            if s is None:
                continue
            face_lines += 1
            if covered[y] == VIEW_W:
                continue
            open_lines += 1
            k = _insert(lines[y], s[0], s[1], pattern)
            pieces += k
            covered[y] = sum(r1 - r0 for r0, r1, _ in lines[y])
    full = sum(1 for c in covered if c == VIEW_W)
    out = []
    for y, runs in enumerate(lines):
        line = []
        at = 0
        for r0, r1, p in runs:
            if r0 > at:
                line.extend(_background(y, at, r0, sky, ground, horizon))
            line.append((r0, r1, p))
            at = r1
        if at < VIEW_W:
            line.extend(_background(y, at, VIEW_W, sky, ground, horizon))
        out.append(line)
    if stats is not None:
        stats.update(face_lines=face_lines, face_lines_open=open_lines,
                     face_runs=pieces, lines_full=full)
    return out
