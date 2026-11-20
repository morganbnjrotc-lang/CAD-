# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude or cut by direction, like Fusion (PLAN 3.5, the user's pick 2026-11-20).

Dragging Extrude's arrow into the part makes it a cut; dragging a cut's arrow back out of the part makes
it an extrude again. FreeCAD has two features for that, Pad and Pocket, and a Pad dragged into the part
just pads backwards, into material that is already there: nothing shows. studio.services.extrude tells
when the feature should be the other one and puts the other one in its place, the same shape of tool.
"""

import math
import unittest
import uuid

import FreeCAD
import Part

from studio.services import extrude

V = FreeCAD.Vector
BLOCK = 20.0  # mm, a 20 x 20 x 10 block
HEIGHT = 10.0
RADIUS = 3.0


class Body(unittest.TestCase):
    """A body with a block in it, and a circle sketched on the block's top face."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("ExtrudeDirection" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.doc.recompute()

    def sketch(self, height, *shapes):
        """A sketch on the XY plane raised to `height`; its normal points up (+Z)."""
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]  # the XY plane
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, height), FreeCAD.Rotation())
        for shape in shapes:
            sketch.addGeometry(shape)
        self.doc.recompute()
        return sketch

    def square(self, size):
        h = size / 2
        corners = [V(-h, -h, 0), V(h, -h, 0), V(h, h, 0), V(-h, h, 0)]
        return [Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])]

    def feature(self, kind, sketch, length, reversed_=False):
        """As Part Design's Pad and Pocket commands make it: along the sketch's normal (N_Axis)."""
        feature = self.body.newObject(kind, kind.split("::")[1])
        feature.Profile = sketch
        feature.Length = length
        feature.Reversed = reversed_
        feature.ReferenceAxis = (sketch, ["N_Axis"])
        self.doc.recompute()
        self.assertTrue(feature.isValid(), feature.getStatusString())
        return feature

    def block(self):
        return self.feature("PartDesign::Pad", self.sketch(0, *self.square(BLOCK)), HEIGHT)

    def on_top(self, kind, length, reversed_=False):
        """The block, then a circle on its top face extruded (Pad) or cut (Pocket) by `length`."""
        self.block()
        return self.feature(kind, self.sketch(HEIGHT, Part.Circle(V(0, 0, 0), V(0, 0, 1), RADIUS)), length, reversed_)

    def volume(self):
        return self.body.Shape.Volume

    def cylinder(self, depth):
        return math.pi * RADIUS ** 2 * depth


class WhenToSwitch(Body):
    def test_an_extrude_dragged_into_the_part_becomes_a_cut(self):
        self.assertEqual(extrude.becomes(self.on_top("PartDesign::Pad", -4)), "PartDesign::Pocket")

    def test_an_extrude_turned_around_into_the_part_becomes_a_cut(self):
        # Clicking the arrow (or Reversed) turns it around: into the part, with a positive length.
        self.assertEqual(extrude.becomes(self.on_top("PartDesign::Pad", 4, reversed_=True)), "PartDesign::Pocket")

    def test_an_extrude_away_from_the_part_stays(self):
        self.assertIsNone(extrude.becomes(self.on_top("PartDesign::Pad", 4)))

    def test_an_extrude_with_nothing_behind_it_stays(self):
        # The body's first solid: below the sketch there is nothing to cut.
        pad = self.feature("PartDesign::Pad", self.sketch(0, *self.square(BLOCK)), -HEIGHT)
        self.assertIsNone(extrude.becomes(pad))

    def test_a_cut_dragged_out_of_the_part_becomes_an_extrude(self):
        self.assertEqual(extrude.becomes(self.on_top("PartDesign::Pocket", -4)), "PartDesign::Pad")

    def test_a_cut_into_the_part_stays(self):
        self.assertIsNone(extrude.becomes(self.on_top("PartDesign::Pocket", 4)))

    def test_a_cut_from_inside_the_part_stays_whichever_way(self):
        # Sketched halfway up the block: either way the cut goes, there is material to cut.
        self.block()
        sketch = self.sketch(HEIGHT / 2, Part.Circle(V(0, 0, 0), V(0, 0, 1), RADIUS))
        self.assertIsNone(extrude.becomes(self.feature("PartDesign::Pocket", sketch, -3)))

    def test_only_the_last_feature_switches(self):
        # Something built on it would lose what it refers to.
        pad = self.on_top("PartDesign::Pad", -4)
        self.feature("PartDesign::Pad", self.sketch(-5, *self.square(4)), 1)
        self.assertIsNone(extrude.becomes(pad))

    def test_only_a_plain_length_switches(self):
        for prop, value in (("SideType", "Symmetric"), ("SideType", "Two sides"), ("Type", "UpToLast")):
            with self.subTest(**{prop: value}):
                pad = self.on_top("PartDesign::Pad", -4)
                setattr(pad, prop, value)
                self.doc.recompute()
                self.assertIsNone(extrude.becomes(pad))

    def test_made_by_a_script_without_a_direction_it_switches_too(self):
        pad = self.on_top("PartDesign::Pad", -4)
        pad.ReferenceAxis = None
        self.doc.recompute()
        self.assertEqual(extrude.becomes(pad), "PartDesign::Pocket")

    def test_a_direction_of_its_own_stays(self):
        pad = self.on_top("PartDesign::Pad", -4)
        pad.ReferenceAxis = (self.body.Origin.OriginFeatures[0], [""])  # the X axis, slanting it
        self.doc.recompute()
        self.assertIsNone(extrude.becomes(pad))

    def test_other_features_never_switch(self):
        self.assertIsNone(extrude.becomes(self.block().Profile[0]))  # a sketch


class Switching(Body):
    def test_the_cut_takes_the_extrudes_place(self):
        pad = self.on_top("PartDesign::Pad", -4)
        name, before = pad.Name, self.volume()
        cut = extrude.switch(pad)
        self.doc.recompute()
        self.assertEqual(cut.TypeId, "PartDesign::Pocket")
        self.assertEqual(self.body.Tip, cut)
        self.assertIsNone(self.doc.getObject(name), "the extrude should be gone")
        self.assertAlmostEqual(self.volume(), before - self.cylinder(4), places=3)

    def test_the_extrude_takes_the_cuts_place(self):
        cut = self.on_top("PartDesign::Pocket", -4)
        pad = extrude.switch(cut)
        self.doc.recompute()
        self.assertEqual(pad.TypeId, "PartDesign::Pad")
        self.assertEqual(self.body.Tip, pad)
        self.assertAlmostEqual(self.volume(), BLOCK * BLOCK * HEIGHT + self.cylinder(4), places=3)

    def assertSameTool(self, feature):
        before = feature.AddSubShape.BoundBox
        after = extrude.switch(feature)
        self.doc.recompute()
        self.assertTrue(after.isValid(), after.getStatusString())
        box = after.AddSubShape.BoundBox
        for a, b in ((box.XMin, before.XMin), (box.XMax, before.XMax), (box.YMin, before.YMin),
                     (box.YMax, before.YMax), (box.ZMin, before.ZMin), (box.ZMax, before.ZMax)):
            self.assertAlmostEqual(a, b, places=6, msg=f"{before} became {box}")

    def test_a_cut_from_an_extrude_dragged_in_has_the_same_tool(self):
        self.assertSameTool(self.on_top("PartDesign::Pad", -4))

    def test_a_cut_from_an_extrude_turned_around_has_the_same_tool(self):
        self.assertSameTool(self.on_top("PartDesign::Pad", 4, reversed_=True))

    def test_an_extrude_from_a_cut_dragged_out_has_the_same_tool(self):
        self.assertSameTool(self.on_top("PartDesign::Pocket", -4))

    def test_in_a_body_moved_away_from_the_origin(self):
        self.body.Placement = FreeCAD.Placement(V(100, 50, 30), FreeCAD.Rotation(V(1, 0, 0), 30))
        pad = self.on_top("PartDesign::Pad", -4)
        self.assertEqual(extrude.becomes(pad), "PartDesign::Pocket")
        before = self.volume()
        extrude.switch(pad)
        self.doc.recompute()
        self.assertAlmostEqual(self.volume(), before - self.cylinder(4), places=3)

    def test_keeps_the_sketch_and_refine(self):
        pad = self.on_top("PartDesign::Pad", -4)
        pad.Refine = True
        sketch = pad.Profile[0]
        cut = extrude.switch(pad)
        self.assertEqual(cut.Profile[0], sketch)
        self.assertTrue(cut.Refine)
        self.assertEqual(cut.ReferenceAxis, (sketch, ["N_Axis"]))

    def test_one_undo_step_with_the_change_that_led_to_it(self):
        pad = self.on_top("PartDesign::Pad", 4)
        self.doc.openTransaction("Extrude")
        pad.Length = -4
        self.doc.recompute()
        extrude.switch(pad)
        self.doc.recompute()
        self.doc.commitTransaction()
        self.doc.undo()
        self.doc.recompute()
        kinds = [o.TypeId for o in self.body.Group]
        self.assertNotIn("PartDesign::Pocket", kinds)
        self.assertEqual(self.body.Tip.TypeId, "PartDesign::Pad")
        self.assertAlmostEqual(self.body.Tip.Length.Value, 4)
