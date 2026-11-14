# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loads workbenches in the background after startup (ADR 0007, decision 3).

`start_once()` is called when Studio's workbench first activates. A second after that, when
startup work is done, it loads the planned workbenches (studio.services.warmup) one per timer
tick, so user input queued in between is handled between loads, and waits while a mouse button
is held (the user is orbiting or dragging).
"""

import FreeCAD
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

from studio.services.warmup import warmup_plan

START_DELAY_MS = 1000  # after the start workbench activates: let startup finish first
STEP_MS = 50  # between workbenches


def _mouse_button_held() -> bool:
    return QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton


class WarmUp:
    def __init__(self, service, plan, step_ms=STEP_MS, user_busy=_mouse_button_held):
        self._service = service
        self.planned = list(plan)
        self._remaining = list(plan)
        self._step_ms = step_ms
        self._user_busy = user_busy
        self.loaded, self.failed, self.done = [], [], False

    def start(self, delay_ms=START_DELAY_MS):
        QtCore.QTimer.singleShot(delay_ms, self._step)

    def _step(self):
        if not self._remaining:
            self.done = True
            return
        if not self._user_busy():
            name = self._remaining.pop(0)
            try:
                self._service.ensure_loaded(name)
                self.loaded.append(name)
            except Exception as exc:  # a broken module must not stop the others
                self.failed.append(name)
                FreeCAD.Console.PrintWarning(f"Studio warm-up: could not load {name}: {exc}\n")
        QtCore.QTimer.singleShot(self._step_ms, self._step)


_current = None
_scheduled = False


def start_once(delay_ms=START_DELAY_MS):
    """Schedules the session's warm-up (once). The catalog and plan are read when it starts, not
    now: this runs during startup."""
    global _scheduled
    if not _scheduled:
        _scheduled = True
        QtCore.QTimer.singleShot(delay_ms, _begin)


def _begin():
    global _current
    from studio.shell import app

    service = app.command_service()
    _current = WarmUp(service, warmup_plan(service, app.settings()))
    _current.start(delay_ms=0)


def current():
    """The session's running or finished warm-up; None before it has begun."""
    return _current
