# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's main window, layout A (docs/adr/0009).

On top of FreeCAD's main window, while Studio's workbench is active:
  top bar  ☰ menu (FreeCAD's File, Edit, View and Help menus) · panel button · "Search tools" (palette)
  toolbar  the tools for the current selection (studio.viewmodels.context_toolbar), icon and label
  status   a hint for the current selection, at the right of the status bar
FreeCAD's menu bar is hidden; the Model panel (tree above properties) is FreeCAD's own dock.
The bars are plain QToolBars: FreeCAD's toolbar manager only hides its own Gui::ToolBar class.
"""

import functools

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.shell.palette import icon_file
from studio.shell.shortcuts import _live_is_active
from studio.viewmodels.context_toolbar import Selected, selection_kind
from studio.viewmodels.tool_names import clean_title

Qt = QtCore.Qt
MODEL_PANEL = "Model"  # FreeCAD's dock with the tree above the properties


class _SelectionObserver:
    def __init__(self, changed):
        self._changed = changed

    def addSelection(self, doc, obj, sub, point):
        self._changed()

    def removeSelection(self, doc, obj, sub):
        self._changed()

    def setSelection(self, doc):
        self._changed()

    def clearSelection(self, doc):
        self._changed()


class _DocumentObserver:
    def __init__(self, changed):
        self._changed = changed

    def slotInEdit(self, view_provider):
        self._changed()

    def slotResetEdit(self, view_provider):
        self._changed()

    def slotActivateDocument(self, document):
        self._changed()


class StudioWindow:
    ENABLE_CHECK_MS = 400  # commands become (in)active without a selection change, e.g. a new document

    def __init__(self, main_window, toolbar, service, contexts=lambda: (), open_palette=None,
                 is_active=_live_is_active):
        self._main = main_window
        self._toolbar = toolbar
        self._service = service
        self._contexts = contexts
        self._open_palette = open_palette
        self._is_active = is_active
        self._icons = {}
        self._pending = False
        self.kind = None
        self.extra_menus = []  # Studio's own menus after FreeCAD's in ☰ (e.g. Appearance)

    # -- setup -------------------------------------------------------------------------------
    def install(self):
        main = self._main
        self.top_bar = QtWidgets.QToolBar("Studio", main)
        self.top_bar.setObjectName("StudioTopBar")
        self.tools = QtWidgets.QToolBar("Tools", main)
        self.tools.setObjectName("StudioToolBar")
        self.tools.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for bar in (self.top_bar, self.tools):
            bar.setMovable(False)
            bar.setFloatable(False)

        self.menu_button = QtWidgets.QToolButton(self.top_bar)
        self.menu_button.setText("☰")
        self.menu_button.setToolTip("Menu: File, Edit, View, Help")
        self.menu_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self.menu_button)
        menu.aboutToShow.connect(lambda: self._fill_menu(menu))
        self.menu_button.setMenu(menu)

        self.panel_button = QtWidgets.QToolButton(self.top_bar)
        self.panel_button.setText("Panel")
        self.panel_button.setToolTip("Show or hide the model tree and properties")
        self.panel_button.setCheckable(True)
        model = self.model_panel()
        self.panel_button.setChecked(model is None or model.isVisible())
        self.panel_button.toggled.connect(self._show_panel)
        if model is not None:
            model.visibilityChanged.connect(self._panel_changed)

        spacer = QtWidgets.QWidget(self.top_bar)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.search_button = QtWidgets.QPushButton("Search tools", self.top_bar)
        self.search_button.setToolTip("Search every tool by name (S or Ctrl+K)")
        self.search_button.setMinimumWidth(220)
        self.search_button.clicked.connect(lambda: self._open_palette and self._open_palette())

        for widget in (self.menu_button, self.panel_button, spacer, self.search_button):
            self.top_bar.addWidget(widget)

        self.hint = QtWidgets.QLabel(main.statusBar())
        main.statusBar().addPermanentWidget(self.hint)

        self._selection_observer = _SelectionObserver(self.schedule_refresh)
        self._document_observer = _DocumentObserver(self.schedule_refresh)
        FreeCADGui.Selection.addObserver(self._selection_observer)
        FreeCADGui.addDocumentObserver(self._document_observer)
        self._timer = QtCore.QTimer(self.tools)
        self._timer.setInterval(self.ENABLE_CHECK_MS)
        self._timer.timeout.connect(self._update_enabled)
        self.show()

    def show(self):
        """Studio's look: our bars in, FreeCAD's menu bar out."""
        main = self._main
        main.menuBar().setVisible(False)
        if self.top_bar.parent() is not None and main.toolBarArea(self.top_bar) == Qt.NoToolBarArea:
            main.addToolBar(Qt.TopToolBarArea, self.top_bar)
            main.addToolBarBreak(Qt.TopToolBarArea)
            main.addToolBar(Qt.TopToolBarArea, self.tools)
        for widget in (self.top_bar, self.tools, self.hint):
            widget.setVisible(True)
        self._timer.start()
        self.refresh()

    def hide(self):
        """Another workbench is active: give FreeCAD its own menu bar back."""
        self._main.menuBar().setVisible(True)
        for widget in (self.top_bar, self.tools, self.hint):
            widget.setVisible(False)
        self._timer.stop()

    # -- parts -------------------------------------------------------------------------------
    def model_panel(self):
        return self._main.findChild(QtWidgets.QDockWidget, MODEL_PANEL)

    def _show_panel(self, visible):
        model = self.model_panel()
        if model is not None:
            model.setVisible(visible)

    def _panel_changed(self, visible):
        self.panel_button.blockSignals(True)
        self.panel_button.setChecked(visible)
        self.panel_button.blockSignals(False)

    def _menus(self):
        return [a for a in self._main.menuBar().actions() if a.menu() is not None and a.text().strip()]

    def menu_titles(self):
        return [clean_title(a.text()) for a in self._menus()]

    def _fill_menu(self, menu):
        menu.clear()
        for action in self._menus():
            menu.addMenu(action.menu())
        if self.extra_menus:
            menu.addSeparator()
            for extra in self.extra_menus:
                menu.addMenu(extra)

    def _icon(self, icon):
        path = icon_file(icon)
        if path not in self._icons:
            self._icons[path] = QtGui.QIcon(path) if path else QtGui.QIcon()
        return self._icons[path]

    # -- the toolbar -------------------------------------------------------------------------
    def schedule_refresh(self):
        """Selection events come in bursts (one per element): rebuild once, after them."""
        if not self._pending:
            self._pending = True
            QtCore.QTimer.singleShot(0, self.refresh)

    def refresh(self):
        self._pending = False
        self.show_tools_for(self._selection(), self._editing())

    @staticmethod
    def _selection():
        return [Selected(s.Object.TypeId, tuple(s.SubElementNames)) for s in FreeCADGui.Selection.getSelectionEx()]

    @staticmethod
    def _editing():
        document = FreeCADGui.ActiveDocument
        view_provider = document.getInEdit() if document is not None else None
        target = getattr(view_provider, "Object", None)
        return getattr(target, "TypeId", None)

    def show_tools_for(self, selected, editing):
        kind = selection_kind(selected, editing)
        contexts = self._contexts()
        self.tools.clear()
        for button in self._toolbar.buttons(kind, contexts):
            action = self.tools.addAction(self._icon(button.icon), button.label)
            key = f" ({button.shortcut})" if button.shortcut else ""
            action.setToolTip(f"{button.label}{key}\n{button.tooltip}")
            action.setData(button.command)
            action.setEnabled(self._active(button.command))
            action.triggered.connect(functools.partial(self._run, button.command))
        self.hint.setText(self._toolbar.hint(kind, contexts))
        self.kind = kind

    def _active(self, command):
        try:
            return self._is_active(command)
        except Exception:
            return False

    def _update_enabled(self):
        for action in self.tools.actions():
            command = action.data()
            if command:
                action.setEnabled(self._active(command))

    def _run(self, command, *_):
        QtCore.QTimer.singleShot(0, lambda: self._run_now(command))

    def _run_now(self, command):
        try:
            self._service.run(command)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"Studio toolbar: {command} failed: {exc}\n")


_window = None


def install_once():
    """Sets up the session's window (once) and shows Studio's look."""
    global _window
    if _window is None:
        from studio.interaction.keymap import Keymap
        from studio.shell import app, palette, shortcuts
        from studio.viewmodels.context_toolbar import ContextToolbar

        service = app.command_service()
        toolbar = ContextToolbar(service.catalog, Keymap(service.catalog, app.settings()))

        def contexts():
            return shortcuts._handler.contexts if shortcuts._handler is not None else []

        _window = StudioWindow(FreeCADGui.getMainWindow(), toolbar, service, contexts, palette.open_palette)
        _window.install()
    else:
        _window.show()
    return _window


def current():
    return _window
