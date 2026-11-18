# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawing in a sketch with synthetic input, for the sketching tests (PLAN 3.2–3.4).

A new document with a sketch being edited, in inches, the view showing about 8 in from top to bottom.
Positions are in the sketch's own coordinates, in inches. The input goes through StudioGui's C++ helpers:
Python wrappers of FreeCAD's 3D view widgets make FreeCAD abort at exit (docs/BASELINE.md).

Made to hold on GitHub's runner, whose 1024 x 768 screen and fast event loop broke clicks that work here:
the window gets at least 1280 x 800 for these tests (a fixed size may exceed the screen); drawing waits
until the camera has stopped turning to the sketch (FreeCAD animates it); and a click aimed where the
navigation cube or the Tasks panel floats over the view (they take the mouse) fails the test, saying so.
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


ROOM = (1280, 800)  # the main window, at least
CUBE = 180  # px: the navigation cube's corner, top right of the view
TASKS = 300  # px: the Tasks panel floating at the view's right
DRAWING_MIDDLE = (1.5, 1.0)  # in: the middle of where the tests draw


def settle(ms=60):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec_()
    QtWidgets.QApplication.processEvents()


def camera_still(view, timeout_ms=5000):
    """Waits until the camera has stopped moving (FreeCAD animates it to a sketch being edited)."""
    def state():
        camera = view.getCameraNode()
        values = [*camera.position.getValue().getValue(), *camera.orientation.getValue().getValue()]
        if hasattr(camera, "height"):
            values.append(camera.height.getValue())
        return [round(v, 6) for v in values]

    last, steady, waited = state(), 0, 0
    while steady < 3 and waited < timeout_ms:
        settle(100)
        waited += 100
        now = state()
        steady = steady + 1 if now == last else 0
        last = now
    return steady >= 3


class SketchInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main = FreeCADGui.getMainWindow()
        cls._room = None
        if main.width() < ROOM[0] or main.height() < ROOM[1]:
            cls._room = (main.minimumSize(), main.maximumSize())
            main.showNormal()
            main.setFixedSize(*ROOM)
            settle(200)

    @classmethod
    def tearDownClass(cls):
        if cls._room is not None:
            main = FreeCADGui.getMainWindow()
            main.setMinimumSize(cls._room[0])
            main.setMaximumSize(cls._room[1])

    def setUp(self):
        original = Settings().get(unit_service.UNITS)
        self.addCleanup(units.current().set_choice, original)
        units.current().set_choice("inches")
        self.doc = FreeCAD.newDocument("Sketching" + uuid.uuid4().hex[:8])
        self.addCleanup(self.close)
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()
        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        settle(200)
        view = FreeCADGui.ActiveDocument.ActiveView
        self.assertTrue(camera_still(view), "the camera kept moving after the sketch opened")
        view.setCameraType("Orthographic")
        camera = view.getCameraNode()
        camera.height.setValue(8 * INCH)
        # The tests draw within about x -1..4 in, y -1..3 in: center that on the part of the view the
        # Tasks panel leaves free (looking straight down at the sketch: x right, y up).
        width, height = StudioGui.view_size()
        free_middle = (20 + width - TASKS) / 2
        center_x = DRAWING_MIDDLE[0] + (width / 2 - free_middle) / (height / 8)
        z = camera.position.getValue().getValue()[2]
        camera.position.setValue(center_x * INCH, DRAWING_MIDDLE[1] * INCH, z)
        self.assertTrue(camera_still(view), "the camera kept moving after zooming")

    def close(self):
        gui = FreeCADGui.getDocument(self.doc.Name)
        if gui.getInEdit() is not None:
            if StudioGui.focus_widget() is not None:
                StudioGui.type_keys("{Escape}")
            gui.resetEdit()
        settle(100)
        FreeCAD.closeDocument(self.doc.Name)
        settle(50)

    # -- input -----------------------------------------------------------------------------------
    def at(self, x, y):
        point = self.sketch.getGlobalPlacement().multVec(FreeCAD.Vector(x * INCH, y * INCH, 0))
        px, py = StudioGui.view_point(point.x, point.y, point.z)
        width, height = StudioGui.view_size()
        where = f"({x}, {y}) in is at pixel ({px:.0f}, {py:.0f}) of a {width} x {height} view"
        self.assertTrue(20 <= px <= width - 20 and 20 <= py <= height - 20, f"{where}: outside it")
        self.assertFalse(px > width - CUBE and py < CUBE, f"{where}: under the navigation cube")
        self.assertFalse(px > width - TASKS and py > CUBE, f"{where}: under the Tasks panel")
        return px, py

    def move(self, x, y):
        StudioGui.view_mouse("move", *self.at(x, y))
        settle()

    def click(self, x, y):
        self.move(x, y)  # preselects what's under the pointer first, as a real pointer does
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
        settle(100)

    def line(self, start, end):
        """Draws one line by clicking its ends, and leaves the tool."""
        count = len(self.sketch.Geometry)
        self.tool("Sketcher_CreateLine")
        self.click(*start)
        self.click(*end)
        self.finish()
        self.assertEqual(len(self.sketch.Geometry), count + 1, f"no line drawn from {start} to {end}")

    # -- what's in the sketch ----------------------------------------------------------------------
    def dimensions(self):
        return sorted((c.Type, round(c.Value, 4)) for c in self.sketch.Constraints
                      if c.Type in ("Distance", "DistanceX", "DistanceY", "Diameter", "Radius"))

    def kinds(self):
        return sorted(c.Type for c in self.sketch.Constraints)

    def constraints(self, kind):
        return [c for c in self.sketch.Constraints if c.Type == kind]
