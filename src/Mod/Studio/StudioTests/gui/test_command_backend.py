# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loading a workbench's commands without switching to it, and running commands through the
command service (docs/adr/0007-lazy-loading-command-catalog.md, PLAN 2.3).

Each test uses a different workbench and first checks it isn't loaded yet, so the tests don't
depend on their order and can't pass because something else loaded the workbench.
"""

import unittest

import FreeCAD
import FreeCADGui
from PySide import QtWidgets  # FreeCAD's PySide shim

from studio.services.commands import CommandCatalog, CommandService
from studio.shell.backend import FreeCADCommandBackend


def registered(command):
    return FreeCADGui.Command.get(command) is not None


def settle():
    """Let pending GUI events run. Closing a document while the window a command just opened
    still has events pending makes FreeCAD hit an access violation (docs/BASELINE.md)."""
    for _ in range(5):
        QtWidgets.QApplication.processEvents()


class WorkbenchLoadingTest(unittest.TestCase):
    def setUp(self):
        import StudioGui  # Studio's C++ helper

        self.helper = StudioGui
        self.active = FreeCADGui.activeWorkbench().name()

    def assert_still_active(self):
        self.assertEqual(FreeCADGui.activeWorkbench().name(), self.active, "switched workbench")

    def test_cpp_workbench_commands_appear_without_switching(self):
        self.assertFalse(registered("Sketcher_NewSketch"), "precondition: Sketcher not loaded yet")
        self.assertTrue(self.helper.initialize_workbench("SketcherWorkbench"))
        self.assertTrue(registered("Sketcher_NewSketch"))
        self.assert_still_active()

    def test_python_workbench_commands_appear_without_switching(self):
        # Python workbenches need FreeCAD's C++ workbench object before Initialize() can run
        # (appendToolbar); only activateWorkbench() creates it, so this is what the helper is for.
        self.assertFalse(registered("Assembly_CreateAssembly"), "precondition: Assembly not loaded yet")
        self.assertTrue(self.helper.initialize_workbench("AssemblyWorkbench"))
        self.assertTrue(registered("Assembly_CreateAssembly"))
        self.assert_still_active()

    def test_second_call_does_nothing(self):
        self.helper.initialize_workbench("PartWorkbench")
        self.assertFalse(self.helper.initialize_workbench("PartWorkbench"))

    def test_switching_to_it_later_does_not_initialize_it_again(self):
        handler = FreeCADGui.getWorkbench("TechDrawWorkbench")
        self.assertFalse(hasattr(handler, "__Workbench__"), "precondition: TechDraw not loaded yet")
        calls = []
        original = handler.Initialize
        handler.Initialize = lambda: (calls.append(1), original())[1]
        self.addCleanup(FreeCADGui.activateWorkbench, self.active)

        self.helper.initialize_workbench("TechDrawWorkbench")
        FreeCADGui.activateWorkbench("TechDrawWorkbench")

        self.assertEqual(FreeCADGui.activeWorkbench().name(), "TechDrawWorkbench")
        self.assertEqual(len(calls), 1, "Initialize() ran again when FreeCAD switched to the workbench")

    def test_unknown_workbench_is_an_error(self):
        with self.assertRaises(Exception):
            self.helper.initialize_workbench("NoSuchWorkbench")


class CommandServiceInTheAppTest(unittest.TestCase):
    def test_first_use_loads_the_workbench_and_runs_the_real_command(self):
        self.assertFalse(registered("Spreadsheet_CreateSheet"), "precondition: Spreadsheet not loaded yet")
        doc = FreeCAD.newDocument("StudioCommandServiceTest")
        self.addCleanup(settle)
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        self.addCleanup(settle)  # cleanups run last-in first-out: settle, close, settle
        service = CommandService(CommandCatalog.load(), FreeCADCommandBackend())

        service.run("Spreadsheet_CreateSheet")

        self.assertTrue(service.is_loaded("SpreadsheetWorkbench"))
        self.assertEqual([o.TypeId for o in doc.Objects], ["Spreadsheet::Sheet"])
