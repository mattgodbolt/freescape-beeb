"""tools/model/clip.py: the near plane in 3D, the view's rectangle in 2D."""
import math
import random
import unittest

from tools.model import clip
from tools.model.view import FX, SUB, VIEW_H, VIEW_W, XC, ZNEAR


class RoundDiv(unittest.TestCase):
    def test_half_up(self):
        self.assertEqual(clip.round_div(1, 2), 1)
        self.assertEqual(clip.round_div(-1, 2), 0)
        self.assertEqual(clip.round_div(-3, 2), -1)
        self.assertEqual(clip.round_div(5, -2), -2)
        self.assertEqual(clip.round_div(7, 3), 2)


class Near(unittest.TestCase):
    def test_inside_untouched(self):
        poly = [(0, 0, ZNEAR), (10, 0, ZNEAR + 5), (0, 10, 9999)]
        self.assertEqual(clip.near_clip(poly), poly)

    def test_all_behind(self):
        self.assertEqual(clip.near_clip([(0, 0, 0), (1, 0, ZNEAR - 1), (0, 1, -5)]), [])

    def test_straddling(self):
        rng = random.Random(2)
        for _ in range(500):
            poly = [(rng.randint(-5000, 5000), rng.randint(-5000, 5000), rng.randint(-2000, 4000))
                    for _ in range(4)]
            out = clip.near_clip(poly)
            for v in out:
                self.assertGreaterEqual(v[2], ZNEAR)
            for v in poly:
                if v[2] >= ZNEAR:
                    self.assertIn(v, out)

    def test_line(self):
        a, b = (0, 0, ZNEAR * 3), (300, 0, ZNEAR - ZNEAR)
        out = clip.near_clip([a, b])
        self.assertEqual(out[0], a)
        self.assertEqual(out[1][2], ZNEAR)
        self.assertEqual(out[1][0], clip.round_div(300 * 2 * ZNEAR, 3 * ZNEAR))


class Outcodes(unittest.TestCase):
    W, H = SUB * VIEW_W, SUB * VIEW_H

    def test_edges(self):
        # The rectangle is closed: on an edge is inside.
        self.assertEqual(clip.outcode2d((0, 0)), 0)
        self.assertEqual(clip.outcode2d((self.W, self.H)), 0)
        self.assertEqual(clip.outcode2d((-1, 5)), clip.LEFT)
        self.assertEqual(clip.outcode2d((self.W + 1, 5)), clip.RIGHT)
        self.assertEqual(clip.outcode2d((5, -1)), clip.TOP)
        self.assertEqual(clip.outcode2d((5, self.H + 1)), clip.BOTTOM)
        self.assertEqual(clip.outcode2d((-1, -1)), clip.LEFT | clip.TOP)


class Crossings(unittest.TestCase):
    def test_fraction(self):
        self.assertEqual(clip.crossing_t(0, -5), 0)
        self.assertEqual(clip.crossing_t(1, -1), 1 << (clip.T_BITS - 1))
        rng = random.Random(23)
        for _ in range(2000):
            fp, fq = rng.randint(0, 1 << 28), -rng.randint(1, 1 << 28)
            t = clip.crossing_t(fp, fq)
            self.assertTrue(0 <= t < 1 << clip.T_BITS)
            # within a unit or two of the exact fraction (normalised to 16 bits)
            exact = (fp << clip.T_BITS) // (fp - fq)
            self.assertLessEqual(abs(t - exact), 2)

    def test_lerp_rounds_half_up(self):
        h = 1 << (clip.T_BITS - 1)
        self.assertEqual(clip.lerp(0, 1, h), 1)
        self.assertEqual(clip.lerp(0, -1, h), 0)
        self.assertEqual(clip.lerp(10, 20, 0), 10)

    def test_shared_edge(self):
        # Two faces that share an edge, each walking it its own way round,
        # cut it at one point.
        a, b = (0, 0), (700, 1900)
        out1 = clip.clip2d([a, b, (900, 0)])
        out2 = clip.clip2d([b, a, (-50, 1500)])
        cut = [p for p in out1 if p[1] == self.H and p not in (a, b)]
        self.assertTrue(cut and cut[0] in out2)

    H = SUB * VIEW_H


class Drawable(unittest.TestCase):
    def test_lines_and_points(self):
        self.assertFalse(clip.drawable([(0, 0), (16, 16)]))
        self.assertFalse(clip.drawable([(0, 0), (16, 16), (32, 32), (48, 48)]))
        self.assertFalse(clip.drawable([(0, 0), (0, 5), (0, 100)]))
        self.assertTrue(clip.drawable([(0, 0), (0, 5), (1, 100)]))
        self.assertTrue(clip.drawable([(0, 0), (16, 16), (32, 33)]))


class Rect(unittest.TestCase):
    W, H = SUB * VIEW_W, SUB * VIEW_H

    def test_inside_untouched(self):
        poly = [(0, 0), (self.W, 0), (self.W, self.H)]
        self.assertEqual(clip.clip2d(poly), poly)

    def test_random(self):
        rng = random.Random(3)
        for _ in range(500):
            poly = [(rng.randint(-3000, 4000), rng.randint(-3000, 4000)) for _ in range(3)]
            for x, y in clip.clip2d(poly):
                self.assertTrue(0 <= x <= self.W and 0 <= y <= self.H)

    def test_outside(self):
        self.assertEqual(clip.clip2d([(-10, 0), (-5, 50), (-1, 9)]), [])

    def test_huge(self):
        # A vertex just past the near plane projects millions of sixteenths out.
        out = clip.clip2d([(-4_000_000, 800), (800, -3_000_000), (900, 900)])
        self.assertTrue(out)
        for x, y in out:
            self.assertTrue(0 <= x <= self.W and 0 <= y <= self.H)

    def test_widened(self):
        self.assertEqual(clip.line_quad((0, 8), (64, 8)), [(0, 0), (64, 0), (64, 16), (0, 16)])
        self.assertEqual(clip.point_square((24, 40)), [(16, 32), (32, 32), (32, 48), (16, 48)])


class Guard(unittest.TestCase):
    """The guard band (decision 17): what's clipped to it projects inside
    16 bits, and what's inside it is untouched."""

    def test_inside_untouched(self):
        poly = [(100, 50, 1000), (-200, 30, 2000), (0, -400, 900)]
        self.assertFalse(any(clip.outside_guard(v) for v in poly))
        self.assertEqual(clip.guard_clip(poly), poly)

    def test_far_side_vertex_clipped_into_range(self):
        from tools.model import parts
        rng = random.Random(17)
        for _ in range(2000):
            poly = [(rng.randint(-1 << 20, 1 << 20), rng.randint(-1 << 19, 1 << 19),
                     rng.randint(ZNEAR, 1 << 16)) for _ in range(rng.randint(2, 5))]
            out = clip.guard_clip(poly)
            for x, y, z in out:
                self.assertGreaterEqual(z, ZNEAR)
                # within the band, give or take a crossing's 2^-15 of an edge
                self.assertLessEqual(abs(x), clip.GUARD_X * z + (2 << 20 >> 14) + clip.GUARD_X)
                self.assertLessEqual(abs(y), clip.GUARD_Y * z + (2 << 20 >> 14) + clip.GUARD_Y)
                sx, sy = parts.project(x, y, z)
                self.assertLess(abs(sx), (1 << 15) - 1)
                self.assertLess(abs(sy), (1 << 15) - 1)


class Cone(unittest.TestCase):
    """The cone (clip.py): a face as the view's rectangle clipped by its
    edges' planes through the eye."""

    def face(self, rng):
        # a random convex quad in a plane, in front of the eye, wound
        # anticlockwise about the normal that faces the eye
        cx, cy, cz = rng.randint(-3000, 3000), rng.randint(-1500, 1500), rng.randint(2000, 9000)
        ux, uy, uz = rng.randint(-900, 900), rng.randint(-900, 900), rng.randint(-300, 300)
        vx, vy, vz = rng.randint(-900, 900), rng.randint(-900, 900), rng.randint(-300, 300)
        quad = [(cx - ux - vx, cy - uy - vy, cz - uz - vz), (cx + ux - vx, cy + uy - vy, cz + uz - vz),
                (cx + ux + vx, cy + uy + vy, cz + uz + vz), (cx - ux + vx, cy - uy + vy, cz - uz + vz)]
        n = clip.cross((2 * ux, 2 * uy, 2 * uz), (2 * vx, 2 * vy, 2 * vz))
        facing = sum(n[k] * quad[0][k] for k in range(3))
        if facing > 0:                  # facing away: turn it round
            quad.reverse()
        # (None if it's seen within a few degrees of edge-on, or is a sliver,
        # where a sixteenth of rounding moves its far corners anywhere)
        size = math.hypot(*n) * math.hypot(*quad[0])
        sliver = math.hypot(*n) < 0.3 * math.hypot(ux, uy, uz) * math.hypot(vx, vy, vz) * 4
        return None if abs(facing) < 0.2 * size or sliver else quad

    def test_matches_the_projection(self):
        """A face in front, inside the guard band: the cone's polygon is its
        projection clipped to the view, to within the projection's error."""
        from tools.model import parts
        rng = random.Random(41)
        checked = 0
        for _ in range(400):
            quad = self.face(rng)
            if quad is None or not all(clip.projectable(v) for v in quad):
                continue
            lines = [clip.screen_line(clip.edge_normal(quad[i], quad[(i + 1) % 4])) for i in range(4)]
            cone = clip.cone_clip(lines)
            flat = clip.clip2d([parts.project(*v) for v in quad])
            self.assertEqual(clip.drawable(cone), clip.drawable(flat))
            if not cone or not flat:
                continue
            # every vertex of each near some vertex of the other
            for p in cone:
                self.assertLess(min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in flat), 12)
            checked += 1
        self.assertGreater(checked, 100)

    def test_joins_match_the_projection(self):
        """With its edges' ends and its vertices' images, where the edges'
        lines meet is each vertex's image: the polygon is the same face to
        within the projection's error."""
        from tools.model import parts
        rng = random.Random(41)
        checked = 0
        for _ in range(400):
            quad = self.face(rng)
            if quad is None or not all(clip.projectable(v) for v in quad):
                continue
            lines = [clip.screen_line(clip.edge_normal(quad[i], quad[(i + 1) % 4])) for i in range(4)]
            ends = [(i, (i + 1) % 4) for i in range(4)]
            cone = clip.cone_clip(lines, ends, lambda i: parts.project(*quad[i]))
            flat = clip.clip2d([parts.project(*v) for v in quad])
            self.assertEqual(clip.drawable(cone), clip.drawable(flat))
            if not cone or not flat:
                continue
            for p in cone:
                self.assertLess(min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in flat), 12)
            checked += 1
        self.assertGreater(checked, 100)

    def test_side_crossing(self):
        """A line's crossing with a side is its exact crossing rounded half
        up from the corner inside it, whichever way the line faces."""
        from fractions import Fraction
        rng = random.Random(61)
        checked = 0
        for _ in range(3000):
            line = (rng.randint(-1 << 14, 1 << 14), rng.randint(-1 << 13, 1 << 13),
                    rng.randint(-1 << 25, 1 << 25))
            for k in range(4):
                c0, c1 = clip.RECT[k], clip.RECT[(k + 1) % 4]
                if (clip.line_f(line, c0) >= 0) == (clip.line_f(line, c1) >= 0):
                    continue
                p = clip.side_crossing(line, k)
                axis = 0 if k in (0, 2) else 1
                a, b, c = line
                exact = (-(b * p[1] + c) / Fraction(a)) if axis == 0 else (-(a * p[0] + c) / Fraction(b))
                self.assertLessEqual(abs(p[axis] - exact), Fraction(1, 2))
                self.assertTrue(0 <= p[0] <= clip.WIDTH and 0 <= p[1] <= clip.HEIGHT)
                self.assertEqual(p[1 - axis], c0[1 - axis])
                # the line facing the other way crosses at the same point, but
                # for a tie, from the other corner
                q = clip.side_crossing(tuple(-v for v in line), k)
                self.assertLessEqual(abs(p[axis] - q[axis]), 1)
                checked += 1
        self.assertGreater(checked, 1000)

    def test_behind_edges_redundant(self):
        """An edge with both ends behind the eye takes nothing off the
        face's image: without its line, the same polygon."""
        rng = random.Random(67)
        checked = 0
        for _ in range(3000):
            quad = self.face(rng)
            if quad is None:
                continue
            # move it back so that one edge is behind the eye
            dz = max(quad[0][2], quad[1][2]) + rng.randint(1, 500)
            quad = [(x, y, z - dz) for x, y, z in quad]
            # (still facing the eye, as the object pass leaves every face)
            n = clip.cross(tuple(quad[1][k] - quad[0][k] for k in range(3)),
                           tuple(quad[2][k] - quad[1][k] for k in range(3)))
            if sum(n[k] * quad[0][k] for k in range(3)) >= 0:
                continue
            edges = [(quad[i], quad[(i + 1) % 4]) for i in range(4)]
            if sum(1 for a, b in edges if a[2] <= 0 and b[2] <= 0) != 1:
                continue
            every = [clip.screen_line(clip.edge_normal(a, b)) for a, b in edges]
            front = [clip.screen_line(clip.edge_normal(a, b)) for a, b in edges if a[2] > 0 or b[2] > 0]
            whole, cut = clip.cone_clip(every), clip.cone_clip(front)
            self.assertEqual(clip.drawable(whole), clip.drawable(cut))
            if whole and cut:
                for p in cut:
                    self.assertLess(min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in whole), 4)
            checked += 1
        self.assertGreater(checked, 50)

    def test_inside_the_view(self):
        rng = random.Random(43)
        for _ in range(300):
            quad = [(rng.randint(-1 << 18, 1 << 18), rng.randint(-1 << 17, 1 << 17),
                     rng.randint(-1 << 16, 1 << 18)) for _ in range(3)]
            lines = [clip.screen_line(clip.edge_normal(quad[i], quad[(i + 1) % 3])) for i in range(3)]
            for x, y in clip.cone_clip(lines):
                self.assertTrue(0 <= x <= clip.WIDTH and 0 <= y <= clip.HEIGHT)

    def test_code3_misses_the_view(self):
        """A point in a code3 half-space is outside the view's pyramid."""
        rng = random.Random(47)
        for _ in range(5000):
            v = (rng.randint(-5000, 5000), rng.randint(-5000, 5000), rng.randint(-5000, 5000))
            if clip.code3(v) and v[2] > 0:
                x, y, z = v
                self.assertTrue(abs(x * FX) > XC * z or abs(y * 2 * FX) > XC * z)

    def test_segment_clip_projectable(self):
        rng = random.Random(53)
        for _ in range(2000):
            a, b = [(rng.randint(-1 << 20, 1 << 20), rng.randint(-1 << 19, 1 << 19),
                     rng.randint(-1 << 18, 1 << 20)) for _ in range(2)]
            for v in clip.segment_clip(a, b):
                self.assertTrue(clip.projectable(v))

    def test_band_inside_the_guard(self):
        rng = random.Random(59)
        for _ in range(5000):
            v = (rng.randint(-1 << 22, 1 << 22), rng.randint(-1 << 21, 1 << 21), rng.randint(ZNEAR, 1 << 20))
            if clip.projectable(v):
                self.assertFalse(clip.outside_guard(v))
