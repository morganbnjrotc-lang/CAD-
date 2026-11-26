# SPDX-License-Identifier: LGPL-2.1-or-later
"""What a feature made in the app starts as (PLAN 3.18; studio.shell.new_features): Studio's names in the model
tree for features made now, files keeping theirs, and a new hole in the user's units' thread standard."""

import os
import tempfile
import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

from StudioTests.gui.sketch_input import settle
from studio.services import units as unit_service
from studio.services.settings import Settings
from studio.shell import units

V = FreeCAD.Vector


class NewFeatures(unittest.TestCase):
    def setUp(self):
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(units.current().set_choice, original)
        self.doc = FreeCAD.newDocument("NewFeatures" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        corners = [V(-10, -10, 0), V(10, -10, 0), V(10, 10, 0), V(-10, 10, 0)]
        self.square = self.sketch(0, *(Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])))

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
        if self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def run_on(self, sketch, command):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(sketch)
        FreeCADGui.runCommand(command, 0)
        settle(800)
        return FreeCADGui.getDocument(self.doc.Name).getInEdit().Object

    def finish(self):
        FreeCADGui.Control.activeTaskDialog().accept()
        settle(500)

    def test_an_extrude_shows_as_extrude_in_the_model_tree(self):
        extrude = self.run_on(self.square, "PartDesign_Pad")
        self.finish()
        self.assertEqual((extrude.Name, extrude.Label), ("Pad", "Extrude"))

    def test_a_file_keeps_its_names(self):
        extrude = self.run_on(self.square, "PartDesign_Pad")
        self.finish()
        extrude.Label = "Pad"  # as in a file made before
        path = os.path.join(tempfile.mkdtemp(), "Names.FCStd")
        self.doc.saveAs(path)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.openDocument(path)
        settle(300)
        self.assertEqual(self.doc.getObject("Pad").Label, "Pad")

    def hole(self, choice):
        units.current().set_choice(choice)
        extrude = self.run_on(self.square, "PartDesign_Pad")
        self.finish()
        circle = self.sketch(extrude.Length.Value, Part.Circle(V(0, 0, 0), V(0, 0, 1), 2))
        return self.run_on(circle, "PartDesign_Hole")

    def test_a_new_hole_starts_in_unc_in_inches(self):
        hole = self.hole("inches")
        self.assertEqual((hole.ThreadType, hole.ThreadSize, hole.Threaded), ("UNC", "1/4", False))

    def test_a_hole_a_script_makes_keeps_freecads_start(self):
        # with a standard, a hole's size comes from it, not from the script's Diameter
        units.current().set_choice("inches")
        hole = self.body.newObject("PartDesign::Hole", "Hole")
        hole.Diameter = 4
        settle(100)
        self.assertEqual((hole.ThreadType, hole.Diameter.Value), ("None", 4))

    def test_a_new_hole_starts_in_iso_metric_in_millimeters(self):
        hole = self.hole("millimeters")
        self.assertEqual((hole.ThreadType, hole.ThreadSize, hole.Threaded), ("ISOMetricProfile", "M6x1.0", False))
