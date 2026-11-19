# SPDX-License-Identifier: LGPL-2.1-or-later
"""Part Design's panels the Fusion way (PLAN 3.11).

Fillet and Chamfer open ready to pick: a click on an edge adds it, a second click takes it out.
FreeCAD opens them picking only when no edge was selected first; with one selected (Studio's toolbar
offers Fillet for a selected edge) its "Select" button had to be pressed before another click counted.
FreeCAD still stops picking when a size is typed, to show the result: "Select" picks again.
"""

import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

PICKING = {"PartDesign::Fillet", "PartDesign::Chamfer"}  # open ready to pick edges


class _EditObserver:
    """A FreeCADGui document observer: a picking panel just opened (the panel exists by then)."""

    def slotInEdit(self, view_provider):
        type_id = getattr(getattr(view_provider, "Object", None), "TypeId", "")
        if type_id in PICKING:
            QtCore.QTimer.singleShot(0, _start_picking)


def _start_picking():
    import StudioGui  # Studio's C++ helpers: Python wrappers of FreeCAD's panels abort at exit

    StudioGui.start_picking()


_observer = None


def install_once():
    global _observer
    if _observer is None:
        _observer = _EditObserver()
        FreeCADGui.addDocumentObserver(_observer)
