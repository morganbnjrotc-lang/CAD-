# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's look in the running app (ADR 0010, PLAN 2.9).

Qt's Fusion style with a palette made from Studio's colors (studio.services.theme) styles every
widget, FreeCAD's dialogs included, and FreeCAD's 3D view and sketch colors follow the same palette.
The mode follows Windows' light or dark setting while the app runs, unless the user picks one in the
☰ menu (Appearance). If the user has chosen a FreeCAD stylesheet in Preferences, its colors stay: only
the 3D and sketch colors are Studio's then.

Where the palette doesn't reach:
- Studio's own widgets (bars, Home) style themselves from the palette: they `follow` the look.
- FreeCAD's panels: the property editor keeps the group-row colors it read when it was built, its
  tab box is drawn a shade lighter than the panel, the panels' title buttons have fixed dark icons
  (FreeCAD's stylesheet handles these), and the status bar keeps the old mode's colors after a
  switch, under a stylesheet of FreeCAD's own. `FreeCADPanels` fixes them.
- Not yet: FreeCAD's Tasks panel floats over the 3D view and, without FreeCAD's stylesheet, is an
  empty box there between tasks. Every way tried to clear it (solid with "Auto task", "Auto show on
  edit", a stylesheet or a transparent palette on the task view) makes FreeCAD crash natively when the
  TechDraw workbench activates. After a live switch, the panel's frame also keeps the old mode's
  colors until the next start: it lives under FreeCAD's overlay stylesheet, and re-polishing it means
  holding FreeCAD's overlay widgets, which FreeCAD destroys so late that the app aborts at exit
  (PLAN 2.9, ADR 0010 notes).
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


def tinted(icon: QtGui.QIcon, color: str, size: int = 32) -> QtGui.QIcon:
    """The icon's shape drawn in one color (keeps its transparency, replaces its colors)."""
    pixmap = icon.pixmap(size, size)
    if pixmap.isNull():
        return icon
    painter = QtGui.QPainter(pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QtGui.QColor(color))
    painter.end()
    return QtGui.QIcon(pixmap)


PROPERTY_EDITOR = "Gui::PropertyEditor::PropertyEditor"
TITLE_BUTTONS = ("OBTN Float", "OBTN Overlay", "OBTN Close")  # FreeCAD's actions in panel title bars


class FreeCADPanels:
    """The FreeCAD widgets Studio styles beyond the palette (see the module notes): the Model panel's
    property editors and tab box, and the actions behind every panel's title buttons.

    Found once, at startup, inside the Model panel only, and kept. A lookup (findChild) gives each
    widget it passes a PySide wrapper. FreeCAD deletes some widgets later (a document's, or toolbar
    buttons when a workbench changes), and stale wrappers of them make FreeCAD abort when it exits.
    The Model panel lives as long as the app. The status bar and the title-button actions are looked
    up each time and not kept: holding them made FreeCAD abort at exit after a workbench change.
    """

    def __init__(self, model_panel):
        self.property_editors = [e for e in model_panel.findChildren(QtWidgets.QTreeView)
                                 if e.metaObject().className() == PROPERTY_EDITOR]
        self.property_tabs = model_panel.findChildren(QtWidgets.QTabWidget, "propertyTab")
        self._model_panel = model_panel
        self._title_icons = {}  # FreeCAD's icon per title action ("OBTN Float"...), kept to tint afresh

    def style(self, p: theme.Palette):
        for editor in self.property_editors:
            editor.setProperty("groupBackground", QtGui.QBrush(QtGui.QColor(p.hover)))
            editor.setProperty("groupTextColor", QtGui.QColor(p.text))
            editor.viewport().update()
        for tabs in self.property_tabs:
            tabs.setDocumentMode(True)  # no frame: the area matches the tree above it
        # FreeCAD styles its status bar ("#statusBar{color: ...}", from OutputWindow/colorText) and
        # sets it again with each message. Under a stylesheet, Qt keeps the labels' palette as it was,
        # so set FreeCAD's normal-message style with the new color now: that re-polishes them.
        self._model_panel.window().statusBar().setStyleSheet(f"#statusBar{{color: {p.text}}}")  # not kept
        for action in self._title_actions():  # one action serves every panel's title bar
            original = self._title_icons.setdefault(action.data(), action.icon())
            action.setIcon(tinted(original, p.muted))

    def _title_actions(self):
        """Looked up each time and not kept: they belong to FreeCAD's panel manager, and a kept
        reference made FreeCAD abort at exit after a workbench change."""
        title = self._model_panel.titleBarWidget()
        actions = {}
        for button in title.findChildren(QtWidgets.QToolButton) if title is not None else ():
            action = button.defaultAction()
            if action is not None and action.data() in TITLE_BUTTONS:
                actions[action.data()] = action
        return list(actions.values())


_panels = None


def freecad_panels():
    """The session's FreeCADPanels, found the first time Studio applies its look (at startup)."""
    global _panels
    if _panels is None:
        from studio.shell import window

        panel = window.current().model_panel() if window.current() is not None else None
        if panel is None:
            return None
        _panels = FreeCADPanels(panel)
    return _panels


class Appearance:
    def __init__(self, settings, colors, system_is_dark=_system_is_dark, freecad_stylesheet=_freecad_stylesheet,
                 panels=freecad_panels):
        self._settings = settings
        self._colors = colors
        self._system_is_dark = system_is_dark
        self._freecad_stylesheet = freecad_stylesheet
        self._panels = panels
        self._menu_actions = {}
        self._followers = []
        self.mode = None  # "light" or "dark" once applied
        self.look = None  # the palette Studio's widgets draw with; None under a FreeCAD stylesheet

    def apply(self):
        mode = theme.current_mode(self._settings, self._system_is_dark())
        p = theme.palette(mode)
        own_colors = not self._freecad_stylesheet()
        if own_colors:  # Fusion itself is picked before the GUI starts (Init.py)
            QtWidgets.QApplication.setPalette(qpalette(p))
            panels = self._panels()
            if panels is not None:
                panels.style(p)
        self._colors.apply(p)  # FreeCAD's 3D views and sketches pick these up live
        self.mode = mode
        self.look = p if own_colors else None
        for follower in list(self._followers):
            self._tell(follower)

    def follow(self, restyle):
        """Calls `restyle(palette)` now (once applied) and whenever the look changes; the palette is
        None while the user's FreeCAD stylesheet supplies the colors."""
        self._followers.append(restyle)
        if self.mode is not None:
            self._tell(restyle)

    def _tell(self, restyle):
        try:
            restyle(self.look)
        except RuntimeError:  # its widget was deleted
            self._followers.remove(restyle)

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
            _appearance.follow(window.current().restyle)
    return _appearance


def current():
    return _appearance
