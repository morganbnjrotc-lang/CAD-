# SPDX-License-Identifier: LGPL-2.1-or-later
"""Command catalog and command service (studio.services.commands), ADR 0007 / PLAN 2.3.

The shell shows catalog entries and runs them through the service, which loads a command's
workbench on first use and then runs the real FreeCAD command. FreeCAD's GUI is behind the
CommandBackend interface (the shell implements it), so these tests use a fake that records calls.
"""

import unittest

from studio.services.commands import CommandBackend, CommandCatalog, CommandService

CATALOG = {
    "freecad": "27.1.0",
    "workbenches": [
        {"name": "SketcherWorkbench", "class": "SketcherGui::Workbench"},
        {"name": "PartDesignWorkbench", "class": "PartDesignGui::Workbench"},
    ],
    "commands": [
        {"name": "Std_Undo", "workbench": None, "menu_text": "&Undo", "tooltip": "Undo",
         "shortcut": "Ctrl+Z", "icon": "src/Gui/Icons/edit-undo.svg"},
        {"name": "Sketcher_NewSketch", "workbench": "SketcherWorkbench", "menu_text": "New Sketch",
         "tooltip": "Creates a new sketch", "shortcut": "", "icon": None},
        {"name": "PartDesign_Pad", "workbench": "PartDesignWorkbench", "menu_text": "Pad",
         "tooltip": "Extrudes a sketch", "shortcut": "", "icon": None},
        {"name": "PartDesign_Pocket", "workbench": "PartDesignWorkbench", "menu_text": "Pocket",
         "tooltip": "Cuts a sketch", "shortcut": "", "icon": None},
    ],
}


class FakeBackend(CommandBackend):
    def __init__(self, failing=()):
        self.calls = []
        self.failing = set(failing)

    def load_workbench(self, name):
        self.calls.append(("load", name))
        if name in self.failing:
            raise RuntimeError(f"cannot load {name}")

    def run(self, command):
        self.calls.append(("run", command))


class Catalog(unittest.TestCase):
    def setUp(self):
        self.catalog = CommandCatalog(CATALOG)

    def test_lookup_by_name(self):
        pad = self.catalog.get("PartDesign_Pad")
        self.assertEqual((pad.name, pad.workbench, pad.menu_text, pad.tooltip),
                         ("PartDesign_Pad", "PartDesignWorkbench", "Pad", "Extrudes a sketch"))

    def test_unknown_command_is_a_key_error(self):
        with self.assertRaises(KeyError):
            self.catalog.get("PartDesign_Teleport")

    def test_all_commands_and_workbenches_in_catalog_order(self):
        self.assertEqual([c.name for c in self.catalog.commands()],
                         ["Std_Undo", "Sketcher_NewSketch", "PartDesign_Pad", "PartDesign_Pocket"])
        self.assertEqual(self.catalog.workbenches(), ["SketcherWorkbench", "PartDesignWorkbench"])

    def test_commands_naming_an_unknown_workbench_are_refused(self):
        broken = dict(CATALOG, commands=CATALOG["commands"] + [
            {"name": "X_Y", "workbench": "NoSuchWorkbench", "menu_text": "", "tooltip": "",
             "shortcut": "", "icon": None}])
        with self.assertRaises(ValueError):
            CommandCatalog(broken)


class ShippedCatalog(unittest.TestCase):
    """The catalog generated from the build (tools/studio/generate_command_catalog.py)."""

    def test_is_installed_with_studio_and_loads(self):
        catalog = CommandCatalog.load()
        self.assertGreater(len(catalog.commands()), 500)
        self.assertIsNone(catalog.get("Std_Undo").workbench)
        self.assertEqual(catalog.get("PartDesign_Pad").workbench, "PartDesignWorkbench")
        self.assertEqual(catalog.get("Part_Box").workbench, "PartWorkbench")
        self.assertIn("CAMWorkbench", catalog.workbenches())


class Service(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.service = CommandService(CommandCatalog(CATALOG), self.backend)

    def test_command_available_from_startup_runs_without_loading_anything(self):
        self.service.run("Std_Undo")
        self.assertEqual(self.backend.calls, [("run", "Std_Undo")])

    def test_first_use_loads_the_owning_workbench_then_runs(self):
        self.service.run("PartDesign_Pad")
        self.assertEqual(self.backend.calls, [("load", "PartDesignWorkbench"), ("run", "PartDesign_Pad")])
        self.assertTrue(self.service.is_loaded("PartDesignWorkbench"))

    def test_a_workbench_is_loaded_only_once(self):
        self.service.run("PartDesign_Pad")
        self.service.run("PartDesign_Pocket")
        self.service.run("PartDesign_Pad")
        self.assertEqual([c for c in self.backend.calls if c[0] == "load"], [("load", "PartDesignWorkbench")])

    def test_unknown_command_is_refused_before_touching_freecad(self):
        with self.assertRaises(KeyError):
            self.service.run("PartDesign_Teleport")
        self.assertEqual(self.backend.calls, [])

    def test_failed_load_does_not_run_and_is_retried_next_time(self):
        backend = FakeBackend(failing={"SketcherWorkbench"})
        service = CommandService(CommandCatalog(CATALOG), backend)
        with self.assertRaises(RuntimeError):
            service.run("Sketcher_NewSketch")
        self.assertFalse(service.is_loaded("SketcherWorkbench"))
        backend.failing.clear()
        service.run("Sketcher_NewSketch")
        self.assertEqual(backend.calls, [("load", "SketcherWorkbench"), ("load", "SketcherWorkbench"),
                                         ("run", "Sketcher_NewSketch")])

    def test_ensure_loaded_is_idempotent_and_checks_the_name(self):
        self.service.ensure_loaded("SketcherWorkbench")
        self.service.ensure_loaded("SketcherWorkbench")
        self.assertEqual(self.backend.calls, [("load", "SketcherWorkbench")])
        with self.assertRaises(KeyError):
            self.service.ensure_loaded("NoSuchWorkbench")


if __name__ == "__main__":
    unittest.main()
