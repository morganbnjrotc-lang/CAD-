# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's look in the running app (ADR 0010, PLAN 2.9).

Qt's Fusion style with a palette made from Studio's colors (studio.services.theme) styles every
widget, FreeCAD's dialogs included, and FreeCAD's 3D view and sketch colors follow the same palette.
The mode follows Windows' light or dark setting while the app runs, unless the user picks one in the
☰ menu (Appearance). If the user has chosen a FreeCAD stylesheet in Preferences, its colors stay: only
the 3D and sketch colors are Studio's then.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import theme

MAIN_WINDOW = theme.MAIN_WINDOW
MODES = (("system", "Follow Windows"), ("light", "Light"), ("dark", "Dark"))
QPalette = QtGui.QPalette


def _system_is_dark():
    return QtGui.QGuiApplication.styleHints().colorScheme() == QtCore.Qt.ColorScheme.Dark


def _freecad_stylesheet():
    return bool(FreeCAD.ParamGet(MAIN_WINDOW).GetString("StyleSheet", ""))


def qpalette(p: theme.Palette) -> QPalette:
    pal = QPalette()
    colors = {
        QPalette.Window: p.window, QPalette.WindowText: p.text,
        QPalette.Base: p.panel, QPalette.AlternateBase: theme.mix(p.panel, p.window, 0.6),
        QPalette.ToolTipBase: p.panel, QPalette.ToolTipText: p.text, QPalette.PlaceholderText: p.muted,
        QPalette.Text: p.text, QPalette.Button: p.field, QPalette.ButtonText: p.text,
        QPalette.BrightText: p.on_accent,
        QPalette.Light: theme.mix(p.field, "#FFFFFF", 0.5 if p.name == "light" else 0.08),
        QPalette.Midlight: theme.mix(p.field, p.border, 0.5), QPalette.Mid: p.border,
        QPalette.Dark: theme.mix(p.border, p.text, 0.3), QPalette.Shadow: theme.mix(p.border, "#000000", 0.5),
        QPalette.Highlight: p.selection, QPalette.HighlightedText: p.text,
        QPalette.Link: p.accent, QPalette.LinkVisited: p.accent, QPalette.Accent: p.accent,
    }
    for role, color in colors.items():
        pal.setColor(role, QtGui.QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QtGui.QColor(p.faint))
    return pal


class Appearance:
    def __init__(self, settings, colors, system_is_dark=_system_is_dark, freecad_stylesheet=_freecad_stylesheet):
        self._settings = settings
        self._colors = colors
        self._system_is_dark = system_is_dark
        self._freecad_stylesheet = freecad_stylesheet
        self._menu_actions = {}
        self.mode = None  # "light" or "dark" once applied

    def apply(self):
        mode = theme.current_mode(self._settings, self._system_is_dark())
        p = theme.palette(mode)
        if not self._freecad_stylesheet():  # Fusion itself is picked before the GUI starts (Init.py)
            QtWidgets.QApplication.setPalette(qpalette(p))
        self._colors.apply(p)  # FreeCAD's 3D views and sketches pick these up live
        self.mode = mode

    def set_mode(self, choice):
        self._settings.set(theme.MODE, choice)
        self.apply()

    def system_scheme_changed(self, *_):
        if self._settings.get(theme.MODE) == "system":
            self.apply()

    def build_menu(self, parent=None):
        menu = QtWidgets.QMenu("Appearance", parent)
        group = QtGui.QActionGroup(menu)
        group.setExclusive(True)
        self._menu_actions = {}
        for choice, label in MODES:
            action = menu.addAction(label)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, c=choice: self.set_mode(c))
            self._menu_actions[choice] = action
        menu.aboutToShow.connect(self._sync_menu)
        self._sync_menu()
        return menu

    def _sync_menu(self):
        chosen = self._settings.get(theme.MODE)
        for choice, action in self._menu_actions.items():
            action.setChecked(choice == chosen)


_appearance = None


def install_once():
    """Applies Studio's look, follows Windows' mode and adds Appearance to the ☰ menu (once)."""
    global _appearance
    if _appearance is None:
        from studio.services.settings import Settings
        from studio.shell import window

        settings = Settings()
        _appearance = Appearance(settings, theme.FreeCADColors(settings))
        _appearance.apply()
        QtGui.QGuiApplication.styleHints().colorSchemeChanged.connect(_appearance.system_scheme_changed)
        if window.current() is not None:
            window.current().extra_menus.append(_appearance.build_menu(FreeCADGui.getMainWindow()))
    return _appearance


def current():
    return _appearance
