# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Thread tool in the app (PLAN 3.20, docs/adr/0014; studio.shell.shaft_threads), on a 1/4 in shaft in
inches: a round face picked offers Thread; its panel opens with the size from the face; OK keeps a cosmetic
thread, drawn with FreeCAD's thread texture; Modeled cuts it; Cancel takes it away."""

import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

from StudioTests.gui.sketch_input import settle
from studio.services import units as unit_service
from studio.services.settings import Settings
from studio.shell import shaft_threads, units

V = FreeCAD.Vector
QUARTER = 0.25 * 25.4


class ThreadTool(unittest.TestCase):
    def setUp(self):
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(units.current().set_choice, original)
        units.current().set_choice("inches")
        self.doc = FreeCAD.newDocument("ThreadTool" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        sketch.MapMode = "FlatFace"
        sketch.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), QUARTER / 2))
        self.shaft = self.body.newObject("PartDesign::Pad", "Shaft")
        self.shaft.Profile = sketch
        self.shaft.Length = 20
        self.doc.recompute()
        sketch.Visibility = False
        self.volume = self.shaft.Shape.Volume
        self.round = next(f"Face{n}" for n, f in enumerate(self.shaft.Shape.Faces, 1)
                          if f.Surface.__class__.__name__ == "Cylinder")
        self.flat = next(f"Face{n}" for n, f in enumerate(self.shaft.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Plane")
        FreeCADGui.SendMsgToActiveView("ViewFit")
        settle(200)

    def close(self):
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
            settle(200)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def pick(self, face):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, self.shaft.Name, face)
        settle(300)

    def thread_tool(self):
        self.pick(self.round)
        FreeCADGui.runCommand("Studio_Thread", 0)
        settle(800)
        return next(o for o in self.doc.Objects if o.Name.startswith("Thread"))

    def panel(self):
        return shaft_threads.current_panel()

    def test_a_round_face_offers_thread_on_the_toolbar(self):
        from studio.shell import window

        self.pick(self.round)
        actions = {a.text(): a for a in window.current().tools.actions()}
        self.assertIn("Thread", actions)
        self.assertTrue(actions["Thread"].isEnabled())

    def test_a_flat_face_doesnt_get_one(self):
        self.pick(self.flat)
        self.assertFalse(FreeCADGui.Command.get("Studio_Thread").isActive())

    def test_the_panel_opens_with_the_size_from_the_face(self):
        thread = self.thread_tool()
        self.assertIsNotNone(self.panel(), "no Thread panel")
        self.assertEqual((thread.ThreadType, thread.ThreadSize, thread.Modeled), ("UNC", "1/4", False))
        self.assertEqual(self.panel().size.currentText(), "1/4")

    def test_cancel_takes_it_away(self):
        self.thread_tool()
        self.panel().reject()
        settle(300)
        self.assertEqual([o.Name for o in self.doc.Objects if o.Name.startswith("Thread")], [])
        self.assertEqual(self.body.Tip, self.shaft)

    def test_ok_keeps_a_cosmetic_thread_with_its_texture(self):
        thread = self.thread_tool()
        self.panel().accept()
        settle(300)
        self.assertIsNotNone(self.doc.getObject(thread.Name))
        self.assertAlmostEqual(thread.Shape.Volume, self.volume, places=6)
        self.assertIsNotNone(shaft_threads.overlay(thread), "no thread texture on the face")

    def test_modeled_cuts_it(self):
        thread = self.thread_tool()
        self.panel().modeled.setChecked(True)
        settle(1500)
        self.panel().accept()
        settle(300)
        self.assertTrue(thread.Modeled)
        self.assertLess(thread.Shape.Volume, self.volume)
        self.assertIsNone(shaft_threads.overlay(thread), "a modeled thread keeps the texture")

    def test_create_lists_thread(self):
        from studio.shell import tool_groups

        bar = tool_groups.current()
        create = next(b for b in bar.buttons if b.text() == "Create")
        create.menu().aboutToShow.emit()
        self.assertIn("Thread", [a.text().split("\t")[0] for a in create.menu().actions()])
