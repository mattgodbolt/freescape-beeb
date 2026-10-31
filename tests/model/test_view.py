"""tools/model/view.py and camera.py: the constants, and where an entrance
puts the camera."""
import unittest

from tests.model.common import db, needs_data
from tools.model import camera, view


class Constants(unittest.TestCase):
    def test_defs(self):
        d = view.read_defs()
        self.assertEqual(view.VIEW_W, d["VIEW_W"])
        self.assertEqual(view.VIEW_BYTES * 2, view.VIEW_W)
        self.assertEqual(view.SCREEN_ROW, 8 * d["SCREEN_COLS"])

    def test_centre(self):
        self.assertEqual((view.XC, view.YC), (view.SUB * view.VIEW_W // 2, view.SUB * view.VIEW_H // 2))

    def test_evaluate(self):
        self.assertEqual(view._evaluate("(&8000 - A) DIV B MOD 7", {"A": 0x4000, "B": 512}), 32 % 7)


@needs_data
class Original(unittest.TestCase):
    def test_focal_lengths_are_the_originals(self):
        """FX and FY are the original's field of view on this view: its
        scaling diagonal folded into the focal lengths, rounded."""
        fx, fy = view.focal_lengths(db()["tables"]["scale"])
        self.assertEqual((view.FX, view.FY), (round(fx), round(fy)))

    def test_centre_is_the_originals_at_half_width(self):
        cx, cy = db()["tables"]["centre"]
        self.assertEqual((view.XC, view.YC), (view.SUB * cx // 2, view.SUB * cy))


class Camera(unittest.TestCase):
    def test_eye(self):
        self.assertEqual(camera.eye_height(1), 96)
        self.assertEqual(camera.eye_height(4, level=1), 4 * 64 - 32)

    def test_from_entrance(self):
        area = {"scale": 1}
        ent = {"pos": [72, 1, 92], "rotation": [0, 34, 0]}
        c = camera.from_entrance(area, ent)
        self.assertEqual((c.x, c.y, c.z, c.pitch, c.yaw, c.roll), (4640, 160, 5920, 0, 34, 0))

    def test_limits(self):
        with self.assertRaises(ValueError):
            camera.Camera(-1, 0, 0)
        with self.assertRaises(ValueError):
            camera.Camera(0, 0, 0, yaw=72)


@needs_data
class Entrances(unittest.TestCase):
    def test_every_entrance(self):
        views = list(camera.entrance_views(db()))
        self.assertEqual(len(views), 65)
        start = [c for a, e, c in views if a["id"] == db()["start_area"] and e["id"] == db()["start_entrance"]]
        # The start as the original's panel shows it (docs/research/zx-driller.md).
        self.assertEqual([(c.x, c.y, c.z) for c in start], [(4640, 160, 5920)])
