"""tools/model/render.py over Driller's entrance views: the whole pipeline,
and the properties the counts rest on."""
import dataclasses
import unittest

from tests.model.common import db, needs_data
from tools.model import camera, clip, counts, render
from tools.model.view import SUB, VIEW_H, VIEW_W


@needs_data
class Views(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = [(a, e, c, render.render(db(), a, c, check=True))
                     for a, e, c in camera.entrance_views(db())]

    def test_every_view(self):
        self.assertEqual(len(self.views), 65)
        for _, _, _, v in self.views:
            self.assertEqual(set(v.counts), set(counts.KEYS))
            self.assertEqual(len(v.lines), VIEW_H)

    def test_faces_inside_the_view(self):
        for _, _, _, v in self.views:
            for f in v.faces:
                for x, y in f.poly:
                    self.assertTrue(0 <= x <= SUB * VIEW_W and 0 <= y <= SUB * VIEW_H)

    def test_order_holds_the_drawn(self):
        for _, _, _, v in self.views:
            self.assertEqual(sorted(v.order), sorted({f.id for f in v.faces}))
            self.assertEqual(len(v.order), v.counts["drawn"])

    def test_coarse_cull_is_conservative(self):
        """Without the coarse cull, every view is the same: it only ever
        throws away what would have drawn nothing. Turned, too."""
        for a, _, c, v in self.views[::4]:
            for yaw in range(0, 72, 9):
                for pitch, roll in ((0, 0), (64, 0), (9, 63)):
                    cc = dataclasses.replace(c, yaw=yaw, pitch=pitch, roll=roll)
                    culled = render.render(db(), a, cc)
                    whole = render.render(db(), a, cc, cull=False)
                    self.assertEqual(culled.bytes, whole.bytes)
                    self.assertEqual([f.poly for f in culled.faces], [f.poly for f in whole.faces])

    def test_object_cull(self):
        """The candidates passed over as beyond the view's sides
        (render.OBJECT_CULL) draw no pixel, over the entrance views turned:
        each view's bytes are the same without the cull; and some are."""
        passed = 0
        saved = render.OBJECT_CULL
        try:
            for a, _, c, v in self.views[::4]:
                for yaw in range(0, 72, 9):
                    for pitch, roll in ((0, 0), (64, 0), (9, 63)):
                        cc = dataclasses.replace(c, yaw=yaw, pitch=pitch, roll=roll)
                        render.OBJECT_CULL = True
                        on = render.render(db(), a, cc)
                        render.OBJECT_CULL = False
                        off = render.render(db(), a, cc)
                        self.assertEqual(on.bytes, off.bytes)
                        passed += off.counts["faces_seen"] - on.counts["faces_seen"]
        finally:
            render.OBJECT_CULL = saved
        self.assertGreater(passed, 0)

    def test_bounds_miss_the_view(self):
        """Each of render.BOUNDS is non-negative everywhere in the view's
        pyramid: at its corners' rays, so on every ray between."""
        from tools.model.view import FX, FY, XC, YC
        for sx in (-XC, XC):
            for sy in (-YC, YC):
                ray = (sx * FY, sy * FX, FX * FY)      # (x, y, z) through the corner, z > 0
                for f in render.BOUNDS:
                    self.assertGreater(f(*ray), 0)

    def test_near_clip_used(self):
        self.assertTrue(any(f.near_clipped for _, _, _, v in self.views for f in v.faces))
        for _, _, _, v in self.views:
            for f in v.faces:
                self.assertGreaterEqual(len(f.poly), 3)

    def test_start_view(self):
        """The start view draws what the original draws there, far to near
        (its draw list, read from the ZX: docs/research/zx-driller.md)."""
        start = [v for a, e, _, v in self.views
                 if a["id"] == db()["start_area"] and e["id"] == db()["start_entrance"]]
        self.assertEqual(start[0].order, [1, 4, 15, 24, 14, 11, 20])


class Rounding(unittest.TestCase):
    def test_clip_rounds_to_integers(self):
        out = clip.near_clip([(1, 1, 0), (2, 2, 1000)])
        self.assertTrue(all(isinstance(c, int) for v in out for c in v))
