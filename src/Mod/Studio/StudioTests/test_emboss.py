# SPDX-License-Identifier: LGPL-2.1-or-later
"""Emboss on a round face, like Fusion's (PLAN 4.3, docs/adr/0016): studio.services.emboss.

A sketch drawn on a plane along a round face (a plane parallel to its axis: through it, tangent to it or
offset) is wrapped onto the face as the face would unroll: across the sketch becomes around the face, along it
stays along the axis, so every length in the sketch is kept on the face. The wrapped shapes are raised from the
face or cut into it by a depth, as a Part Design feature (Emboss: adds; Deboss: cuts).

A cylinder 20 mm in radius, 40 mm tall, on the XY plane; profiles on the XZ plane (along the axis), whose
normal points to the face's side the wrap lands on. And cones: a cone unrolls flat too (into a ring's slice), so
across the sketch becomes a level circle around the cone and along it goes up the cone's slope, lengths kept up
the slope and around the cone at the sketch's middle height (the sketch's shapes a little wider toward the
cone's wide end, narrower toward its tip, in proportion to its radius there). Any other face (flat, a dome, a
fillet) doesn't unroll: the sketch is projected onto it along the sketch's normal, on the side it looks at, and
its patches on the face raised or cut along the face's normal (letters on a dome stand out of it, not up).
"""

import math
import unittest
import uuid

import FreeCAD
import Part

from studio.services import emboss

V = FreeCAD.Vector
R, HEIGHT = 20.0, 40.0
CONES = ((20.0, 10.0), (10.0, 20.0))  # foot and top radii: narrowing upward, widening


class _Sketches:
    """Profiles on the body's planes, and embossing them on `self.pad`'s `self.face`."""

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


class OnACylinder(_Sketches, unittest.TestCase):
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


class OnACone(_Sketches, unittest.TestCase):
    """A cone 20 mm in radius at its foot and 10 mm at its top, 40 mm tall (sloping 14°), so 15 mm in radius at
    mid-height, where the profiles' middle is; and the same cone upside down (widening upward)."""

    def setUp(self):
        self.doc = None
        self.addCleanup(self.close)

    def close(self):
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None

    def cone(self, foot, top):
        """A new document with the cone in a body."""
        self.close()
        self.doc = FreeCAD.newDocument("EmbossCone" + uuid.uuid4().hex[:8])
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.foot, self.top = foot, top
        self.pad = self.body.newObject("PartDesign::AdditiveCone", "Cone")
        self.pad.Radius1, self.pad.Radius2, self.pad.Height = foot, top, HEIGHT
        self.doc.recompute()
        self.volume = self.pad.Shape.Volume
        self.face = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Cone")
        self.cos = HEIGHT / math.hypot(HEIGHT, foot - top)  # of its slope

    def radius_at(self, z):
        return self.foot + (self.top - self.foot) * z / HEIGHT

    def test_on_the_face(self):
        for foot, top in CONES:
            with self.subTest(foot=foot, top=top):
                self.cone(foot, top)
                for edge in emboss.wrapped_edges(self.square_profile(), self.pad, self.face):
                    for point in edge.discretize(8):
                        self.assertAlmostEqual(math.hypot(point.x, point.y), self.radius_at(point.z), places=6)

    def test_lengths_up_the_slope_and_around_the_middle_are_kept(self):
        for foot, top in CONES:
            with self.subTest(foot=foot, top=top):
                self.cone(foot, top)
                profile = self.sketch()
                profile.addGeometry(Part.LineSegment(V(-8, 20, 0), V(8, 20, 0)))  # across the middle
                profile.addGeometry(Part.LineSegment(V(3, 12, 0), V(3, 28, 0)))  # up the slope
                self.doc.recompute()
                flat = [e.Length for e in profile.Shape.Edges]
                wrapped = [e.Length for e in emboss.wrapped_edges(profile, self.pad, self.face)]
                for a, b in zip(sorted(flat), sorted(wrapped)):
                    self.assertAlmostEqual(a, b, places=6)

    def test_across_is_level_and_along_goes_up_the_slope(self):
        for foot, top in CONES:
            with self.subTest(foot=foot, top=top):
                self.cone(foot, top)
                profile = self.sketch()
                profile.addGeometry(Part.LineSegment(V(-8, 12, 0), V(8, 12, 0)))  # across, 8 mm below the middle
                profile.addGeometry(Part.LineSegment(V(4, 12, 0), V(4, 28, 0)))  # along, off the axis
                self.doc.recompute()
                across, along = emboss.wrapped_edges(profile, self.pad, self.face)
                heights = [p.z for p in across.discretize(9)]
                self.assertAlmostEqual(max(heights) - min(heights), 0.0, places=6)  # a level circle
                # 8 mm down the slope from mid-height, as long as the circle there is to the one at mid-height
                self.assertAlmostEqual(heights[0], 20.0 - 8.0 * self.cos, places=6)
                self.assertAlmostEqual(across.Length, 16.0 * self.radius_at(heights[0]) / self.radius_at(20.0),
                                       places=6)
                angles = [math.atan2(p.y, p.x) for p in along.discretize(9)]
                self.assertAlmostEqual(max(angles) - min(angles), 0.0, places=9)  # one of the cone's lines
                self.assertAlmostEqual(along.Length, 16.0, places=6)

    def test_on_the_side_the_sketch_faces_at_its_height(self):
        for foot, top in CONES:
            with self.subTest(foot=foot, top=top):
                self.cone(foot, top)
                profile = self.square_profile()
                normal = profile.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
                middle = Part.Compound(emboss.wrapped_edges(profile, self.pad, self.face)).BoundBox.Center
                self.assertGreater(V(middle.x, middle.y, 0).dot(normal), 0.9 * self.radius_at(20.0))
                self.assertAlmostEqual(middle.z, 20.0, places=6)

    def test_raised_and_cut_by_the_depth(self):
        # the 10 mm square on the cone at mid-height (15 mm radius), 1 mm along the face's normal: the cone
        # curves around by cos(slope) / radius, so 100 mm² times 1 mm, a little more outward and less inward
        for foot, top in CONES:
            with self.subTest(foot=foot, top=top):
                self.cone(foot, top)
                bulge = self.cos / (2 * 15.0)
                raised = self.emboss(self.square_profile(), depth=1.0)
                self.assertEqual(len(raised.Shape.Solids), 1)
                self.assertAlmostEqual(raised.Shape.Volume - self.volume, 100 * (1 + bulge), places=4)
                cut = self.emboss(self.square_profile(), depth=1.0, cut=True)
                self.assertAlmostEqual(raised.Shape.Volume - cut.Shape.Volume, 100 * (1 - bulge), places=4)

    def test_text(self):
        from StudioTests.test_sketch_text import NOTO
        from studio.services import fonts, sketch_text
        from studio.services.sketch_text import TextBox

        self.cone(20.0, 10.0)
        profile = self.sketch()
        sketch_text.add(profile, TextBox("Lesleigh", "Noto Sans", "Regular", 6.0, 1.0, 1.0, fit=True),
                        fonts.read(NOTO), corner=(-12.0, 17.0))
        self.doc.recompute()
        feature = self.emboss(profile, depth=0.8)
        self.assertEqual(len(feature.Shape.Solids), 1)
        self.assertGreater(feature.Shape.Volume, self.volume)


def shell(outer, inner, across=6.0, radius=20.0):
    """The volume between spheres `outer` and `inner` in radius, inside the cone from their middle through the
    circle `across` in radius around the pole of a sphere `radius` in radius."""
    return 2 * math.pi / 3 * (1 - math.sqrt(1 - (across / radius) ** 2)) * (outer ** 3 - inner ** 3)


class OnAnyFace(_Sketches, unittest.TestCase):
    """Faces that don't unroll: the top of a 40 x 40 x 20 mm box, and a dome (a sphere 20 mm in radius); the
    profiles on the XY plane, looking up at them."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("EmbossAny" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1
        self.addCleanup(lambda: FreeCAD.closeDocument(self.doc.Name))
        self.body = self.doc.addObject("PartDesign::Body", "Body")

    def box(self):
        self.pad = self.body.newObject("PartDesign::AdditiveBox", "Box")
        self.pad.Length, self.pad.Width, self.pad.Height = 40, 40, 20
        self.doc.recompute()
        self.volume = self.pad.Shape.Volume
        self.face = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                         if abs(f.CenterOfMass.z - 20) < 1e-9)

    def dome(self):
        self.pad = self.body.newObject("PartDesign::AdditiveSphere", "Sphere")
        self.pad.Radius = 20
        self.doc.recompute()
        self.volume = self.pad.Shape.Volume
        self.face = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Sphere")

    def up(self, tilt=0.0):
        """A profile on the XY plane, looking up; tilted `tilt` degrees about X."""
        sketch = self.sketch(plane=3)
        sketch.AttachmentOffset = FreeCAD.Placement(V(0, 0, 0), FreeCAD.Rotation(V(1, 0, 0), tilt))
        self.doc.recompute()
        return sketch

    def circle(self, sketch, radius, center=(0.0, 0.0)):
        sketch.addGeometry(Part.Circle(V(center[0], center[1], 0), V(0, 0, 1), radius))
        self.doc.recompute()
        return sketch

    def added(self, feature):
        return feature.Shape.Volume - self.volume

    def test_a_flat_face(self):
        self.box()
        raised = self.emboss(self.rectangle(self.up(), 10, 10, 20, 20), depth=1.0)
        self.assertEqual(len(raised.Shape.Solids), 1)
        self.assertAlmostEqual(self.added(raised), 100.0, places=6)
        self.assertAlmostEqual(raised.Shape.BoundBox.ZMax, 21.0, places=6)
        cut = self.emboss(self.rectangle(self.up(), 25, 25, 35, 35), depth=1.0, cut=True)
        self.assertAlmostEqual(raised.Shape.Volume - cut.Shape.Volume, 100.0, places=6)

    def test_a_tilted_sketch_is_stretched_onto_the_face(self):
        # seen from a plane tilted 30° to the face, the square covers 1 / cos 30° as much of it
        self.box()
        raised = self.emboss(self.rectangle(self.up(tilt=30), 10, 20, 20, 30), depth=1.0)
        self.assertAlmostEqual(self.added(raised), 100.0 / math.cos(math.radians(30)), places=6)

    def test_a_dome(self):
        # a circle 6 mm in radius seen from the dome's middle plane: the cap it covers, 1 mm out of the sphere
        # (or into it) along the sphere's radius
        self.dome()
        raised = self.emboss(self.circle(self.up(), 6.0), depth=1.0)
        self.assertEqual(len(raised.Shape.Solids), 1)
        self.assertAlmostEqual(self.added(raised), shell(21, 20), places=4)
        cut = self.emboss(self.circle(self.up(), 6.0), depth=1.0, cut=True)
        self.assertAlmostEqual(raised.Shape.Volume - cut.Shape.Volume, shell(20, 19), places=4)

    def test_on_the_side_the_sketch_looks_at(self):
        # from the dome's middle, looking up: on the top half only
        self.dome()
        raised = self.emboss(self.circle(self.up(), 6.0), depth=1.0)
        added = raised.Shape.cut(self.pad.Shape)
        self.assertGreater(added.BoundBox.ZMin, 0.0)

    def test_text_on_a_dome(self):
        from StudioTests.test_sketch_text import NOTO
        from studio.services import fonts, sketch_text
        from studio.services.sketch_text import TextBox

        self.dome()
        profile = self.up()
        sketch_text.add(profile, TextBox("Lesleigh", "Noto Sans", "Regular", 6.0, 1.0, 1.0, fit=True),
                        fonts.read(NOTO), corner=(-12.0, -3.0))
        self.doc.recompute()
        feature = self.emboss(profile, depth=0.8)
        self.assertEqual(len(feature.Shape.Solids), 1)
        self.assertGreater(self.added(feature), 0.0)

    def test_a_rounded_edge(self):
        # a cylinder's top edge rounded 5 mm (a torus): a dot under the rounding, looking up, raised out of it
        base = self.sketch(plane=3)
        base.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 20))
        pad = self.body.newObject("PartDesign::Pad", "Pad")
        pad.Profile, pad.Length = base, 40
        self.doc.recompute()
        top = next(f"Edge{n}" for n, e in enumerate(pad.Shape.Edges, 1)
                   if e.Curve.__class__.__name__ == "Circle" and abs(e.BoundBox.ZMin - 40) < 1e-9)
        self.pad = self.body.newObject("PartDesign::Fillet", "Fillet")
        self.pad.Base, self.pad.Radius = (pad, [top]), 5
        self.doc.recompute()
        base.Visibility = False
        self.volume = self.pad.Shape.Volume
        self.face = next(f"Face{n}" for n, f in enumerate(self.pad.Shape.Faces, 1)
                         if f.Surface.__class__.__name__ == "Toroid")
        raised = self.emboss(self.circle(self.up(), 1.5, center=(17.5, 0.0)), depth=0.5)
        self.assertEqual(len(raised.Shape.Solids), 1)
        added = raised.Shape.cut(self.pad.Shape)
        self.assertGreater(added.Volume, 0.5 * math.pi * 1.5 ** 2 * 0.5)  # more than the dot's own size
        # on the rounding, under the dot (17.5 ± 1.5 mm out, so from 38 mm up): OCC's quick bounding box of a
        # torus patch spans the whole rounding
        self.assertGreater(added.optimalBoundingBox().ZMin, 37.5)

    def test_off_the_face_is_an_error(self):
        self.box()
        for cut in (False, True):
            with self.subTest(cut=cut):
                feature = emboss.make(self.body, self.rectangle(self.up(), 50, 10, 60, 20), self.pad, self.face,
                                      1.0, cut)
                self.doc.recompute()
                self.assertFalse(feature.isValid())
                self.assertIn("off the face", feature.getStatusString())
                self.body.removeObject(feature)
                self.doc.removeObject(feature.Name)

    def test_not_a_face_is_refused(self):
        self.box()
        with self.assertRaisesRegex(ValueError, "isn't a face"):
            emboss.make(self.body, self.rectangle(self.up(), 10, 10, 20, 20), self.pad, "Edge1")
