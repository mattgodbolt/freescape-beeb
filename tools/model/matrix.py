"""The camera's matrix (docs/engine.md, section 4, stage 1).

Nine signed bytes, 1.0 = 64, row-major: a camera-space vector is M times a
world-space one, x right, y up and z ahead. Each rotation comes from the
original's sine table, and the three are composed as Castle Master II
composes yaw and pitch (L95de_init_rotation_matrix, La089_3x3_matrix_multiply):
pitch times yaw, each product's sum of three rounded to the nearest 64th, half
up, back to a byte. Driller's roll is then applied the same way, last, about
the view's own axis.
"""


def yaw_matrix(a, sin, cos):
    s, c = sin[a], cos[a]
    return ((c, 0, -s), (0, 64, 0), (s, 0, c))


def pitch_matrix(a, sin, cos):
    s, c = sin[a], cos[a]
    return ((64, 0, 0), (0, c, s), (0, -s, c))


def roll_matrix(a, sin, cos):
    s, c = sin[a], cos[a]
    return ((c, s, 0), (-s, c, 0), (0, 0, 64))


def compose(a, b):
    """a times b, as CM2's La089: each sum of three byte products, plus 32,
    shifted right by six (rounding half up), must fit a signed byte."""
    out = []
    for r in range(3):
        row = []
        for c in range(3):
            v = (sum(a[r][k] * b[k][c] for k in range(3)) + 32) >> 6
            if not -128 <= v <= 127:
                raise OverflowError("matrix entry %d" % v)
            row.append(v)
        out.append(tuple(row))
    return tuple(out)


def rotation(camera, tables):
    """The camera's matrix: roll times (pitch times yaw)."""
    sin, cos = tables["sin"], tables["cos"]
    m = compose(pitch_matrix(camera.pitch, sin, cos), yaw_matrix(camera.yaw, sin, cos))
    return compose(roll_matrix(camera.roll, sin, cos), m)
