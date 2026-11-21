# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click section view (PLAN 3.7): where the section plane starts (studio.services.section).

A plane cuts the view of the model; the side it keeps is the side its normal points to. On a flat face
picked first, the plane lies on the face and keeps the part behind it (dragging the arrow then moves it
into the part, as in Fusion). With nothing picked, it goes through the middle of the model and keeps the
half away from the viewer, so the inside shows straight away.
"""

import unittest

import FreeCAD
import Part

from studio.services import section

V = FreeCAD.Vector


def close(a, b, places=6):
    return all(abs(x - y) < 10 ** -places for x, y in zip(a, b))


class StartingPlane(unittest.TestCase):
    def setUp(self):
        self.box = Part.makeBox(10, 20, 30)  # 0..10, 0..20, 0..30

    def face(self, normal):
        return next(f for f in self.box.Faces if close(f.normalAt(0, 0), normal))

    def test_on_a_flat_face_keeping_the_part_behind_it(self):
        point, normal = section.on_face(self.face((0, 0, 1)))  # the top
        self.assertAlmostEqual(point.z, 30)
        self.assertTrue(close(normal, (0, 0, -1)), normal)
        point, normal = section.on_face(self.face((1, 0, 0)))
        self.assertAlmostEqual(point.x, 10)
        self.assertTrue(close(normal, (-1, 0, 0)), normal)

    def test_a_curved_face_gives_no_plane(self):
        cylinder = Part.makeCylinder(5, 10)
        side = next(f for f in cylinder.Faces if f.Surface.TypeId == "Part::GeomCylinder")
        self.assertIsNone(section.on_face(side))

    def test_through_the_middle_facing_away_from_the_viewer(self):
        point, normal = section.through_middle(self.box.BoundBox, V(0, 0, -2))  # looking down
        self.assertTrue(close(point, (5, 10, 15)), point)
        self.assertTrue(close(normal, (0, 0, -1)), normal)

    def test_through_the_middle_on_the_main_plane_nearest_the_view(self):
        # Exactly along the view the arrow would point at the viewer, a dot that can't be dragged: the
        # plane is the front, side or top one nearest the view, the arrow then slanting on screen.
        _, normal = section.through_middle(self.box.BoundBox, V(-0.2, 0.9, -0.3))
        self.assertTrue(close(normal, (0, 1, 0)), normal)
        _, normal = section.through_middle(self.box.BoundBox, V(0.8, 0.1, -0.5))
        self.assertTrue(close(normal, (1, 0, 0)), normal)

    def test_from_the_usual_corner_view_it_is_the_front_plane(self):
        _, normal = section.through_middle(self.box.BoundBox, V(-1, 1, -1))
        self.assertTrue(close(normal, (0, 1, 0)), normal)
        # FreeCAD's own isometric view, as the app reported it: not quite equal
        _, normal = section.through_middle(self.box.BoundBox, V(-0.5773504972, 0.5773501396, -0.5773503184))
        self.assertTrue(close(normal, (0, 1, 0)), normal)

    def test_the_arrow_points_out_of_what_is_kept(self):
        self.assertTrue(close(section.arrow(V(0, 0, -1)), (0, 0, 1)))

    def test_moving_along_the_arrow(self):
        point, normal = section.moved(V(0, 0, 30), V(0, 0, -1), -5.0)  # dragged 5 into the part
        self.assertTrue(close(point, (0, 0, 25)), point)
        self.assertTrue(close(normal, (0, 0, -1)), normal)
