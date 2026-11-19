# SPDX-License-Identifier: LGPL-2.1-or-later
"""Right-clicking the model in the 3D view (the user's crash report, 2026-11-19).

With something under the pointer, FreeCAD's 3D view menu gets a "Clarify Selection" item, labelled from
that command's button (`Command::getAction()`). FreeCAD makes a command's button only when a menu or
toolbar first shows the command, and Studio removes FreeCAD's Tools menu, where this one lives
(InitGui.py, docs/adr/0009). So the right-click read a button that didn't exist and FreeCAD crashed
("Illegal storage access", at address 0x10). Fixed in FreeCAD's NavigationStyle (docs/CORE_PATCHES.md).

The menu is read and closed through StudioGui's C++ helpers: Python wrappers of FreeCAD's widgets make
FreeCAD abort at exit (docs/BASELINE.md).
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui

import StudioGui
from StudioTests.gui.sketch_input import settle


class RightClick(unittest.TestCase):
    """A document with a box filling the middle of the 3D view."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("RightClick" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.box = self.doc.addObject("Part::Box", "Box")
        self.doc.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewIsometric()
        view.fitAll()
        settle(300)

    def close(self):
        StudioGui.close_popups()
        settle(50)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def right_click_the_box(self):
        center = self.box.Shape.BoundBox.Center
        px, py = StudioGui.view_point(center.x, center.y, center.z)
        StudioGui.view_mouse("move", px, py)  # preselects the box, as a real pointer does
        settle()
        StudioGui.view_mouse("right_click", px, py)
        settle(200)
        menu = StudioGui.popup_menu()
        StudioGui.close_popups()
        settle(100)
        return menu

    def test_right_clicking_the_model_opens_its_menu_again_and_again(self):
        # The user right-clicked a few times; the first right-click on the model already crashed.
        command = FreeCADGui.Command.get("Std_ClarifySelection")
        self.assertEqual(command.getAction(), [],
                         "precondition: Studio's menus never made Clarify Selection's button")
        for attempt in (1, 2, 3):
            menu = self.right_click_the_box()
            self.assertIsNotNone(menu, f"right-click {attempt}: no menu opened")
            self.assertIn("Clarify Selection", menu, f"right-click {attempt}: {menu}")
