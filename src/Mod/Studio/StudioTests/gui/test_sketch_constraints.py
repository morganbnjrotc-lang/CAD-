# SPDX-License-Identifier: LGPL-2.1-or-later
"""Constraints added while drawing (PLAN 3.3), as Fusion adds them: a line drawn nearly level is
horizontal, a line started on another's end is joined to it, and so on.

FreeCAD's sketch tools already infer these; the tests check each one in Studio with synthetic input
(StudioTests/gui/sketch_input.py). Fusion infers no "equal" either; the decisions are in docs/PLAN.md 3.3.
"""

import FreeCADGui

from StudioTests.gui.sketch_input import INCH, SketchInput, settle


class WhileDrawing(SketchInput):
    def test_a_nearly_level_line_is_horizontal(self):
        self.line((0.5, 1), (3, 1.03))  # 0.7° off level (FreeCAD: within 2°)
        self.assertEqual(self.kinds(), ["Horizontal"])
        line = self.sketch.Geometry[0]
        self.assertAlmostEqual(line.StartPoint.y, line.EndPoint.y, places=6)

    def test_a_nearly_upright_line_is_vertical(self):
        self.line((1, 0.5), (1.03, 3))
        self.assertEqual(self.kinds(), ["Vertical"])

    def test_a_slanted_line_gets_nothing(self):
        self.line((0.5, 0.5), (2.5, 1.5))
        self.assertEqual(self.kinds(), [])

    def test_a_line_started_on_another_lines_end_is_joined_to_it(self):
        self.line((0.5, 0.5), (2.5, 1.5))
        self.line((2.5, 1.5), (3, -1))
        self.assertEqual(len(self.constraints("Coincident")), 1)
        first, second = self.sketch.Geometry
        self.assertLess((first.EndPoint - second.StartPoint).Length, 1e-6)

    def test_a_line_continued_square_off_a_slanted_one_is_perpendicular(self):
        self.line((0.5, 0.5), (2.5, 1.5))  # slope 1/2
        self.line((2.5, 1.5), (2.0, 2.5))  # slope -2: square to it
        self.assertEqual(len(self.constraints("Perpendicular")), 1)

    def test_a_line_continued_along_a_slanted_one_is_parallel(self):
        self.line((0.5, 0.5), (2.5, 1.5))
        self.line((2.5, 1.5), (3.5, 2.0))
        self.assertEqual(len(self.constraints("Parallel")), 1)

    def test_a_line_started_on_another_lines_middle_is_at_its_midpoint(self):
        self.line((0, 0), (3, 0))  # horizontal, middle at (1.5, 0)
        self.line((1.5, 0), (1.5, 2))
        self.assertEqual(len(self.constraints("Symmetric")), 1, self.kinds())

    def test_a_line_ended_on_another_line_stays_on_it(self):
        self.line((0, 0), (3, 2))
        self.line((0.5, 2.5), (0.9, 0.6))  # ends on the first line, away from its ends and middle
        self.assertEqual(len(self.constraints("PointOnObject")), 1, self.kinds())

    def test_a_circle_centered_on_another_circles_center_is_concentric(self):
        self.tool("Sketcher_CreateCircle")
        self.click(1.5, 1)
        self.click(2.5, 1)
        self.finish()
        self.tool("Sketcher_CreateCircle")
        self.click(1.5, 1)  # the first circle's center
        self.click(2, 1)
        self.finish()
        self.assertEqual(len(self.constraints("Coincident")), 1, self.kinds())
        first, second = self.sketch.Geometry
        self.assertLess((first.Center - second.Center).Length, 1e-6)

    def test_a_line_ended_on_a_circle_stays_on_it(self):
        self.tool("Sketcher_CreateCircle")
        self.click(1, 1)
        self.click(2, 1)
        self.finish()
        self.line((3, 3), (1, 2))  # (1, 2) is on the circle (radius 1 around (1, 1))
        self.assertEqual(len(self.constraints("PointOnObject")), 1, self.kinds())

    def test_inches_dont_change_what_is_inferred(self):
        # The same drawing in millimeters gives the same constraints (snapping works in screen pixels).
        from studio.shell import units

        units.current().set_choice("millimeters")
        self.line((0.5, 1), (3, 1.03))
        self.assertEqual(self.kinds(), ["Horizontal"])
        self.assertAlmostEqual(self.sketch.Geometry[0].length() / INCH, 2.5, places=1)


class FullyConstrainTool(SketchInput):
    """The sketch toolbar's Fully Constrain (PLAN 3.4), on a shape drawn with the tools."""

    def test_it_fully_constrains_what_was_drawn(self):
        self.tool("Sketcher_CreateRectangle")
        self.click(0.5, 0.5)
        self.click(3, 2)
        self.finish()
        self.assertGreater(self.sketch.DoF, 0)
        FreeCADGui.runCommand("Studio_FullyConstrain", 0)
        settle(100)
        self.assertEqual(self.sketch.DoF, 0, self.kinds())
        from studio.shell import sketching

        self.assertTrue(sketching.last_message.startswith("Fully constrained"), sketching.last_message)

    def test_one_undo_takes_it_back(self):
        self.tool("Sketcher_CreateCircle")
        self.click(1, 1)
        self.click(2, 1)
        self.finish()
        drawn = len(self.sketch.Constraints)
        FreeCADGui.runCommand("Studio_FullyConstrain", 0)
        settle(100)
        self.assertGreater(len(self.sketch.Constraints), drawn)
        self.doc.undo()
        settle(100)
        self.assertEqual(len(self.sketch.Constraints), drawn)

    def test_it_is_on_the_sketch_toolbar(self):
        from studio.shell import window

        window.current().refresh()
        labels = [a.text() for a in window.current().tools.actions() if not a.isSeparator()]
        self.assertIn("Fully Constrain", labels)
