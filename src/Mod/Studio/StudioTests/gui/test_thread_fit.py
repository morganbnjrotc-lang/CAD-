# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar's Fit box in the app (PLAN 3.9, the allowance scrubber; studio.shell.thread_fit).

A threaded hole picked in the model tree shows Fit on the toolbar; scrolling over it loosens or tightens
the hole a step at a time (one undo step for a run of scrolls), and a value can be typed. The tests
scroll and type as the user does, with synthetic events.
"""

from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim
import FreeCADGui
import StudioGui

from StudioTests.gui.sketch_input import settle
from StudioTests.test_threads import TAP_DRILL, ThreadedPart
from studio.services import threads
from studio.shell import thread_fit, window
from studio.viewmodels.thread_fit import FitBox

Qt = QtCore.Qt


class ThreadFit(ThreadedPart):
    def setUp(self):
        super().setUp()
        self.addCleanup(FreeCADGui.Selection.clearSelection)
        settle(100)

    def pick(self, *objects):
        FreeCADGui.Selection.clearSelection()
        for o in objects:
            FreeCADGui.Selection.addSelection(o)
        settle(100)
        window.current().refresh()

    def box(self):
        return window.current().tool_box("StudioFit")

    def field(self):
        return self.box().findChild(QtWidgets.QLineEdit, "StudioFitBox")

    def scroll(self, notches):
        """Scroll notches over the box, without clicking it first (the pointer just over it)."""
        spin = self.field()
        at = QtCore.QPointF(spin.rect().center())
        for _ in range(abs(notches)):
            event = QtGui.QWheelEvent(at, spin.mapToGlobal(at), QtCore.QPoint(0, 0),
                                      QtCore.QPoint(0, 120 if notches > 0 else -120), Qt.NoButton,
                                      Qt.NoModifier, Qt.NoScrollPhase, False)
            QtWidgets.QApplication.sendEvent(spin, event)
            settle(30)

    @staticmethod
    def step_mm():
        rules = FitBox(thread_fit.units_shown())
        return rules.mm(rules.step)

    def test_a_threaded_hole_shows_fit(self):
        self.pick(self.hole)
        self.assertIsNotNone(self.box(), "no Fit box on the toolbar")
        self.assertEqual(self.field().text(), FitBox(thread_fit.units_shown()).text(0))

    def test_a_hole_without_a_thread_shows_no_fit(self):
        self.hole.Threaded = False
        self.doc.recompute()
        self.pick(self.hole)
        self.assertIsNone(self.box())

    def test_scrolling_up_loosens_the_hole(self):
        self.pick(self.hole)
        self.scroll(2)
        self.assertAlmostEqual(threads.fit(self.hole), 2 * self.step_mm(), places=6)
        self.assertAlmostEqual(self.hole.Diameter.Value, TAP_DRILL + 2 * self.step_mm(), places=6)

    def test_scrolling_down_tightens_it(self):
        self.pick(self.hole)
        self.scroll(-1)
        self.assertAlmostEqual(threads.fit(self.hole), -self.step_mm(), places=6)

    def test_a_run_of_scrolls_is_one_undo_step(self):
        undo = self.doc.UndoCount
        self.pick(self.hole)
        self.scroll(3)
        settle(thread_fit.QUIET_MS + 300)
        self.assertEqual(self.doc.UndoCount, undo + 1)
        self.doc.undo()
        self.doc.recompute()
        self.assertEqual(threads.fit(self.hole), 0)
        self.assertAlmostEqual(self.hole.Diameter.Value, TAP_DRILL)

    def test_a_typed_fit(self):
        self.pick(self.hole)
        field = self.field()
        field.setFocus()
        field.selectAll()
        shown = FitBox(thread_fit.units_shown())
        StudioGui.type_keys(f"{2 * shown.step:.{shown.decimals}f}{{Return}}")
        settle(150)
        self.assertAlmostEqual(threads.fit(self.hole), shown.mm(2 * shown.step), places=6)

    def test_the_box_follows_an_undo(self):
        self.pick(self.hole)
        self.scroll(1)
        settle(thread_fit.QUIET_MS + 300)
        self.doc.undo()
        settle(window.StudioWindow.ENABLE_CHECK_MS + 200)
        self.assertEqual(self.field().text(), FitBox(thread_fit.units_shown()).text(0))
