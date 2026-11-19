# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keep the app in Studio's one environment (docs/adr/0009).

FreeCAD switches workbench by itself in a few places. The most common: editing a sketch activates
the sketch's `EditingWorkbench` (SketcherWorkbench) through Show.TempoVis and switches back when the
editing ends. Studio doesn't need that: the sketch editor, its task panel and its context menu work
in any workbench, and Studio's toolbar, keymap and palette provide the tools.

- While Studio is active, TempoVis's workbench step is skipped, so editing a sketch stays in Studio.
  (Setting each sketch's EditingWorkbench to "" would also work, but changes the document, which
  would then ask to be saved.)
- While Studio is active, a switch asked for from Python (`FreeCADGui.activateWorkbench`) doesn't
  happen: the workbench's commands are loaded instead, which is what the switch was for. Part Design
  asks for its workbench each time one of its panels opens (Extrude's included, through
  `Command::assureWorkbench`), and the switch there and back took the window out of maximized.
  `switch_workbench` still makes FreeCAD's own switch, for tests.
- Any other switch (FreeCAD's C++ code switching directly) is undone right after it: Studio comes back.
"""

import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

STUDIO = "StudioWorkbench"
_installed = False
_freecad_activate = None  # FreeCAD's own switch, once Studio's is installed


def _studio_active() -> bool:
    active = FreeCADGui.activeWorkbench()
    return active is not None and active.name() == STUDIO


def switch_workbench(name):
    """FreeCAD's own switch, even while Studio is active (Studio then comes back right after it)."""
    return (_freecad_activate or FreeCADGui.activateWorkbench)(name)


def _activate_workbench(name, *args):
    """FreeCADGui.activateWorkbench while Studio's environment is installed."""
    if name == STUDIO or not _studio_active() or name not in FreeCADGui.listWorkbenches():
        return _freecad_activate(name, *args)
    import StudioGui  # Studio's C++ helpers

    StudioGui.initialize_workbench(name)  # its commands, without switching to it
    return False  # Studio stays: no switch happened


def install_once():
    """Stops editing a sketch, Part Design's panels and macros from leaving Studio (once)."""
    global _installed, _freecad_activate
    if _installed:
        return
    _installed = True
    _freecad_activate = FreeCADGui.activateWorkbench
    from Show.SceneDetails.Workbench import Workbench

    original = Workbench.apply_data

    def apply_data(self, value):
        if value != STUDIO and _studio_active():
            return  # stay in Studio's one environment
        original(self, value)

    Workbench.apply_data = apply_data
    FreeCADGui.activateWorkbench = _activate_workbench


def schedule_return():
    """Studio was just deactivated: come back once the switch is done (not while closing)."""
    QtCore.QTimer.singleShot(0, _return_to_studio)


def _return_to_studio():
    app = QtWidgets.QApplication.instance()
    main = FreeCADGui.getMainWindow()
    if app is None or app.closingDown() or main is None or not main.isVisible() or _studio_active():
        return
    switch_workbench(STUDIO)
