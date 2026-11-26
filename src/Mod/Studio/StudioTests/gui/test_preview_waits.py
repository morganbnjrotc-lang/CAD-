# SPDX-License-Identifier: LGPL-2.1-or-later
"""A feature's preview waits while a recompute shows a progress bar (CORE_PATCHES.md, the user 2026-11-26:
"the CAD is crashing/freezing after changing the hole to have threads").

The Hole panel's Tap drill recomputed the hole; on the user's filleted part the cut took long enough for
FreeCAD's progress bar, which keeps the window updating. FreeCAD's preview of the open feature (Part's
PreviewUpdateScheduler) then started a second OpenCASCADE cut inside the first, which waited for the first
one's lock: the app froze with no CPU in use (stack in docs/BASELINE.md). The preview now waits until no
progress bar or recompute is running. A progress bar is started from Python here, as OpenCASCADE's long
operations do, so the moment is the same every run.
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

from StudioTests.gui.sketch_input import settle

V = FreeCAD.Vector


class PreviewDuringProgress(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("PreviewWaits" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        corners = [V(-10, -10, 0), V(10, -10, 0), V(10, 10, 0), V(-10, 10, 0)]
        block = self.body.newObject("PartDesign::Pad", "Block")
        block.Profile = self.sketch(0, *(Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])))
        block.Length = 10
        self.doc.recompute()
        self.circle = self.sketch(10, Part.Circle(V(0, 0, 0), V(0, 0, 1), 3))
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.circle)
        FreeCADGui.runCommand("PartDesign_Hole", 0)
        settle(800)
        self.hole = FreeCADGui.getDocument(self.doc.Name).getInEdit().Object
        self.progress = None

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
        if self.progress is not None:
            self.progress.stop()
        dialog = FreeCADGui.Control.activeTaskDialog()
        if dialog is not None:
            dialog.reject()
            settle(300)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def preview_volume(self):
        shape = self.hole.PreviewShape
        return 0.0 if shape.isNull() else round(shape.Volume, 6)

    def test_the_preview_waits_for_the_progress_bar_and_then_catches_up(self):
        before = self.preview_volume()
        self.progress = FreeCAD.Base.ProgressIndicator()
        self.progress.start("A long cut", 10)  # as OpenCASCADE's progress during a slow boolean
        self.hole.Diameter = 8  # what the panel does on a change: recompute the hole, then its preview
        self.hole.recompute()  # (scheduled for when the window updates next, Part's PreviewUpdateScheduler)
        settle(500)
        self.assertEqual(self.preview_volume(), before, "the preview was computed during the progress bar")
        self.progress.stop()
        self.progress = None
        settle(500)
        self.assertNotEqual(self.preview_volume(), before, "the preview didn't catch up afterwards")
