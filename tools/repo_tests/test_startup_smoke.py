# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the end-to-end startup check (tools/test/startup_smoke.py). No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

The smoke test judges what a brand-new user sees after startup. These tests pin down its verdict
for a given app state, so a gap like the one below can't come back unnoticed.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "test"))
sys.path.insert(0, str(REPO / "tools" / "bench"))

import benchlib  # noqa: E402
import startup_smoke  # noqa: E402


class Verdict(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self._tmp.name)
        self.clean = {
            "active_workbench": "StudioWorkbench",
            "dialogs": [],
            "user_parameter_file": str(self.profile / "home" / "user.cfg"),
        }

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_start_passes(self):
        self.assertEqual(startup_smoke.failures(self.clean, self.profile), {})

    def test_a_dialog_waiting_after_startup_fails(self):
        # Gap found 2026-11-14: on CI a modal "Invalid OpenGL Version" warning was up (opened
        # with show(), so the event loop kept running) and the smoke test still passed.
        state = dict(self.clean, dialogs=["FreeCAD - Invalid OpenGL Version"])
        self.assertIn("dialogs", startup_smoke.failures(state, self.profile))

    def test_unknown_dialog_state_fails(self):
        # A probe that didn't report dialogs must not count as "no dialogs".
        state = {k: v for k, v in self.clean.items() if k != "dialogs"}
        self.assertIn("dialogs", startup_smoke.failures(state, self.profile))

    def test_real_profile_fails(self):
        state = dict(self.clean, user_parameter_file=r"C:\Users\someone\AppData\Roaming\FreeCAD\user.cfg")
        self.assertIn("user_parameter_file", startup_smoke.failures(state, self.profile))

    def test_uses_the_shared_throwaway_profile(self):
        # Same profile as the benchmarks: brand-new, except the OpenGL 1.x warning is dismissed
        # (GitHub's GPU-less runners would show it; see test_benchlib.py).
        self.assertIs(startup_smoke.make_profile, benchlib.make_profile)


if __name__ == "__main__":
    unittest.main()
