# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's tool groups on the top bar and pinned tools, in the app (PLAN 3.17; studio.shell.tool_groups).

The top bar reads ☰ · Panel · Create Modify Construct Inspect Insert · Display … Search tools; while a sketch is
edited the groups are Create Modify Constrain Inspect. Picking a tool runs it through the command service;
right-clicking it pins it to the toolbar for the kind of selection there is; right-clicking the pinned
button unpins it. Kinds that need other modules (sketches) are shown through `show_tools_for`, and commands
are caught before they run, so these tests load neither Sketcher nor Part Design.
"""

import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

import StudioGui
from studio.viewmodels.context_toolbar import TOOLS
from studio.viewmodels.tool_groups import ToolGroups

from .sketch_input import settle

SKETCH = "Sketcher::SketchObject"


def session_window():
    from studio.shell import window

    return window.current()


def toolbar_labels():
    return [a.text() for a in session_window().tools.actions() if not a.isSeparator()]


class ToolGroupsBar(unittest.TestCase):
    def setUp(self):
        from studio.shell import app, tool_groups

        self.window = session_window()
        self.bar = tool_groups.current()
        self.assertIsNotNone(self.bar, "the tool groups weren't set up when Studio activated")
        settings = app.settings()
        pins = {kind: settings.get(ToolGroups.pins_setting(kind)) for kind in TOOLS}
        self.addCleanup(lambda: [settings.set(ToolGroups.pins_setting(k), v) for k, v in pins.items()])
        self.addCleanup(lambda: (FreeCADGui.Selection.clearSelection(), settle(), self.window.refresh()))
        self.addCleanup(StudioGui.close_popups)  # a menu left open would keep FreeCAD from quitting
        service = app.command_service()
        self.ran = []
        service.run = lambda *command: self.ran.append(command)
        self.addCleanup(delattr, service, "run")
        self.window.show_tools_for([], None)

    # -- helpers ---------------------------------------------------------------------------------
    def top_bar(self):
        """What the top bar shows, in order: button texts, "|" for a separator."""
        names = []
        for action in self.window.top_bar.actions():
            if not action.isVisible():
                continue
            if action.isSeparator():
                names.append("|")
                continue
            widget = self.window.top_bar.widgetForAction(action)
            text = widget.text() if hasattr(widget, "text") else ""
            if text:
                names.append(text)
        return names

    def button(self, label):
        return next(b for b in self.bar.buttons if b.text() == label)

    def filled(self, label):
        """The group's menu, filled as when it opens."""
        menu = self.button(label).menu()
        menu.aboutToShow.emit()
        return menu

    @staticmethod
    def item(menu, label):
        return next(a for a in menu.actions() if a.text().split("\t")[0] == label)

    def while_open(self, label, *steps):
        """Opens the group's menu as a click does, and runs each step 300 ms after the one before, the first
        one with the menu open."""
        def run(n):
            if n < len(steps):
                steps[n]()
                QtCore.QTimer.singleShot(300, lambda: run(n + 1))
            else:
                StudioGui.close_popups()

        QtCore.QTimer.singleShot(300, lambda: run(0))
        self.button(label).showMenu()
        settle(300 * (len(steps) + 2))

    @staticmethod
    def right_click_item(label):
        """A right-click on the open menu's item."""
        menu = QtWidgets.QApplication.activePopupWidget()
        action = next(a for a in menu.actions() if a.text().split("\t")[0] == label)
        pos = QtCore.QPointF(menu.actionGeometry(action).center())
        for kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
            event = QtGui.QMouseEvent(kind, pos, QtCore.QPointF(menu.mapToGlobal(pos.toPoint())),
                                      QtCore.Qt.RightButton, QtCore.Qt.RightButton, QtCore.Qt.NoModifier)
            QtWidgets.QApplication.sendEvent(menu, event)

    # -- the groups --------------------------------------------------------------------------------
    def test_the_top_bar_reads_like_fusions(self):
        self.assertEqual(self.top_bar(), ["☰", "Panel", "|", "Create", "Modify", "Construct", "Inspect", "Insert",
                                          "|", "Display", "Search tools"])

    def test_while_sketching_the_sketchs_groups(self):
        self.window.show_tools_for([], SKETCH)
        self.assertEqual(self.bar.labels(), ["Create", "Modify", "Constrain", "Inspect"])
        self.assertEqual(self.filled("Create").actions()[0].text(), "Line")  # a side menu of its ways
        self.window.show_tools_for([], None)
        self.assertEqual(self.bar.labels(), ["Create", "Modify", "Construct", "Inspect", "Insert"])

    def test_a_group_lists_its_tools_with_icons_and_keys(self):
        seen = []
        self.while_open("Create", lambda: seen.append(StudioGui.popup_menu()))
        self.assertTrue(seen and seen[0], "the Create menu didn't open")
        self.assertEqual(seen[0][:3], ["New Sketch", "Extrude\tE", "Revolve"])
        self.assertIn("Primitive", seen[0])
        self.assertFalse(self.item(self.filled("Create"), "Extrude").icon().isNull())

    def test_picking_a_tool_runs_it(self):
        doc = FreeCAD.newDocument("StudioGroups")  # Section is grayed without one
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        settle(200)
        picked = []
        self.while_open("Inspect", lambda: picked.append(StudioGui.choose_popup("Section")))
        self.assertEqual(picked, [True], "no enabled Section in the Inspect menu")
        self.assertEqual(self.ran, [("Studio_Section",)])

    def test_a_primitive_runs_its_item(self):
        primitive = self.item(self.filled("Create"), "Primitive").menu()
        self.item(primitive, "Cylinder").trigger()
        settle()
        self.assertEqual(self.ran, [("PartDesign_CompPrimitiveAdditive", 1)])

    def test_a_tool_that_cant_run_now_is_grayed(self):
        # FreeCAD says both can run (the sketch here is only shown as being edited: once Sketcher has
        # loaded, FreeCAD itself grays its tools without a real one); Move waits for a selection
        is_active = self.window._is_active
        self.window._is_active = lambda command: True
        self.addCleanup(setattr, self.window, "_is_active", is_active)
        self.window.show_tools_for([], SKETCH)  # nothing in the sketch selected
        self.assertFalse(self.item(self.filled("Modify"), "Move").isEnabled())
        self.assertTrue(self.item(self.filled("Modify"), "Trim").isEnabled())

    # -- pins --------------------------------------------------------------------------------------
    def test_right_click_pins_a_tool_for_this_selection_and_again_unpins_it(self):
        seen = []
        self.while_open("Modify", lambda: self.right_click_item("Combine"),
                        lambda: (seen.append(StudioGui.popup_menu()),
                                 StudioGui.choose_popup("Pin to toolbar when nothing is selected")))
        self.assertEqual(seen, [["Pin to toolbar when nothing is selected"]])
        settle(200)
        self.assertEqual(toolbar_labels()[-1], "Combine")
        self.window.show_tools_for([], SKETCH)
        self.assertNotIn("Combine", toolbar_labels())  # pinned for nothing selected only
        self.window.show_tools_for([], None)

        seen.clear()
        self.while_open("Modify", lambda: self.right_click_item("Combine"),
                        lambda: (seen.append(StudioGui.popup_menu()),
                                 StudioGui.choose_popup("Unpin from toolbar when nothing is selected")))
        self.assertEqual(seen, [["Unpin from toolbar when nothing is selected"]])
        settle(200)
        self.assertNotIn("Combine", toolbar_labels())

    def test_a_right_click_doesnt_run_the_tool(self):
        self.while_open("Inspect", lambda: self.right_click_item("Section"))
        self.assertEqual(self.ran, [])

    def test_a_pinned_button_runs_its_tool_and_right_click_unpins_it(self):
        self.bar.pin("nothing", "PartDesign_CompPrimitiveAdditive#1")
        settle(200)
        self.assertEqual(toolbar_labels()[-1], "Cylinder")
        action = self.window.tools.actions()[-1]
        action.trigger()
        settle()
        self.assertEqual(self.ran, [("PartDesign_CompPrimitiveAdditive", 1)])

        seen = []
        widget = self.window.tools.widgetForAction(action)

        def choose():
            seen.append(StudioGui.popup_menu())
            StudioGui.choose_popup("Unpin from toolbar when nothing is selected")
            StudioGui.close_popups()

        QtCore.QTimer.singleShot(300, choose)
        widget.customContextMenuRequested.emit(QtCore.QPoint(5, 5))
        settle(600)
        self.assertEqual(seen, [["Unpin from toolbar when nothing is selected"]])
        self.assertNotIn("Cylinder", toolbar_labels())
