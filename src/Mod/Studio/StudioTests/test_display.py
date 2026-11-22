# SPDX-License-Identifier: LGPL-2.1-or-later
"""Display presets (PLAN 3.8): how the 3D view draws the model, and perspective or not
(studio.services.display). The choice is Studio's setting, so every document's view follows it."""

import unittest
import uuid

import FreeCAD

from studio.services import display
from studio.services.settings import Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


class Presets(unittest.TestCase):
    def setUp(self):
        name = "Display" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.display = display.Display(self.settings)

    def test_the_styles_offered_with_freecads_draw_style_for_each(self):
        self.assertEqual([(s.label, s.mode) for s in display.STYLES], [
            ("Shaded with Edges", "As Is"), ("Shaded", "Shaded"), ("Hidden Line", "Hidden Line"),
            ("Wireframe", "Wireframe"), ("Pretty", "As Is"), ("Gray Box", "Shaded"), ("Realistic", "Shaded")])

    def test_each_style_has_its_own_key_the_old_ones_unchanged(self):
        # the setting stored a draw style before the presets came: those still read
        self.assertEqual([s.key for s in display.STYLES], [
            "As Is", "Shaded", "Hidden Line", "Wireframe", "Pretty", "Gray Box", "Realistic"])

    def test_the_presets_looks(self):
        looks = {s.key: s.look for s in display.STYLES}
        self.assertEqual(looks["Pretty"], display.Look(shadows=True))
        self.assertEqual(looks["Gray Box"], display.Look(shadows=True, gray=True))
        self.assertEqual(looks["Realistic"], display.Look(shadows=True, shiny=True))
        for plain in ("As Is", "Shaded", "Hidden Line", "Wireframe"):
            self.assertEqual(looks[plain], display.Look(), plain)

    def test_the_current_style(self):
        self.display.set_style("Gray Box")
        self.assertEqual(self.display.current().label, "Gray Box")
        self.assertTrue(self.display.current().look.gray)

    def test_starts_shaded_with_edges_and_orthographic(self):
        self.assertEqual(self.display.style(), "As Is")
        self.assertFalse(self.display.perspective())

    def test_the_choice_is_remembered(self):
        self.display.set_style("Hidden Line")
        self.display.set_perspective(True)
        again = display.Display(Settings(root=self.settings.root))
        self.assertEqual(again.style(), "Hidden Line")
        self.assertTrue(again.perspective())

    def test_only_offered_styles(self):
        with self.assertRaises(ValueError):
            self.display.set_style("Points")
