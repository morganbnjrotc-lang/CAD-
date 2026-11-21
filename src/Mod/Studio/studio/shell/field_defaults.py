# SPDX-License-Identifier: LGPL-2.1-or-later
"""Right-click a tool's field → Make Default, in the app (PLAN 3.6; studio.services.field_defaults).

Right-clicking a size box in a Part Design feature's panel offers Make Default (and Forget Default once
one is made); StudioGui shows the menu with FreeCAD's items first. When a tool then makes a new feature
of that type, its panel's boxes start with the defaults made. Editing an existing feature keeps its
values.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore  # FreeCAD's PySide shim

from studio.services.field_defaults import FieldDefaults

MAKE, FORGET = "Make Default", "Forget Default"


def _editing_kind():
    """The type of the Part Design feature whose panel is open, or None."""
    document = FreeCADGui.ActiveDocument
    view_provider = document.getInEdit() if document is not None else None
    kind = getattr(getattr(view_provider, "Object", None), "TypeId", "")
    return kind if kind.startswith("PartDesign::") and kind != "PartDesign::Body" else None


class _Created:
    """FreeCAD document observer: the last Part Design feature made, to tell a new one from one edited."""

    def __init__(self):
        self.last = None

    def slotCreatedObject(self, obj):
        if obj.TypeId.startswith("PartDesign::"):
            self.last = (obj.Document.Name, obj.Name)


class Defaults:
    """FreeCADGui document observer, and the field menu's two callbacks."""

    def __init__(self, store, created):
        self._store = store
        self._created = created

    # -- the field's menu (StudioGui.add_field_menu) -----------------------------------------
    def items(self, field, value):
        kind = _editing_kind()
        if kind is None:
            return []
        return [MAKE, FORGET] if self._store.get(kind, field) is not None else [MAKE]

    def chosen(self, field, label, value):
        kind = _editing_kind()
        if kind is None:
            return
        if label == MAKE:
            self._store.make(kind, field, value)
            _tell(f"New {_short(kind)} features will start with this value")
        elif label == FORGET:
            self._store.forget(kind, field)
            _tell(f"New {_short(kind)} features will start with FreeCAD's value again")

    # -- a new feature's panel opens ---------------------------------------------------------
    def slotInEdit(self, view_provider):
        obj = getattr(view_provider, "Object", None)
        kind = getattr(obj, "TypeId", "")
        if obj is None or self._created.last != (obj.Document.Name, obj.Name):
            return  # an existing feature edited: its own values stay
        self._created.last = None  # new only for the panel its tool opened, not when edited later
        defaults = self._store.for_feature(kind)
        if defaults:
            QtCore.QTimer.singleShot(0, lambda: _fill(defaults))


def _fill(defaults):
    import StudioGui  # C++: Python wrappers of FreeCAD's panels make FreeCAD abort at exit

    for field, value in defaults.items():
        StudioGui.set_field(field, value)


def _short(kind):
    from studio.viewmodels.tool_names import PLAIN_NAMES

    command = "PartDesign_" + kind.split("::")[1]
    return PLAIN_NAMES.get(command, kind.split("::")[1])


def _tell(text):
    FreeCADGui.getMainWindow().statusBar().showMessage(text, 4000)


_defaults = None


def install_once():
    global _defaults
    if _defaults is None:
        import StudioGui

        from studio.services.settings import Settings

        created = _Created()
        FreeCAD.addDocumentObserver(created)
        _defaults = Defaults(FieldDefaults(Settings()), created)
        FreeCADGui.addDocumentObserver(_defaults)
        StudioGui.add_field_menu(_defaults.items, _defaults.chosen)
    return _defaults
