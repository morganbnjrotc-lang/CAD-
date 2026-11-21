# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click section view in the app (PLAN 3.7; studio.shell.section, StudioGui's section helpers).

The toolbar's Section cuts the 3D view of the model with a plane; an arrow on the plane drags it. It is a
switch: lit while on, a second click turns it off. The plane is read back through StudioGui (C++), as the
3D view's nodes are FreeCAD's.
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui

import StudioGui
from StudioTests.gui.sketch_input import settle
from studio.shell import window


def close(a, b, tolerance=1e-4):
    return all(abs(x - y) < tolerance for x, y in zip(a, b))


class Section(unittest.TestCase):
    """A 10 x 20 x 30 mm box, seen from the usual corner."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("Section" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.box = self.doc.addObject("Part::Box", "Box")
        self.box.Length, self.box.Width, self.box.Height = 10, 20, 30
        self.doc.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewIsometric()
        view.fitAll()
        FreeCADGui.Selection.clearSelection()
        settle(300)

    def close(self):
        if StudioGui.section_plane() is not None:
            StudioGui.section_off()
        FreeCAD.closeDocument(self.doc.Name)
        settle(100)

    def button(self):
        window.current().refresh()
        actions = {a.text(): a for a in window.current().tools.actions()}
        self.assertIn("Section", actions, f"toolbar shows {list(actions)}")
        return actions["Section"]

    def click_section(self):
        self.button().trigger()
        settle(400)

    def test_with_nothing_picked_it_cuts_through_the_middle_on_the_front_plane(self):
        self.click_section()
        plane = StudioGui.section_plane()
        self.assertIsNotNone(plane, "no section")
        point, normal = plane
        self.assertTrue(close(point, (5, 10, 15)), point)
        self.assertTrue(close(normal, (0, 1, 0)), normal)  # seen from the usual corner: the front half goes
        self.assertTrue(FreeCADGui.ActiveDocument.ActiveView.hasClippingPlane())

    def test_the_button_is_lit_while_on_and_a_second_click_turns_it_off(self):
        self.click_section()
        self.assertTrue(self.button().isChecked())
        self.click_section()
        self.assertIsNone(StudioGui.section_plane())
        self.assertFalse(FreeCADGui.ActiveDocument.ActiveView.hasClippingPlane())
        self.assertFalse(self.button().isChecked())

    def test_from_a_flat_face_it_keeps_the_part_behind_it(self):
        top = next(f"Face{i + 1}" for i, f in enumerate(self.box.Shape.Faces) if close(f.normalAt(0, 0), (0, 0, 1)))
        FreeCADGui.Selection.addSelection(self.box, top)
        settle(300)
        self.click_section()
        point, normal = StudioGui.section_plane()
        self.assertAlmostEqual(point[2], 30, places=4)
        self.assertTrue(close(normal, (0, 0, -1)), normal)

    def test_dragging_the_arrow_moves_the_plane(self):
        top = next(f"Face{i + 1}" for i, f in enumerate(self.box.Shape.Faces) if close(f.normalAt(0, 0), (0, 0, 1)))
        FreeCADGui.Selection.addSelection(self.box, top)
        settle(300)
        self.click_section()
        StudioGui.section_drag(-12.5)  # the arrow points up, out of the part: down into it
        settle(200)
        point, normal = StudioGui.section_plane()
        self.assertAlmostEqual(point[2], 17.5, places=4)
        self.assertTrue(close(normal, (0, 0, -1)), normal)

    def test_closing_the_document_ends_the_section(self):
        self.click_section()
        FreeCAD.closeDocument(self.doc.Name)
        settle(200)
        self.assertIsNone(StudioGui.section_plane())
        self.doc = FreeCAD.newDocument("Section" + uuid.uuid4().hex[:8])  # for the cleanup
