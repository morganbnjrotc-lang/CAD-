# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click hole chamfer in the app (PLAN 3.9; studio.shell.holes): a hole picked in the model tree,
then the toolbar's Chamfer Hole. Part Design's Chamfer opens on the hole's openings, sized for the hole;
Finish keeps it, Cancel takes it away."""

import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

from StudioTests.gui.sketch_input import settle
from studio.services import holes
from studio.shell import window

V = FreeCAD.Vector


class ChamferHole(unittest.TestCase):
    """A 20 x 20 x 10 mm block with two 4 mm holes from its top face."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("HoleChamfer" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        h = 10
        corners = [V(-h, -h, 0), V(h, -h, 0), V(h, h, 0), V(-h, h, 0)]
        pad = self.body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = self.sketch(0, *(Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])))
        pad.Length = 10
        self.doc.recompute()
        self.hole = self.body.newObject("PartDesign::Hole", "Hole")
        self.hole.Profile = self.sketch(10, Part.Circle(V(-5, 0, 0), V(0, 0, 1), 2), Part.Circle(V(5, 0, 0), V(0, 0, 1), 2))
        self.hole.Diameter = 4
        self.hole.Depth = 6
        self.doc.recompute()
        FreeCADGui.SendMsgToActiveView("ViewFit")
        settle(300)

    def sketch(self, height, *shapes):
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, height), FreeCAD.Rotation())
        for shape in shapes:
            sketch.addGeometry(shape)
        self.doc.recompute()
        return sketch

    def close(self):
        dialog = FreeCADGui.Control.activeTaskDialog()
        if dialog is not None:
            dialog.reject()
            settle(300)
        FreeCAD.closeDocument(self.doc.Name)
        settle(100)

    def chamfer_hole(self):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.hole)
        settle(300)
        window.current().refresh()
        actions = {a.text(): a for a in window.current().tools.actions()}
        self.assertIn("Chamfer Hole", actions, f"toolbar shows {list(actions)}")
        actions["Chamfer Hole"].trigger()
        settle(1200)

    def chamfers(self):
        return [o for o in self.doc.Objects if o.TypeId == "PartDesign::Chamfer"]

    def test_the_chamfer_opens_on_the_holes_openings(self):
        openings = holes.opening_edges(self.hole)
        self.chamfer_hole()
        editing = FreeCADGui.ActiveDocument.getInEdit()
        self.assertEqual(getattr(getattr(editing, "Object", None), "TypeId", None), "PartDesign::Chamfer")
        chamfer = self.chamfers()[0]
        self.assertEqual(chamfer.Base[0], self.hole)
        self.assertEqual(sorted(chamfer.Base[1]), sorted(openings))
        self.assertAlmostEqual(chamfer.Size.Value, 0.4, places=4)

    def test_finish_keeps_it(self):
        before = self.body.Shape.Volume
        self.chamfer_hole()
        FreeCADGui.Control.activeTaskDialog().accept()
        settle(600)
        self.assertEqual(len(self.chamfers()), 1)
        self.assertTrue(self.chamfers()[0].isValid())
        self.assertLess(self.body.Shape.Volume, before)

    def test_cancel_takes_it_away(self):
        self.chamfer_hole()
        FreeCADGui.Control.activeTaskDialog().reject()
        settle(600)
        self.assertEqual(self.chamfers(), [])
