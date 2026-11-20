# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns in sketches (the user, 2026-11-19: "patterns, both in sketches and regular modeling").

The sketch toolbar's Pattern button lists Rectangular Pattern, Circular Pattern and Mirror (FreeCAD's Move /
Array, Rotate / Polar and Mirror tools). They work on the sketch geometry selected first, so the button waits
for a selection; the patterns start with three elements, as Fusion's do. The model's Pattern is tested in
TestStudioModelingGui (StudioTests.gui.test_model_patterns).
"""

import FreeCADGui

from StudioTests.gui.sketch_input import INCH, settle
from StudioTests.gui.test_sketch_ways import ToolbarDrawing


class SketchPatterns(ToolbarDrawing):
    def select(self, *edges):
        for edge in edges:
            FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, edge)
        settle(300)  # the toolbar follows the selection

    def test_the_button_waits_for_geometry_to_be_selected(self):
        self.line((0, 0), (0, 1))
        settle(300)
        self.assertFalse(self.button("Pattern").isEnabled())
        self.select("Edge1")
        self.assertTrue(self.button("Pattern").isEnabled())

    def test_a_rectangular_pattern_starts_with_three(self):
        self.line((0, 0), (0, 1))
        self.select("Edge1")
        self.pick("Pattern", "Rectangular Pattern")
        self.click(0, 0)
        self.click(1, 0)  # the step from one to the next
        self.finish()
        xs = sorted(round(g.StartPoint.x / INCH, 1) for g in self.lines())
        self.assertEqual(len(xs), 3, xs)
        self.assertEqual(len(set(xs)), 3, xs)
        self.assertEqual(xs[0], 0)

    def test_a_circular_pattern_starts_with_three(self):
        self.line((1, 0), (2, 0))
        self.select("Edge1")
        self.pick("Pattern", "Circular Pattern")
        self.click(0, 0)  # center
        self.click(1.5, 0)  # from here
        self.click(0, 1.5)  # round to here
        self.finish()
        self.assertLengths([1, 1, 1])

    def test_mirror(self):
        self.line((1, 0), (2, 1))
        self.select("Edge1")
        self.pick("Pattern", "Mirror")
        self.click(0, 0.5)  # the vertical axis
        self.finish()
        self.assertEqual(len(self.lines()), 2)
        starts = sorted(g.StartPoint.x / INCH for g in self.lines())
        self.assertAlmostEqual(starts[0], -starts[1], places=6)  # mirrored about the axis exactly
        self.assertAlmostEqual(starts[1], 1, delta=self.near())  # where it was clicked
