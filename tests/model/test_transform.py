"""tools/model/transform.py: exact, so its cached and corner-and-edge forms
equal the direct one."""
import random
import unittest

from tests.model.common import sine_tables
from tools.model import matrix, transform
from tools.model.camera import Camera

T = sine_tables()


class Transform(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(1)

    def camera(self):
        r = self.rng
        return Camera(r.randrange(8192), r.randrange(4096), r.randrange(8192),
                      r.randrange(72), r.randrange(72), r.randrange(72))

    def test_cached_equals_direct(self):
        for _ in range(200):
            c = self.camera()
            m = matrix.rotation(c, T)
            mc = transform.mul(m, c.position)
            for _ in range(8):
                v = tuple(64 * self.rng.randrange(128) for _ in range(3))
                self.assertEqual(transform.cached(transform.mul(m, v), mc),
                                 transform.transform(m, v, c.position))

    def test_cuboid_equals_direct(self):
        for _ in range(200):
            c = self.camera()
            m = matrix.rotation(c, T)
            lo = tuple(64 * self.rng.randrange(100) for _ in range(3))
            size = tuple(64 * self.rng.randrange(28) for _ in range(3))
            got = transform.cuboid(m, lo, size, c.position)
            for i in range(8):
                v = tuple(lo[k] + (size[k] if i >> k & 1 else 0) for k in range(3))
                self.assertEqual(got[i], transform.transform(m, v, c.position))

    def test_fits_24_bits(self):
        # The farthest corner of the world from a camera at the other.
        m = matrix.rotation(Camera(0, 0, 0, 9, 9, 9), T)
        transform.transform(m, (127 * 64, 99 * 64, 127 * 64), (0, 0, 0))
        with self.assertRaises(OverflowError):
            transform.check24((1 << 23,))
