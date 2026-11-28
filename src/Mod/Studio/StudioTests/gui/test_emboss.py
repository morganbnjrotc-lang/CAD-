# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Emboss tool in the app (PLAN 4.3, docs/adr/0016; studio.shell.emboss), on a 20 mm radius cylinder with a
10 mm square sketched on the plane through its axis: the toolbar offers Emboss for the sketch; the panel waits
for the round face, then shows the emboss; Deboss cuts instead; OK keeps it (one undo step) and hides the
sketch; Cancel takes it away; double-click edits it."""

import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

from StudioTests.gui.sketch_input import settle
from studio.services import emboss as emboss_service
from studio.shell import emboss

V = FreeCAD.Vector
R = 20.0


class EmbossTool(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("EmbossTool" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        base = self.body.newObject("Sketcher::SketchObject", "Sketch")
        base.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        base.MapMode = "FlatFace"
        base.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), R))
        self.pad = self.body.newObject("PartDesign::Pad", "Pad")
        self.pad.Profile = base
        self.pad.Length = 40
        self.profile = self.body.newObject("Sketcher::SketchObject", "Profile")
        self.profile.AttachmentSupport = [(self.body.Origin.OriginFeatures[4], "")]
        self.profile.MapMode = "FlatFace"
        corners = [V(-5, 15, 0), V(5, 15, 0), V(5, 25, 0), V(-5, 25, 0)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            self.profile.addGeometry(Part.LineSegment(a, b))
        self.doc.recompute()
        base.Visibility = False
        self.volume = self.pad.Shape.Volume
        self.face = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Cylinder")
        FreeCADGui.SendMsgToActiveView("ViewFit")
        settle(200)

    def close(self):
        panel = emboss.current_panel()
        if panel is not None:
            panel.reject()
            settle(200)
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
            settle(200)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def pick(self, *picks):
        FreeCADGui.Selection.clearSelection()
        for obj, sub in picks:
            FreeCADGui.Selection.addSelection(self.doc.Name, obj.Name, sub)
        settle(300)

    def tool(self):
        FreeCADGui.runCommand("Studio_Emboss", 0)
        settle(500)
        panel = emboss.current_panel()
        self.assertIsNotNone(panel, "no Emboss panel")
        return panel

    def embosses(self):
        return [o for o in self.doc.Objects if isinstance(getattr(o, "Proxy", None), emboss_service.EmbossFeature)]

    def test_the_toolbar_offers_it_for_a_sketch(self):
        from studio.shell import window

        self.pick((self.profile, ""))
        actions = {a.text(): a for a in window.current().tools.actions()}
        self.assertIn("Emboss", actions)
        self.assertTrue(actions["Emboss"].isEnabled())

    def test_the_panel_waits_for_the_round_face(self):
        self.pick((self.profile, ""))
        panel = self.tool()
        self.assertEqual(self.embosses(), [])
        self.assertIn("Pick the round face", panel.face_label.text())
        self.pick((self.pad, self.face))
        [made] = self.embosses()
        self.assertTrue(made.isValid(), made.getStatusString())
        self.assertGreater(self.body.Shape.Volume, self.volume)

    def test_ok_keeps_it_and_hides_the_sketch(self):
        self.pick((self.profile, ""), (self.pad, self.face))
        undo = self.doc.UndoCount
        panel = self.tool()
        panel.accept()
        settle(300)
        self.assertIsNone(emboss.current_panel())
        self.assertEqual(len(self.embosses()), 1)
        self.assertFalse(self.profile.Visibility)
        self.assertEqual(self.doc.UndoCount, undo + 1)

    def test_deboss_cuts(self):
        self.pick((self.profile, ""), (self.pad, self.face))
        panel = self.tool()
        panel.cut.setChecked(True)
        settle(300)
        [made] = self.embosses()
        self.assertEqual(made.TypeId, emboss_service.CUT)
        self.assertLess(self.body.Shape.Volume, self.volume)

    def test_cancel_takes_it_away(self):
        self.pick((self.profile, ""), (self.pad, self.face))
        panel = self.tool()
        panel.reject()
        settle(300)
        self.assertEqual(self.embosses(), [])
        self.assertTrue(self.profile.Visibility)

    def test_double_click_edits_it(self):
        self.pick((self.profile, ""), (self.pad, self.face))
        self.tool().accept()
        settle(300)
        [made] = self.embosses()
        FreeCADGui.ActiveDocument.setEdit(made.Name, 0)
        settle(300)
        panel = emboss.current_panel()
        self.assertIsNotNone(panel, "no panel on double-click")
        self.assertFalse(panel.new)
        panel.depth.setProperty("rawValue", 2.0)
        settle(300)
        panel.accept()
        settle(300)
        self.assertAlmostEqual(made.Depth.Value, 2.0)
