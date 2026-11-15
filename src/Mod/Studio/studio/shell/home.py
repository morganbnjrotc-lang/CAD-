# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home page (PLAN 2.8), in place of FreeCAD's Start page.

It covers the main area while no document is open: at startup and after the last document closes.
New Part (a new document with a body) and Open, then the recent files as cards (studio.viewmodels.
home). A card shows the preview FreeCAD stored in a .FCStd file; previews load one per idle moment
after the page appears, so they don't hold up startup. Click a card to open the file; right-click
for "Remove from list". FreeCAD's Start page is switched off: it costs startup time and its buttons
switch workbench.
"""

import os

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services.thumbnails import thumbnail_png

Qt = QtCore.Qt
START_PREFERENCES = "User parameter:BaseApp/Preferences/Mod/Start"
ICON = QtCore.QSize(168, 112)
CELL = QtCore.QSize(196, 172)


def _open_file(path):
    FreeCADGui.loadFile(path)  # what File > Open does: FreeCAD files open, other formats import


class HomePage(QtWidgets.QWidget):
    def __init__(self, home, service, opener=None, parent=None):
        super().__init__(parent)
        self._home, self._service = home, service
        self._open = opener or _open_file
        self._placeholders = {}
        self._pending = []
        self._generation = 0
        self.previews_loaded = True
        self.setObjectName("StudioHome")
        self.setAutoFillBackground(True)

        title = QtWidgets.QLabel("Home", self)
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.8)
        font.setBold(True)
        title.setFont(font)
        self.new_part_button = QtWidgets.QPushButton("New Part", self)
        self.new_part_button.setToolTip("A new document with an empty body to model in")
        self.open_button = QtWidgets.QPushButton("Open…", self)
        self.open_button.setToolTip("Open a FreeCAD file or import STEP, STL and other formats")
        heading = QtWidgets.QLabel("Recent files", self)
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)

        self.cards = QtWidgets.QListWidget(self)
        self.cards.setViewMode(QtWidgets.QListView.IconMode)
        self.cards.setIconSize(ICON)
        self.cards.setGridSize(CELL)
        self.cards.setResizeMode(QtWidgets.QListView.Adjust)
        self.cards.setMovement(QtWidgets.QListView.Static)
        self.cards.setWordWrap(True)
        self.cards.setUniformItemSizes(True)
        self.cards.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.cards.setContextMenuPolicy(Qt.CustomContextMenu)
        self.empty_note = QtWidgets.QLabel(
            "No recent files yet. Create a part or open a file to start.", self)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.new_part_button)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addLayout(buttons)
        layout.addSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(self.empty_note)
        layout.addWidget(self.cards, 1)

        self.new_part_button.clicked.connect(self._new_part)
        self.open_button.clicked.connect(lambda: self._service.run("Std_Open"))
        self.cards.itemActivated.connect(self._activate)
        self.cards.customContextMenuRequested.connect(self._context_menu)

    # -- content -----------------------------------------------------------------------------
    def refresh(self):
        self._generation += 1
        self.cards.clear()
        self._pending = []
        cards = self._home.cards()
        for card in cards:
            item = QtWidgets.QListWidgetItem(self._placeholder(card.kind), f"{card.title}\n{card.when}")
            item.setData(Qt.UserRole, card.path)
            item.setToolTip(card.path if card.exists else f"{card.path}\nThis file no longer exists.")
            item.setSizeHint(CELL)
            if not card.exists:
                item.setForeground(self.palette().brush(QtGui.QPalette.Disabled, QtGui.QPalette.Text))
            self.cards.addItem(item)
            if card.exists and card.kind == "FreeCAD":
                self._pending.append(item)
        self.empty_note.setVisible(not cards)
        self.cards.setVisible(bool(cards))
        self.previews_loaded = not self._pending
        if self._pending:
            generation = self._generation
            QtCore.QTimer.singleShot(0, lambda: self._load_next_preview(generation))

    def _load_next_preview(self, generation):
        if generation != self._generation:
            return  # refreshed meanwhile: those items are gone
        if not self._pending:
            self.previews_loaded = True
            return
        item = self._pending.pop(0)
        png = thumbnail_png(item.data(Qt.UserRole))
        if png:
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(png, "PNG"):
                item.setIcon(QtGui.QIcon(pixmap))
        QtCore.QTimer.singleShot(0, lambda: self._load_next_preview(generation))

    def _placeholder(self, kind):
        """A plain tile naming the file type, for files without a stored preview."""
        if kind not in self._placeholders:
            pixmap = QtGui.QPixmap(ICON)
            pixmap.fill(self.palette().color(QtGui.QPalette.AlternateBase))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(self.palette().color(QtGui.QPalette.PlaceholderText))
            font = painter.font()
            font.setBold(True)
            font.setPointSizeF(font.pointSizeF() * 1.4)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, kind)
            painter.end()
            self._placeholders[kind] = QtGui.QIcon(pixmap)
        return self._placeholders[kind]

    # -- actions -----------------------------------------------------------------------------
    def _activate(self, item):
        path = item.data(Qt.UserRole)
        if os.path.isfile(path):
            self._open(path)

    def _context_menu(self, position):
        item = self.cards.itemAt(position)
        if item is None:
            return
        menu = QtWidgets.QMenu(self.cards)
        remove = menu.addAction("Remove from list")
        path = item.data(Qt.UserRole)
        remove.triggered.connect(lambda: self.remove_path(path))
        menu.exec(self.cards.viewport().mapToGlobal(position))

    def remove_path(self, path):
        self._home.remove(path)
        self.refresh()

    def _new_part(self):
        self._service.run("Std_New")
        self._service.run("PartDesign_Body")


class _Cover(QtCore.QObject):
    """Keeps the page covering the main area and shows it only while no document is open."""

    def __init__(self, page, area):
        super().__init__(area)
        self._page, self._area = page, area
        self._pending = False
        area.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._area and event.type() == QtCore.QEvent.Resize:
            self._page.setGeometry(self._area.rect())
        return False

    def schedule(self):
        if not self._pending:
            self._pending = True
            QtCore.QTimer.singleShot(0, self.update)

    def update(self):
        self._pending = False
        show = not FreeCAD.listDocuments()
        if show:
            self._page.setGeometry(self._area.rect())
            self._page.refresh()
            self._page.raise_()
        self._page.setVisible(show)

    # FreeCADGui document observer
    def slotCreatedDocument(self, document):
        self.schedule()

    def slotDeletedDocument(self, document):
        self.schedule()


_page = None


def install_once():
    """Switches FreeCAD's Start page off and sets up the session's Home page (once)."""
    global _page
    FreeCAD.ParamGet(START_PREFERENCES).SetBool("ShowOnStartup", False)
    if _page is None:
        from studio.services.recent_files import RecentFiles, raise_limit_once
        from studio.services.settings import Settings
        from studio.shell.shortcuts import _SessionService
        from studio.viewmodels.home import Home

        recent = RecentFiles()
        raise_limit_once(recent, Settings())  # FreeCAD's 4 recent files are too few for Home
        area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        _page = HomePage(Home(recent), _SessionService(), parent=area)
        cover = _Cover(_page, area)
        _page._cover = cover  # keep it alive with the page
        FreeCADGui.addDocumentObserver(cover)
        cover.update()
    return _page


def current():
    return _page
