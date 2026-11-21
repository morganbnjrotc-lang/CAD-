# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click hole chamfer (PLAN 3.9): studio.services.holes finds a hole's opening edges, where it starts
on the part's face, and a chamfer size to start with."""

import unittest
import uuid

import FreeCAD
import Part

from studio.services import holes

V = FreeCAD.Vector


class Holes(unittest.TestCase):
    """A 20 x 20 x 10 mm block with holes from its top face."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("Holes" + uuid.uuid4().hex[:8])
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        h = 10
        corners = [V(-h, -h, 0), V(h, -h, 0), V(h, h, 0), V(-h, h, 0)]
        base = self.sketch(0, *(Part.LineSegment(a, b) for a, b in zip(corners, corners[1:] + corners[:1])))
        pad = self.body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = base
        pad.Length = 10
        self.doc.recompute()

    def sketch(self, height, *shapes):
        sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[3], "")]
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, height), FreeCAD.Rotation())
        for shape in shapes:
            sketch.addGeometry(shape)
        self.doc.recompute()
        return sketch

    def hole(self, *centers, diameter=4.0, through=False):
        # on the top face; a hole drills against its sketch's normal, down into the block
        sketch = self.sketch(10, *(Part.Circle(V(x, y, 0), V(0, 0, 1), diameter / 2) for x, y in centers))
        hole = self.body.newObject("PartDesign::Hole", "Hole")
        hole.Profile = sketch
        hole.Diameter = diameter
        hole.DepthType = "ThroughAll" if through else "Dimension"
        hole.Depth = 6
        self.doc.recompute()
        self.assertTrue(hole.isValid(), hole.getStatusString())
        return hole

    def test_the_opening_of_a_hole(self):
        hole = self.hole((0, 0))
        edges = holes.opening_edges(hole)
        self.assertEqual(len(edges), 1, edges)
        edge = hole.Shape.getElement(edges[0])
        self.assertAlmostEqual(edge.Curve.Radius, 2.0, places=6)
        self.assertAlmostEqual(edge.Curve.Center.z, 10.0, places=6)

    def test_every_hole_of_the_feature(self):
        self.assertEqual(len(holes.opening_edges(self.hole((-5, -5), (5, 5), (5, -5)))), 3)

    def test_not_where_a_through_hole_comes_out(self):
        edges = holes.opening_edges(self.hole((0, 0), through=True))
        self.assertEqual(len(edges), 1)

    def test_a_size_to_start_with(self):
        self.assertAlmostEqual(holes.chamfer_size(self.hole((0, 0), diameter=4.0)), 0.4)
        self.assertAlmostEqual(holes.chamfer_size(self.hole((0, 0), diameter=1.0)), 0.2)  # no smaller

    def test_not_a_hole(self):
        self.assertEqual(holes.opening_edges(self.body.Tip.Profile[0]), [])

    def test_the_chamfer_made_from_them_is_sound(self):
        hole = self.hole((0, 0))
        before = self.body.Shape.Volume
        chamfer = self.body.newObject("PartDesign::Chamfer", "Chamfer")
        chamfer.Base = (hole, holes.opening_edges(hole))
        chamfer.Size = holes.chamfer_size(hole)
        self.doc.recompute()
        self.assertTrue(chamfer.isValid(), chamfer.getStatusString())
        self.assertLess(self.body.Shape.Volume, before)
