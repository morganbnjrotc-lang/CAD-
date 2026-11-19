# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extruding a sketch (PLAN 3.5): select it, press E, type or drag the length.

E runs Part Design's Pad, whose panel opens with the length's number selected and a drag arrow in the 3D
view. These tests type into that panel the way the user would (StudioGui's C++ helpers; Python wrappers
of FreeCAD's panels make FreeCAD abort at exit, docs/BASELINE.md).
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

import StudioGui
from StudioTests.gui.sketch_input import INCH, settle
from studio.services import units as unit_service
from studio.services.settings import Settings
from studio.shell import units


class Extruding(unittest.TestCase):
    """A body with a 3 in circle sketched on its XY plane, in inches; `extrude` types into Pad's panel."""

    def setUp(self):
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(units.current().set_choice, original)
        units.current().set_choice("inches")
        self.doc = FreeCAD.newDocument("Extrude" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        body = self.doc.addObject("PartDesign::Body", "Body")
        self.sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        self.sketch.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]  # the XY plane
        self.sketch.MapMode = "FlatFace"
        self.sketch.addGeometry(Part.Circle(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), 3 * INCH))
        self.doc.recompute()

    def close(self):
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
        settle(100)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def extrude(self, keys):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.sketch)
        FreeCADGui.runCommand("PartDesign_Pad", 0)
        settle(500)
        StudioGui.focus_field("lengthEdit")  # as the panel does when it opens (its own focus is queued)
        settle(100)
        StudioGui.type_keys(keys)
        settle(500)
        return next(o for o in self.doc.Objects if o.TypeId == "PartDesign::Pad")


class TypedLength(Extruding):
    def test_a_typed_length_in_inches(self):
        pad = self.extrude("1.5{Return}")
        self.assertAlmostEqual(pad.Length.Value, 1.5 * INCH, places=6)
        self.assertFalse(FreeCADGui.Control.activeDialog(), "Return should finish the extrude")

    def test_a_length_typed_with_a_unit_is_converted(self):
        # The panel selects only the number ("0.39| in|"): "20 mm" made "20 mm in", which Return ignored.
        pad = self.extrude("20 mm{Return}")
        self.assertAlmostEqual(pad.Length.Value, 20, places=6)
        self.assertFalse(FreeCADGui.Control.activeDialog(), "Return should finish the extrude")


class StaysInStudio(Extruding):
    """Part Design asks to switch to its workbench when its panel opens. Studio came straight back, and
    the round trip took the window out of full screen (maximized: the user's report)."""

    def test_extruding_keeps_the_window_maximized(self):
        main = FreeCADGui.getMainWindow()
        if not main.isMaximized():
            self.addCleanup(main.showNormal)
            main.showMaximized()
            settle(300)
        self.assertTrue(main.isMaximized(), "precondition: the window is maximized")
        switches = []
        main.workbenchActivated.connect(switches.append)
        self.addCleanup(main.workbenchActivated.disconnect, switches.append)

        self.extrude("0.75{Return}")

        self.assertEqual(switches, [], "extruding switched workbench")
        self.assertTrue(main.isMaximized(), "extruding took the window out of full screen")
