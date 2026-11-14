# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the startup profiler (tools/bench/profile_startup.py). No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

The profiler splits startup into phases at known log lines. If a phase boundary is wrong or
silently missing, time gets blamed on the wrong code and we optimize the wrong thing, so these
tests pin down how time is attributed.
"""

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "bench"))

import benchlib  # noqa: E402
import profile_startup  # noqa: E402

# Shape of a real FreeCAD 27.1 startup log (abridged), as (seconds since launch, line).
LOG = [
    (0.120, "\ufeffMsg: FreeCAD 27.1.0, Libs: 27.1.0devRDev Build"),
    (0.140, "Log: XERCESC_VERSION = 3.3.0"),
    (0.520, "Log: Create Application"),
    (0.600, "Log: Init:      Initializing C:\\b\\Mod\\Part... done"),  # App side: not InitGui
    (0.640, "Log: Using C:\\b\\Mod as module path!"),
    (0.660, "Log: Local server 'FreeCAD' started"),
    (0.950, "Log: OpenGL version is: 4.6 (4.6.0 Compatibility Profile Context)"),
    (1.000, "Log: Run Gui init script"),
    (1.010, "Log: Init:   Searching modules"),
    (1.260, "Log: Init:      Initializing C:\\b\\Mod\\AddonManager... done"),
    (1.300, "Log: Loading Material module… done"),
    (1.310, "Log: Init:      Initializing C:\\b\\Mod\\Material... done"),
    (1.310, "Log: Init:      Initializing C:\\b\\Mod\\Plot (InitGui.py not found)... ignore"),
    (1.330, "Log: Init: Initializing freecad.ExtAddon... done"),
    (1.380, "Log: Init: Running FreeCADGuiInit.py start script... done"),
    (1.400, "Log: Init: Activating default workbench StudioWorkbench"),
    (1.600, "Log: Init: Showing main window"),
    (1.700, "Log: Init: Entering event loop"),
    (2.030, "Log: Init: Processing command line files"),
]
READY = 2.250


class Phases(unittest.TestCase):
    def test_each_phase_runs_from_the_previous_boundary_to_its_own(self):
        phases = dict(profile_startup.split_phases(LOG, READY))
        expected = {
            "process start → first log line": 0.120,
            "config + crash reporter setup": 0.400,
            "App init script (FreeCADInit.py)": 0.120,
            "Qt application + OpenGL check": 0.310,
            "main window + splash": 0.050,
            "GUI init script (all InitGui.py)": 0.380,
            "between GUI init and workbench": 0.020,
            "start workbench activation": 0.200,
            "show main window": 0.100,
            "first events (Start page, …)": 0.330,
            "command-line files → idle": 0.220,
        }
        self.assertEqual(list(phases), list(expected), "phases out of order or renamed")
        for name, seconds in expected.items():
            with self.subTest(phase=name):
                self.assertAlmostEqual(phases[name], seconds, places=6)

    def test_phases_add_up_to_time_to_ready(self):
        total = sum(s for _, s in profile_startup.split_phases(LOG, READY) if s is not None)
        self.assertAlmostEqual(total, READY, places=6)

    def test_missing_boundary_is_reported_not_blamed_on_a_neighbour(self):
        # If an upstream merge rewords a log line, that phase must show as unknown (None), and
        # its time goes to the next phase that can still be measured, so the total stays right.
        log = [entry for entry in LOG if "Showing main window" not in entry[1]]
        phases = dict(profile_startup.split_phases(log, READY))
        self.assertIsNone(phases["start workbench activation"])
        self.assertAlmostEqual(phases["show main window"], 0.300, places=6)
        self.assertAlmostEqual(sum(s for s in phases.values() if s is not None), READY, places=6)


class InitGuiTimes(unittest.TestCase):
    def test_each_module_gets_the_time_since_the_previous_module(self):
        times = dict(profile_startup.initgui_times(LOG))
        self.assertEqual(list(times), ["AddonManager", "Material", "Plot", "freecad.ExtAddon"])
        self.assertAlmostEqual(times["AddonManager"], 0.250, places=6)  # from "Searching modules"
        self.assertAlmostEqual(times["Material"], 0.050, places=6)  # includes its own log lines
        self.assertAlmostEqual(times["Plot"], 0.0, places=6)
        self.assertAlmostEqual(times["freecad.ExtAddon"], 0.020, places=6)

    def test_app_side_init_lines_are_not_counted(self):
        self.assertNotIn("Part", dict(profile_startup.initgui_times(LOG)))


class LogTail(unittest.TestCase):
    def test_lines_are_stamped_when_they_are_written(self):
        # FreeCAD flushes its log file after every message; the reader stamps each line as it
        # appears, so a pause in the writer must show up as a gap between timestamps.
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "out.log"
            writer = (
                "import sys, time\n"
                "f = open(sys.argv[1], 'w', encoding='utf-8')\n"
                "f.write('Log: one\\n'); f.flush(); time.sleep(0.3)\n"
                "f.write('Log: two\\n'); f.flush()\n"
            )
            start = time.perf_counter()
            proc = subprocess.Popen([sys.executable, "-c", writer, str(log)])
            lines = benchlib.tail_log(log, proc, start)
        self.assertEqual([line for _, line in lines], ["Log: one", "Log: two"])
        self.assertGreater(lines[1][0] - lines[0][0], 0.2)


if __name__ == "__main__":
    unittest.main()
