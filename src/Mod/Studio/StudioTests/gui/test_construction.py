# SPDX-License-Identifier: LGPL-2.1-or-later
"""Construction geometry while sketching (PLAN 3.13): the user asked for "a way to activate construction
geometry". The Construction button on the sketch toolbar, or X as in Fusion: with sketch geometry selected
it switches that geometry to or from construction; with nothing selected it switches what gets drawn next,
also in the middle of a shape, and the button stays lit while construction is on.
"""

import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

import StudioGui
from StudioTests.gui.sketch_input import SketchInput, settle
from StudioTests.gui.test_shortcuts import press
from studio.shell import window


class Construction(SketchInput):
    def setUp(self):
        super().setUp()
        settle(200)  # the toolbar follows the sketch being edited

    def button(self):
        action = next((a for a in window.current().tools.actions() if a.data() == "Studio_Construction"), None)
        self.assertIsNotNone(action, "no Construction button on the sketch toolbar")
        return action

    def assertLit(self, lit):
        settle(150)  # the toolbar follows the mode
        self.assertEqual(StudioGui.construction_mode(), lit)
        self.assertTrue(self.button().isCheckable())
        self.assertEqual(self.button().isChecked(), lit)

    def press_x(self):
        """X with no tool running: the key goes to the 3D view (a plain widget of the window stands in)."""
        view = QtWidgets.QWidget(FreeCADGui.getMainWindow())
        self.addCleanup(view.deleteLater)
        self.assertTrue(press(view, QtCore.Qt.Key_X, text="x"), "Studio didn't take X while sketching")
        settle(150)

    def construction(self):
        return [self.sketch.getConstruction(i) for i in range(len(self.sketch.Geometry))]

    def test_the_button_switches_construction_on_and_off(self):
        self.assertLit(False)
        self.button().trigger()
        self.assertLit(True)
        self.button().trigger()
        self.assertLit(False)

    def test_x_draws_construction_until_pressed_again(self):
        self.press_x()
        self.assertLit(True)
        self.line((0, 0), (2, 0))
        self.press_x()
        self.assertLit(False)
        self.line((0, 1), (2, 1))
        self.assertEqual(self.construction(), [True, False])

    def test_x_in_the_middle_of_a_line_makes_it_construction(self):
        # The line's size boxes have the keys after the first click; FreeCAD passes letter keys from them
        # to the 3D view (DrawSketchKeyboardManager) until a number is typed, so X still reaches Studio.
        self.tool("Sketcher_CreateLine")
        self.click(0, 0)
        focus = StudioGui.focus_widget()
        self.assertTrue(focus is not None and focus[1], f"precondition: a size box has the keys ({focus})")
        self.type("X")
        self.click(2, 1)
        self.finish()
        self.assertEqual(self.construction(), [True])
        self.assertLit(True)

    def test_x_with_geometry_selected_switches_that_geometry(self):
        self.line((0, 0), (2, 0))
        self.line((0, 1), (2, 1))
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, "Edge2")
        self.press_x()
        self.assertEqual(self.construction(), [False, True])
        self.assertLit(False)  # what gets drawn next didn't change
