"""tools/model/clip.py: the near plane in 3D, the view's rectangle in 2D."""
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
    def test_edges(self):
        z = 10000
        # Exactly on the left edge is inside; a unit left of it is out.
        x = -XC * z // FX
        self.assertEqual(clip.outcode((x, 0, z)) & clip.LEFT, 0 if XC * z + FX * x >= 0 else clip.LEFT)
        self.assertEqual(clip.outcode((-z, 0, z)), clip.LEFT)
        self.assertEqual(clip.outcode((z, 0, z)), clip.RIGHT)
        self.assertEqual(clip.outcode((0, z, z)), clip.TOP)
        self.assertEqual(clip.outcode((0, -z, z)), clip.BOTTOM)
        self.assertEqual(clip.outcode((0, 0, ZNEAR - 1)), clip.NEAR)


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
                # within the band, give or take the rounding of a new vertex
                self.assertLessEqual(abs(x), clip.GUARD_X * z + clip.GUARD_X)
                self.assertLessEqual(abs(y), clip.GUARD_Y * z + clip.GUARD_Y)
                sx, sy = parts.project(x, y, z)
                self.assertLess(abs(sx), (1 << 15) - 1)
                self.assertLess(abs(sy), (1 << 15) - 1)
