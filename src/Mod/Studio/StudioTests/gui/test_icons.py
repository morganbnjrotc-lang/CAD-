# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's line icons in the running app (ADR 0010, PLAN 2.9 step 4).

FreeCAD's places (model tree, menus) find Studio's drawings under FreeCAD's own icon names, in the
neutral grey; Studio's toolbar draws them in the mode's text color.
"""

import os
import tempfile
import unittest

import FreeCADGui

from studio.services import icons, theme

from .test_appearance import ink, near, restore_session_look


def freecad_icon_ink(name):
    icon = FreeCADGui.getIcon(name)
    return ink(icon.pixmap(32, 32).toImage()) if icon is not None and not icon.isNull() else None


class FreeCADPlaces(unittest.TestCase):
    def test_freecad_finds_studios_drawings_under_its_own_names(self):
        for name in ("PartDesign_Pad", "PartDesign_Pad.svg", "Sketcher_Sketch", "TreeItemVisible", "document-new"):
            color = freecad_icon_ink(name)
            self.assertTrue(near(color, theme.ICON_NEUTRAL), f"{name}: {color}")

    def test_icons_studio_has_no_drawing_for_stay_freecads(self):
        color = freecad_icon_ink("document-print")  # always loaded, in FreeCAD's colors
        self.assertIsNotNone(color)
        self.assertFalse(near(color, theme.ICON_NEUTRAL), color)

    def test_studio_can_put_a_drawing_under_any_name(self):
        import StudioGui

        name = "StudioTestIcon"
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "test.svg")
            with open(icons.icon_path("circle"), encoding="utf-8") as source, open(path, "w", encoding="utf-8") as copy:
                copy.write(source.read())
            self.assertEqual(StudioGui.add_icons({path: [name]}), 1)
        self.assertTrue(near(freecad_icon_ink(name), theme.ICON_NEUTRAL))


class Toolbar(unittest.TestCase):
    def setUp(self):
        from studio.shell import window

        self.addCleanup(restore_session_look)
        self.window = window.current()

    def test_tools_are_drawn_in_the_text_color(self):
        for p in (theme.DARK, theme.LIGHT):
            self.window.restyle(p)
            self.window.show_tools_for([], None)  # nothing selected: New Sketch, New Body, Import...
            colors = {a.text(): ink(a.icon().pixmap(32, 32).toImage()) for a in self.window.tools.actions()}
            self.assertTrue(colors)
            self.assertEqual({label: c for label, c in colors.items() if not near(c, p.text)}, {}, p.name)
