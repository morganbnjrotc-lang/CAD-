# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Tasks panel floats medium-sized at the right of the 3D view (PLAN 3.10), also after the window
changes size, and shows only while a task is open (no empty box over the model between tasks). Measured on FreeCAD's panel through StudioGui (Python wrappers of FreeCAD's floating
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

    def test_no_panel_while_no_task_is_open(self):
        settle(600)
        self.assertIsNone(StudioGui.tasks_panel_rect(), "an empty Tasks panel shows over the model")

    def test_shown_for_a_task_and_hidden_after_it(self):
        self.open_panel()
        self.assertIsNotNone(StudioGui.tasks_panel_rect())
        FreeCADGui.Control.activeTaskDialog().reject()
        for _ in range(20):  # FreeCAD slides the panel out: about half a second
            settle(100)
            if StudioGui.tasks_panel_rect() is None:
                break
        self.assertIsNone(StudioGui.tasks_panel_rect(), "the panel stays after its task")
