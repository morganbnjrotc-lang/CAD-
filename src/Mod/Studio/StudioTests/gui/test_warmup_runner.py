# SPDX-License-Identifier: LGPL-2.1-or-later
"""The warm-up runner (studio.shell.warmup), ADR 0007 decision 3.

Runs in the real app's event loop, but with a recording fake backend: what loading a workbench
really does is covered by test_command_backend, and nothing here may load real workbenches (other
GUI tests check that their workbench isn't loaded yet).
"""

import time
import unittest

from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

from studio.services.commands import CommandCatalog, CommandService
from studio.shell.warmup import WarmUp

from ..test_commands import FakeBackend
from ..test_warmup import CATALOG


def run_until(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
    return condition()


class WarmUpRunnerTest(unittest.TestCase):
    def make(self, plan, backend=None, **options):
        self.backend = backend or FakeBackend()
        service = CommandService(CommandCatalog(CATALOG), self.backend)
        return WarmUp(service, plan, step_ms=0, **options)

    def test_loads_one_workbench_per_step_letting_other_events_run_between(self):
        warmup = self.make(["SketcherWorkbench", "PartDesignWorkbench"])
        warmup.start(delay_ms=0)
        # Queued after the first step, before the second: must run between them.
        QtCore.QTimer.singleShot(0, lambda: self.backend.calls.append(("other event", None)))

        self.assertTrue(run_until(lambda: warmup.done), "warm-up did not finish")
        self.assertEqual(self.backend.calls, [("load", "SketcherWorkbench"), ("other event", None),
                                              ("load", "PartDesignWorkbench")])
        self.assertEqual(warmup.loaded, ["SketcherWorkbench", "PartDesignWorkbench"])

    def test_a_failed_load_is_reported_and_the_rest_still_load(self):
        warmup = self.make(["SketcherWorkbench", "PartDesignWorkbench"],
                           backend=FakeBackend(failing={"SketcherWorkbench"}))
        warmup.start(delay_ms=0)
        self.assertTrue(run_until(lambda: warmup.done))
        self.assertEqual(warmup.failed, ["SketcherWorkbench"])
        self.assertEqual(warmup.loaded, ["PartDesignWorkbench"])

    def test_waits_while_the_user_is_busy(self):
        busy_checks = [True, True, True]  # e.g. a mouse button held during an orbit
        warmup = self.make(["SketcherWorkbench"], user_busy=lambda: bool(busy_checks and busy_checks.pop()))
        warmup.start(delay_ms=0)
        self.assertTrue(run_until(lambda: warmup.done))
        self.assertEqual(busy_checks, [], "did not ask whether the user was busy")
        self.assertEqual(warmup.loaded, ["SketcherWorkbench"])

    def test_empty_plan_finishes_without_loading(self):
        warmup = self.make([])
        warmup.start(delay_ms=0)
        self.assertTrue(run_until(lambda: warmup.done))
        self.assertEqual(self.backend.calls, [])
