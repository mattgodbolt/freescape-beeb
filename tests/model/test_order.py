"""tools/model/order.py: the original's sort.

Checked against a second transcription that follows Castle Master II's Z80
step by step (L9c2d_sort_objects_for_rendering: 16-bit subtractions and
their sign bits), on random lists with many ties and overlaps."""
import random
import unittest

from tools.model import order


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def neg(v):
    return s16(v) < 0


def cm2_axis(b1c1, b1c2, b2c1, b2c2):
    """One axis of CM2's L9c66 loop: 1 if object 1 is closer, 2 if object 2,
    0 for none."""
    if neg(b1c1 - b2c2):                       # jp p not taken
        if neg(b2c1 - b1c2):                   # jp m: overlap
            return 0
    e = neg(b1c1)
    if neg(b1c2) != e:
        return 1
    d = neg(b2c1)
    if neg(b2c2) != d:
        return 2
    if d != e:
        return 0
    diff = s16(b2c1 - b1c1)
    if diff != 0:
        return 1 if neg(diff) == neg(b2c1) else 2
    diff = s16(b2c2 - b1c2)
    return 2 if neg(diff) != neg(b2c2) else 1


KEEP = {0x20, 0x08, 0x02, 0x28, 0x0A, 0x22, 0x2A}


def cm2_sort(boxes):
    out = list(range(len(boxes)))
    n = len(out)
    passes = n
    while True:
        passes -= 1
        if passes <= 0:
            return out
        changed = False
        for j in range(n - 1):
            a, b = boxes[out[j]], boxes[out[j + 1]]
            r = 0
            for k in range(3):
                r = (r << 2) | cm2_axis(a[0][k], a[1][k], b[0][k], b[1][k])
            if r in KEEP:
                continue
            out[j], out[j + 1] = out[j + 1], out[j]
            changed = True
        if not changed:
            return out


class Axis(unittest.TestCase):
    def test_cases(self):
        f, s, n = order.FIRST, order.SECOND, order.INCOMPARABLE
        self.assertEqual(order.compare_axis(1, 5, 3, 9), n)       # overlap
        self.assertEqual(order.compare_axis(-2, 2, 5, 9), f)      # first straddles
        self.assertEqual(order.compare_axis(5, 9, -2, 0), s)      # second straddles (max 0)
        self.assertEqual(order.compare_axis(-9, -5, 5, 9), n)     # opposite sides
        self.assertEqual(order.compare_axis(2, 4, 4, 9), f)       # touching, first nearer
        self.assertEqual(order.compare_axis(-9, -6, -5, -1), s)   # both below, second nearer
        self.assertEqual(order.compare_axis(3, 3, 3, 3), f)       # a tie

    def test_keep(self):
        self.assertTrue(order.keep(0b100000))
        self.assertTrue(order.keep(0b101010))
        self.assertFalse(order.keep(0))
        self.assertFalse(order.keep(0b100001))


class AgainstCM2(unittest.TestCase):
    def test_random_lists(self):
        rng = random.Random(4)
        for _ in range(3000):
            n = rng.randint(1, 14)
            span = rng.choice([4, 64, 3000])
            boxes = []
            for _ in range(n):
                lo = [rng.randint(-span, span) for _ in range(3)]
                hi = [lo[k] + rng.randint(0, span) for k in range(3)]
                boxes.append((tuple(lo), tuple(hi)))
            ours, _ = order.sort(range(n), lambda i: boxes[i], (0, 0, 0))
            self.assertEqual(list(ours), cm2_sort(boxes))

    def test_camera_relative(self):
        boxes = [((10, 0, 0), (20, 1, 1)), ((30, 0, 0), (40, 1, 1))]
        near_first, _ = order.sort([0, 1], lambda i: boxes[i], (100, 0, 0))
        self.assertEqual(near_first, [0, 1])       # the farther first: 0, then 1
        far_first, _ = order.sort([0, 1], lambda i: boxes[i], (0, 0, 0))
        self.assertEqual(far_first, [1, 0])
