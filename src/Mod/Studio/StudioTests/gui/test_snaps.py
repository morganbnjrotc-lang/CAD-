# SPDX-License-Identifier: LGPL-2.1-or-later
"""Snapping onto geometry already in the sketch (PLAN 3.15; the user, 2026-11-19: "some snaps would be much
appreciated to help placing geometry on pre-existing geometry"). Added to FreeCAD's sketcher: where two curves
cross, a circle's quadrants, a circle's center offered from hovering its edge, an easier middle of a line.
A point snaps within about 12 pixels and keeps to what it snapped onto (constraints).
"""

import FreeCAD
import Part

from StudioTests.gui.sketch_input import INCH, SketchInput, settle


class Snaps(SketchInput):
    def start_of(self, geo_id):
        point = self.sketch.getPoint(geo_id, 1)
        return point.x / INCH, point.y / INCH

    def assertAt(self, got, wanted):
        for g, w in zip(got, wanted):
            self.assertAlmostEqual(g, w, places=6, msg=f"{got} != {wanted}: didn't snap")

    def held(self, geo_id, pos=1):
        """(type, other geometry, its position) of the constraints holding a point of `geo_id`."""
        held = []
        for c in self.sketch.Constraints:
            if c.First == geo_id and c.FirstPos == pos:
                held.append((c.Type, c.Second, c.SecondPos))
            elif c.Second == geo_id and c.SecondPos == pos:
                held.append((c.Type, c.First, c.FirstPos))
            elif c.Third == geo_id and c.ThirdPos == pos:  # Symmetric: the middle of First and Second
                held.append((c.Type, c.First, 0))
        return sorted(held)

    def circle(self):
        """A circle at (1, 1), 1 in across its radius, made directly: the pointer hasn't been on it (the
        circle tool leaves the pointer on the edge it drew)."""
        self.sketch.addGeometry(Part.Circle(FreeCAD.Vector(INCH, INCH, 0), FreeCAD.Vector(0, 0, 1), INCH))
        self.doc.recompute()
        settle(100)
        return 1, 1, 1

    def test_where_two_lines_cross(self):
        self.line((0, 0), (3, 3))  # they cross at about (1, 1), away from either's middle
        self.line((0, 2), (2.5, -0.5))
        self.tool("Sketcher_CreateLine")
        self.click(1.05, 1.05)  # on the first line, near where they cross
        self.click(3, 1.5)
        self.finish()
        (a, b), (c, d) = [((g.StartPoint.x / INCH, g.StartPoint.y / INCH), (g.EndPoint.x / INCH, g.EndPoint.y / INCH))
                          for g in self.sketch.Geometry[:2]]
        # where the two lines, as drawn, cross
        u, v = (b[0] - a[0], b[1] - a[1]), (d[0] - c[0], d[1] - c[1])
        t = ((c[0] - a[0]) * v[1] - (c[1] - a[1]) * v[0]) / (u[0] * v[1] - u[1] * v[0])
        self.assertAt(self.start_of(2), (a[0] + t * u[0], a[1] + t * u[1]))
        self.assertEqual(self.held(2), [("PointOnObject", 0, 0), ("PointOnObject", 1, 0)])

    def test_a_circles_quadrant(self):
        x, y, r = self.circle()
        self.tool("Sketcher_CreateLine")
        self.click(0.9128, 1.9962)  # on the circle, a few pixels left of its top
        self.click(3, 2.5)
        self.finish()
        self.assertAt(self.start_of(1), (x, y + r))

    # Near the center, beyond FreeCAD's own pick of its dot (about 8 pixels; this is 14 or more at the
    # tests' zoom) and within the center snap (about 24 pixels).
    NEAR_CENTER = (1.13, 1.12)

    def test_the_center_after_hovering_the_edge(self):
        # The center dot is small; hovering the edge offers it from farther.
        x, y, _ = self.circle()
        self.tool("Sketcher_CreateLine")
        self.move(2, 1)  # on the edge
        self.click(*self.NEAR_CENTER)
        self.click(3, 2.5)
        self.finish()
        self.assertAt(self.start_of(1), (x, y))
        self.assertEqual(self.held(1), [("Coincident", 0, 3)])

    def test_the_center_stays_put_without_hovering_the_edge(self):
        x, y, _ = self.circle()
        self.tool("Sketcher_CreateLine")
        self.click(*self.NEAR_CENTER)
        self.click(3, 2.5)
        self.finish()
        start = self.start_of(1)
        self.assertGreater(abs(start[0] - x) + abs(start[1] - y), 0.05, start)

    def test_the_middle_of_a_short_line_is_easier_to_catch(self):
        # FreeCAD caught the middle within 5 % of the length: 0.05 in on this 1 in line.
        self.line((0, 0), (1, 0))
        self.tool("Sketcher_CreateLine")
        self.click(0.58, 0)
        self.click(0.5, 2)
        self.finish()
        line = self.sketch.Geometry[0]
        middle = ((line.StartPoint.x + line.EndPoint.x) / 2 / INCH, (line.StartPoint.y + line.EndPoint.y) / 2 / INCH)
        self.assertAt(self.start_of(1), middle)
        self.assertIn("Symmetric", [t for t, _, _ in self.held(1)])
