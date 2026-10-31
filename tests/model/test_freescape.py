"""tools/freescape.py: the tape, the records, and the database's checks."""
import struct
import unittest

from tests.model.common import db, needs_data
from tools import freescape


def tzx(*blocks):
    """A TZX file of standard-speed data blocks."""
    out = b"ZXTape!\x1a\x01\x14"
    for data in blocks:
        out += bytes([0x10]) + struct.pack("<HH", 1000, len(data)) + data
    return out


def with_checksum(flag, body):
    x = flag
    for b in body:
        x ^= b
    return bytes([flag]) + body + bytes([x])


class Tape(unittest.TestCase):
    def test_blocks(self):
        blocks = freescape.tzx_blocks(tzx(b"abc", b"de"))
        self.assertEqual([d for _, d in blocks], [b"abc", b"de"])

    def test_not_tzx(self):
        with self.assertRaises(ValueError):
            freescape.tzx_blocks(b"nothing like a tape")

    def test_data_block_checksum(self):
        body = bytes(range(40))
        good = [with_checksum(0, b"x")] * freescape.BLOCK + [with_checksum(0xFF, body)]
        self.assertEqual(freescape.data_block(tzx(*good)), body)
        bad = good[:-1] + [good[-1][:-1] + bytes([good[-1][-1] ^ 1])]
        with self.assertRaises(ValueError):
            freescape.data_block(tzx(*bad))


class Records(unittest.TestCase):
    def test_cuboid(self):
        rec = bytes([0x81, 1, 2, 3, 4, 5, 6, 9, 12, 0x21, 0x43, 0x65])
        o, end = freescape.parse_object(rec, 0, 0)
        self.assertEqual(end, 12)
        self.assertEqual(o["kind"], "cuboid")
        self.assertTrue(o["initially_invisible"])
        self.assertEqual((o["pos"], o["size"], o["id"]), ([1, 2, 3], [4, 5, 6], 9))
        self.assertEqual(o["colours"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(o["fcl"], "")

    def test_entrance_angles(self):
        o, _ = freescape.parse_object(bytes([0x80, 7, 1, 9, 2, 34, 0, 19, 9]), 0, 0)
        self.assertEqual(o["rotation"], [2, 34, 0])
        self.assertNotIn("size", o)

    def test_pyramid_and_fcl(self):
        rec = bytes([6, 1, 1, 1, 8, 8, 8, 5, 18, 0x21, 0x43, 0x65, 4, 4, 4, 4, 0xAA, 0xBB])
        o, end = freescape.parse_object(rec, 0, 0)
        self.assertEqual(end, 18)
        self.assertEqual(o["apex"], [4, 4, 4, 4])
        self.assertEqual(o["fcl"], "aabb")

    def test_polygon_vertices(self):
        rec = bytes([11, 0, 0, 0, 1, 1, 0, 3, 19, 0x11, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        o, _ = freescape.parse_object(rec, 0, 0)
        self.assertEqual(o["vertices"], [[1, 2, 3], [4, 5, 6], [7, 8, 9]])

    def test_sensor(self):
        rec = bytes([2, 5, 5, 5, 0, 0, 0, 15, 14, 3, 34, 0xDC, 0x0D, 2])
        o, _ = freescape.parse_object(rec, 0, 0)
        self.assertEqual(o["sensor"], {"colour": 3, "interval": 34, "range": 3548, "axes": 2})

    def test_short_fixed_part(self):
        with self.assertRaises(ValueError):
            freescape.parse_object(bytes([1, 0, 0, 0, 1, 1, 1, 1, 11, 0, 0, 0, 0]), 0, 0)


@needs_data
class Database(unittest.TestCase):
    def test_checks_pass(self):
        self.assertEqual(freescape.check(db()), [])

    def test_counts(self):
        self.assertEqual(freescape.counts(db()), freescape.EXPECTED)

    def test_steps_and_turns_are_counted_tables(self):
        t = db()["tables"]
        self.assertEqual(len(t["steps"]), 8)
        self.assertEqual(len(t["turns"]), 6)
        self.assertEqual(t["steps"], sorted(t["steps"]))
