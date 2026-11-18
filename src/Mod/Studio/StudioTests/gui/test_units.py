# SPDX-License-Identifier: LGPL-2.1-or-later
"""Inches or millimeters in the running app (PLAN 3.1): ☰ › Units, a switch, files saved in other units."""

import os
import tempfile
import unittest
import uuid

import FreeCAD
import FreeCADGui
from PySide import QtWidgets  # FreeCAD's PySide shim

from studio.services import units as unit_service
from studio.services.settings import Settings
from studio.shell import units


def shown(mm):
    return FreeCAD.Units.Quantity(f"{mm} mm").UserString


def unit_system(doc):
    return doc.getEnumerationsOfProperty("UnitSystem").index(doc.UnitSystem)


class SessionUnits(unittest.TestCase):
    def setUp(self):
        self.units = units.current()
        self.assertIsNotNone(self.units, "Studio did not set up its units")
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(self.units.set_choice, original)

    def test_the_menu_offers_units(self):
        from studio.shell import window

        menu = QtWidgets.QMenu()
        self.addCleanup(menu.deleteLater)
        window.current()._fill_menu(menu)
        found = [a.menu() for a in menu.actions() if a.menu() is not None and a.text() == "Units"]
        self.assertEqual(len(found), 1)
        labels = [a.text() for a in found[0].actions()]
        windows = "Inches" if units.windows_uses_inches() else "Millimeters"
        self.assertEqual(labels, [f"Follow Windows ({windows})", "Inches", "Millimeters"])

    def test_inches_and_millimeters(self):
        self.units.set_choice("inches")
        self.assertEqual(shown(25.4), "1.00 in")
        self.units.set_choice("millimeters")
        self.assertEqual(shown(25.4), "25.40 mm")

    def test_follow_windows(self):
        self.units.set_choice("system")
        self.assertEqual(shown(25.4), "1.00 in" if units.windows_uses_inches() else "25.40 mm")

    def test_a_new_part_is_in_the_users_units(self):
        self.units.set_choice("inches")
        doc = FreeCAD.newDocument("Units" + uuid.uuid4().hex[:8])
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        self.assertEqual(unit_system(doc), unit_service.schema_index("inches"))
        self.assertEqual(shown(25.4), "1.00 in")


class SavedInMillimeters(unittest.TestCase):
    """A part saved in millimeters (an example file, someone else's), opened while the user works in inches."""

    def setUp(self):
        self.units = units.current()
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(self.units.set_choice, original)
        self.units.set_choice("millimeters")
        folder = tempfile.mkdtemp(prefix="studio-units-")
        self.path = os.path.join(folder, "Metric.FCStd")
        doc = FreeCAD.newDocument("Metric")
        box = doc.addObject("Part::Box", "Box")
        doc.recompute()
        doc.saveAs(self.path)
        FreeCAD.closeDocument(doc.Name)
        self.units.set_choice("inches")
        self.doc = FreeCAD.openDocument(self.path)
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        FreeCADGui.updateGui()
        del box

    def test_it_shows_inches(self):
        self.assertEqual(unit_system(self.doc), unit_service.schema_index("inches"))
        self.assertEqual(shown(25.4), "1.00 in")

    def test_opening_it_changes_nothing_to_save(self):
        self.assertFalse(FreeCADGui.getDocument(self.doc.Name).Modified)

    def test_editing_it_stays_in_inches(self):
        # A property's status change makes FreeCAD switch to the document's own units
        # (Gui::Document::slotChangePropertyEditor); Part Design does it as you edit features.
        self.doc.getObject("Box").setEditorMode("Length", 1)
        FreeCADGui.updateGui()
        self.assertEqual(shown(25.4), "1.00 in")
