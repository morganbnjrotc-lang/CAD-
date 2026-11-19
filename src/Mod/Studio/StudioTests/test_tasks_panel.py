# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the Tasks panel floats (PLAN 3.10): right of the 3D view, under the navigation cube, medium height,
a bit wider than FreeCAD makes it (the user: "not really tall and skinny, but medium and slightly wider")."""

import unittest
import uuid

import FreeCAD

from studio.services import tasks_panel
from studio.services.settings import Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
CUBE = 132  # px: FreeCAD's navigation cube


def height(area_height, cube=CUBE):
    """The panel's height FreeCAD lays out: the room under the cube less the gap Studio keeps below it."""
    room = area_height - (cube + tasks_panel.CUBE_GAP)
    return room - tasks_panel.bottom_gap(area_height, cube)


class Size(unittest.TestCase):
    def test_medium_height_under_the_cube(self):
        room = 760 - (CUBE + tasks_panel.CUBE_GAP)  # a maximized window on a 1080p screen at 125 %
        self.assertAlmostEqual(height(760) / room, tasks_panel.SHARE, delta=0.01)
        self.assertGreater(tasks_panel.bottom_gap(760, CUBE), 150, "not medium: nearly the whole height")

    def test_never_shorter_than_its_minimum_while_there_is_room(self):
        self.assertEqual(height(560), tasks_panel.MIN_HEIGHT)

    def test_a_short_view_gets_the_whole_height(self):
        self.assertEqual(tasks_panel.bottom_gap(400, CUBE), 0)

    def test_a_bit_wider_than_freecads(self):
        self.assertGreater(tasks_panel.WIDTH, 352)  # FreeCAD's width for the panel
        self.assertLess(tasks_panel.WIDTH, 352 * 1.4)  # "slightly"


class FreeCADPanelSettings(unittest.TestCase):
    def setUp(self):
        name = "TasksPanel" + uuid.uuid4().hex[:8]
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.overlay = FreeCAD.ParamGet(f"{TEST_PARENT}/{name}/OverlayRight")
        self.overlay.SetInt("Width", 352)  # what FreeCAD saved
        self.panel = tasks_panel.FreeCADTasksPanel(f"{TEST_PARENT}/{name}/OverlayRight",
                                                   Settings(f"{TEST_PARENT}/{name}/Studio"))

    def test_sets_the_width_and_the_gap_below(self):
        self.assertTrue(self.panel.apply(760, CUBE))
        self.assertEqual(self.overlay.GetInt("Width"), tasks_panel.WIDTH)
        self.assertEqual(self.overlay.GetInt("Offset2"), tasks_panel.bottom_gap(760, CUBE))

    def test_the_width_only_once_then_the_users(self):
        self.panel.apply(760, CUBE)
        self.overlay.SetInt("Width", 500)  # the user dragged the panel's edge
        self.panel.apply(700, CUBE)
        self.assertEqual(self.overlay.GetInt("Width"), 500)

    def test_the_gap_follows_the_window(self):
        self.panel.apply(760, CUBE)
        self.panel.apply(600, CUBE)
        self.assertEqual(self.overlay.GetInt("Offset2"), tasks_panel.bottom_gap(600, CUBE))

    def test_writes_nothing_when_nothing_changes(self):
        # FreeCAD lays its floating panels out again on each write.
        self.panel.apply(760, CUBE)
        self.assertFalse(self.panel.apply(760, CUBE))
