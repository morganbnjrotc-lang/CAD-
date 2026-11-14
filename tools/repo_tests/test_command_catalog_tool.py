# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks on the command catalog generator (tools/studio/generate_command_catalog.py), ADR 0007.

Run from the repo root:
    pixi run python -m unittest discover -s tools/repo_tests -v

The catalog lets the unified environment show every command without loading its module. If the
generator attributes a command to the wrong workbench, loading that workbench on first use won't
make the command exist; if output isn't deterministic, the drift check cries wolf.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "studio"))
sys.path.insert(0, str(REPO / "tools" / "bench"))

import generate_command_catalog as gen  # noqa: E402


def info(name, menu="", tip="", pixmap="", shortcut=""):
    return {"name": name, "menuText": menu, "toolTip": tip, "pixmap": pixmap, "shortcut": shortcut,
            "whatsThis": "", "statusTip": ""}


# What the probe reports: commands registered at startup, then per workbench the commands its
# first activation added.
PROBE = {
    "freecad": "27.1.0",
    "core": [info("Std_Undo", "&Undo", "Undo exactly one action", "edit-undo", "Ctrl+Z")],
    "workbenches": [
        {"name": "SketcherWorkbench", "class": "SketcherGui::Workbench",
         "commands": [info("Sketcher_NewSketch", "Create sketch", "Creates a new sketch", "Sketcher_NewSketch")]},
        {"name": "PartDesignWorkbench", "class": "PartDesignGui::Workbench",
         "commands": [info("PartDesign_Pad", "Pad", "Extrudes a sketch", "PartDesign_Pad", "P, D"),
                      info("PartDesign_Body", "Body", "", ":/icons/PartDesign_Body.svg")]},
    ],
}


class IconLookup(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        src = Path(self._tmp.name) / "src"
        for path in (
            "Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg",
            "Mod/Sketcher/Gui/Resources/icons/general/Sketcher_NewSketch.svg",
            "Mod/Part/Gui/Resources/icons/PartDesign_Pad.svg",  # same name in another module
            "Gui/Icons/edit-undo.svg",
        ):
            (src / path).parent.mkdir(parents=True, exist_ok=True)
            (src / path).write_text("<svg/>", encoding="utf-8")
        self.icons = gen.IconIndex(src)

    def tearDown(self):
        self._tmp.cleanup()

    def test_finds_icons_in_subfolders_as_repo_relative_paths(self):
        self.assertEqual(self.icons.find("Sketcher_NewSketch", "Sketcher"),
                         "src/Mod/Sketcher/Gui/Resources/icons/general/Sketcher_NewSketch.svg")

    def test_prefers_the_commands_own_module_when_names_clash(self):
        self.assertEqual(self.icons.find("PartDesign_Pad", "PartDesign"),
                         "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg")

    def test_resource_paths_and_extensions_are_reduced_to_the_name(self):
        for pixmap in (":/icons/PartDesign_Pad.svg", "PartDesign_Pad.svg", "PartDesign_Pad"):
            with self.subTest(pixmap=pixmap):
                self.assertEqual(self.icons.find(pixmap, "PartDesign"),
                                 "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg")

    def test_core_icons_are_found_and_unknown_ones_are_none(self):
        self.assertEqual(self.icons.find("edit-undo", None), "src/Gui/Icons/edit-undo.svg")
        self.assertIsNone(self.icons.find("No_Such_Icon", "PartDesign"))
        self.assertIsNone(self.icons.find("", "PartDesign"))


class Catalog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        src = Path(self._tmp.name) / "src"
        (src / "Mod/PartDesign/Gui/Resources/icons").mkdir(parents=True)
        (src / "Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg").write_text("<svg/>")
        self.catalog = gen.build_catalog(PROBE, gen.IconIndex(src))

    def tearDown(self):
        self._tmp.cleanup()

    def test_each_command_belongs_to_the_workbench_whose_loading_registered_it(self):
        owner = {c["name"]: c["workbench"] for c in self.catalog["commands"]}
        self.assertEqual(owner, {
            "Std_Undo": None,  # available from startup
            "Sketcher_NewSketch": "SketcherWorkbench",
            "PartDesign_Pad": "PartDesignWorkbench",
            "PartDesign_Body": "PartDesignWorkbench",
        })

    def test_command_fields(self):
        pad = next(c for c in self.catalog["commands"] if c["name"] == "PartDesign_Pad")
        self.assertEqual(pad, {
            "name": "PartDesign_Pad", "workbench": "PartDesignWorkbench", "menu_text": "Pad",
            "tooltip": "Extrudes a sketch", "shortcut": "P, D",
            "icon": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg",
        })

    def test_workbenches_listed_in_load_order_with_their_class(self):
        self.assertEqual(self.catalog["workbenches"], [
            {"name": "SketcherWorkbench", "class": "SketcherGui::Workbench"},
            {"name": "PartDesignWorkbench", "class": "PartDesignGui::Workbench"},
        ])

    def test_missing_icons_are_reported(self):
        self.assertEqual(gen.missing_icons(self.catalog), ["PartDesign_Body", "Sketcher_NewSketch", "Std_Undo"])

    def test_output_is_deterministic(self):
        shuffled = dict(PROBE, workbenches=[dict(w, commands=list(reversed(w["commands"])))
                                            for w in PROBE["workbenches"]])
        other = gen.build_catalog(shuffled, gen.IconIndex(Path(self._tmp.name) / "src"))
        self.assertEqual(gen.dumps(self.catalog), gen.dumps(other))
        self.assertTrue(gen.dumps(self.catalog).endswith("\n"))


class Ownership(unittest.TestCase):
    """Each workbench is loaded alone in a fresh process; a command can be registered by several
    (Sketcher's loading also registers Part's commands, Assembly's registers Spreadsheet's). Its
    owner is the workbench loaded on its first use, so pick the one it obviously belongs to."""

    ALONE = {
        "SketcherWorkbench": [info("Sketcher_NewSketch"), info("Part_Box")],
        "PartWorkbench": [info("Part_Box"), info("Std_Measure")],
        "AssemblyWorkbench": [info("Assembly_New"), info("Spreadsheet_CreateSheet"), info("Std_Measure")],
        "SpreadsheetWorkbench": [info("Spreadsheet_CreateSheet")],
    }
    CLASSES = {name: f"{name}Class" for name in ALONE}
    ORDER = ("SketcherWorkbench", "PartWorkbench", "AssemblyWorkbench", "SpreadsheetWorkbench")

    def owners(self):
        workbenches = gen.assign_owners(self.ALONE, self.CLASSES, self.ORDER)
        return {c["name"]: w["name"] for w in workbenches for c in w["commands"]}

    def test_the_workbench_named_by_the_command_prefix_wins(self):
        self.assertEqual(self.owners()["Part_Box"], "PartWorkbench")
        self.assertEqual(self.owners()["Spreadsheet_CreateSheet"], "SpreadsheetWorkbench")

    def test_without_a_matching_workbench_the_earliest_in_load_order_wins(self):
        self.assertEqual(self.owners()["Std_Measure"], "PartWorkbench")

    def test_every_command_appears_once_and_workbenches_keep_load_order(self):
        workbenches = gen.assign_owners(self.ALONE, self.CLASSES, self.ORDER)
        self.assertEqual([w["name"] for w in workbenches], list(self.ORDER))
        names = [c["name"] for w in workbenches for c in w["commands"]]
        self.assertEqual(sorted(names), sorted(set(names)))
        self.assertEqual(workbenches[0]["class"], "SketcherWorkbenchClass")


class DriftCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.icons = gen.IconIndex(Path(self._tmp.name) / "src")
        self.shipped = gen.build_catalog(PROBE, self.icons)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_difference_when_nothing_changed(self):
        self.assertEqual(gen.differences(self.shipped, gen.build_catalog(PROBE, self.icons)), [])

    def test_renamed_removed_added_and_changed_commands_are_all_reported(self):
        sketcher, partdesign = PROBE["workbenches"]
        changed = dict(PROBE, workbenches=[
            dict(sketcher, commands=[info("Sketcher_NewSketch", "New sketch", "Creates a new sketch",
                                          "Sketcher_NewSketch")]),
            dict(partdesign, commands=[info("PartDesign_Extrude", "Extrude"),
                                       partdesign["commands"][1]]),
        ])
        found = "\n".join(gen.differences(self.shipped, gen.build_catalog(changed, self.icons)))
        self.assertIn("removed: PartDesign_Pad", found)
        self.assertIn("added: PartDesign_Extrude", found)
        self.assertIn("changed: Sketcher_NewSketch menu_text", found)


if __name__ == "__main__":
    unittest.main()
