# SPDX-License-Identifier: LGPL-2.1-or-later
"""The command palette window (PLAN 2.5). Opened by Studio_CommandPalette, bound to S and Ctrl+K.

A popup at the top of the main window: a search field and the best matches (studio.viewmodels.
palette) with icon, category and active shortcut. Type to filter, Up/Down to choose, Enter (or a
double-click) runs the command through the session's command service, Esc or a click elsewhere
closes it. Built on first use, then reused.
"""

import os

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.viewmodels.palette import Palette

Qt = QtCore.Qt
_STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ICON_ROOT = os.path.join(_STUDIO_DIR, "Resources", "command_icons")


def icon_file(icon):
    """Where the build put a catalog icon ("src/Mod/X/.../name.svg" -> Studio's command_icons);
    None if the command has no icon."""
    if not icon:
        return None
    return os.path.join(_ICON_ROOT, *icon.removeprefix("src/").split("/"))


class PaletteWindow(QtWidgets.QFrame):
    MAX_RESULTS = 50

    def __init__(self, palette: Palette, service, parent, contexts=lambda: ()):
        super().__init__(parent, Qt.Popup)
        self._palette, self._service, self._contexts = palette, service, contexts
        self._icons = {}
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Search tools")
        self.search.setClearButtonEnabled(True)
        self.results = QtWidgets.QTreeWidget(self)
        self.results.setColumnCount(3)
        self.results.setHeaderHidden(True)
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setAllColumnsShowFocus(True)
        self.results.setFocusPolicy(Qt.NoFocus)  # typing always goes to the search field
        header = self.results.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.search)
        layout.addWidget(self.results)
        self.resize(560, 380)
        self.search.textChanged.connect(self._refresh)
        self.search.installEventFilter(self)
        self.results.itemActivated.connect(lambda row, column: self._run(row))

    def open(self):
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._refresh("")
        parent = self.parentWidget()
        if parent is not None:
            corner = parent.mapToGlobal(QtCore.QPoint((parent.width() - self.width()) // 2, parent.height() // 10))
            self.move(corner)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def _icon(self, icon):
        path = icon_file(icon)
        if path is None or not os.path.isfile(path):
            return None
        if path not in self._icons:
            self._icons[path] = QtGui.QIcon(path)
        return self._icons[path]

    def _refresh(self, text):
        self.results.clear()
        for item in self._palette.search(text, contexts=self._contexts(), limit=self.MAX_RESULTS):
            row = QtWidgets.QTreeWidgetItem([item.title, item.category, item.shortcut])
            row.setData(0, Qt.UserRole, item.command)
            row.setToolTip(0, item.detail)
            icon = self._icon(item.icon)
            if icon is not None:
                row.setIcon(0, icon)
            self.results.addTopLevelItem(row)
        if self.results.topLevelItemCount():
            self.results.setCurrentItem(self.results.topLevelItem(0))

    def _move(self, step):
        count = self.results.topLevelItemCount()
        if count:
            row = self.results.indexOfTopLevelItem(self.results.currentItem())
            self.results.setCurrentItem(self.results.topLevelItem(max(0, min(count - 1, row + step))))

    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Up):
                self._move(1 if key == Qt.Key_Down else -1)
                return True
            if key in (Qt.Key_PageDown, Qt.Key_PageUp):
                self._move(10 if key == Qt.Key_PageDown else -10)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._run(self.results.currentItem())
                return True
            if key == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def _run(self, row):
        if row is None:
            return
        command = row.data(0, Qt.UserRole)
        self.close()
        self._palette.record_use(command)
        QtCore.QTimer.singleShot(0, lambda: self._run_later(command))

    def _run_later(self, command):
        try:
            self._service.run(command)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"Studio palette: {command} failed: {exc}\n")


_window = None


def open_palette():
    """Opens the session's palette (built on first use)."""
    global _window
    if _window is None:
        from studio.interaction.keymap import Keymap
        from studio.shell import app, shortcuts

        service = app.command_service()
        settings = app.settings()
        palette = Palette(service.catalog, Keymap(service.catalog, settings), settings)

        def contexts():
            return shortcuts._handler.contexts if shortcuts._handler is not None else []

        _window = PaletteWindow(palette, service, FreeCADGui.getMainWindow(), contexts)
    _window.open()
    return _window


def current_window():
    return _window
