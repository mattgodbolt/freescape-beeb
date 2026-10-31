"""The stand-ins for the other tracks' parts: the fill rule, the span buffer,
the writer's layout. They'll be replaced, so these test the interface
(docs/engine.md, section 9) as much as the code."""
import random
import unittest

from tools.model.standin import colours, maths, raster, writer
from tools.model.view import SUB, VIEW_H, VIEW_W, XC, YC, ZNEAR

W, H = SUB * VIEW_W, SUB * VIEW_H
SKY, GROUND = (0,) * 4, (99,) * 4


def coverage(lines):
    return [[p[0] for x0, x1, p in runs for _ in range(x0, x1)] for runs in lines]


class Project(unittest.TestCase):
    def test_centre(self):
        self.assertEqual(maths.project(0, 0, 5000), (XC, YC))
        x, y = maths.project(100, 100, 5000)
        self.assertGreater(x, XC)
        self.assertLess(y, YC)
        with self.assertRaises(ValueError):
            maths.project(0, 0, ZNEAR - 1)


class Raster(unittest.TestCase):
    def test_partition(self):
        rng = random.Random(5)
        for _ in range(50):
            faces = []
            for i in range(rng.randint(0, 6)):
                pts = [(rng.randint(0, W), rng.randint(0, H)) for _ in range(3)]
                faces.append(((i + 1,) * 4, pts))
            lines = raster.rasterise(faces, SKY, GROUND)
            self.assertEqual(len(lines), VIEW_H)
            for runs in lines:
                at = 0
                for x0, x1, _ in runs:
                    self.assertEqual(x0, at)
                    self.assertLess(x0, x1)
                    at = x1
                self.assertEqual(at, VIEW_W)

    def test_pixel_square(self):
        # A square on pixel edges covers exactly its pixels.
        sq = [(16, 32), (48, 32), (48, 64), (16, 64)]
        cov = coverage(raster.rasterise([((5,) * 4, sq)], SKY, GROUND))
        got = {(x, y) for y in range(VIEW_H) for x in range(VIEW_W) if cov[y][x] == 5}
        self.assertEqual(got, {(1, 2), (2, 2), (1, 3), (2, 3)})

    def test_shared_edges_cover_once(self):
        # Triangles fanned round a point tile their hull: every pixel centre
        # inside goes to exactly one of them (the top-left rule).
        rng = random.Random(6)
        for _ in range(30):
            c = (rng.randint(0, W), rng.randint(0, H))
            ring = [(0, 0), (W // 2, 0), (W, 0), (W, H // 3), (W, H), (0, H), (0, H // 2)]
            count = [[0] * VIEW_W for _ in range(VIEW_H)]
            for i in range(len(ring)):
                tri = [c, ring[i], ring[(i + 1) % len(ring)]]
                for y in range(VIEW_H):
                    s = raster.span(tri, y)
                    if s:
                        for x in range(*s):
                            count[y][x] += 1
            self.assertTrue(all(v == 1 for row in count for v in row))

    def test_front_to_back(self):
        near = [(0, 0), (W, 0), (W, H // 2)]
        far = [(0, 0), (W, 0), (W, H), (0, H)]
        cov = coverage(raster.rasterise([((1,) * 4, near), ((2,) * 4, far)], SKY, GROUND))
        self.assertEqual(cov[0][VIEW_W - 1], 1)
        self.assertEqual(cov[VIEW_H - 1][0], 2)

    def test_horizon(self):
        # Level: sky above the middle line, ground below.
        cov = coverage(raster.rasterise([], SKY, GROUND, ((0, H // 2), (1, 0))))
        self.assertEqual(cov[0][0], 0)
        self.assertEqual(cov[VIEW_H - 1][0], 99)


class Writer(unittest.TestCase):
    def test_layout_and_masks(self):
        a, b = colours.solid(1), colours.solid(2)
        lines = [[(0, 3, a), (3, VIEW_W, b)]] * VIEW_H
        view = writer.write(lines)
        self.assertEqual(len(view), writer.LENGTH)
        self.assertEqual(view[writer.address(9, 0)], a[1])
        # Pixel 3 is the right of byte 1: left from a, right from b.
        self.assertEqual(view[writer.address(9, 1)], (a[1] & 0xAA) | (b[1] & 0x55))
        pix = writer.decode(view)
        self.assertEqual(pix[9][:5], [1, 1, 1, 2, 2])

    def test_rejects_gaps(self):
        with self.assertRaises(ValueError):
            writer.write([[(0, 5, SKY)]] * VIEW_H)

    def test_mode2(self):
        self.assertEqual(colours.mode2(15, 0), 0xAA)
        self.assertEqual(colours.mode2(0, 15), 0x55)
        self.assertEqual(writer.pixel_colours(colours.mode2(5, 10)), (5, 10))
