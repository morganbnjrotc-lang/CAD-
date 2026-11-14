# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keep the app in Studio's one environment (docs/adr/0009).

FreeCAD switches workbench by itself in a few places. The most common: editing a sketch activates
the sketch's `EditingWorkbench` (SketcherWorkbench) through Show.TempoVis and switches back when the
editing ends. Studio doesn't need that: the sketch editor, its task panel and its context menu work
in any workbench, and Studio's toolbar, keymap and palette provide the tools.

- While Studio is active, TempoVis's workbench step is skipped, so editing a sketch stays in Studio.
  (Setting each sketch's EditingWorkbench to "" would also work, but changes the document, which
  would then ask to be saved.)
- Any other switch (a macro, FreeCAD's Start page) is undone right after it: Studio comes back.
"""

import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

STUDIO = "StudioWorkbench"
_installed = False


def _studio_active() -> bool:
    active = FreeCADGui.activeWorkbench()
    return active is not None and active.name() == STUDIO


def install_once():
    """Stops editing a sketch from leaving Studio (patches Show's workbench step, once)."""
    global _installed
    if _installed:
        return
    _installed = True
    from Show.SceneDetails.Workbench import Workbench

    original = Workbench.apply_data

    def apply_data(self, value):
        if value != STUDIO and _studio_active():
            return  # stay in Studio's one environment
        original(self, value)

    Workbench.apply_data = apply_data


def schedule_return():
    """Studio was just deactivated: come back once the switch is done (not while closing)."""
    QtCore.QTimer.singleShot(0, _return_to_studio)


def _return_to_studio():
    app = QtWidgets.QApplication.instance()
    main = FreeCADGui.getMainWindow()
    if app is None or app.closingDown() or main is None or not main.isVisible() or _studio_active():
        return
    FreeCADGui.activateWorkbench(STUDIO)
