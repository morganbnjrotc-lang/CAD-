# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the slim build configuration (docs/adr/0006-slim-build.md). No FreeCAD build needed.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

The slim build switches off FreeCAD modules this product doesn't ship. These tests guard against
upstream merges quietly undoing that: a renamed BUILD_* option (our OFF would then set a dead
variable and the module would come back), or a kept module starting to require a removed one.
"""

import json
import re
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRESETS = REPO / "CMakePresets.json"
OPTIONS = REPO / "cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake"
DEPENDENCIES = REPO / "cMake/FreeCAD_Helpers/CheckInterModuleDependencies.cmake"
PIXI = REPO / "pixi.toml"

# docs/PLAN.md task 1.5
REMOVED = {
    "BUILD_FEM",
    "BUILD_BIM",
    "BUILD_ROBOT",
    "BUILD_OPENSCAD",
    "BUILD_POINTS",
    "BUILD_REVERSEENGINEERING",
    "BUILD_INSPECTION",
    "BUILD_WEB",
    "BUILD_JTREADER",
    "BUILD_ADDONMGR",
}
SLIM_PRESETS = {
    "studio-slim-windows-rel-with-deb-info": ("conda-windows-rel-with-deb-info", "build/slim"),
    "studio-slim-windows-release": ("conda-windows-release", "build/slim-release"),
}


def configure_presets() -> dict:
    data = json.loads(PRESETS.read_text(encoding="utf-8"))
    return {p["name"]: p for p in data["configurePresets"]}


class SlimPresetTest(unittest.TestCase):
    def test_slim_preset_turns_off_exactly_the_planned_modules(self):
        slim = configure_presets()["studio-slim"]
        turned_off = {
            name
            for name, var in slim["cacheVariables"].items()
            if str(var.get("value", var) if isinstance(var, dict) else var).upper() == "OFF"
        }
        self.assertEqual(sorted(turned_off), sorted(REMOVED))

    def test_every_option_we_turn_off_still_exists(self):
        declared = set(re.findall(r"option\((BUILD_\w+)", OPTIONS.read_text(encoding="utf-8")))
        self.assertEqual(sorted(REMOVED - declared), [], "upstream renamed or removed these options")

    def test_windows_slim_presets_inherit_slim_and_build_separately(self):
        presets = configure_presets()
        for name, (base, binary_dir) in SLIM_PRESETS.items():
            with self.subTest(preset=name):
                preset = presets[name]
                # The first preset in `inherits` wins conflicts, so studio-slim must come first.
                self.assertEqual(preset["inherits"], ["studio-slim", base])
                self.assertEqual(preset["binaryDir"], "${sourceDir}/" + binary_dir)


class SlimDependencyTest(unittest.TestCase):
    def test_no_kept_module_requires_a_removed_one(self):
        rules = re.findall(
            r"^\s*REQUIRES_MODS\((\w+)\s+([\w\s]+?)\)", DEPENDENCIES.read_text(encoding="utf-8"), re.M
        )
        self.assertGreater(len(rules), 10, "dependency rules not found; did the file change shape?")
        for dependent, prerequisites in rules:
            if dependent in REMOVED:
                continue
            with self.subTest(module=dependent):
                self.assertEqual(sorted(set(prerequisites.split()) & REMOVED), [])


class SlimPixiTasksTest(unittest.TestCase):
    def test_one_command_configure_and_build(self):
        tasks = tomllib.loads(PIXI.read_text(encoding="utf-8"))["target"]["win-64"]["tasks"]
        for task, text in {
            "configure-slim": "studio-slim-windows-rel-with-deb-info",
            "configure-slim-release": "studio-slim-windows-release",
            "build-slim": "build/slim",
            "build-slim-release": "build/slim-release",
        }.items():
            with self.subTest(task=task):
                self.assertIn(text, " ".join(tasks[task]["cmd"]))


if __name__ == "__main__":
    unittest.main()
