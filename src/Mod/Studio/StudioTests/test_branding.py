# SPDX-License-Identifier: LGPL-2.1-or-later
"""Product configuration that comes from bin/branding.xml."""

import unittest

import FreeCAD

from StudioTests.support import preserve_param

GENERAL = "User parameter:BaseApp/Preferences/General"
START = "User parameter:BaseApp/Preferences/Mod/Start"


class BrandingTest(unittest.TestCase):
    def test_studio_is_the_startup_workbench(self):
        self.assertEqual(FreeCAD.ConfigGet("StartWorkbench"), "StudioWorkbench")

    def test_first_run_migration_keeps_the_branded_start_workbench(self):
        """A brand-new profile must start in the branded workbench.

        FreeCAD's Start module runs a one-time 2024 settings migration on every profile that hasn't
        been migrated, including brand-new ones, and it used to hardcode PartDesign as the startup
        workbench, overriding branding.xml.
        """
        import StartMigrator

        general = FreeCAD.ParamGet(GENERAL)
        start = FreeCAD.ParamGet(START)
        preserve_param(self, general, "String", "AutoloadModule")
        preserve_param(self, start, "Bool", "ShowOnStartup")
        general.RemString("AutoloadModule")  # a brand-new profile has no value

        StartMigrator.StartMigrator2024()._update_startup_flags()

        self.assertEqual(general.GetString("AutoloadModule"), "StudioWorkbench")
