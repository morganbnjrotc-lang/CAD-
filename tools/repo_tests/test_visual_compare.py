# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the screenshot comparison of Studio's visual baselines (tools/test/visual_compare.py).
No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

A screenshot matches its baseline when no more than a small share of pixels differ by more than a
small tolerance (FreeCAD's own snapshot tests use 8 per channel and 0.2 %), ignoring masked areas
(the 3D view, whose OpenGL drawing differs between graphics cards).
"""

import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "test"))

import visual_compare  # noqa: E402


def screen(color=(240, 242, 245), size=(100, 200)):
    image = np.zeros((*size, 3), dtype=np.uint8)
    image[:] = color
    return image


class Compare(unittest.TestCase):
    def test_the_same_picture_matches(self):
        result = visual_compare.compare(screen(), screen())
        self.assertTrue(result.ok)
        self.assertEqual(result.mismatch_pct, 0.0)

    def test_small_differences_within_the_tolerance_match(self):
        actual = screen()
        actual[:, :, 0] += 5  # e.g. a different anti-aliasing of text edges
        self.assertTrue(visual_compare.compare(actual, screen()).ok)

    def test_a_changed_area_fails_and_shows_where(self):
        actual = screen()
        actual[10:30, 10:40] = (30, 30, 30)  # a 20x30 dark box: 3 % of 100x200
        result = visual_compare.compare(actual, screen())
        self.assertFalse(result.ok)
        self.assertAlmostEqual(result.mismatch_pct, 3.0)
        self.assertEqual(result.diff.shape, actual.shape)
        self.assertTrue((result.diff[15, 20] != result.diff[90, 190]).any())  # marked vs. unmarked

    def test_a_few_stray_pixels_are_allowed(self):
        actual = screen()
        actual[0, 0:20] = (0, 0, 0)  # 20 of 20,000 pixels: 0.1 %
        self.assertTrue(visual_compare.compare(actual, screen()).ok)

    def test_masked_areas_are_ignored(self):
        actual = screen()
        actual[10:60, 50:150] = (90, 10, 10)  # the 3D view drew differently
        masks = [(50, 10, 100, 50)]  # x, y, width, height
        self.assertTrue(visual_compare.compare(actual, screen(), masks).ok)
        self.assertFalse(visual_compare.compare(actual, screen()).ok)

    def test_a_different_size_fails(self):
        result = visual_compare.compare(screen(size=(100, 200)), screen(size=(100, 180)))
        self.assertFalse(result.ok)
        self.assertIn("size", result.reason)


class Files(unittest.TestCase):
    def test_png_round_trip(self):
        import tempfile

        picture = screen((12, 34, 56))
        picture[5, 7] = (200, 100, 50)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shot.png"
            visual_compare.save(picture, path)
            again = visual_compare.load(path)
        self.assertTrue((again == picture).all())


if __name__ == "__main__":
    unittest.main()
