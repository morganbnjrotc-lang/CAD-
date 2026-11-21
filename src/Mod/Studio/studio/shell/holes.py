# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click hole chamfer in the app (PLAN 3.9; studio.services.holes finds the openings).

With a hole picked in the model tree, the toolbar's Chamfer Hole selects the hole's openings and runs
Part Design's own Chamfer on them, so its panel opens with the result shown, Finish keeps it and Cancel
takes it away. The size starts at a tenth of the hole's diameter, unless the user made Chamfer's size
their default (PLAN 3.6, right-click → Make Default).
"""

import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

from studio.services import holes

CHAMFER, SIZE_FIELD = "PartDesign::Chamfer", "chamferSize"


def selected_hole():
    for picked in FreeCADGui.Selection.getSelectionEx():
        if picked.Object.TypeId == "PartDesign::Hole" and not picked.SubElementNames:
            return picked.Object
    return None


def chamfer_selected():
    hole = selected_hole()
    edges = holes.opening_edges(hole) if hole is not None else []
    if not edges:
        return False
    FreeCADGui.Selection.clearSelection()
    for edge in edges:
        FreeCADGui.Selection.addSelection(hole.Document.Name, hole.Name, edge)
    FreeCADGui.runCommand("PartDesign_Chamfer", 0)
    size = holes.chamfer_size(hole)
    QtCore.QTimer.singleShot(0, lambda: _size(size))
    return True


def _size(size):
    import StudioGui

    from studio.services.field_defaults import FieldDefaults
    from studio.services.settings import Settings

    if FieldDefaults(Settings()).get(CHAMFER, SIZE_FIELD) is not None:
        return  # the user's own default (Make Default) wins
    if StudioGui.set_field(SIZE_FIELD, size):
        StudioGui.focus_field(SIZE_FIELD)
