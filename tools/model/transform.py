"""The transform, exact so it can be cached (docs/engine.md, section 4, stage 3).

A camera-space vertex is V = M (v - c), with M the camera's matrix (signed
bytes, 1.0 = 64), v and c in world units, and nothing shifted or rounded:
24-bit signed, 64 to the world unit. Projection needs only ratios.

The cached form keeps M v for each vertex while the orientation holds and
takes M c once a frame: V = M v - M c, identical because nothing is rounded.
A cuboid's vertices come from M times its corner and its three edges, by
additions, as the original builds them (CM2 asm, L9661_project_cube_objects).
"""

LIMIT = 1 << 23   # 24-bit signed


def mul(m, v):
    """M v: three sums of three products."""
    return tuple(m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2] for r in range(3))


def check24(v):
    for x in v:
        if not -LIMIT <= x < LIMIT:
            raise OverflowError("camera-space value %d outside 24 bits" % x)
    return v


def transform(m, v, c):
    """V = M (v - c), directly."""
    return check24(mul(m, (v[0] - c[0], v[1] - c[1], v[2] - c[2])))


def cached(mv, mc):
    """V = M v - M c, from the cached M v and the frame's M c."""
    return check24((mv[0] - mc[0], mv[1] - mc[1], mv[2] - mc[2]))


def cuboid(m, lo, size, c):
    """The eight vertices of a box from lo to lo + size (world units), as
    M (lo - c) and the three rotated edges, M times each size along its
    axis, added: vertex i has bit 0 for x, bit 1 for y, bit 2 for z."""
    corner = transform(m, lo, c)
    edges = [tuple(m[r][k] * size[k] for r in range(3)) for k in range(3)]
    out = []
    for i in range(8):
        v = list(corner)
        for k in range(3):
            if i >> k & 1:
                v = [v[r] + edges[k][r] for r in range(3)]
        out.append(check24(tuple(v)))
    return out
