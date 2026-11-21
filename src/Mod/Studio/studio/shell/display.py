# SPDX-License-Identifier: LGPL-2.1-or-later
"""Display presets in the app (PLAN 3.8; studio.services.display keeps the choice).

A Display menu on the top bar: Shaded with Edges, Shaded, Hidden Line, Wireframe, and Perspective. The
choice applies to every open document's 3D views and to documents opened later (when one becomes the
active document), through FreeCAD's own viewer calls: setOverrideMode, setCameraType.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import display as service


def _views():
    """Every open 3D view."""
    for name in list(FreeCAD.listDocuments()):
        document = FreeCADGui.getDocument(name)
        if document is not None:
            yield from document.mdiViewsOfType("Gui::View3DInventor")


def _apply_to(view, mode, perspective):
    try:
        view.getViewer().setOverrideMode(mode)
        camera = "Perspective" if perspective else "Orthographic"
        if view.getCameraType() != camera:
            view.setCameraType(camera)
    except Exception:  # a view closing meanwhile
        pass


class DisplayMenu:
    """The top bar's Display button and its menu; a FreeCADGui document observer for new documents."""

    def __init__(self, store, parent):
        self._store = store
        self.button = QtWidgets.QToolButton(parent)
        self.button.setText("Display")
        self.button.setToolTip("How the 3D view draws the model")
        self.button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu = QtWidgets.QMenu(self.button)
        group = QtGui.QActionGroup(self.menu)
        group.setExclusive(True)
        self._styles = {}
        for style in service.STYLES:
            action = self.menu.addAction(style.label)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, m=style.mode: self.choose(m))
            self._styles[style.mode] = action
        self.menu.addSeparator()
        self.perspective_action = self.menu.addAction("Perspective")
        self.perspective_action.setCheckable(True)
        self.perspective_action.triggered.connect(self.set_perspective)
        self.button.setMenu(self.menu)
        self._sync()

    def choose(self, mode):
        self._store.set_style(mode)
        self.apply_everywhere()

    def set_perspective(self, on):
        self._store.set_perspective(bool(on))
        self.apply_everywhere()

    def apply_everywhere(self):
        mode, perspective = self._store.style(), self._store.perspective()
        for view in _views():
            _apply_to(view, mode, perspective)
        self._sync()

    def _sync(self):
        self._styles[self._store.style()].setChecked(True)
        self.perspective_action.setChecked(self._store.perspective())

    # A new document's view starts as FreeCAD's preferences say: give it the choice once it shows.
    def slotCreatedDocument(self, gui_document):
        QtCore.QTimer.singleShot(0, self.apply_everywhere)

    def slotActivateDocument(self, gui_document):
        QtCore.QTimer.singleShot(0, self.apply_everywhere)


_menu = None


def install_once():
    global _menu
    if _menu is None:
        from studio.services.settings import Settings
        from studio.shell import window

        if window.current() is None:
            return None
        _menu = DisplayMenu(service.Display(Settings()), window.current().top_bar)
        window.current().add_to_top_bar(_menu.button)
        FreeCADGui.addDocumentObserver(_menu)
        _menu.apply_everywhere()
    return _menu


def current():
    return _menu
