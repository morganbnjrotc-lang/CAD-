# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sizes typed while drawing (PLAN 3.2), the way Fusion does it: start a shape, type its size in the box
next to the cursor, Tab to the next box, Return; the typed sizes become dimensions.

FreeCAD's sketch tools already do this ("on-view parameters"); these tests check them in Studio (its own
environment, its single-key shortcuts, the user's units) with synthetic mouse and key input. The input
goes through StudioGui's C++ helpers: Python wrappers of FreeCAD's 3D view widgets make FreeCAD abort at
exit (docs/BASELINE.md).
"""

import unittest
import uuid

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

import StudioGui
from studio.services import units as unit_service
from studio.services.settings import Settings
from studio.shell import units

INCH = 25.4


def settle(ms=60):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec_()
    QtWidgets.QApplication.processEvents()


class TypedSizes(unittest.TestCase):
    def setUp(self):
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(units.current().set_choice, original)
        units.current().set_choice("inches")
        self.doc = FreeCAD.newDocument("Sizes" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()
        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        settle(200)
        view = FreeCADGui.ActiveDocument.ActiveView
        view.setCameraType("Orthographic")
        view.getCameraNode().height.setValue(8 * INCH)  # the view shows about 8 in from top to bottom
        settle(100)

    def close(self):
        if FreeCAD.ActiveDocument is not None:
            gui = FreeCADGui.getDocument(self.doc.Name)
            if gui.getInEdit() is not None:
                StudioGui.type_keys("{Escape}") if StudioGui.focus_widget() else None
                gui.resetEdit()
        settle(100)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    # -- input, in the sketch's own coordinates (inches) ---------------------------------------
    def at(self, x, y):
        point = self.sketch.getGlobalPlacement().multVec(FreeCAD.Vector(x * INCH, y * INCH, 0))
        return StudioGui.view_point(point.x, point.y, point.z)

    def move(self, x, y):
        StudioGui.view_mouse("move", *self.at(x, y))
        settle()

    def click(self, x, y):
        StudioGui.view_mouse("click", *self.at(x, y))
        settle(120)

    def type(self, keys):
        StudioGui.type_keys(keys)
        settle(120)

    def tool(self, command):
        FreeCADGui.runCommand(command, 0)
        settle(150)

    def finish(self):
        """Leaves the tool (FreeCAD's tools keep drawing until Escape)."""
        if StudioGui.focus_widget() is not None:
            self.type("{Escape}")
        FreeCADGui.ActiveDocument.ActiveView.getViewer()  # nothing: keeps the view alive
        settle(100)

    def dimensions(self):
        return sorted((c.Type, round(c.Value, 4)) for c in self.sketch.Constraints
                      if c.Type in ("Distance", "DistanceX", "DistanceY", "Diameter", "Radius"))

    def kinds(self):
        return sorted(c.Type for c in self.sketch.Constraints)

    # -- the tests -----------------------------------------------------------------------------
    def test_the_size_box_takes_typing_once_a_line_is_started(self):
        self.tool("Sketcher_CreateLine")
        self.click(1, 1)
        self.move(2.5, 1.2)
        focus = StudioGui.focus_widget()
        self.assertIsNotNone(focus)
        self.assertTrue(focus[1], f"keys would go to {focus[0]}, not a size box in the 3D view")

    def test_a_typed_line_length_and_angle_become_dimensions_in_inches(self):
        self.tool("Sketcher_CreateLine")
        self.click(1, 1)
        self.move(2.5, 1.2)
        self.type("2{Tab}0{Return}")
        self.finish()
        self.assertEqual(len(self.sketch.Geometry), 1)
        self.assertAlmostEqual(self.sketch.Geometry[0].length(), 2 * INCH, places=4)
        self.assertIn(("Distance", round(2 * INCH, 4)), self.dimensions())
        self.assertIn("Horizontal", self.kinds())

    def test_a_size_typed_with_a_unit_is_converted(self):
        self.tool("Sketcher_CreateLine")
        self.click(1, 1)
        self.move(2.5, 1.2)
        self.type("50 mm{Tab}0{Return}")
        self.finish()
        self.assertAlmostEqual(self.sketch.Geometry[0].length(), 50, places=4)

    def test_shortcut_letters_type_into_the_box(self):
        # F is Studio's "focus the selection" (and E extrude, S search): in a size box they're text.
        self.tool("Sketcher_CreateLine")
        self.click(1, 1)
        self.move(2.5, 1.2)
        self.type("0.5 ft{Tab}0{Return}")
        self.finish()
        self.assertAlmostEqual(self.sketch.Geometry[0].length(), 6 * INCH, places=4)

    def test_a_typed_circle_size_is_its_diameter(self):
        # Fusion asks for a circle's diameter; so does FreeCAD by default (Sketcher/dimensioning).
        self.tool("Sketcher_CreateCircle")
        self.click(0.5, 0.5)
        self.move(1.5, 0.5)
        self.type("3{Return}")
        self.finish()
        self.assertEqual(len(self.sketch.Geometry), 1)
        self.assertAlmostEqual(self.sketch.Geometry[0].Radius, 1.5 * INCH, places=4)
        self.assertIn(("Diameter", round(3 * INCH, 4)), self.dimensions())

    def test_a_typed_arc_radius_and_sweep(self):
        self.tool("Sketcher_CreateArc")
        self.click(1, 1)  # center
        self.move(2, 1)
        self.type("1{Tab}0{Return}")  # radius, start angle
        self.move(1, 2)
        self.type("90{Return}")  # sweep
        self.finish()
        arcs = [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomArcOfCircle"]
        self.assertEqual(len(arcs), 1)
        self.assertAlmostEqual(arcs[0].Radius, INCH, places=4)
        self.assertAlmostEqual(abs(arcs[0].LastParameter - arcs[0].FirstParameter), 3.141592653589793 / 2, places=4)
        self.assertIn(("Radius", round(INCH, 4)), self.dimensions())

    def test_a_typed_rectangle_width_and_height_become_dimensions(self):
        self.tool("Sketcher_CreateRectangle")
        self.click(0.5, 0.5)
        self.move(2, 1.5)
        self.type("3{Tab}1.5{Return}")
        self.finish()
        lines = [g for g in self.sketch.Geometry if g.TypeId == "Part::GeomLineSegment"]
        self.assertEqual(len(lines), 4)
        lengths = sorted(round(g.length() / INCH, 4) for g in lines)
        self.assertEqual(lengths, [1.5, 1.5, 3.0, 3.0])
        sizes = sorted(round(v / INCH, 4) for t, v in self.dimensions())
        self.assertEqual(sizes, [1.5, 3.0])
