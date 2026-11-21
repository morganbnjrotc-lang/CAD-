# SPDX-License-Identifier: LGPL-2.1-or-later
"""Model all threads on export (PLAN 3.9): studio.services.threads.

Threads stay cosmetic in the model (FreeCAD's default: a threaded hole is drilled at the thread's size,
no thread cut), which keeps it light; an export gets them modeled (for a printer or a machinist). Inside
`modeled(doc)` every cosmetic threaded hole is modeled; after it the document is as it was, with no undo
step left.
"""

import os
import tempfile
import unittest
import uuid

import FreeCAD
import Import
import Part

from studio.services import threads

V = FreeCAD.Vector


class ThreadedPart(unittest.TestCase):
    """A 20 x 20 x 10 mm block with an M6 threaded hole, cosmetic."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("Threads" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        h = 10
        corners = [V(-h, -h, 0), V(h, -h, 0), V(h, h, 0), V(-h, h, 0)]
        base = self.sketch(0, *(Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])))
        pad = self.body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = base
        pad.Length = 10
        self.doc.recompute()
        self.hole = self.threaded_hole()
        self.cosmetic_faces = len(self.body.Shape.Faces)

    def sketch(self, height, *shapes):
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, height), FreeCAD.Rotation())
        for shape in shapes:
            sketch.addGeometry(shape)
        self.doc.recompute()
        return sketch

    def threaded_hole(self, modeled=False):
        sketch = self.sketch(10, Part.Circle(V(0, 0, 0), V(0, 0, 1), 3))
        hole = self.body.newObject("PartDesign::Hole", "Hole")
        hole.Profile = sketch
        hole.Threaded = True
        hole.ThreadType = "ISOMetricProfile"
        hole.ThreadSize = "M6x1.0"
        hole.ModelThread = modeled
        hole.Depth = 8
        self.doc.recompute()
        self.assertTrue(hole.isValid(), hole.getStatusString())
        return hole


class Threads(ThreadedPart):
    def test_the_cosmetic_threaded_holes(self):
        self.assertEqual(threads.cosmetic_holes(self.doc), [self.hole])

    def test_inside_threads_are_modeled_after_it_cosmetic_again(self):
        with threads.modeled(self.doc) as holes:
            self.assertEqual(holes, [self.hole])
            self.assertTrue(self.hole.ModelThread)
            self.assertGreater(len(self.body.Shape.Faces), self.cosmetic_faces, "no thread cut")
        self.assertFalse(self.hole.ModelThread)
        self.assertEqual(len(self.body.Shape.Faces), self.cosmetic_faces)

    def test_no_undo_step_is_left(self):
        undo = self.doc.UndoCount
        with threads.modeled(self.doc):
            pass
        self.assertEqual(self.doc.UndoCount, undo)

    def test_a_document_without_threads_is_left_alone(self):
        self.hole.Threaded = False
        self.doc.recompute()
        with threads.modeled(self.doc) as holes:
            self.assertEqual(holes, [])

    def test_an_exported_step_file_has_the_threads(self):
        path = os.path.join(tempfile.mkdtemp(), "part.step")
        Import.export([self.body], path)
        cosmetic = len(Part.read(path).Faces)
        with threads.modeled(self.doc):
            Import.export([self.body], path)
        self.assertGreater(len(Part.read(path).Faces), cosmetic)
