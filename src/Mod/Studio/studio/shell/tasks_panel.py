# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keeps FreeCAD's Tasks panel medium-sized at the right of the 3D view (PLAN 3.10).

The size comes from studio.services.tasks_panel; here it follows the room in the main area: once Studio is
active, shortly after the window stops changing size (FreeCAD lays its floating panels out again each
time one of their settings changes, so not on every step of a drag), and when documents open or close
(the documents' tab bar, which FreeCAD's layout counts, appears with the first one).
"""

import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

from studio.services.tasks_panel import FreeCADTasksPanel

SETTLE_MS = 250  # after the last resize


class _Follow(QtCore.QObject):
    """Watches the main window's size (the main window is the one FreeCAD widget Python may hold)."""

    def __init__(self, main, panel):
        super().__init__(main)
        self._main, self._panel = main, panel
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SETTLE_MS)
        self._timer.timeout.connect(self.apply)
        main.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._main and event.type() == QtCore.QEvent.Resize:
            self._timer.start()
        return False

    # FreeCADGui document observer
    def slotCreatedDocument(self, document):
        self._timer.start()

    def slotDeletedDocument(self, document):
        self._timer.start()

    def slotActivateDocument(self, document):
        self._timer.start()

    def apply(self):
        import StudioGui  # Studio's C++ helpers

        area_height, cube = StudioGui.tasks_room()
        if area_height > 0:
            self._panel.apply(area_height, cube)


_follow = None


def install_once():
    global _follow
    if _follow is None:
        _follow = _Follow(FreeCADGui.getMainWindow(), FreeCADTasksPanel())
        FreeCADGui.addDocumentObserver(_follow)
        QtCore.QTimer.singleShot(0, _follow.apply)
