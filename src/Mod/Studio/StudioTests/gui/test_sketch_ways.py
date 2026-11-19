# SPDX-License-Identifier: LGPL-2.1-or-later
"""More ways to draw each shape (PLAN 3.12): picked from the drop-down under a sketch tool on Studio's
toolbar, as in Fusion and Inventor, and drawn with synthetic clicks (StudioTests.gui.sketch_input)."""

import math

import StudioGui
from StudioTests.gui.sketch_input import INCH, SketchInput, settle
from studio.shell import window


def tools():
    return window.current()


class DrawingWays(SketchInput):
    def setUp(self):
        super().setUp()
        settle(200)  # the toolbar follows the sketch being edited
        for tool in ("Sketcher_CreateRectangle", "Sketcher_CreateCircle"):
            self.addCleanup(tools().choose_way, tool, 0)

    def button(self, label):
        button = tools().tool_widget(label)
        self.assertIsNotNone(button, f"no {label} button on the toolbar")
        return button

    def pick(self, label, way):
        menu = self.button(label).menu()
        self.assertIsNotNone(menu, f"{label} has no list of ways")
        action = next((a for a in menu.actions() if a.text() == way), None)
        self.assertIsNotNone(action, f"{label} has no {way}: {[a.text() for a in menu.actions()]}")
        action.trigger()
        settle(400)

    def lines(self):
        return [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomLineSegment"]

    def lengths(self):
        return sorted(g.length() / INCH for g in self.lines())

    def near(self):
        """How far off clicked sizes can be, in inches: a click lands on a pixel (the view shows 8 in)."""
        return 2 * 8 / StudioGui.view_size()[1]

    def assertLengths(self, expected):
        lengths = self.lengths()
        self.assertEqual(len(lengths), len(expected), lengths)
        for got, wanted in zip(lengths, sorted(expected)):
            self.assertAlmostEqual(got, wanted, delta=self.near(), msg=f"{lengths} != {sorted(expected)}")

    def test_the_rectangle_lists_its_ways(self):
        self.assertEqual([a.text() for a in self.button("Rectangle").menu().actions()],
                         ["2-Point Rectangle", "Center Rectangle", "3-Point Rectangle", "3-Point Center Rectangle",
                          "Rounded Rectangle"])

    def test_a_center_rectangle(self):
        self.pick("Rectangle", "Center Rectangle")
        self.click(1, 1)  # center
        self.click(2.5, 2)  # corner
        self.finish()
        self.assertLengths([2, 2, 3, 3])
        xs = [p.x / INCH for g in self.lines() for p in (g.StartPoint, g.EndPoint)]
        self.assertAlmostEqual((min(xs) + max(xs)) / 2, 1, delta=self.near())

    def test_a_3_point_rectangle_is_turned_along_its_first_side(self):
        self.pick("Rectangle", "3-Point Rectangle")
        self.click(0, 0)
        self.click(2, 1)  # the first side
        self.click(1.5, 2)  # how wide
        self.finish()
        side, width = math.hypot(2, 1), (2 * 2 - 1 * 1.5) / math.hypot(2, 1)
        self.assertLengths([side, side, width, width])

    def test_a_3_point_circle(self):
        self.pick("Circle", "3-Point Circle")
        self.click(0, 1)
        self.click(2, 1)
        self.click(1, 2)
        self.finish()
        circles = [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomCircle"]
        self.assertEqual(len(circles), 1)
        self.assertAlmostEqual(circles[0].Radius / INCH, 1, delta=self.near())

    def test_the_button_draws_the_way_picked_last(self):
        self.pick("Rectangle", "Center Rectangle")
        self.finish()
        settle(300)
        self.assertTrue(self.button("Rectangle").toolTip().startswith("Center Rectangle"))
        self.button("Rectangle").click()
        settle(400)
        self.click(1, 1)
        self.click(2.5, 2)
        self.finish()
        self.assertLengths([2, 2, 3, 3])
