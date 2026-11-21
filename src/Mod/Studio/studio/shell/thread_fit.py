# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar's Fit box (PLAN 3.9, the allowance scrubber; the rules in studio.viewmodels.thread_fit).

A threaded hole picked in the model tree shows Fit on the toolbar, after Chamfer Hole: how much bigger
(+) or smaller (-) the hole is made than standard, for 3D-printed parts (studio.services.threads.fit).
Scrolling over it (or Up and Down in it) steps it and the hole follows straight away; a fit can be
typed too. A run of scrolls is one undo step: the step closes once the scrolling stops for QUIET_MS.
"""

import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

from studio.services import threads
from studio.viewmodels.thread_fit import FitBox

Qt = QtCore.Qt
QUIET_MS = 700


def units_shown():
    """"inches" or "millimeters": the user's units (studio.shell.units)."""
    from studio.shell import units

    current = units.current()
    return current.units if current is not None and current.units else "millimeters"


class _Scrub:
    """Changes in a row go in one undo step, closed QUIET_MS after the last."""

    def __init__(self):
        self._doc = None
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.finish)

    def is_open(self):
        return self._doc is not None

    def change(self, holes, mm):
        doc = holes[0].Document
        # A new run, another document, or the step closed under us (Ctrl+Z commits an open step first).
        if self._doc is not doc or not doc.HasPendingTransaction:
            self.finish()
            doc.openTransaction("Thread Fit")
            self._doc = doc
        threads.set_fit(holes, mm)
        self._timer.start(QUIET_MS)

    def finish(self):
        self._timer.stop()
        doc, self._doc = self._doc, None
        if doc is not None:
            try:
                doc.commitTransaction()
            except Exception:  # the document was closed meanwhile
                pass


_scrub = None


class _FitField(QtWidgets.QLineEdit):
    """The box. A plain text field that steps on the wheel itself: FreeCAD swallows wheel events on spin
    boxes without the keyboard focus (Gui::WheelEventFilter), and Fit should scroll on hover."""

    def __init__(self, owner, parent):
        super().__init__(parent)
        self._owner = owner
        self._remainder = 0  # a touchpad scrolls in fractions of a notch

    def wheelEvent(self, event):
        self._remainder += event.angleDelta().y()
        notches = int(self._remainder / 120)
        self._remainder -= notches * 120
        if notches:
            self._owner.step(notches)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self._owner.step(1 if event.key() == Qt.Key_Up else -1)
            event.accept()
            return
        if event.key() == Qt.Key_Escape:  # back to the hole's fit
            self._owner.show_fit()
            event.accept()
            return
        super().keyPressEvent(event)


class FitWidget(QtWidgets.QWidget):
    """The box with "Fit" under it, as the toolbar's buttons have their names under them."""

    def __init__(self, holes, rules, parent=None):
        super().__init__(parent)
        self.setObjectName("StudioFit")
        self._holes = holes
        self._rules = rules
        self._mm = threads.fit(holes[0])
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 0)
        layout.setSpacing(1)
        self.field = _FitField(self, self)
        self.field.setObjectName("StudioFitBox")
        self.field.setAlignment(Qt.AlignRight)
        self.field.setFixedWidth(96)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.field.setToolTip(rules.tooltip)
        self.field.editingFinished.connect(self._typed)  # Return, or clicking elsewhere
        label = QtWidgets.QLabel(rules.label, self)
        label.setAlignment(Qt.AlignHCenter)
        label.setToolTip(rules.tooltip)
        layout.addWidget(self.field)
        layout.addWidget(label)
        self.show_fit()

    def show_fit(self):
        self.field.setText(self._rules.text(self._mm))

    def step(self, notches):
        self._apply(self._rules.stepped(self._mm, notches))

    def _typed(self):
        if not self.field.isModified():
            return
        mm = self._rules.read(self.field.text())
        if mm is None or abs(mm - self._mm) < 1e-12:
            self.show_fit()  # not a fit, or the same: show the hole's again
            return
        self._apply(mm)

    def _apply(self, mm):
        self._mm = mm
        self.show_fit()
        try:
            _scrub.change(self._holes, mm)
        except Exception as exc:  # the holes were deleted meanwhile
            import FreeCAD

            FreeCAD.Console.PrintWarning(f"Studio: could not change the fit: {exc}\n")

    def sync(self):
        """Shows the hole's fit, e.g. after an undo; not while scrolling or typing."""
        if _scrub.is_open() or self.field.isModified():
            return
        try:
            mm = threads.fit(self._holes[0])
        except Exception:  # deleted
            return
        if abs(mm - self._mm) > 1e-9:
            self._mm = mm
            self.show_fit()


def make_box(parent):
    """The Fit box for the threaded holes selected, or None."""
    holes = threads.threaded(FreeCADGui.Selection.getSelection())
    if not holes:
        return None
    return FitWidget(holes, FitBox(units_shown()), parent)


def install_once():
    global _scrub
    if _scrub is None:
        from studio.shell import window

        _scrub = _Scrub()
        if window.current() is not None:
            window.current().add_tool_widget("hole", make_box)
    return _scrub
