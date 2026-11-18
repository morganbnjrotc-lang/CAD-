# SPDX-License-Identifier: LGPL-2.1-or-later
"""Inches or millimeters in the app (PLAN 3.1): applied at startup, ☰ › Units, and files opened later take
the user's units (see studio.services.units for why)."""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import units

MENU = (("system", "Follow Windows"), ("inches", "Inches"), ("millimeters", "Millimeters"))
NAMES = {"inches": "Inches", "millimeters": "Millimeters"}


def windows_uses_inches() -> bool:
    """Windows' measurement system (Settings › Time & language › Region): US means inches."""
    return QtCore.QLocale.system().measurementSystem() == QtCore.QLocale.ImperialUSSystem


def _views_changed():
    try:
        import StudioGui
    except ImportError:
        return
    StudioGui.units_changed()


class Units:
    def __init__(self, settings, freecad_units, windows_uses_inches=windows_uses_inches, views_changed=_views_changed):
        self._settings = settings
        self._freecad = freecad_units
        self._windows_uses_inches = windows_uses_inches
        self._views_changed = views_changed
        self._menu_actions = {}
        self.units = None  # "inches" or "millimeters" once applied

    def apply(self):
        self.units = units.resolve(self._settings.get(units.UNITS), self._windows_uses_inches())
        self._freecad.apply(self.units)
        self._views_changed()

    def set_choice(self, choice):
        self._settings.set(units.UNITS, choice)
        self.apply()

    def adopt(self, doc):
        """A document just opened takes the user's units, without asking to be saved for it."""
        try:
            gui_doc = FreeCADGui.getDocument(doc.Name)
        except Exception:  # no view of it (yet)
            gui_doc = None
        was_modified = gui_doc.Modified if gui_doc is not None else True
        if self._freecad.adopt(doc) and gui_doc is not None and not was_modified:
            gui_doc.Modified = False

    def build_menu(self, parent=None):
        menu = QtWidgets.QMenu("Units", parent)
        group = QtGui.QActionGroup(menu)
        group.setExclusive(True)
        self._menu_actions = {}
        for choice, label in MENU:
            action = menu.addAction(label)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, c=choice: self.set_choice(c))
            self._menu_actions[choice] = action
        menu.aboutToShow.connect(self._sync_menu)
        self._sync_menu()
        return menu

    def _sync_menu(self):
        chosen = self._settings.get(units.UNITS)
        windows = NAMES[units.resolve("system", self._windows_uses_inches())]
        for choice, action in self._menu_actions.items():
            action.setChecked(choice == chosen)
            if choice == "system":
                action.setText(f"Follow Windows ({windows})")


class _OpenedDocuments:
    """FreeCAD document observer: a file just opened takes the user's units. A file opened becomes the
    active document (Python observers get no "restored" call); for one already in them, nothing happens."""

    def __init__(self, owner):
        self._owner = owner

    def slotActivateDocument(self, doc):
        try:
            self._owner.adopt(doc)
        except Exception as exc:  # never break opening a file over its units
            FreeCAD.Console.PrintWarning(f"Studio: could not set the units of {doc.Name}: {exc}\n")


_units = None
_observer = None


def install_once():
    """Applies the user's units, gives files opened later the same, adds Units to the ☰ menu (once)."""
    global _units, _observer
    if _units is None:
        from studio.services.settings import Settings
        from studio.shell import window

        _units = Units(Settings(), units.FreeCADUnits())
        _units.apply()
        _observer = _OpenedDocuments(_units)
        FreeCAD.addDocumentObserver(_observer)
        if window.current() is not None:
            window.current().extra_menus.append(_units.build_menu(FreeCADGui.getMainWindow()))
    return _units


def current():
    return _units
