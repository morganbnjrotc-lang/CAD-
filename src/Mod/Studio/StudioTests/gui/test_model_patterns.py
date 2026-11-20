# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns in the model (the user, 2026-11-19: "patterns, both in sketches and regular modeling").

The toolbar's Pattern button lists Rectangular Pattern, Circular Pattern and Mirror (Part Design's Linear
Pattern, Polar Pattern and Mirrored). With nothing selected it patterns the whole part; with a feature
picked in the model tree, that feature.
"""

import FreeCADGui

from StudioTests.gui.sketch_input import settle
from StudioTests.gui.test_extrude import Extruding
from studio.shell import window


class ModelPatterns(Extruding):
    def setUp(self):
        super().setUp()
        self.addCleanup(window.current().choose_way, "PartDesign_LinearPattern", 0)
        self.pad = self.extrude("1{Return}")
        FreeCADGui.Selection.clearSelection()
        settle(300)  # the toolbar follows the selection

    def pick(self, way):
        button = window.current().tool_widget("Pattern")
        self.assertIsNotNone(button, "no Pattern button on the toolbar")
        self.assertTrue(button.isEnabled(), "Pattern is off with a part to pattern")
        action = next((a for a in button.menu().actions() if a.text() == way), None)
        self.assertIsNotNone(action, [a.text() for a in button.menu().actions()])
        action.trigger()
        settle(600)

    def made(self, type_id):
        return [o for o in self.doc.Objects if o.TypeId == type_id]

    def test_with_nothing_selected_the_whole_part_is_patterned(self):
        self.pick("Rectangular Pattern")
        patterns = self.made("PartDesign::LinearPattern")
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].TransformMode, "Whole shape")

    def test_a_feature_picked_in_the_tree_is_patterned(self):
        FreeCADGui.Selection.addSelection(self.pad)
        settle(300)
        self.pick("Circular Pattern")
        patterns = self.made("PartDesign::PolarPattern")
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].Originals, [self.pad])

    def test_mirror(self):
        self.pick("Mirror")
        self.assertEqual(len(self.made("PartDesign::Mirrored")), 1)
