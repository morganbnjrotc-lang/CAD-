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


class DisplayMenu(unittest.TestCase):
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

    def test_the_top_bar_has_a_display_menu(self):
        self.assertEqual(display.current().button.text(), "Display")
        self.assertEqual(list(self.items()),
                         ["Shaded with Edges", "Shaded", "Hidden Line", "Wireframe", "Perspective"])

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
