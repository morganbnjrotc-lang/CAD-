# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Tasks panel floats medium-sized at the right of the 3D view (PLAN 3.10), also after the window
changes size. Measured on FreeCAD's panel through StudioGui (Python wrappers of FreeCAD's floating
panels make FreeCAD abort at exit, docs/BASELINE.md)."""

import FreeCADGui

import StudioGui
from StudioTests.gui.sketch_input import settle
from StudioTests.gui.test_extrude import Extruding
from studio.services import tasks_panel


class MediumSize(Extruding):
    def open_panel(self):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.sketch)
        FreeCADGui.runCommand("PartDesign_Pad", 0)
        settle(800)

    def expected(self):
        area_height, cube = StudioGui.tasks_room()
        top = cube + tasks_panel.CUBE_GAP
        return top, area_height - top - tasks_panel.bottom_gap(area_height, cube)

    def test_medium_height_under_the_cube_and_a_bit_wider(self):
        self.open_panel()
        rect = StudioGui.tasks_panel_rect()
        self.assertIsNotNone(rect, "the Tasks panel isn't showing")
        top, height = self.expected()
        self.assertEqual(rect[2], tasks_panel.WIDTH)
        self.assertEqual((rect[1], rect[3]), (top, height))

    def test_follows_the_window(self):
        main = FreeCADGui.getMainWindow()
        maximized, size = main.isMaximized(), main.size()

        def restore():
            main.resize(size)
            if maximized:
                main.showMaximized()
            settle(600)

        self.addCleanup(restore)
        main.showNormal()
        main.resize(main.width(), main.height() - 150)
        settle(800)
        self.open_panel()
        top, height = self.expected()
        self.assertEqual(StudioGui.tasks_panel_rect()[1:4:2], (top, height))
