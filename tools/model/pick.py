"""The shot's pick, and the laser's lines (the original's $B153 and
$AA50-$AA8C, docs/research/laser.md), at the BBC's view.

The original walks its last redraw's draw list from the nearest object back,
and its first object with a face round the crosshair is hit: a face is round
it when its vertices bracket the crosshair on both axes and the edges'
crossings of the crosshair's row bracket its column (a vertex or crossing on
it counts). The disc does the same over the faces of the last frame it drew,
nearest first (src/order.6502's draw list): the first face whose polygon
holds the crosshair pixel's centre, its edges counting, is hit. The
crosshair pixel is the one decision 38 centres the crosshair on.

The laser: four lines, each from a corner of the view's bottom to the
crosshair, drawn by the original's line ($A803, a DDA along the longer axis
with its error from half that axis) and EORed into the view as the
crosshair is (colour 7), at the BBC's half width: each end's x halved as the
crosshair's is (decision 130).
"""
from tools.model.view import SUB, VIEW_H, VIEW_W


def cross_pixel(cross_x, cross_y):
    """The view's pixel the crosshair is centred on (decision 38):
    ((CrossX - 1) DIV 2, VIEW_H - CrossY), as src/live.6502's cross_eor."""
    return ((cross_x - 1) & 0xFF) >> 1, (VIEW_H - cross_y) & 0xFF


def covers(poly, px, py):
    """Whether the convex polygon (view coordinates, either winding) holds
    pixel (px, py)'s centre, its edges and vertices counting."""
    x, y = SUB * px + SUB // 2, SUB * py + SUB // 2
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    if not (min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys)):
        return False
    pos = neg = False
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        c = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if c > 0:
            pos = True
        elif c < 0:
            neg = True
    return not (pos and neg)


def pick(faces, px, py):
    """The id of the object whose face, nearest first, is the first to hold
    pixel (px, py), or None: faces are render.View's (DrawnFace, with .id
    and .poly)."""
    if px >= VIEW_W or py >= VIEW_H:
        return None
    for f in faces:
        if covers(f.poly, px, py):
            return f.id
    return None


def line(x0, y0, x1, y1):
    """The original's line ($A803) from (x0, y0) to (x1, y1), its pixels in
    order: the longer axis stepped every pixel, the shorter when the error,
    from half the longer, reaches the longer; ties go to y as the longer."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = (x1 > x0) - (x1 < x0)
    sy = (y1 > y0) - (y1 < y0)
    if dy >= dx:
        major, minor = dy, dx
        always, sometimes = (0, sy), (sx, 0)
    else:
        major, minor = dx, dy
        always, sometimes = (sx, 0), (0, sy)
    e = major >> 1
    x, y = x0, y0
    out = []
    for _ in range(major + 1):
        out.append((x, y))
        x, y = x + always[0], y + always[1]
        e += minor
        if e >= major:
            e -= major
            x, y = x + sometimes[0], y + sometimes[1]
    return out


# The lines' far ends, as the original's (x, y up from the view's bottom,
# x 1 to twice the view's centre): (1, 5), (2 cx, 5), (5, 1), (2 cx - 5, 1)
def laser_starts(centre_x):
    return [(1, 5), (2 * centre_x, 5), (5, 1), (2 * centre_x - 5, 1)]


def sensor_pixels(x, y, centre_x, centre_y):
    """Every pixel of a sensor's shot's four lines ($BC1B) at the BBC's
    view: from its point (x, y, as the crosshair's) to (cx - 3, 0),
    (cx + 3, 0), (cx + 3, 2 cy) and (cx - 3, 2 cy), each halved as the
    crosshair is; a pixel past the view's bottom (y 0) isn't drawn."""
    bx, by = cross_pixel(x, y)
    out = []
    for ex, ey in ((centre_x - 3, 0), (centre_x + 3, 0), (centre_x + 3, 2 * centre_y), (centre_x - 3, 2 * centre_y)):
        out += line(bx, by, *cross_pixel(ex & 0xFF, ey & 0xFF))
    return out


def laser_pixels(cross_x, cross_y, centre_x):
    """Every pixel of the laser's four lines at the BBC's view, in drawing
    order (a pixel twice is EORed twice): each from its far end, halved as
    the crosshair is, to the crosshair's pixel."""
    ex, ey = cross_pixel(cross_x, cross_y)
    out = []
    for sx, sy in laser_starts(centre_x):
        bx, by = cross_pixel(sx, sy)
        out += line(bx, by, ex, ey)
    return out
