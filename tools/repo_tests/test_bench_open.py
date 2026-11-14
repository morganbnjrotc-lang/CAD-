# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the reference-file benchmark (tools/bench/bench_open.py). No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

A load benchmark is only worth something if every timed load was complete. A model that opens with
missing objects, or with objects whose Python code couldn't be imported, opens *faster*, so a
broken load would look like a speed-up. These tests pin down how the benchmark recognizes that.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "bench"))

import bench_open  # noqa: E402  (needs the path above)

COMPLETE = {"objects": 28, "missing_proxies": [], "faces": 120}


class ReferenceFiles(unittest.TestCase):
    def test_reference_set_has_step_and_native_files(self):
        # docs/PLAN.md §1.3: "Open reference model (STEP + native)".
        suffixes = {Path(f).suffix.lower() for f in bench_open.REFERENCE_FILES}
        self.assertIn(".fcstd", suffixes)
        self.assertTrue(suffixes & {".step", ".stp"}, "no STEP reference file")

    def test_reference_files_are_tracked_in_the_repo(self):
        # Results are only comparable over time if the files can't change unnoticed.
        for name in bench_open.REFERENCE_FILES:
            with self.subTest(name=name):
                self.assertFalse(Path(name).is_absolute())
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", name], cwd=REPO, capture_output=True
                )
                self.assertEqual(tracked.returncode, 0, f"{name} is not tracked by git")

    def test_expected_object_count_comes_from_the_saved_document(self):
        examples = REPO / "data" / "examples"
        self.assertEqual(bench_open.expected_objects(examples / "PartDesignExample.FCStd"), 28)
        self.assertEqual(bench_open.expected_objects(examples / "FEMExample.FCStd"), 43)
        # STEP files don't say how many FreeCAD objects they become.
        self.assertIsNone(bench_open.expected_objects(examples / "Schenkel.stp"))


class LoadProblems(unittest.TestCase):
    def test_complete_load_has_no_problems(self):
        self.assertEqual(bench_open.load_problems(COMPLETE, expected_objects=28), [])

    def test_objects_that_could_not_be_created(self):
        # e.g. FEMExample on the slim build: 14 of 43 objects, FEM types are unknown.
        problems = bench_open.load_problems(dict(COMPLETE, objects=14), expected_objects=28)
        self.assertEqual(len(problems), 1)
        self.assertIn("14 of 28", problems[0])

    def test_objects_whose_python_code_is_missing(self):
        # e.g. BIMExample on the slim build: every object loads, 135 have no Python code.
        report = dict(COMPLETE, missing_proxies=["Wall", "Window001", "Stairs"])
        problems = bench_open.load_problems(report, expected_objects=28)
        self.assertEqual(len(problems), 1)
        self.assertIn("3 objects", problems[0])
        self.assertIn("Wall", problems[0])

    def test_no_geometry(self):
        problems = bench_open.load_problems(dict(COMPLETE, faces=0), expected_objects=28)
        self.assertEqual(len(problems), 1)
        self.assertIn("no geometry", problems[0])

    def test_error_reported_by_the_probe(self):
        # e.g. a modal dialog stopped the load, or the file couldn't be opened at all.
        report = {"error": "modal dialog 'Recomputation required'"}
        problems = bench_open.load_problems(report, expected_objects=28)
        self.assertEqual(problems, ["modal dialog 'Recomputation required'"])

    def test_step_files_are_not_held_to_an_object_count(self):
        self.assertEqual(bench_open.load_problems(dict(COMPLETE, objects=5), expected_objects=None), [])


if __name__ == "__main__":
    unittest.main()
