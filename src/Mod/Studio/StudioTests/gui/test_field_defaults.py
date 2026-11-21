# SPDX-License-Identifier: LGPL-2.1-or-later
"""Right-click a tool's field → Make Default, in the app (PLAN 3.6; studio.shell.field_defaults).

Extrude's length box is right-clicked as the user would (StudioGui sends the right-click; the menu is read
and an item picked from a timer, so a menu that waits, as FreeCAD's own does, can't hang the test).
"""

import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

import StudioGui
from StudioTests.gui.sketch_input import INCH, settle
from StudioTests.gui.test_extrude import Extruding
from studio.services.field_defaults import FieldDefaults
from studio.services.settings import Settings

PAD = "PartDesign::Pad"


class MakeDefault(Extruding):
    def setUp(self):
        super().setUp()
        defaults = FieldDefaults(Settings())
        self.addCleanup(defaults.forget, PAD, "lengthEdit")
        defaults.forget(PAD, "lengthEdit")

    def open_extrude(self):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.sketch)
        FreeCADGui.runCommand("PartDesign_Pad", 0)
        settle(600)
        pads = [o for o in self.doc.Objects if o.TypeId == PAD]
        return pads[-1]

    def cancel(self):
        FreeCADGui.Control.activeTaskDialog().reject()
        settle(400)

    def menu_of(self, field, choose=None):
        """Right-clicks the field: the menu's items; picks `choose` from it if given."""
        seen = []

        def read_and_close():
            seen.append(StudioGui.popup_menu())
            if choose is not None:
                StudioGui.choose_popup(choose)
            StudioGui.close_popups()

        QtCore.QTimer.singleShot(400, read_and_close)
        StudioGui.right_click_field(field)
        settle(900)
        self.assertTrue(seen and seen[0], "no menu opened")
        return seen[0]

    def test_the_fields_menu_offers_make_default_and_keeps_freecads(self):
        self.open_extrude()
        items = self.menu_of("lengthEdit")
        self.assertIn("Make Default", items)
        self.assertIn("Save Value", items)  # FreeCAD's own items stay
        self.assertNotIn("Forget Default", items)

    def test_a_new_extrude_starts_with_the_default(self):
        self.open_extrude()
        StudioGui.set_field("lengthEdit", 0.75 * INCH)
        settle(300)
        self.menu_of("lengthEdit", choose="Make Default")
        self.cancel()
        pad = self.open_extrude()
        self.assertAlmostEqual(pad.Length.Value, 0.75 * INCH, places=4)

    def test_forget_default_goes_back_to_freecads_start(self):
        self.open_extrude()
        StudioGui.set_field("lengthEdit", 0.75 * INCH)
        settle(300)
        self.menu_of("lengthEdit", choose="Make Default")
        self.cancel()
        self.open_extrude()
        self.assertIn("Forget Default", self.menu_of("lengthEdit", choose="Forget Default"))
        self.cancel()
        pad = self.open_extrude()
        self.assertAlmostEqual(pad.Length.Value, 10.0, places=4)  # FreeCAD's own start

    def test_editing_an_existing_extrude_keeps_its_length(self):
        FieldDefaults(Settings()).make(PAD, "lengthEdit", 0.75 * INCH)
        self.open_extrude()
        StudioGui.focus_field("lengthEdit")
        StudioGui.type_keys("2{Return}")
        settle(500)
        pad = [o for o in self.doc.Objects if o.TypeId == PAD][-1]
        FreeCADGui.ActiveDocument.setEdit(pad.Name, 0)
        settle(600)
        self.assertAlmostEqual(pad.Length.Value, 2 * INCH, places=4)
