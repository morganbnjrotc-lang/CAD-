# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picking a sketch's regions while Extrude is open, like Fusion (PLAN 3.16, the user 2026-11-22: "the sketch
should disappear after the extrusion has been confirmed so I can select all the things that apply and
deselect anything that might be accidentally selected"). studio.services.profile_regions tells which regions
of its sketch an Extrude, Cut, Revolve or Revolve Cut takes, and adds or takes one out.

A sketch's regions are the areas its closed shapes enclose, each one a face FreeCAD can pick
("InternalFace1"…). The sketch here: a 10 x 10 square with a circle in it (two regions: the square around
the circle, and the circle) and a second 10 x 10 square beside it.
"""

import math
import unittest
import uuid

import FreeCAD
import Part

from studio.services import profile_regions

V = FreeCAD.Vector
LENGTH = 5.0
RADIUS = 2.0
SQUARE = 100.0  # mm², each square
DISK = math.pi * RADIUS ** 2
RING = SQUARE - DISK  # the first square around the circle


class Regions(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("ProfileRegions" + uuid.uuid4().hex[:8])
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        self.sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]  # the XY plane
        self.sketch.MapMode = "FlatFace"
        self.square(0, 0)
        self.square(20, 0)
        self.sketch.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), RADIUS))
        self.doc.recompute()
        areas = {round(f.Area, 3): n for n, f in enumerate(self.sketch.InternalShape.Faces, 1)}
        self.ring, self.square2, self.disk = areas[round(RING, 3)], areas[SQUARE], areas[round(DISK, 3)]

    def square(self, x, y):
        corners = [V(x, y, 0), V(x + 10, y, 0), V(x + 10, y + 10, 0), V(x, y + 10, 0)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            self.sketch.addGeometry(Part.LineSegment(a, b))

    def extrude(self, *regions, kind="PartDesign::Pad"):
        """As Part Design's command makes it from the regions picked first (none: the sketch picked whole)."""
        feature = self.body.newObject(kind, kind.split("::")[1])
        feature.Profile = (self.sketch, [f"InternalFace{n}" for n in regions])
        if kind == "PartDesign::Revolution":
            feature.ReferenceAxis = (self.sketch, ["V_Axis"])
            feature.Angle = 90
        else:
            feature.Length = LENGTH
        self.doc.recompute()
        self.assertTrue(feature.isValid(), feature.getStatusString())
        return feature

    def area(self, feature):
        """The extruded area: the volume over the length."""
        self.doc.recompute()
        self.assertTrue(feature.isValid(), feature.getStatusString())
        return feature.Shape.Volume / LENGTH

    # -- which regions ----------------------------------------------------------------------------
    def test_the_regions_picked(self):
        feature = self.extrude(self.ring, self.square2)
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2})

    def test_a_whole_sketch_takes_the_regions_it_extrudes(self):
        # the circle in the square is a hole: the whole sketch extrudes the ring and the other square
        feature = self.extrude()
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2})

    def test_a_whole_sketch_as_part_designs_command_stores_it(self):
        feature = self.extrude()
        feature.Profile = (self.sketch, [""])  # the sketch picked in the model tree
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2})
        self.assertTrue(profile_regions.toggle(feature, self.disk))
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2, self.disk})

    def test_a_whole_sketch_moved_and_turned(self):
        # its regions are kept in the sketch's own frame, its shapes where the sketch is
        self.sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[4], "")]  # the XZ plane
        self.sketch.AttachmentOffset = FreeCAD.Placement(V(3, 4, 5), FreeCAD.Rotation(V(0, 0, 1), 30))
        self.doc.recompute()
        self.assertEqual(profile_regions.taken(self.extrude()), {self.ring, self.square2})

    def test_a_profile_that_isnt_regions(self):
        feature = self.extrude(self.ring)
        feature.Profile = (self.sketch, ["Edge1"])
        self.assertIsNone(profile_regions.taken(feature))

    def test_the_region_a_picked_name_is(self):
        self.assertEqual(profile_regions.region("InternalFace12"), 12)
        self.assertEqual(profile_regions.region(";#22:1;;:Hb83:1,F.InternalFace1"), 1)  # FreeCAD's long name
        self.assertIsNone(profile_regions.region("Edge3"))
        self.assertIsNone(profile_regions.region("Face3"))
        self.assertIsNone(profile_regions.region(""))

    # -- adding and taking out ----------------------------------------------------------------------
    def test_a_region_added(self):
        feature = self.extrude(self.ring)
        self.assertTrue(profile_regions.toggle(feature, self.square2))
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2})
        self.assertAlmostEqual(self.area(feature), RING + SQUARE, places=3)

    def test_a_region_taken_out(self):
        feature = self.extrude(self.ring, self.square2)
        self.assertTrue(profile_regions.toggle(feature, self.ring))
        self.assertEqual(profile_regions.taken(feature), {self.square2})
        self.assertAlmostEqual(self.area(feature), SQUARE, places=3)

    def test_the_hole_added_to_a_whole_sketch_fills_it(self):
        feature = self.extrude()
        self.assertTrue(profile_regions.toggle(feature, self.disk))
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2, self.disk})
        self.assertAlmostEqual(self.area(feature), 2 * SQUARE, places=3)

    def test_a_region_taken_out_of_a_whole_sketch(self):
        feature = self.extrude()
        self.assertTrue(profile_regions.toggle(feature, self.square2))
        self.assertEqual(profile_regions.taken(feature), {self.ring})
        self.assertAlmostEqual(self.area(feature), RING, places=3)

    def test_the_last_region_stays(self):
        # FreeCAD reads a profile with no regions as the whole sketch
        feature = self.extrude(self.ring)
        self.assertFalse(profile_regions.toggle(feature, self.ring))
        self.assertEqual(profile_regions.taken(feature), {self.ring})

    def test_not_a_region_of_the_sketch(self):
        feature = self.extrude(self.ring)
        self.assertFalse(profile_regions.toggle(feature, 9))
        self.assertEqual(profile_regions.taken(feature), {self.ring})

    def test_nothing_changes_on_a_profile_that_isnt_regions(self):
        feature = self.extrude(self.ring)
        feature.Profile = (self.sketch, ["Edge1"])
        self.assertFalse(profile_regions.toggle(feature, self.square2))
        self.assertEqual(feature.Profile[1], ["Edge1"])

    def test_revolve_too(self):
        feature = self.extrude(self.square2, kind="PartDesign::Revolution")
        self.assertTrue(profile_regions.toggle(feature, self.ring))
        self.assertEqual(profile_regions.taken(feature), {self.ring, self.square2})

    def test_which_features(self):
        self.assertEqual(profile_regions.KINDS, {"PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Revolution",
                                                 "PartDesign::Groove"})
