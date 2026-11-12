# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCADCmd.exe for run_headless_suites.py. Do not run directly.

Environment:
  STUDIO_SUITES        comma-separated test module names, or "0" for every registered suite
  STUDIO_TEST_TIMEOUT  seconds a single test may take before all thread stacks are dumped and
                       the process exits (default 300)
"""

import faulthandler
import os
import sys
import unittest

import FreeCAD

TIMEOUT = int(os.environ.get("STUDIO_TEST_TIMEOUT", "300"))
SUITES = os.environ.get("STUDIO_SUITES", "0")


class WatchdogResult(unittest.TextTestResult):
    """Re-arms a per-test watchdog: a hung test dumps every thread's stack and ends the run."""

    def startTest(self, test):
        faulthandler.dump_traceback_later(TIMEOUT, exit=True, file=sys.stderr)
        sys.stderr.write(f"\n[watchdog] {test.id()}\n")
        super().startTest(test)

    def stopTest(self, test):
        faulthandler.cancel_dump_traceback_later()
        super().stopTest(test)


EXCLUDE = {n.strip() for n in os.environ.get("STUDIO_SUITES_EXCLUDE", "").split(",") if n.strip()}


def load():
    names = list(FreeCAD.__unit_test__) if SUITES == "0" else SUITES.split(",")
    names = [n.strip() for n in names if n.strip() and n.strip() not in EXCLUDE]
    FreeCAD.Console.PrintMessage(f"STUDIO_SUITES_RUNNING {','.join(names)}\n")
    if EXCLUDE:
        FreeCAD.Console.PrintMessage(f"STUDIO_SUITES_EXCLUDED {','.join(sorted(EXCLUDE))}\n")
    import TestApp

    suite = unittest.TestSuite()
    for name in names:
        suite.addTest(TestApp.tryLoadingTest(name))
    return suite


FreeCAD.Console.PrintMessage(f"STUDIO_USER_PARAMETER {FreeCAD.ConfigGet('UserParameter')}\n")

runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=WatchdogResult)
result = runner.run(load())
sys.stdout.flush()
FreeCAD.Console.PrintMessage(
    f"\nSTUDIO_SUITE_SUMMARY ran={result.testsRun} failures={len(result.failures)} "
    f"errors={len(result.errors)} skipped={len(result.skipped)}\n"
)
os._exit(0 if result.wasSuccessful() else 1)
