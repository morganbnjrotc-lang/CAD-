# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click Fully Constrain (PLAN 3.4): adds what a sketch is missing so it is fully defined, without
moving anything, nothing redundant or conflicting; one undo step."""

import math
import unittest
import uuid

import FreeCAD
import Part
import Sketcher

from studio.services import auto_constrain

V = FreeCAD.Vector


def points(sketch):
    """Every vertex of the sketch, to check that nothing moved."""
    result = []
    for geo_id, geo in enumerate(sketch.Geometry):
        for pos in (1, 2, 3):
            try:
                result.append(sketch.getPoint(geo_id, pos))
            except Exception:  # this geometry has no such point
                pass
    return result


class Base(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("AutoConstrain" + uuid.uuid4().hex[:8])
        self.doc.UndoMode = 1
        self.addCleanup(FreeCAD.closeDocument, self.doc.Name)
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()

    def add(self, *geometry, construction=False):
        return [self.sketch.addGeometry(g, construction) for g in geometry]

    def polygon(self, *corners):
        ids = self.add(*(Part.LineSegment(V(*a, 0), V(*b, 0)) for a, b in zip(corners, corners[1:] + corners[:1])))
        return ids

    def constrain(self):
        before = points(self.sketch)
        result = auto_constrain.fully_constrain(self.sketch)
        self.assertEqual(self.sketch.solve(), 0, "the sketch doesn't solve cleanly")
        self.assertEqual(self.sketch.RedundantConstraints, [])
        self.assertEqual(self.sketch.ConflictingConstraints, [])
        self.assertEqual(self.sketch.PartiallyRedundantConstraints, [])
        after = points(self.sketch)
        for a, b in zip(before, after):
            self.assertLess((a - b).Length, 1e-6, "a point moved")
        return result

    def kinds(self):
        return sorted(c.Type for c in self.sketch.Constraints)

    def assertFullyConstrained(self):
        self.assertEqual(self.sketch.DoF, 0, self.kinds())


class Shapes(Base):
    def test_a_rectangle_at_the_origin(self):
        self.polygon((0, 0), (30, 0), (30, 20), (0, 20))
        result = self.constrain()
        self.assertFullyConstrained()
        self.assertEqual(result.dof_before, 16)
        self.assertEqual(self.kinds().count("Horizontal"), 2)
        self.assertEqual(self.kinds().count("Vertical"), 2)
        # its corner on the origin, then its two sizes: no position dimensions needed
        sizes = sorted(round(c.Value, 6) for c in self.sketch.Constraints if c.Type in ("Distance", "DistanceX", "DistanceY"))
        self.assertEqual(sizes, [20.0, 30.0])

    def test_a_rectangle_away_from_the_origin_gets_its_position(self):
        self.polygon((10, 5), (40, 5), (40, 25), (10, 25))
        self.constrain()
        self.assertFullyConstrained()
        values = sorted(round(c.Value, 6) for c in self.sketch.Constraints if c.Type in ("Distance", "DistanceX", "DistanceY"))
        self.assertEqual(values, [5.0, 10.0, 20.0, 30.0])  # two sizes, two positions

    def test_a_circle_gets_its_diameter(self):
        self.add(Part.Circle(V(0, 0, 0), V(0, 0, 1), 76.2))  # the spindle stand's base: 6 in across
        self.constrain()
        self.assertFullyConstrained()
        diameters = [c for c in self.sketch.Constraints if c.Type == "Diameter"]
        self.assertEqual(len(diameters), 1)
        self.assertAlmostEqual(diameters[0].Value, 152.4)
        self.assertIn("Coincident", self.kinds())  # its center on the origin

    def test_a_circle_away_from_the_origin(self):
        self.add(Part.Circle(V(20, 10, 0), V(0, 0, 1), 5))
        self.constrain()
        self.assertFullyConstrained()

    def test_an_arc(self):
        self.add(Part.ArcOfCircle(Part.Circle(V(5, 5, 0), V(0, 0, 1), 10), 0.2, 2.0))
        self.constrain()
        self.assertFullyConstrained()
        self.assertIn("Radius", self.kinds())

    def test_a_slanted_triangle(self):
        self.polygon((0, 0), (40, 10), (15, 30))
        self.constrain()
        self.assertFullyConstrained()

    def test_a_turned_rectangle_keeps_its_square_corners(self):
        a = math.radians(30)
        def p(x, y):
            return (5 + x * math.cos(a) - y * math.sin(a), 5 + x * math.sin(a) + y * math.cos(a))
        self.polygon(p(0, 0), p(30, 0), p(30, 20), p(0, 20))
        self.constrain()
        self.assertFullyConstrained()
        self.assertGreaterEqual(self.kinds().count("Perpendicular"), 3)

    def test_a_slot_keeps_its_tangent_ends(self):
        # two lines and two half circles, joined end to end and tangent
        self.add(Part.LineSegment(V(0, 0, 0), V(40, 0, 0)),
                 Part.ArcOfCircle(Part.Circle(V(40, 5, 0), V(0, 0, 1), 5), -math.pi / 2, math.pi / 2),
                 Part.LineSegment(V(40, 10, 0), V(0, 10, 0)),
                 Part.ArcOfCircle(Part.Circle(V(0, 5, 0), V(0, 0, 1), 5), math.pi / 2, 3 * math.pi / 2))
        self.constrain()
        self.assertFullyConstrained()
        self.assertGreaterEqual(self.kinds().count("Tangent"), 2)

    def test_a_point_on_a_line(self):
        self.add(Part.LineSegment(V(0, 0, 0), V(30, 15, 0)), Part.LineSegment(V(10, 5, 0), V(20, 30, 0)))
        self.constrain()
        self.assertFullyConstrained()
        self.assertIn("PointOnObject", self.kinds())

    def test_two_separate_shapes(self):
        self.polygon((0, 0), (30, 0), (30, 20), (0, 20))
        self.add(Part.Circle(V(60, 10, 0), V(0, 0, 1), 5))
        self.constrain()
        self.assertFullyConstrained()

    def test_construction_lines_are_constrained_too(self):
        self.add(Part.LineSegment(V(0, 0, 0), V(0, 40, 0)), construction=True)
        self.polygon((-10, 5), (10, 5), (10, 25), (-10, 25))
        self.constrain()
        self.assertFullyConstrained()


class Limits(Base):
    def test_a_sketch_point(self):
        self.add(Part.Point(V(5, 7, 0)))
        self.constrain()
        self.assertFullyConstrained()

    def test_what_it_cant_size_is_left_free_and_reported(self):
        # Ellipses get their center placed but no sizes: the rest is reported, nothing breaks.
        self.add(Part.Ellipse(V(10, 0, 0), V(0, 5, 0), V(0, 0, 0)))
        result = self.constrain()
        self.assertEqual(result.dof_after, self.sketch.DoF)
        self.assertGreater(result.dof_after, 0)

    def test_a_busy_sketch_takes_seconds_at_most(self):
        import time

        for n in range(10):
            x = 40 * n
            self.polygon((x, 0), (x + 30, 0), (x + 30, 20), (x, 20))
        start = time.perf_counter()
        self.constrain()
        elapsed = time.perf_counter() - start
        self.assertFullyConstrained()
        self.assertLess(elapsed, 6.0, f"{elapsed:.2f} s for 40 lines")  # ~1.5 s here; CI is slower


class Keeping(Base):
    def test_the_users_constraints_stay(self):
        self.polygon((0, 0), (30, 0), (30, 20), (0, 20))
        self.sketch.addConstraint(Sketcher.Constraint("Distance", 1, 20.0))
        mine = [(c.Type, c.First, c.Value) for c in self.sketch.Constraints]
        self.constrain()
        self.assertFullyConstrained()
        self.assertEqual([(c.Type, c.First, c.Value) for c in self.sketch.Constraints][: len(mine)], mine)

    def test_a_fully_constrained_sketch_gets_nothing(self):
        self.polygon((0, 0), (30, 0), (30, 20), (0, 20))
        self.constrain()
        count = len(self.sketch.Constraints)
        result = self.constrain()
        self.assertEqual(result.added, [])
        self.assertEqual(len(self.sketch.Constraints), count)

    def test_an_empty_sketch_gets_nothing(self):
        result = self.constrain()
        self.assertEqual(result.added, [])

    def test_one_undo_removes_everything_it_added(self):
        self.polygon((0, 0), (30, 0), (30, 20), (0, 20))
        self.doc.commitTransaction()
        self.constrain()
        self.assertGreater(len(self.sketch.Constraints), 0)
        self.doc.undo()
        self.assertEqual(len(self.sketch.Constraints), 0)

    def test_a_sketch_with_conflicts_is_left_alone(self):
        self.polygon((0, 0), (30, 0), (30, 20), (0, 20))
        self.sketch.addConstraint(Sketcher.Constraint("Distance", 0, 30.0))
        self.sketch.addConstraint(Sketcher.Constraint("Distance", 0, 31.0))  # conflicts
        with self.assertRaises(auto_constrain.SketchHasProblems):
            auto_constrain.fully_constrain(self.sketch)
        self.assertEqual(len(self.sketch.Constraints), 2)


class Report(Base):
    def test_the_summary_says_what_happened(self):
        R = auto_constrain.Result
        self.assertEqual(auto_constrain.summary(R(added=[("Distance", (0, None))] * 11, dof_before=16, dof_after=0)),
                         "Fully constrained: added 11 constraints")
        self.assertEqual(auto_constrain.summary(R(added=[("Diameter", (0, None))], dof_before=1, dof_after=0)),
                         "Fully constrained: added 1 constraint")
        self.assertEqual(auto_constrain.summary(R(added=[], dof_before=0, dof_after=0)),
                         "Already fully constrained")
        self.assertEqual(auto_constrain.summary(R(added=[("Coincident", (0, 1))] * 2, dof_before=5, dof_after=3)),
                         "Added 2 constraints; 3 degrees of freedom are left (ellipses and splines aren't "
                         "sized automatically)")

    def test_what_was_added_is_reported(self):
        self.add(Part.Circle(V(0, 0, 0), V(0, 0, 1), 10))
        result = self.constrain()
        self.assertEqual(result.dof_after, 0)
        self.assertEqual(len(result.added), len(self.sketch.Constraints))
