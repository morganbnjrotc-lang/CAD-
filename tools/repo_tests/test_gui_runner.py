# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the GUI test runner (tools/test/run_gui_suites.py). No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

FreeCAD can crash after the last test, while it shuts down (e.g. Python still holding a FreeCAD widget
that FreeCAD destroys late). Its exit code was then sometimes 0, so the runner reads FreeCAD's own
crash messages too.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "test"))
sys.path.insert(0, str(REPO / "tools" / "bench"))

import run_gui_suites  # noqa: E402

PASSED = "Ran 5 tests in 0.9s\n\nOK\nSystem exit\n"


class CrashAtExit(unittest.TestCase):
    def test_a_clean_run_keeps_its_exit_code(self):
        self.assertEqual(run_gui_suites.verdict(PASSED, 0), 0)
        self.assertEqual(run_gui_suites.verdict("FAILED (failures=1)\n", 1), 1)

    def test_an_abort_fails_the_run_even_with_exit_code_0(self):
        output = PASSED + "Abnormal program termination...\n<Exception> Break signal occurred\n"
        self.assertNotEqual(run_gui_suites.verdict(output, 0), 0)

    def test_an_access_violation_fails_the_run(self):
        self.assertNotEqual(run_gui_suites.verdict(PASSED + "Illegal storage access...\n", 0), 0)

    def test_a_fatal_python_error_fails_the_run(self):
        self.assertNotEqual(run_gui_suites.verdict(PASSED + "Fatal Python error: Aborted\n", 0), 0)


if __name__ == "__main__":
    unittest.main()
