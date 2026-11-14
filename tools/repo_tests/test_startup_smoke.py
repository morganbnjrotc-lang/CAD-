# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the end-to-end startup check (tools/test/startup_smoke.py). No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

The smoke test starts the real app twice on brand-new profiles: once with background warm-up off,
to prove startup itself loads none of the catalog's workbenches (ADR 0007), and once as a new user
gets it, to see warm-up load the cheap workbenches afterwards. These tests pin down the verdicts.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "test"))
sys.path.insert(0, str(REPO / "tools" / "bench"))

import benchlib  # noqa: E402
import run_gui_suites  # noqa: E402
import startup_smoke  # noqa: E402

WARMUP_OFF = {"BaseApp/Preferences/Mod/Studio/Commands/WarmUp": False}


class Verdict(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self._tmp.name)
        common = {
            "active_workbench": "StudioWorkbench",
            "dialogs": [],
            "user_parameter_file": str(self.profile / "home" / "user.cfg"),
        }
        self.lazy = dict(common, early_commands=[])
        self.warm = dict(common, warmup={
            "done": True, "planned": ["SketcherWorkbench", "PartDesignWorkbench"],
            "loaded": ["SketcherWorkbench", "PartDesignWorkbench"], "failed": []}, cam_loaded=False)

    def tearDown(self):
        self._tmp.cleanup()

    def verdict(self, mode, state):
        return startup_smoke.failures(mode, state, self.profile)

    def test_clean_starts_pass(self):
        self.assertEqual(self.verdict("lazy", self.lazy), {})
        self.assertEqual(self.verdict("warm", self.warm), {})

    def test_a_dialog_waiting_after_startup_fails(self):
        # Gap found 2026-11-14: on CI a modal "Invalid OpenGL Version" warning was up (opened
        # with show(), so the event loop kept running) and the smoke test still passed.
        for mode, state in (("lazy", self.lazy), ("warm", self.warm)):
            with self.subTest(mode=mode):
                state = dict(state, dialogs=["FreeCAD - Invalid OpenGL Version"])
                self.assertIn("dialogs", self.verdict(mode, state))

    def test_unknown_dialog_state_fails(self):
        # A probe that didn't report dialogs must not count as "no dialogs".
        state = {k: v for k, v in self.lazy.items() if k != "dialogs"}
        self.assertIn("dialogs", self.verdict("lazy", state))

    def test_real_profile_fails(self):
        state = dict(self.lazy, user_parameter_file=r"C:\Users\someone\AppData\Roaming\FreeCAD\user.cfg")
        self.assertIn("user_parameter_file", self.verdict("lazy", state))

    def test_startup_that_loads_a_catalog_workbench_fails(self):
        # ADR 0007: with warm-up off, no command of a catalog workbench may exist after startup.
        state = dict(self.lazy, early_commands=["Sketcher_NewSketch"])
        self.assertIn("early_commands", self.verdict("lazy", state))
        self.assertIn("early_commands", self.verdict("lazy", {k: v for k, v in self.lazy.items()
                                                            if k != "early_commands"}))

    def test_warm_up_must_finish_load_its_plan_and_leave_cam_alone(self):
        broken = {
            "not finished": dict(self.warm, warmup=dict(self.warm["warmup"], done=False)),
            "never started": dict(self.warm, warmup=None),
            "load failed": dict(self.warm, warmup=dict(self.warm["warmup"], failed=["SketcherWorkbench"],
                                                       loaded=["PartDesignWorkbench"])),
            "plan not loaded": dict(self.warm, warmup=dict(self.warm["warmup"], loaded=["SketcherWorkbench"])),
            "empty plan": dict(self.warm, warmup=dict(self.warm["warmup"], planned=[], loaded=[])),
            "CAM loaded": dict(self.warm, cam_loaded=True),
            "switched workbench": dict(self.warm, active_workbench="SketcherWorkbench"),
        }
        for case, state in broken.items():
            with self.subTest(case=case):
                self.assertNotEqual(self.verdict("warm", state), {})

    def test_runs_lazy_with_warm_up_off_and_warm_as_a_new_user_gets_it(self):
        self.assertEqual(startup_smoke.RUNS, (("lazy", WARMUP_OFF), ("warm", {})))

    def test_uses_the_shared_throwaway_profile(self):
        # Same profile as the benchmarks: brand-new, except the OpenGL 1.x warning is dismissed
        # (GitHub's GPU-less runners would show it; see test_benchlib.py).
        self.assertIs(startup_smoke.make_profile, benchlib.make_profile)


class GuiSuiteProfile(unittest.TestCase):
    def test_gui_suites_run_with_warm_up_off_in_the_shared_profile(self):
        # Warm-up would load workbenches while GUI tests run; tests that check their workbench
        # isn't loaded yet would then fail depending on timing.
        self.assertIs(run_gui_suites.make_profile, benchlib.make_profile)
        self.assertEqual(run_gui_suites.SETTINGS, WARMUP_OFF)


if __name__ == "__main__":
    unittest.main()
