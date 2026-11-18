# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drawing in a sketch with synthetic input, for the sketching tests (PLAN 3.2–3.4).

A new document with a sketch being edited, in inches, the view showing about 8 in from top to bottom.
Positions are in the sketch's own coordinates, in inches. The input goes through StudioGui's C++ helpers:
Python wrappers of FreeCAD's 3D view widgets make FreeCAD abort at exit (docs/BASELINE.md).
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


class SketchInput(unittest.TestCase):
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
        view.setCameraType("Orthographic")
        view.getCameraNode().height.setValue(8 * INCH)
        settle(100)

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
        return StudioGui.view_point(point.x, point.y, point.z)

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
        self.tool("Sketcher_CreateLine")
        self.click(*start)
        self.click(*end)
        self.finish()

    # -- what's in the sketch ----------------------------------------------------------------------
    def dimensions(self):
        return sorted((c.Type, round(c.Value, 4)) for c in self.sketch.Constraints
                      if c.Type in ("Distance", "DistanceX", "DistanceY", "Diameter", "Radius"))

    def kinds(self):
        return sorted(c.Type for c in self.sketch.Constraints)

    def constraints(self, kind):
        return [c for c in self.sketch.Constraints if c.Type == kind]
