# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude or cut by direction in the app, like Fusion (PLAN 3.5; studio.shell.extrude_direction).

An extrude let go pointing into the part becomes a cut; a cut typed out of the part becomes an extrude.
Part Design's panels are driven as the user would: typing into the length, letting go of the mouse in
the 3D view, Finish (the panel's OK), Cancel. One undo step takes the result away, and Cancel leaves
nothing behind.
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

V = FreeCAD.Vector
BLOCK, HEIGHT, RADIUS = 2 * INCH, 1 * INCH, 0.25 * INCH


class OnABlock(unittest.TestCase):
    """A 2 x 2 x 1 in block, and a 0.5 in circle sketched on its top face; in inches."""

    def setUp(self):
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(units.current().set_choice, original)
        units.current().set_choice("inches")
        self.doc = FreeCAD.newDocument("ExtrudeDirection" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        h = BLOCK / 2
        corners = [V(-h, -h, 0), V(h, -h, 0), V(h, h, 0), V(-h, h, 0)]
        base = self.sketch(0, *(Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])))
        self.block = self.body.newObject("PartDesign::Pad", "Block")
        self.block.Profile = base
        self.block.Length = HEIGHT
        self.doc.recompute()
        self.top = self.sketch(HEIGHT, Part.Circle(V(0, 0, 0), V(0, 0, 1), RADIUS))
        self.top.Visibility = True
        self.doc.recompute()
        FreeCADGui.SendMsgToActiveView("ViewFit")
        settle(200)

    def sketch(self, height, *shapes):
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]  # the XY plane
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, height), FreeCAD.Rotation())
        for shape in shapes:
            sketch.addGeometry(shape)
        self.doc.recompute()
        return sketch

    def close(self):
        dialog = FreeCADGui.Control.activeTaskDialog()
        if dialog is not None:  # cancelled as the user would: FreeCAD aborted at exit after closeDialog
            dialog.reject()
            settle(300)
        settle(100)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    def start(self, command):
        """Selects the sketch on the block and runs Extrude (PartDesign_Pad) or Cut (PartDesign_Pocket)."""
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.top)
        FreeCADGui.runCommand(command, 0)
        settle(500)
        StudioGui.focus_field("lengthEdit")  # as the panel does when it opens (its own focus is queued)
        settle(100)

    def type(self, keys):
        StudioGui.type_keys(keys)
        settle(500)

    def drag_to(self, inches):
        """Drags the length arrow to `inches` and lets go. The arrow sets the panel's length box as it
        moves (Gui::LinearGizmo); the mouse let go is a click in an empty corner of the 3D view."""
        self.assertTrue(StudioGui.set_field("lengthEdit", inches * INCH), "no length box")
        settle(500)
        width, height = StudioGui.view_size()
        StudioGui.view_mouse("click", 12, height - 12)
        settle(1500)

    def in_edit(self):
        view_provider = FreeCADGui.ActiveDocument.getInEdit()
        return getattr(getattr(view_provider, "Object", None), "TypeId", None)

    def finish(self):
        FreeCADGui.Control.activeTaskDialog().accept()
        settle(1000)

    def cancel(self):
        FreeCADGui.Control.activeTaskDialog().reject()
        settle(1000)

    def kinds(self):
        return sorted(o.TypeId.split("::")[1] for o in self.body.Group if o.TypeId.startswith("PartDesign::P"))

    def volume(self):
        self.doc.recompute()
        return self.body.Shape.Volume

    def cylinder(self, depth):
        return 3.141592653589793 * RADIUS ** 2 * depth


class LettingGo(OnABlock):
    def test_an_extrude_let_go_pointing_into_the_part_becomes_a_cut(self):
        self.start("PartDesign_Pad")
        self.drag_to(-0.25)
        self.assertEqual(self.in_edit(), "PartDesign::Pocket", "the cut's panel should be open now")
        cut = FreeCADGui.ActiveDocument.getInEdit().Object
        self.assertAlmostEqual(cut.Length.Value, 0.25 * INCH, places=4)
        self.assertEqual(self.kinds(), ["Pad", "Pocket"])  # the block and the cut

    def test_finish_keeps_the_cut_and_one_undo_takes_it_back(self):
        self.start("PartDesign_Pad")
        self.drag_to(-0.25)
        self.finish()
        self.assertFalse(FreeCADGui.Control.activeDialog())
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT - self.cylinder(0.25 * INCH), places=1)
        self.doc.undo()
        self.assertEqual(self.kinds(), ["Pad"])
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT, places=1)

    def test_cancel_after_the_switch_leaves_nothing(self):
        self.start("PartDesign_Pad")
        self.drag_to(-0.25)
        self.cancel()
        self.assertFalse(FreeCADGui.Control.activeDialog())
        self.assertEqual(self.kinds(), ["Pad"])
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT, places=1)

    def test_an_extrude_edited_later_switches_when_finished_not_when_let_go(self):
        # Letting go starts the other tool on the sketch: only for the extrude its panel just made. An
        # existing one, double-clicked, would get a second feature on its sketch.
        self.start("PartDesign_Pad")
        self.type("0.25{Return}")
        pad = next(o for o in self.body.Group if o.TypeId == "PartDesign::Pad" and o != self.block)
        pad.ViewObject.doubleClicked()
        settle(600)
        self.drag_to(-0.25)
        self.assertEqual(self.in_edit(), "PartDesign::Pad", "its own panel should still be open")
        self.finish()
        self.assertEqual(self.kinds(), ["Pad", "Pocket"])
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT - self.cylinder(0.25 * INCH), places=1)

    def test_an_extrude_let_go_pointing_away_stays(self):
        self.start("PartDesign_Pad")
        self.drag_to(0.25)
        self.assertEqual(self.in_edit(), "PartDesign::Pad")


class Typing(OnABlock):
    def test_a_length_typed_into_the_part_cuts(self):
        self.start("PartDesign_Pad")
        self.type("-0.25{Return}")
        self.assertFalse(FreeCADGui.Control.activeDialog(), "Return should finish")
        self.assertEqual(self.kinds(), ["Pad", "Pocket"])
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT - self.cylinder(0.25 * INCH), places=1)
        self.doc.undo()  # one step
        self.assertEqual(self.kinds(), ["Pad"])

    def test_a_cut_typed_out_of_the_part_extrudes(self):
        self.start("PartDesign_Pocket")
        self.type("-0.25{Return}")
        self.assertFalse(FreeCADGui.Control.activeDialog(), "Return should finish")
        self.assertEqual(self.kinds(), ["Pad", "Pad"])
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT + self.cylinder(0.25 * INCH), places=1)

    def test_a_cut_into_the_part_stays(self):
        self.start("PartDesign_Pocket")
        self.type("0.25{Return}")
        self.assertEqual(self.kinds(), ["Pad", "Pocket"])
