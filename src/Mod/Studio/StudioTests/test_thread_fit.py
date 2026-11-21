# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar's Fit box (PLAN 3.9, the allowance scrubber): studio.viewmodels.thread_fit.

A threaded hole picked shows Fit on the toolbar: how much bigger (+) or smaller (-) the hole is made than
standard, for 3D-printed parts. Scrolling over it steps it in the user's units; the hole stores it in mm.
"""

import unittest

from studio.viewmodels.thread_fit import FitBox


class FitBoxRules(unittest.TestCase):
    def test_millimeters_step_by_five_hundredths(self):
        box = FitBox("millimeters")
        self.assertEqual((box.suffix, box.decimals), (" mm", 2))
        self.assertAlmostEqual(box.step, 0.05)
        self.assertAlmostEqual(box.limit, 2.0)

    def test_inches_step_by_two_thousandths(self):
        box = FitBox("inches")
        self.assertEqual((box.suffix, box.decimals), (" in", 3))
        self.assertAlmostEqual(box.step, 0.002)
        self.assertAlmostEqual(box.limit, 0.08)

    def test_shown_in_the_units(self):
        self.assertAlmostEqual(FitBox("inches").shown(0.254), 0.01)
        self.assertAlmostEqual(FitBox("millimeters").shown(0.2), 0.2)

    def test_stored_in_mm(self):
        self.assertAlmostEqual(FitBox("inches").mm(0.01), 0.254)
        self.assertAlmostEqual(FitBox("millimeters").mm(-0.1), -0.1)

    def test_says_what_it_does(self):
        box = FitBox("millimeters")
        self.assertEqual(box.label, "Fit")
        self.assertIn("scroll", box.tooltip.lower())
        self.assertIn("3D", box.tooltip)

    def test_text_has_a_sign_and_the_unit(self):
        self.assertEqual(FitBox("millimeters").text(0.1), "+0.10 mm")
        self.assertEqual(FitBox("millimeters").text(-0.05), "-0.05 mm")
        self.assertEqual(FitBox("millimeters").text(0), "0.00 mm")
        self.assertEqual(FitBox("inches").text(0.1016), "+0.004 in")

    def test_a_notch_is_a_step(self):
        box = FitBox("millimeters")
        self.assertAlmostEqual(box.stepped(0, 1), 0.05)
        self.assertAlmostEqual(box.stepped(0.1, -3), -0.05)
        inches = FitBox("inches")
        self.assertAlmostEqual(inches.stepped(0, 2), 0.004 * 25.4)

    def test_steps_land_on_the_units_grid(self):
        # 0.0508 mm is 0.002 in: in millimeters it shows 0.05 and steps from there
        self.assertAlmostEqual(FitBox("millimeters").stepped(0.0508, 1), 0.1)

    def test_steps_stop_at_the_limit(self):
        self.assertAlmostEqual(FitBox("millimeters").stepped(1.98, 5), 2.0)
        self.assertAlmostEqual(FitBox("millimeters").stepped(-1.98, -5), -2.0)

    def test_reading_a_typed_fit(self):
        mm, inches = FitBox("millimeters"), FitBox("inches")
        self.assertAlmostEqual(mm.read("0.1"), 0.1)
        self.assertAlmostEqual(mm.read("+0.15 mm"), 0.15)
        self.assertAlmostEqual(mm.read("-0.1mm"), -0.1)
        self.assertAlmostEqual(inches.read("0.004"), 0.1016)
        self.assertAlmostEqual(inches.read("0.2 mm"), 0.2)  # typed with a unit: that unit
        self.assertAlmostEqual(mm.read("0.004 in"), 0.1016)
        self.assertAlmostEqual(mm.read("0.01\""), 0.254)

    def test_a_typed_fit_beyond_the_limit_is_the_limit(self):
        self.assertAlmostEqual(FitBox("millimeters").read("5"), 2.0)

    def test_nonsense_is_not_a_fit(self):
        for text in ("", "abc", "0.1 ft2", "1..2"):
            self.assertIsNone(FitBox("millimeters").read(text), text)

    def test_unknown_units_are_an_error(self):
        with self.assertRaises(KeyError):
            FitBox("cubits")
