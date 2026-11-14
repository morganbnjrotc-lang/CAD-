# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's main window (studio.shell.window), docs/adr/0009, layout A.

Checks the session's window, set up when Studio's workbench activates. Real selections use a
Part box (faces and edges); kinds that need other modules (sketches, editing) are shown through
`show_tools_for`, so these tests don't load Sketcher before other tests check it isn't loaded.
"""

import unittest

import FreeCAD
import FreeCADGui
from PySide import QtWidgets  # FreeCAD's PySide shim

from studio.viewmodels.context_toolbar import Selected

from .test_shortcuts import settle

FREECAD_TOOLBARS = ("File", "Edit", "Clipboard", "Workbench", "Macro", "View", "Individual Views",
                    "Structure", "Help")


def session_window():
    from studio.shell import window

    return window.current()


def labels():
    return [a.text() for a in session_window().tools.actions() if not a.isSeparator()]


class Chrome(unittest.TestCase):
    def test_studio_set_the_window_up_when_it_activated(self):
        self.assertIsNotNone(session_window(), "not set up when Studio activated")

    def test_freecads_toolbars_and_the_workbench_switcher_are_gone(self):
        main = FreeCADGui.getMainWindow()
        shown = {bar.objectName() for bar in main.findChildren(QtWidgets.QToolBar) if bar.isVisible()}
        self.assertFalse(shown & set(FREECAD_TOOLBARS), shown)
        self.assertEqual(FreeCADGui.getWorkbench("StudioWorkbench").listToolbars(), [])

    def test_one_menu_button_holds_file_edit_view_and_help(self):
        self.assertFalse(FreeCADGui.getMainWindow().menuBar().isVisible())
        self.assertEqual(session_window().menu_titles(), ["File", "Edit", "View", "Help"])

    def test_top_bar_and_toolbar_are_shown(self):
        window = session_window()
        self.assertTrue(window.top_bar.isVisible())
        self.assertTrue(window.tools.isVisible())
        self.assertIn("Search", window.search_button.text())

    def test_the_panel_button_closes_and_opens_the_model_panel(self):
        window = session_window()
        model = window.model_panel()
        self.assertIsNotNone(model)
        self.assertTrue(model.isVisible())
        window.panel_button.click()
        settle()
        self.assertFalse(model.isVisible())
        window.panel_button.click()
        settle()
        self.assertTrue(model.isVisible())


class OneEnvironment(unittest.TestCase):
    """Found by hand (2026-11-14): editing a sketch switched to FreeCAD's Sketcher workbench and
    its old window (workbench dropdown, toolbars, menu bar) came back."""

    def test_editing_a_sketch_stays_in_studio_with_sketch_tools(self):
        doc = FreeCAD.newDocument("StudioSketchEditTest")
        self.addCleanup(settle)
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
        doc.recompute()
        settle()

        FreeCADGui.ActiveDocument.setEdit(sketch.Name)
        settle()
        self.addCleanup(lambda: FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.resetEdit())

        self.assertEqual(FreeCADGui.activeWorkbench().name(), "StudioWorkbench")
        self.assertTrue(session_window().top_bar.isVisible())
        self.assertFalse(FreeCADGui.getMainWindow().menuBar().isVisible())
        self.assertEqual(labels()[0], "Line")

        FreeCADGui.ActiveDocument.resetEdit()
        settle()
        self.assertEqual(FreeCADGui.activeWorkbench().name(), "StudioWorkbench")
        # FreeCAD leaves the sketch selected after editing, so the next step is offered: Extrude.
        self.assertEqual([o.Name for o in FreeCADGui.Selection.getSelection()], ["Sketch"])
        self.assertEqual(labels()[0], "Extrude")

    def test_a_switch_from_elsewhere_comes_back_to_studio(self):
        FreeCADGui.activateWorkbench("PartWorkbench")  # e.g. a macro or FreeCAD's Start page
        settle()
        settle()
        self.assertEqual(FreeCADGui.activeWorkbench().name(), "StudioWorkbench")
        self.assertTrue(session_window().top_bar.isVisible())
        self.assertFalse(FreeCADGui.getMainWindow().menuBar().isVisible())


class FollowsSelection(unittest.TestCase):
    def setUp(self):
        self.addCleanup(lambda: (FreeCADGui.Selection.clearSelection(), settle(), session_window().refresh()))

    def test_each_kind_of_selection_shows_its_tools(self):
        window = session_window()
        window.show_tools_for([Selected("Sketcher::SketchObject")], None)
        self.assertEqual(labels(), ["Extrude", "Cut", "Revolve", "Hole", "Edit Sketch"])
        window.show_tools_for([], "Sketcher::SketchObject")
        self.assertEqual(labels(), ["Line", "Rectangle", "Circle", "Arc", "Dimension", "Close Sketch"])
        window.show_tools_for([], None)
        self.assertEqual(labels(), ["New Sketch", "New Body", "Import", "Measure", "Search"])

    def test_selecting_faces_and_edges_of_a_real_model(self):
        doc = FreeCAD.newDocument("StudioWindowTest")
        self.addCleanup(settle)
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        box = doc.addObject("Part::Box", "Box")
        doc.recompute()
        settle()

        FreeCADGui.Selection.addSelection(doc.Name, box.Name, "Face1")
        settle()
        self.assertEqual(labels()[:3], ["Sketch on Face", "Fillet", "Chamfer"])
        self.assertIn("face", session_window().hint.text())

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(doc.Name, box.Name, "Edge1")
        settle()
        self.assertEqual(labels(), ["Fillet", "Chamfer", "Measure", "Fit Selection"])

        FreeCADGui.Selection.clearSelection()
        settle()
        self.assertEqual(labels()[0], "New Sketch")
        self.assertIn("search every tool", session_window().hint.text())

    def test_buttons_show_shortcut_and_freecads_name_and_run_through_the_command_service(self):
        from studio.shell import app

        window = session_window()
        window.show_tools_for([Selected("Sketcher::SketchObject")], None)
        extrude = window.tools.actions()[0]
        self.assertIn("(E)", extrude.toolTip())
        self.assertIn("FreeCAD: Pad", extrude.toolTip())
        self.assertFalse(extrude.icon().isNull())

        service = app.command_service()
        ran = []
        service.run = ran.append
        self.addCleanup(delattr, service, "run")
        extrude.trigger()
        settle()
        self.assertEqual(ran, ["PartDesign_Pad"])
