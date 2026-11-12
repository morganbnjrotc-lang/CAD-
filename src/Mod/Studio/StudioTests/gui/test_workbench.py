# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Studio workbench is the single environment the app runs in."""

import unittest

import FreeCADGui


class StudioWorkbenchTest(unittest.TestCase):
    def test_is_registered(self):
        self.assertIn("StudioWorkbench", FreeCADGui.listWorkbenches())

    def test_activates(self):
        previous = FreeCADGui.activeWorkbench()
        if previous is not None:
            self.addCleanup(FreeCADGui.activateWorkbench, previous.name())

        FreeCADGui.activateWorkbench("StudioWorkbench")

        self.assertEqual(FreeCADGui.activeWorkbench().name(), "StudioWorkbench")
