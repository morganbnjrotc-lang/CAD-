# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which workbenches warm up after startup (studio.services.warmup), ADR 0007 decision 3."""

import unittest
import uuid

import FreeCAD

from studio.services.commands import CommandCatalog, CommandService
from studio.services.settings import Settings
from studio.services.warmup import TOO_SLOW_TO_WARM, WARM_UP, warmup_plan

from .test_commands import FakeBackend

CATALOG = {
    "freecad": "27.1.0",
    "workbenches": [{"name": n, "class": ""} for n in
                    ("SketcherWorkbench", "PartDesignWorkbench", "CAMWorkbench", "SpreadsheetWorkbench")],
    "commands": [],
}
TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


class WarmUpPlan(unittest.TestCase):
    def setUp(self):
        name = "WarmUp" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.service = CommandService(CommandCatalog(CATALOG), FakeBackend())

    def test_on_by_default(self):
        self.assertIs(WARM_UP.default, True)

    def test_cheap_workbenches_in_catalog_order_never_cam(self):
        # CAM takes ~0.6 s in one blocking import (ADR 0007 measurements): too long to hide in an
        # idle moment, so it loads on its first use instead.
        self.assertIn("CAMWorkbench", TOO_SLOW_TO_WARM)
        self.assertEqual(warmup_plan(self.service, self.settings),
                         ["SketcherWorkbench", "PartDesignWorkbench", "SpreadsheetWorkbench"])

    def test_nothing_when_the_user_turned_it_off(self):
        self.settings.set(WARM_UP, False)
        self.assertEqual(warmup_plan(self.service, self.settings), [])

    def test_already_loaded_workbenches_are_skipped(self):
        self.service.ensure_loaded("PartDesignWorkbench")
        self.assertEqual(warmup_plan(self.service, self.settings),
                         ["SketcherWorkbench", "SpreadsheetWorkbench"])


if __name__ == "__main__":
    unittest.main()
