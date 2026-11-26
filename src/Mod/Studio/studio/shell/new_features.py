# SPDX-License-Identifier: LGPL-2.1-or-later
"""What a feature made in the app starts as (PLAN 3.18; studio.services.new_features decides).

A feature made now gets Studio's name in the model tree (Extrude, Cut…) when it still has FreeCAD's own, as
it is made, inside its tool's undo step. Objects read from a file, or brought back by an undo, aren't new:
they keep their names.

A hole made with the Hole tool starts in the user's units' thread standard when its panel opens (the panel
follows the change). A hole a script makes keeps FreeCAD's start: with a standard, the size comes from it,
not from the script's Diameter.
"""

import FreeCAD

from studio.services import new_features

HOLE = "PartDesign::Hole"


class _Made:
    """FreeCAD document observer: objects made. (FreeCADGui's observers get a slotCreatedObject too, with view
    providers: a separate one, `_Opened`, watches the panels.)"""

    def __init__(self):
        self.hole = None  # (document, name) of the hole made last, until its panel opens or another is made

    def slotCreatedObject(self, obj):
        doc = obj.Document
        if doc.Restoring or doc.Transacting:  # read from a file, or back from an undo: not made now
            return
        try:
            new_features.rename(obj)
        except Exception as exc:  # never in the way of making the feature
            FreeCAD.Console.PrintWarning(f"Studio: {obj.Name} keeps FreeCAD's name: {exc}\n")
        self.hole = (doc.Name, obj.Name) if obj.TypeId == HOLE else None


class _Opened:
    """FreeCADGui document observer: a panel opening for the hole just made."""

    def __init__(self, made):
        self._made = made

    def slotInEdit(self, view_provider):
        hole = getattr(view_provider, "Object", None)
        made, self._made.hole = self._made.hole, None
        if getattr(hole, "TypeId", "") != HOLE or made != (hole.Document.Name, hole.Name):
            return
        from studio.shell import units

        current = units.current()
        try:
            if current is not None and current.units and new_features.start_hole(hole, current.units):
                hole.recompute()
        except Exception as exc:
            FreeCAD.Console.PrintWarning(f"Studio: {hole.Name} keeps FreeCAD's thread standard: {exc}\n")


_made = None


def install_once():
    global _made
    if _made is None:
        import FreeCADGui

        _made = _Made()
        FreeCAD.addDocumentObserver(_made)
        FreeCADGui.addDocumentObserver(_Opened(_made))
    return _made
