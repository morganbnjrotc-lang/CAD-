# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's tool groups on the top bar, and pinning a tool to the toolbar (PLAN 3.17, docs/adr/0013;
studio.viewmodels.tool_groups lists them).

The top bar reads ☰ · Panel · Create Modify Construct Inspect Insert · Display … Search; while a sketch is
being edited the groups are Create Modify Constrain Inspect. Each group is a menu of every tool in it, with
icons, plain names and keys; a tool drawing more than one way, and Part Design's primitives, open a side
menu. A tool that can't run now is grayed, as on the toolbar.

Right-clicking a tool in a group offers "Pin to toolbar" for the kind of selection there is now (faces,
sketches…): from then on it shows on the toolbar after that kind's tools. Right-clicking a pinned button,
or the tool in its group again, unpins it.
"""

import functools

from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.viewmodels.tool_groups import KIND_WORDS, SubMenu

Qt = QtCore.Qt
MOST_GROUPS = 5  # Create, Modify, Construct, Inspect, Insert; four while sketching


class GroupBar:
    def __init__(self, window, groups, contexts=lambda: ()):
        self._window = window
        self._groups = groups
        self._contexts = contexts
        self.buttons = []
        self._actions = []  # the top bar's, one per button: what shows and hides it
        self._pin_target = None  # (kind, key) while the pin menu is open, for tests

    def install(self):
        window = self._window
        window.add_top_bar_separator()
        for n in range(MOST_GROUPS):
            button = QtWidgets.QToolButton(window.top_bar)
            button.setObjectName(f"StudioGroup{n}")
            button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            menu = QtWidgets.QMenu(button)
            menu.setToolTipsVisible(True)
            menu.installEventFilter(_RIGHT_CLICK)
            menu.aboutToShow.connect(functools.partial(self._fill, n, menu))
            button.setMenu(menu)
            self.buttons.append(button)
            self._actions.append(window.add_to_top_bar(button))
        window.add_top_bar_separator()
        window.on_refresh(self.follow)
        self.follow(window.kind)

    # -- which groups ------------------------------------------------------------------------
    @staticmethod
    def sketching(kind):
        return kind == "editing"

    def labels(self):
        """The groups' names as the top bar shows them now."""
        return [b.text() for b, a in zip(self.buttons, self._actions) if a.isVisible()]

    def follow(self, kind):
        """The selection's kind changed: the sketch's groups while sketching, the model's otherwise."""
        labels = self._groups.labels(self.sketching(kind))
        for n, (button, action) in enumerate(zip(self.buttons, self._actions)):
            shown = n < len(labels)
            action.setVisible(shown)
            if shown:
                button.setText(labels[n])
                button.setToolTip(f"Every {labels[n]} tool")

    # -- a group's menu ------------------------------------------------------------------------
    def _fill(self, n, menu):
        window = self._window
        kind = window.kind
        groups = self._groups.groups(self.sketching(kind), self._contexts())
        menu.clear()
        if n >= len(groups):
            return
        for item in groups[n].items:
            if item is None:
                menu.addSeparator()
            elif isinstance(item, SubMenu):
                side = menu.addMenu(window.icon(item.icon), item.label)
                side.setToolTipsVisible(True)
                side.installEventFilter(_RIGHT_CLICK)
                for way in item.items:
                    self._add(side, way, kind)
            else:
                self._add(menu, item, kind)

    def _add(self, menu, item, kind):
        window = self._window
        # The key shows at the right of the name (after a tab) without becoming a second shortcut.
        text = f"{item.label}\t{item.shortcut}" if item.shortcut else item.label
        action = menu.addAction(window.icon(item.icon), text)
        action.setToolTip(item.tooltip)
        pinned = self._groups.is_pinned(kind, item.key)
        action.setStatusTip(("Pinned to the toolbar " if pinned else "Right-click to pin it to the toolbar ")
                            + KIND_WORDS[kind])
        action.setEnabled(window.is_enabled(item.command))
        action.setData(item.key)
        action.setProperty("studioPin", (self, kind, item.key))
        action.triggered.connect(functools.partial(self._pick, item))

    def _pick(self, item, *_):
        if item.tool:  # a way: the toolbar's button draws it from now on too
            self._window.choose_way(item.tool, item.way)
        self._window.run_tool(item.command, item.method, item.settings, item.index)

    # -- pins ----------------------------------------------------------------------------------
    def pin_menu(self, kind, key, where):
        """The menu a right-click on a group's tool opens: pin it for `kind`, or unpin it."""
        menu = QtWidgets.QMenu(self._window.top_bar)
        menu.setObjectName("StudioPinMenu")
        words = KIND_WORDS[kind]
        if self._groups.is_pinned(kind, key):
            menu.addAction(f"Unpin from toolbar {words}", lambda: self.unpin(kind, key))
        else:
            pin = menu.addAction(f"Pin to toolbar {words}", lambda: self.pin(kind, key))
            pin.setEnabled(self._groups.can_pin(kind, key))
        self._pin_target = (kind, key)
        try:
            menu.exec_(where)
        finally:
            self._pin_target = None
            menu.deleteLater()

    def pin(self, kind, key):
        if self._groups.pin(kind, key):
            self._window.schedule_refresh()

    def unpin(self, kind, key):
        if self._groups.unpin(kind, key):
            self._window.schedule_refresh()


class _RightClickFilter(QtCore.QObject):
    """A right-click on a group's tool opens the pin menu instead of running it."""

    def eventFilter(self, menu, event):
        kind = event.type()
        if kind not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.ContextMenu):
            return False
        if kind != QtCore.QEvent.ContextMenu and event.button() != Qt.RightButton:
            return False
        action = menu.actionAt(event.pos())
        target = action.property("studioPin") if action is not None else None
        if not target:
            return False
        if kind == QtCore.QEvent.MouseButtonRelease or kind == QtCore.QEvent.ContextMenu:
            bar, selection_kind, key = target
            where = event.globalPos()
            # Not from inside the menu's own event: the pin menu runs an event loop of its own.
            QtCore.QTimer.singleShot(0, lambda: bar.pin_menu(selection_kind, key, where))
        return True


_RIGHT_CLICK = _RightClickFilter()
_bar = None


def install_once():
    global _bar
    if _bar is None:
        from studio.interaction.keymap import Keymap
        from studio.shell import app, shortcuts, window
        from studio.viewmodels.tool_groups import ToolGroups

        studio_window = window.current()
        service = app.command_service()
        groups = ToolGroups(service.catalog, studio_window.toolbar_model(),
                            Keymap(service.catalog, app.settings()), app.settings())

        def contexts():
            return shortcuts._handler.contexts if shortcuts._handler is not None else []

        studio_window.use_pins(groups)
        _bar = GroupBar(studio_window, groups, contexts)
        _bar.install()
    return _bar


def current():
    return _bar
