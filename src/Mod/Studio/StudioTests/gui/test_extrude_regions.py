# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picking a sketch's regions while Extrude is open, in the app (PLAN 3.16; studio.shell.extrude_regions).

The user (2026-11-22): with one region picked, Extrude hid the sketch straight away, so adding a second one
meant cancelling, picking both and starting again. "The sketch should disappear after the extrusion has
been confirmed so I can select all the things that apply and deselect anything that might be accidentally
selected." The sketch stays shown while the panel is open; a click on a region adds it or takes it out;
Finish hides the sketch. Clicks are real mouse clicks in the 3D view.

The sketch lies on top of a 40 x 20 x 5 mm block: a 10 x 10 square with a circle in it (two regions: the
square around the circle, the circle) and a second 10 x 10 square beside it.
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui
import Part

import StudioGui
from StudioTests.gui.sketch_input import settle

V = FreeCAD.Vector
TOP = 5.0  # mm, the block's top, where the sketch lies
RADIUS = 2.0


class _AnyPick:
    """A selection gate letting everything through, as a panel's own picking (a face to extrude up to)
    puts one on."""

    def allow(self, doc, obj, sub):
        return True


class PickingRegions(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("ExtrudeRegions" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        base = self.new_sketch(0)
        self.square(base, -5, -5, 40, 20)
        self.block = self.body.newObject("PartDesign::Pad", "Block")
        self.block.Profile = base
        self.block.Length = TOP
        self.doc.recompute()
        base.Visibility = False
        self.sketch = self.new_sketch(TOP)
        self.square(self.sketch, 0, 0, 10, 10)
        self.square(self.sketch, 20, 0, 10, 10)
        self.sketch.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), RADIUS))
        self.doc.recompute()
        self.sketch.Visibility = True
        areas = {round(f.Area): n for n, f in enumerate(self.sketch.InternalShape.Faces, 1)}
        self.ring, self.square2, self.disk = areas[87], areas[100], areas[13]
        view = FreeCADGui.getDocument(self.doc.Name).activeView()
        view.viewIsometric()
        view.fitAll()
        settle(300)

    def new_sketch(self, height):
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]  # the XY plane
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, height), FreeCAD.Rotation())
        return sketch

    @staticmethod
    def square(sketch, x, y, width, height):
        corners = [V(x, y, 0), V(x + width, y, 0), V(x + width, y + height, 0), V(x, y + height, 0)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            sketch.addGeometry(Part.LineSegment(a, b))

    def close(self):
        dialog = FreeCADGui.Control.activeTaskDialog()
        if dialog is not None:
            dialog.reject()
            settle(300)
        settle(100)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    # -- what the user does --------------------------------------------------------------------------
    def start(self, *regions, command="PartDesign_Pad"):
        """Picks the regions (none: the sketch, as in the model tree) and starts Extrude."""
        FreeCADGui.Selection.clearSelection()
        for n in regions:
            FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, f"InternalFace{n}")
        if not regions:
            FreeCADGui.Selection.addSelection(self.sketch)
        FreeCADGui.runCommand(command, 0)
        settle(800)
        return FreeCADGui.getDocument(self.doc.Name).getInEdit().Object

    def click(self, x, y):
        """A click on the sketch at (x, y) mm; the pointer moves there first, as a real one does."""
        px, py = StudioGui.view_point(x, y, TOP)
        StudioGui.view_mouse("move", px, py)
        settle(150)
        StudioGui.view_mouse("click", px, py)
        settle(600)

    def click_ring(self):
        self.click(1, 1)  # in the first square, outside its circle

    def click_square2(self):
        self.click(25, 5)

    def click_disk(self):
        self.click(5, 5)

    def finish(self):
        FreeCADGui.Control.activeTaskDialog().accept()
        settle(800)

    def cancel(self):
        FreeCADGui.Control.activeTaskDialog().reject()
        settle(800)

    def regions(self, feature):
        return sorted(feature.Profile[1])

    def names(self, *regions):
        return sorted(f"InternalFace{n}" for n in regions)

    def sketch_shown(self):
        return self.sketch.ViewObject.isVisible()

    # -- the tests -----------------------------------------------------------------------------------
    def test_the_sketch_stays_shown_while_extrude_is_open(self):
        self.start(self.ring)
        self.assertTrue(self.sketch_shown())

    def test_a_click_on_another_region_adds_it(self):
        extrude = self.start(self.ring)
        self.click_square2()
        self.assertEqual(self.regions(extrude), self.names(self.ring, self.square2))
        self.assertEqual(FreeCADGui.Selection.getSelectionEx("", 0), [], "the click left something selected")
        self.assertTrue(extrude.isValid(), extrude.getStatusString())

    def test_a_second_click_takes_it_out_again(self):
        extrude = self.start(self.ring)
        self.click_square2()
        self.click_square2()
        self.assertEqual(self.regions(extrude), self.names(self.ring))

    def test_a_click_on_a_region_being_extruded_takes_it_out(self):
        extrude = self.start(self.ring, self.square2)
        self.click_ring()
        self.assertEqual(self.regions(extrude), self.names(self.square2))

    def test_the_circle_added_to_the_whole_sketch(self):
        extrude = self.start()
        self.click_disk()
        self.assertEqual(self.regions(extrude), self.names(self.ring, self.square2, self.disk))

    def test_finish_hides_the_sketch(self):
        extrude = self.start(self.ring)
        self.click_square2()
        self.finish()
        self.assertIsNone(FreeCADGui.getDocument(self.doc.Name).getInEdit())
        self.assertFalse(self.sketch_shown())
        self.assertEqual(self.regions(extrude), self.names(self.ring, self.square2))

    def test_cancel_leaves_no_extrude_and_the_sketch_shown(self):
        self.start(self.ring)
        self.click_square2()
        self.cancel()
        self.assertIsNone(self.doc.getObject("Pad"))
        self.assertTrue(self.sketch_shown())

    def test_cut_too(self):
        cut = self.start(self.ring, command="PartDesign_Pocket")
        self.assertTrue(self.sketch_shown())
        self.click_square2()
        self.assertEqual(self.regions(cut), self.names(self.ring, self.square2))

    def test_editing_an_extrude_shows_its_sketch_and_cancel_hides_it_again(self):
        extrude = self.start(self.ring)
        self.finish()
        # As the user does: the double-click opens the edit's undo step (Cancel takes back what changed)
        extrude.ViewObject.doubleClicked()
        settle(800)
        self.assertTrue(self.sketch_shown())
        self.click_square2()
        self.assertEqual(self.regions(extrude), self.names(self.ring, self.square2))
        self.cancel()
        self.assertFalse(self.sketch_shown())
        self.assertEqual(self.regions(extrude), self.names(self.ring))

    def test_a_click_while_the_panel_picks_is_the_panels(self):
        # picking a face to extrude up to (or an axis), FreeCAD has a selection gate on
        extrude = self.start(self.ring)
        FreeCADGui.Selection.addSelectionGate(_AnyPick())
        self.addCleanup(FreeCADGui.Selection.removeSelectionGate)
        self.click_square2()
        self.assertEqual(self.regions(extrude), self.names(self.ring))

    def test_dragged_into_the_part_the_cut_keeps_the_regions(self):
        self.start(self.ring)
        self.click_square2()
        self.assertTrue(StudioGui.set_field("lengthEdit", -2.0), "no length box")
        settle(500)
        width, height = StudioGui.view_size()
        StudioGui.view_mouse("click", 12, height - 12)  # the mouse let go, in an empty corner
        settle(1500)
        cut = FreeCADGui.getDocument(self.doc.Name).getInEdit().Object
        self.assertEqual(cut.TypeId, "PartDesign::Pocket")
        self.assertEqual(self.regions(cut), self.names(self.ring, self.square2))
        self.assertTrue(self.sketch_shown())
