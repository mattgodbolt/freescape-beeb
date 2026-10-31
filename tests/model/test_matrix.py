"""tools/model/matrix.py: the camera's matrix."""
import math
import unittest

from tests.model.common import sine_tables
from tools.model import matrix
from tools.model.camera import Camera

T = sine_tables()
IDENTITY = ((64, 0, 0), (0, 64, 0), (0, 0, 64))


def m(yaw=0, pitch=0, roll=0):
    return matrix.rotation(Camera(0, 0, 0, yaw, pitch, roll), T)


class Matrix(unittest.TestCase):
    def test_identity(self):
        self.assertEqual(m(), IDENTITY)

    def test_identity_composes_exactly(self):
        for a in range(72):
            y = matrix.yaw_matrix(a, T["sin"], T["cos"])
            self.assertEqual(matrix.compose(IDENTITY, y), y)

    def test_yaw_looks_along(self):
        # Yaw 0 looks along +z, yaw 18 along +x; camera x is screen right.
        self.assertEqual(m(yaw=18)[2], (64, 0, 0))
        self.assertEqual(m(yaw=18)[0], (0, 0, -64))
        self.assertEqual(m(yaw=36)[2], (0, 0, -64))

    def test_pitch_down_is_positive(self):
        # Pitched 90 degrees down, ahead is -y.
        self.assertEqual(m(pitch=18)[2], (0, -64, 0))

    def test_roll(self):
        # Rolled left 90 degrees, the camera's x (screen right) is world up.
        self.assertEqual(m(roll=18)[0], (0, 64, 0))

    def test_rounding_half_up(self):
        a = ((1, 0, 0), (0, 0, 0), (0, 0, 0))
        b = ((32, 0, 0), (0, 0, 0), (0, 0, 0))
        self.assertEqual(matrix.compose(a, b)[0][0], 1)       # 32/64 rounds up
        b = ((-32, 0, 0), (0, 0, 0), (0, 0, 0))
        self.assertEqual(matrix.compose(a, b)[0][0], 0)       # -32/64 rounds up too
        b = ((-33, 0, 0), (0, 0, 0), (0, 0, 0))
        self.assertEqual(matrix.compose(a, b)[0][0], -1)

    def test_near_orthonormal(self):
        for yaw in range(0, 72, 5):
            for pitch in range(0, 72, 7):
                for roll in (0, 9, 63):
                    r = m(yaw, pitch, roll)
                    for i in range(3):
                        self.assertLess(abs(math.hypot(*r[i]) - 64), 2.5)
                        for j in range(i + 1, 3):
                            self.assertLess(abs(sum(r[i][k] * r[j][k] for k in range(3))), 150)
