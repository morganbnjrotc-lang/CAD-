# SPDX-License-Identifier: LGPL-2.1-or-later
"""More ways to draw each shape (PLAN 3.12): picked from the drop-down under a sketch tool on Studio's
toolbar, as in Fusion and Inventor, and drawn with synthetic clicks (StudioTests.gui.sketch_input)."""

import math

import StudioGui
from StudioTests.gui.sketch_input import INCH, SketchInput, settle
from studio.shell import window


def tools():
    return window.current()


class DrawingWays(SketchInput):
    def setUp(self):
        super().setUp()
        settle(200)  # the toolbar follows the sketch being edited
        for tool in ("Sketcher_CreateLine", "Sketcher_CreateRectangle", "Sketcher_CreateCircle",
                     "Sketcher_CreateArc", "Sketcher_CreateRegularPolygon", "Sketcher_CreateSlot"):
            self.addCleanup(tools().choose_way, tool, 0)

    def button(self, label):
        button = tools().tool_widget(label)
        self.assertIsNotNone(button, f"no {label} button on the toolbar")
        return button

    def pick(self, label, way):
        menu = self.button(label).menu()
        self.assertIsNotNone(menu, f"{label} has no list of ways")
        action = next((a for a in menu.actions() if a.text() == way), None)
        self.assertIsNotNone(action, f"{label} has no {way}: {[a.text() for a in menu.actions()]}")
        action.trigger()
        settle(400)

    def lines(self):
        return [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomLineSegment"]

    def lengths(self):
        return sorted(g.length() / INCH for g in self.lines())

    def near(self):
        """How far off clicked sizes can be, in inches: a click lands on a pixel (the view shows 8 in)."""
        return 2 * 8 / StudioGui.view_size()[1]

    def assertLengths(self, expected):
        lengths = self.lengths()
        self.assertEqual(len(lengths), len(expected), lengths)
        for got, wanted in zip(lengths, sorted(expected)):
            self.assertAlmostEqual(got, wanted, delta=self.near(), msg=f"{lengths} != {sorted(expected)}")

    def test_the_rectangle_lists_its_ways(self):
        self.assertEqual([a.text() for a in self.button("Rectangle").menu().actions()],
                         ["2-Point Rectangle", "Center Rectangle", "3-Point Rectangle", "3-Point Center Rectangle",
                          "Rounded Rectangle"])

    def test_a_center_rectangle(self):
        self.pick("Rectangle", "Center Rectangle")
        self.click(1, 1)  # center
        self.click(2.5, 2)  # corner
        self.finish()
        self.assertLengths([2, 2, 3, 3])
        xs = [p.x / INCH for g in self.lines() for p in (g.StartPoint, g.EndPoint)]
        self.assertAlmostEqual((min(xs) + max(xs)) / 2, 1, delta=self.near())

    def test_a_3_point_rectangle_is_turned_along_its_first_side(self):
        self.pick("Rectangle", "3-Point Rectangle")
        self.click(0, 0)
        self.click(2, 1)  # the first side
        self.click(1.5, 2)  # how wide
        self.finish()
        side, width = math.hypot(2, 1), (2 * 2 - 1 * 1.5) / math.hypot(2, 1)
        self.assertLengths([side, side, width, width])

    def test_a_3_point_circle(self):
        self.pick("Circle", "3-Point Circle")
        self.click(0, 1)
        self.click(2, 1)
        self.click(1, 2)
        self.finish()
        circles = [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomCircle"]
        self.assertEqual(len(circles), 1)
        self.assertAlmostEqual(circles[0].Radius / INCH, 1, delta=self.near())

    def point(self, geo_id, pos):
        point = self.sketch.getPoint(geo_id, pos)
        return point.x / INCH, point.y / INCH

    def assertNear(self, got, wanted):
        for g, w in zip(got, wanted):
            self.assertAlmostEqual(g, w, delta=self.near(), msg=f"{got} != {wanted}")

    def test_a_center_point_line(self):
        # The user asked for it, 2026-11-19 (SolidWorks' Midpoint Line): the first click is the middle.
        self.pick("Line", "Center Point Line")
        self.click(1, 1)  # middle
        self.click(2.5, 2)  # one end; the other mirrors it
        self.finish()
        self.assertEqual(len(self.lines()), 1)
        self.assertNear(self.point(0, 1), (-0.5, 0))
        self.assertNear(self.point(0, 2), (2.5, 2))
        # The middle stays the middle: a construction point there, the ends symmetric about it.
        points = [i for i, g in enumerate(self.sketch.Geometry) if g.TypeId == "Part::GeomPoint"]
        self.assertEqual(len(points), 1)
        self.assertTrue(self.sketch.getConstruction(points[0]))
        self.assertNear(self.point(points[0], 1), (1, 1))
        symmetric = self.constraints("Symmetric")
        self.assertEqual([(c.First, c.FirstPos, c.Second, c.SecondPos, c.Third) for c in symmetric],
                         [(0, 1, 0, 2, points[0])])

    def test_a_center_point_line_takes_a_typed_length(self):
        self.pick("Line", "Center Point Line")
        self.click(1, 1)
        self.move(2.5, 1.2)
        self.type("3{Tab}0{Return}")  # the whole length in inches, the angle
        self.finish()
        self.assertEqual(len(self.lines()), 1)
        self.assertAlmostEqual(self.lines()[0].length() / INCH, 3, places=6)
        self.assertIn(("Distance", round(3 * INCH, 4)), self.dimensions())
        self.assertIn("Horizontal", self.kinds())
        self.assertNear(self.point(0, 1), (-0.5, 1))  # still centered on the first click
        self.assertNear(self.point(0, 2), (2.5, 1))

    def circles(self):
        return [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomCircle"]

    def test_a_2_point_circle(self):
        self.pick("Circle", "2-Point Circle")
        self.click(0, 1)
        self.click(2, 1)  # straight across: the two points are a diameter apart
        self.finish()
        self.assertEqual(len(self.circles()), 1)
        circle = self.circles()[0]
        self.assertAlmostEqual(circle.Radius / INCH, 1, delta=self.near())
        self.assertNear((circle.Center.x / INCH, circle.Center.y / INCH), (1, 1))

    def test_a_2_point_circle_takes_a_typed_diameter(self):
        self.pick("Circle", "2-Point Circle")
        self.click(0, 1)
        self.move(2, 1)
        self.type("3{Return}")
        self.finish()
        self.assertEqual(len(self.circles()), 1)
        circle = self.circles()[0]
        self.assertAlmostEqual(circle.Radius / INCH, 1.5, places=6)
        self.assertIn(("Diameter", round(3 * INCH, 4)), self.dimensions())
        self.assertNear((circle.Center.x / INCH, circle.Center.y / INCH), (1.5, 1))  # from the first point

    def radii(self):
        return sorted(c.Radius / INCH for c in self.circles())

    def ends_at(self, x):
        """The lines with both ends at x (inches)."""
        return [g for g in self.lines() if abs(g.StartPoint.x / INCH - x) < self.near()
                and abs(g.EndPoint.x / INCH - x) < self.near()]

    def test_a_circumscribed_hexagon(self):
        # Fusion's Circumscribed Polygon: the second click is the middle of a side, so a size typed is
        # the distance across the flats' half (a nut's key size).
        self.pick("Polygon", "Circumscribed Polygon")
        self.click(1, 1)  # center
        self.click(2, 1)  # the middle of a side
        self.finish()
        side = 2 * math.tan(math.pi / 6)
        self.assertLengths([side] * 6)
        self.assertEqual(len(self.ends_at(2)), 1, "the side through the click isn't upright")
        radii = self.radii()  # both construction: through the corners, and touching the sides
        self.assertEqual(len(radii), 2, radii)
        self.assertAlmostEqual(radii[0], 1, delta=self.near())
        self.assertAlmostEqual(radii[1], 1 / math.cos(math.pi / 6), delta=self.near())
        self.assertEqual(len(self.constraints("Tangent")), 1)

    def test_a_circumscribed_hexagon_takes_a_typed_size(self):
        self.pick("Polygon", "Circumscribed Polygon")
        self.click(1, 1)
        self.move(2, 1.2)
        self.type("1.5{Tab}0{Return}")  # center to the middle of a side, its direction
        self.finish()
        self.assertLengths([2 * 1.5 * math.tan(math.pi / 6)] * 6)
        self.assertIn(("Radius", round(1.5 * INCH, 4)), self.dimensions())
        self.assertEqual(len(self.ends_at(2.5)), 1, "the side isn't upright at the typed size")

    def test_an_edge_polygon(self):
        # AutoCAD's Edge: two corners of one side; the polygon goes on the left going from the first.
        self.pick("Polygon", "Edge Polygon")
        self.click(0, 0)
        self.click(1, 0)
        self.finish()
        self.assertLengths([1] * 6)
        ys = [p.y / INCH for g in self.lines() for p in (g.StartPoint, g.EndPoint)]
        self.assertAlmostEqual(min(ys), 0, delta=self.near())
        self.assertAlmostEqual(max(ys), math.sqrt(3), delta=self.near())

    def test_an_edge_polygon_takes_a_typed_side(self):
        self.pick("Polygon", "Edge Polygon")
        self.click(0, 0)
        self.move(1, 0.2)
        self.type("2{Tab}0{Return}")  # the side's length and direction
        self.finish()
        self.assertLengths([2] * 6)
        self.assertIn(("Distance", round(2 * INCH, 4)), self.dimensions())

    def arcs(self):
        return sorted((g for g in self.sketch.Geometry if g.TypeId == "Part::GeomArcOfCircle"),
                      key=lambda arc: arc.Center.x)

    def assertSlot(self, centers, radius):
        arcs = self.arcs()
        self.assertEqual(len(arcs), 2)
        for arc, center in zip(arcs, centers):
            self.assertNear((arc.Center.x / INCH, arc.Center.y / INCH), center)
            self.assertAlmostEqual(arc.Radius / INCH, radius, delta=self.near())

    def test_an_overall_slot(self):
        # Fusion's Overall Slot: the clicks are the slot's ends, then its width.
        self.pick("Slot", "Overall Slot")
        self.click(0, 1)
        self.click(3, 1)
        self.click(1.5, 1.5)  # half the width
        self.finish()
        self.assertSlot([(0.5, 1), (2.5, 1)], 0.5)
        # a construction centerline from end to end carries the overall length
        centerline = [g for i, g in enumerate(self.sketch.Geometry)
                      if g.TypeId == "Part::GeomLineSegment" and self.sketch.getConstruction(i)]
        self.assertEqual(len(centerline), 1)
        self.assertAlmostEqual(centerline[0].length() / INCH, 3, delta=self.near())

    def test_an_overall_slot_takes_typed_sizes(self):
        self.pick("Slot", "Overall Slot")
        self.click(0, 1)
        self.move(3, 1.2)
        self.type("4{Tab}0{Return}")  # end to end, direction
        self.move(1.5, 1.5)
        self.type("0.5{Return}")  # radius
        self.finish()
        self.assertSlot([(0.5, 1), (3.5, 1)], 0.5)
        self.assertIn(("Distance", round(4 * INCH, 4)), self.dimensions())
        self.assertIn(("Radius", round(0.5 * INCH, 4)), self.dimensions())

    def test_a_center_point_slot(self):
        # Fusion's Center Point Slot: the middle, then one end's center; the other end mirrors it.
        self.pick("Slot", "Center Point Slot")
        self.click(1.5, 1)
        self.click(2.5, 1)
        self.click(2.5, 1.4)
        self.finish()
        self.assertSlot([(0.5, 1), (2.5, 1)], 0.4)
        self.assertEqual(len(self.constraints("Symmetric")), 1)

    def test_a_tangent_arc_goes_on_from_the_end_of_a_line(self):
        # Fusion's and Inventor's Tangent Arc: start at the end of a line or arc, carry on its direction.
        self.line((0, 0), (1, 0))
        self.pick("Arc", "Tangent Arc")
        self.click(1, 0)  # the line's end
        self.click(2, 1)
        self.finish()
        arcs = self.arcs()
        self.assertEqual(len(arcs), 1)
        self.assertNear((arcs[0].Center.x / INCH, arcs[0].Center.y / INCH), (1, 1))
        self.assertAlmostEqual(arcs[0].Radius / INCH, 1, delta=self.near())
        tangent = self.constraints("Tangent")
        self.assertEqual(len(tangent), 1, self.kinds())
        self.assertEqual({tangent[0].First, tangent[0].Second}, {0, 1})  # the line and the arc, end to end

    def test_a_tangent_arc_needs_the_end_of_a_line_or_arc(self):
        self.pick("Arc", "Tangent Arc")
        self.click(2, 2)  # nothing there
        self.click(3, 2.5)
        self.finish()
        self.assertEqual(self.arcs(), [])

    def corner(self):
        """Two lines meeting square at (-0.5, -0.5): along the bottom and up the left."""
        self.line((-0.5, -0.5), (3, -0.5))
        self.line((-0.5, -0.5), (-0.5, 2.5))

    def test_a_2_tangent_circle(self):
        # Fusion's 2-Tangent Circle: pick two lines, then where it sits (and its size).
        self.corner()
        self.pick("Circle", "2-Tangent Circle")
        self.click(1.5, -0.5)  # the bottom line
        self.click(-0.5, 1)  # the left one
        self.click(0.5, 0.5)  # in the corner, on the line halfway between them
        self.finish()
        self.assertEqual(len(self.circles()), 1)
        circle = self.circles()[0]
        self.assertNear((circle.Center.x / INCH, circle.Center.y / INCH), (0.5, 0.5))
        self.assertAlmostEqual(circle.Radius / INCH, 1, delta=self.near())
        self.assertEqual(len(self.constraints("Tangent")), 2)

    def test_a_2_tangent_circle_takes_a_typed_size(self):
        self.corner()
        self.pick("Circle", "2-Tangent Circle")
        self.click(1.5, -0.5)
        self.click(-0.5, 1)
        self.move(0.5, 0.5)
        self.type("1{Return}")  # its diameter
        self.finish()
        circle = self.circles()[0]
        self.assertAlmostEqual(circle.Radius / INCH, 0.5, places=6)
        self.assertNear((circle.Center.x / INCH, circle.Center.y / INCH), (0, 0))
        self.assertIn(("Diameter", round(1 * INCH, 4)), self.dimensions())

    def test_a_3_tangent_circle_inside_a_triangle(self):
        # Fusion's 3-Tangent Circle and Inventor's Tangent Circle: pick three lines.
        self.line((0, 0), (3, 0))
        self.line((3, 0), (1.5, 1.5 * math.sqrt(3)))
        self.line((1.5, 1.5 * math.sqrt(3)), (0, 0))
        self.pick("Circle", "3-Tangent Circle")
        self.click(1.5, 0)
        self.click(2.25, 0.75 * math.sqrt(3))
        self.click(0.75, 0.75 * math.sqrt(3))
        self.finish()
        self.assertEqual(len(self.circles()), 1)
        circle = self.circles()[0]
        inradius = 1.5 / math.sqrt(3)
        self.assertNear((circle.Center.x / INCH, circle.Center.y / INCH), (1.5, inradius))
        self.assertAlmostEqual(circle.Radius / INCH, inradius, delta=self.near())
        self.assertEqual(len(self.constraints("Tangent")), 3)

    def test_the_button_draws_the_way_picked_last(self):
        self.pick("Rectangle", "Center Rectangle")
        self.finish()
        settle(300)
        self.assertTrue(self.button("Rectangle").toolTip().startswith("Center Rectangle"))
        self.button("Rectangle").click()
        settle(400)
        self.click(1, 1)
        self.click(2.5, 2)
        self.finish()
        self.assertLengths([2, 2, 3, 3])
