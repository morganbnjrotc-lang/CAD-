# SPDX-License-Identifier: LGPL-2.1-or-later
"""Emboss on a round face, like Fusion's (PLAN 4.3, docs/adr/0016): studio.services.emboss.

A sketch drawn on a plane along a round face (a plane parallel to its axis: through it, tangent to it or
offset) is wrapped onto the face as the face would unroll: across the sketch becomes around the face, along it
stays along the axis, so every length in the sketch is kept on the face. The wrapped shapes are raised from the
face or cut into it by a depth, as a Part Design feature (Emboss: adds; Deboss: cuts).

A cylinder 20 mm in radius, 40 mm tall, on the XY plane; profiles on the XZ plane (along the axis), whose
normal points to the face's side the wrap lands on.
"""

import math
import unittest
import uuid

import FreeCAD
import Part

from studio.services import emboss

V = FreeCAD.Vector
R, HEIGHT = 20.0, 40.0


class OnACylinder(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("Emboss" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1
        self.addCleanup(lambda: FreeCAD.closeDocument(self.doc.Name))
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        base = self.sketch(plane=3)
        base.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), R))
        self.pad = self.body.newObject("PartDesign::Pad", "Pad")
        self.pad.Profile = base
        self.pad.Length = HEIGHT
        self.doc.recompute()
        self.volume = self.pad.Shape.Volume
        self.face = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Cylinder")

    def sketch(self, plane=4, offset=0.0):
        """A sketch on the body's XY (3), XZ (4) or YZ (5) plane, `offset` along its normal."""
        sketch = self.body.newObject("Sketcher::SketchObject", "Profile")
        sketch.AttachmentSupport = [(self.body.Origin.OriginFeatures[plane], "")]
        sketch.MapMode = "FlatFace"
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, offset), FreeCAD.Rotation())
        self.doc.recompute()
        return sketch

    def rectangle(self, sketch, x0, y0, x1, y1):
        corners = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            sketch.addGeometry(Part.LineSegment(a, b))
        self.doc.recompute()
        return sketch

    def square_profile(self, x=-5.0, y=15.0, size=10.0):
        return self.rectangle(self.sketch(), x, y, x + size, y + size)

    def emboss(self, profile, depth=1.0, cut=False):
        feature = emboss.make(self.body, profile, self.pad, self.face, depth, cut)
        self.doc.recompute()
        self.assertTrue(feature.isValid(), feature.getStatusString())
        return feature

    # the wrap

    def test_lengths_are_kept(self):
        profile = self.sketch()
        profile.addGeometry(Part.LineSegment(V(-8, 10, 0), V(8, 10, 0)))  # across: around the face
        profile.addGeometry(Part.LineSegment(V(0, 12, 0), V(0, 30, 0)))  # along the axis
        profile.addGeometry(Part.LineSegment(V(-6, 5, 0), V(9, 25, 0)))  # slanted: a helix on the face
        profile.addGeometry(Part.Circle(V(3, 20, 0), V(0, 0, 1), 4))
        self.doc.recompute()
        flat = [e.Length for e in profile.Shape.Edges]
        wrapped = [e.Length for e in emboss.wrapped_edges(profile, self.pad, self.face)]
        for a, b in zip(sorted(flat), sorted(wrapped)):
            self.assertAlmostEqual(a, b, places=6)

    def test_on_the_face(self):
        for edge in emboss.wrapped_edges(self.square_profile(), self.pad, self.face):
            for point in edge.discretize(8):
                self.assertAlmostEqual(math.hypot(point.x, point.y), R, places=6)

    def test_on_the_side_the_sketch_faces(self):
        profile = self.square_profile()
        normal = profile.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
        middle = Part.Compound(emboss.wrapped_edges(profile, self.pad, self.face)).BoundBox.Center
        self.assertGreater(V(middle.x, middle.y, 0).dot(normal), 0.9 * R)
        self.assertAlmostEqual(middle.z, 20.0, places=6)  # the square's middle, along the axis

    def test_a_tangent_or_offset_plane_wraps_the_same(self):
        # the sketch is wrapped as seen along its normal: how far its plane is from the axis doesn't matter
        through = Part.Compound(emboss.wrapped_edges(self.square_profile(), self.pad, self.face)).BoundBox
        for offset in (R, R + 5, -7):
            with self.subTest(offset=offset):
                profile = self.rectangle(self.sketch(offset=offset), -5, 15, 5, 25)
                moved = Part.Compound(emboss.wrapped_edges(profile, self.pad, self.face)).BoundBox
                for a, b in zip((through.XMin, through.YMin, through.ZMin, through.XMax, through.YMax, through.ZMax),
                                (moved.XMin, moved.YMin, moved.ZMin, moved.XMax, moved.YMax, moved.ZMax)):
                    self.assertAlmostEqual(a, b, places=6)

    # raised and cut

    def test_raised_by_the_depth(self):
        # a 10 mm square raised 1 mm on a 20 mm radius: 100 mm² times 1 mm, a little more outward
        feature = self.emboss(self.square_profile(), depth=1.0)
        self.assertEqual(feature.TypeId, "PartDesign::FeatureAdditivePython")
        self.assertAlmostEqual(feature.Shape.Volume - self.volume, 100 * (1 + 1 / (2 * R)), places=4)
        self.assertEqual(len(feature.Shape.Solids), 1)

    def test_cut_by_the_depth(self):
        feature = self.emboss(self.square_profile(), depth=1.0, cut=True)
        self.assertEqual(feature.TypeId, "PartDesign::FeatureSubtractivePython")
        self.assertAlmostEqual(self.volume - feature.Shape.Volume, 100 * (1 - 1 / (2 * R)), places=4)

    def test_letters_keep_their_holes(self):
        # an O: the wrapped ring, not a disc
        profile = self.sketch()
        profile.addGeometry(Part.Circle(V(0, 20, 0), V(0, 0, 1), 6))
        profile.addGeometry(Part.Circle(V(0, 20, 0), V(0, 0, 1), 3))
        self.doc.recompute()
        feature = self.emboss(profile, depth=1.0)
        ring = math.pi * (6 ** 2 - 3 ** 2) * (1 + 1 / (2 * R))
        # a disc would add 29 mm³ more; OCC thickens curved outlines with approximated sides (~0.005 % here)
        self.assertAlmostEqual(feature.Shape.Volume - self.volume, ring, delta=1e-4 * ring)

    def test_text(self):
        from StudioTests.test_sketch_text import NOTO
        from studio.services import fonts, sketch_text
        from studio.services.sketch_text import TextBox

        profile = self.sketch()
        sketch_text.add(profile, TextBox("Lesleigh", "Noto Sans", "Regular", 6.0, 1.0, 1.0, fit=True),
                        fonts.read(NOTO), corner=(-15.0, 17.0))
        self.doc.recompute()
        feature = self.emboss(profile, depth=0.8)
        self.assertEqual(len(feature.Shape.Solids), 1)
        self.assertGreater(feature.Shape.Volume, self.volume)

    def test_it_follows_the_sketch(self):
        profile = self.square_profile()
        feature = self.emboss(profile)
        profile.AttachmentOffset = FreeCAD.Placement(V(0, 5, 0), FreeCAD.Rotation())  # 5 mm up the axis
        self.doc.recompute()
        self.assertTrue(feature.isValid(), feature.getStatusString())
        added = feature.Shape.cut(self.pad.Shape)
        self.assertAlmostEqual(added.BoundBox.Center.z, 25.0, places=3)

    def test_a_deeper_emboss(self):
        feature = self.emboss(self.square_profile(), depth=1.0)
        feature.Depth = 2.0
        self.doc.recompute()
        self.assertAlmostEqual(feature.Shape.Volume - self.volume, 100 * (2 + 4 / (2 * R)), places=4)

    def test_switched_to_a_cut(self):
        feature = self.emboss(self.square_profile(), depth=1.0)
        name = feature.Name
        cut = emboss.set_cut(feature, True)
        self.doc.recompute()
        self.assertEqual(cut.TypeId, "PartDesign::FeatureSubtractivePython")
        self.assertIsNone(self.doc.getObject(name))
        self.assertEqual(self.body.Tip, cut)
        self.assertEqual(cut.Depth.Value, 1.0)
        self.assertAlmostEqual(self.volume - cut.Shape.Volume, 100 * (1 - 1 / (2 * R)), places=4)

    # refused

    def test_a_sketch_across_the_axis_is_refused(self):
        profile = self.rectangle(self.sketch(plane=3, offset=10), -5, -5, 5, 5)
        with self.assertRaisesRegex(ValueError, "along the round face"):
            emboss.wrapped_edges(profile, self.pad, self.face)

    def test_a_flat_face_is_refused(self):
        flat = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                    if f.Surface.__class__.__name__ == "Plane")
        with self.assertRaisesRegex(ValueError, "isn't round"):
            emboss.make(self.body, self.square_profile(), self.pad, flat)

    def test_nothing_raised_on_the_face_is_an_error(self):
        # the square above the cylinder's top: wrapped onto the face's surface, but off the face
        feature = emboss.make(self.body, self.square_profile(y=HEIGHT + 5), self.pad, self.face, 1.0)
        self.doc.recompute()
        self.assertFalse(feature.isValid())
        self.assertIn("off the face", feature.getStatusString())

    def test_nothing_cut_is_an_error(self):
        feature = emboss.make(self.body, self.square_profile(y=HEIGHT + 5), self.pad, self.face, 1.0, cut=True)
        self.doc.recompute()
        self.assertFalse(feature.isValid())
        self.assertIn("off the face", feature.getStatusString())

    def test_saved_and_reopened(self):
        import os
        import shutil
        import tempfile

        self.emboss(self.square_profile(), depth=1.0)
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, "emboss.FCStd")
        self.doc.saveAs(path)
        FreeCAD.closeDocument(self.doc.Name)  # else opening the file gives back the same document
        self.doc = FreeCAD.openDocument(path)
        feature = self.doc.getObject("Emboss")
        feature.Depth = 2.0
        self.doc.recompute()
        self.assertTrue(feature.isValid(), feature.getStatusString())
        self.assertAlmostEqual(feature.Shape.Volume - self.volume, 100 * (2 + 4 / (2 * R)), places=4)
