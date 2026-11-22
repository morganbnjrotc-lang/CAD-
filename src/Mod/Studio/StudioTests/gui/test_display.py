# SPDX-License-Identifier: LGPL-2.1-or-later
"""Display presets in the app (PLAN 3.8; studio.shell.display): the top bar's Display menu.

The draw style the 3D view uses is read back through StudioGui (C++: FreeCAD's viewer keeps it).
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui

import StudioGui
from StudioTests.gui.sketch_input import settle
from studio.services import display as display_service
from studio.services.settings import Settings
from studio.shell import display


class WithDocument(unittest.TestCase):
    """A document with a box; the Display choice put back afterwards."""

    def setUp(self):
        settings = Settings()
        style, perspective = settings.get(display_service.STYLE), settings.get(display_service.PERSPECTIVE)
        self.addCleanup(self.restore, style, perspective)
        self.doc = self.new_document()

    def restore(self, style, perspective):
        display.current().choose(style)
        display.current().set_perspective(perspective)
        for name in list(FreeCAD.listDocuments()):
            if name.startswith("Display"):
                FreeCAD.closeDocument(name)
        settle(100)

    def new_document(self):
        doc = FreeCAD.newDocument("Display" + uuid.uuid4().hex[:8])
        doc.addObject("Part::Box", "Box")
        doc.recompute()
        settle(300)
        return doc

    def items(self):
        return {a.text(): a for a in display.current().menu.actions() if not a.isSeparator()}


class DisplayMenu(WithDocument):
    def test_the_top_bar_has_a_display_menu(self):
        self.assertEqual(display.current().button.text(), "Display")
        self.assertEqual(list(self.items()),
                         ["Shaded with Edges", "Shaded", "Hidden Line", "Wireframe", "Pretty", "Gray Box",
                          "Realistic", "Perspective"])

    def test_picking_a_style_draws_the_model_that_way(self):
        self.items()["Hidden Line"].trigger()
        settle(200)
        self.assertEqual(StudioGui.draw_style(), "Hidden Line")
        self.assertTrue(self.items()["Hidden Line"].isChecked())
        self.items()["Shaded with Edges"].trigger()
        settle(200)
        self.assertEqual(StudioGui.draw_style(), "As Is")

    def test_perspective_switches_the_camera(self):
        self.items()["Perspective"].trigger()
        settle(200)
        self.assertEqual(FreeCADGui.ActiveDocument.ActiveView.getCameraType(), "Perspective")
        self.items()["Perspective"].trigger()
        settle(200)
        self.assertEqual(FreeCADGui.ActiveDocument.ActiveView.getCameraType(), "Orthographic")

    def test_a_document_opened_later_follows_the_choice(self):
        self.items()["Wireframe"].trigger()
        self.items()["Perspective"].trigger()
        settle(200)
        self.new_document()
        settle(300)
        self.assertEqual(StudioGui.draw_style(), "Wireframe")
        self.assertEqual(FreeCADGui.ActiveDocument.ActiveView.getCameraType(), "Perspective")


class Looks(WithDocument):
    """Pretty, Gray Box and Realistic (PLAN 3.8): Coin's shadows on a floor under the model, read back through
    StudioGui.look() (shadows, gray, shiny, the floor's height or None)."""

    def pick(self, label):
        self.items()[label].trigger()
        settle(300)

    def test_pretty_draws_shadows_under_the_model_with_edges(self):
        self.pick("Pretty")
        shadows, gray, shiny, floor = StudioGui.look()
        self.assertEqual((shadows, gray, shiny), (True, False, False))
        self.assertEqual(StudioGui.draw_style(), "As Is")
        self.assertLess(floor, 0, "the floor isn't under the box (it starts at 0)")
        self.assertGreater(floor, -1)

    def test_gray_box(self):
        self.pick("Gray Box")
        self.assertEqual(StudioGui.look()[:3], (True, True, False))
        self.assertEqual(StudioGui.draw_style(), "Shaded")

    def test_realistic(self):
        self.pick("Realistic")
        self.assertEqual(StudioGui.look()[:3], (True, False, True))
        self.assertEqual(StudioGui.draw_style(), "Shaded")

    def test_a_plain_style_takes_the_shadows_away(self):
        self.pick("Pretty")
        self.pick("Shaded with Edges")
        self.assertEqual(StudioGui.look(), (False, False, False, None))

    def test_the_floor_follows_the_model(self):
        self.pick("Pretty")
        box = self.doc.getObject("Box")
        box.Placement.Base = FreeCAD.Vector(0, 0, -20)
        self.doc.recompute()
        settle(300)
        self.assertLess(StudioGui.look()[3], -20)

    def test_the_model_can_still_be_picked(self):
        self.pick("Pretty")
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewIsometric()
        view.fitAll()
        settle(200)
        width, height = view.getSize()
        info = view.getObjectInfo((width // 2, height // 2))
        self.assertIsNotNone(info, "nothing under the middle of the view")
        self.assertEqual(info["Object"], "Box")

    def test_a_document_opened_later_gets_the_look(self):
        self.pick("Gray Box")
        self.new_document()
        settle(300)
        self.assertEqual(StudioGui.look()[:3], (True, True, False))
