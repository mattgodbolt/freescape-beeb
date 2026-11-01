"""tools/model/objects.py: shapes, which faces are seen, the coarse cull."""
import unittest

from tests.model.common import db, needs_data, sine_tables
from tools.model import matrix, objects
from tools.model.camera import Camera


def obj(t, pos, size, colours=None, **kw):
    o = {"type": t, "id": 1, "pos": list(pos), "size": list(size),
         "initially_invisible": False, "colours": colours or [1] * 6}
    o.update(kw)
    return o


def seen(shape, c):
    return sorted(f.colour for f in shape.faces if f.seen_from(c))


class Cuboid(unittest.TestCase):
    s = objects.shape(obj(1, (10, 10, 10), (2, 3, 4), [1, 2, 3, 4, 5, 6]))

    def test_slab(self):
        self.assertEqual(seen(self.s, (0, 700, 700)), [1])           # below x: -x
        self.assertEqual(seen(self.s, (2000, 700, 700)), [2])        # above x: +x
        self.assertEqual(seen(self.s, (0, 0, 0)), [1, 3, 5])
        self.assertEqual(seen(self.s, (2000, 2000, 2000)), [2, 4, 6])
        # On the face's plane, it isn't seen.
        self.assertEqual(seen(self.s, (640, 700, 700)), [])

    def test_flat(self):
        s = objects.shape(obj(1, (0, 0, 0), (5, 0, 5), [1, 2, 3, 4, 5, 6]))
        self.assertEqual(sorted(f.colour for f in s.faces), [3, 4])

    def test_colour_zero(self):
        s = objects.shape(obj(1, (0, 0, 0), (1, 1, 1), [0, 0, 0, 4, 0, 0]))
        self.assertEqual(len(s.faces), 1)
        self.assertIsNone(objects.shape(obj(1, (0, 0, 0), (1, 1, 1), [0] * 6)))


class Flat(unittest.TestCase):
    def test_rectangle_sides(self):
        s = objects.shape(obj(3, (5, 0, 5), (0, 4, 4), [7, 9]))
        self.assertEqual(seen(s, (0, 100, 400)), [7])
        self.assertEqual(seen(s, (1000, 100, 400)), [9])

    def test_rectangle_line(self):
        s = objects.shape(obj(3, (5, 0, 5), (0, 4, 0), [2, 2]))
        self.assertTrue(s.line)
        self.assertEqual(s.vertices, [(320, 0, 320), (320, 256, 320)])

    def test_polygon_sides(self):
        # Anticlockwise seen from +z: colour 1 from +z, colour 0 from -z.
        tri = obj(11, (0, 0, 0), (2, 2, 0), [4, 5], vertices=[[0, 0, 1], [2, 0, 1], [0, 2, 1]])
        s = objects.shape(tri)
        self.assertEqual(seen(s, (10, 10, 500)), [5])
        self.assertEqual(seen(s, (10, 10, 0)), [4])

    def test_sensor(self):
        s = objects.shape({"type": 2, "id": 3, "pos": [5, 5, 56], "size": [0, 0, 0],
                           "initially_invisible": False,
                           "sensor": {"colour": 3, "interval": 34, "range": 3548, "axes": 2}})
        self.assertTrue(s.point)
        self.assertTrue(objects.sensor_watching(s, (2464, 352, 4192)))
        # The wrong side of its axis bits, or out of range.
        self.assertFalse(objects.sensor_watching(s, (100, 352, 4192)))
        self.assertFalse(objects.sensor_watching(s, (6000, 352, 4192)))


class Pyramids(unittest.TestCase):
    def check_outward(self, s):
        """Every face's normal points away from the shape's middle."""
        n = len(s.vertices)
        mid = [sum(v[k] for v in s.vertices) / n for k in range(3)]
        for f in s.faces:
            v = s.vertices[f.loop[0]]
            d = sum(f.normal[k] * (mid[k] - v[k]) for k in range(3))
            self.assertLess(d, 0, "face %r of %r" % (f, s.obj))

    def test_every_orientation(self):
        for t in range(4, 10):
            for apex in ([1, 1, 3, 3], [0, 0, 4, 4], [2, 2, 2, 2], [0, 2, 4, 2]):
                s = objects.shape(obj(t, (10, 10, 10), (4, 4, 4), [1, 2, 3, 4, 5, 6], apex=apex))
                self.check_outward(s)

    def test_point_apex(self):
        s = objects.shape(obj(6, (0, 0, 0), (8, 8, 8), [1, 2, 3, 4, 5, 6], apex=[4, 4, 4, 4]))
        # Four triangles and the base: the apex face has no area.
        self.assertEqual(sorted(len(f.loop) for f in s.faces), [3, 3, 3, 3, 4])

    @needs_data
    def test_driller(self):
        for a in db()["areas"]:
            for o in a["objects"]:
                if 4 <= o["type"] <= 9:
                    self.check_outward(objects.shape(o))


class Cull(unittest.TestCase):
    def test_behind(self):
        t = sine_tables()
        c = Camera(4000, 100, 4000, yaw=0)
        m = matrix.rotation(c, t)
        behind = ((0, 0, 0), (8000, 640, 3990))
        ahead = ((0, 0, 0), (8000, 640, 4100))
        self.assertTrue(objects.coarse_cull(behind, m, c.position))
        self.assertFalse(objects.coarse_cull(ahead, m, c.position))

    def test_hidden(self):
        self.assertFalse(objects.shown({"id": 1, "initially_invisible": True}))
        self.assertTrue(objects.shown({"id": 1, "initially_invisible": True}, {1: True}))


@needs_data
class Windings(unittest.TestCase):
    def test_loops_anticlockwise(self):
        """Every face's loop winds anticlockwise about its outward normal
        (the cone, clip.py, takes it so)."""
        for area in db()["areas"]:
            for o in area["objects"] + db()["globals"]:
                s = objects.shape(o)
                if s is None or s.line or s.point:
                    continue
                for f in s.faces:
                    n = objects.newell([s.vertices[i] for i in f.loop])
                    self.assertGreater(sum(a * b for a, b in zip(n, f.normal)), 0, (o["id"], f.loop))
