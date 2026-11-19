# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keyboard shortcuts (docs/adr/0008-keymap-contexts.md).

`ShortcutHandler` hooks an application-wide event filter, as FreeCAD's own ShortcutManager does. The
filter is Studio's C++ `StudioGui.add_key_filter`: every event of the app passes through it, so
only key events reach Python (a Python filter added ~2.5 us to every event). When Qt asks whether a
widget wants a key before treating it as a shortcut (ShortcutOverride), the handler claims every key
the active keymap binds, including ones FreeCAD's menu actions also have (it runs the same
command); the key press then comes to the handler, which runs the command through the command
service. That works before a command's module is loaded, and a claimed key never reaches a second
owner. Leaving some keys to FreeCAD's actions instead breaks sequences: with "V, S" Studio's and
"V, F" FreeCAD's, Studio must claim "V" and FreeCAD's sequence could never complete. Keys the keymap
doesn't bind go their usual way.

Keys are left alone in text fields, while a modal dialog is open, and outside the main window (the
C++ filter checks). The size boxes a sketch tool shows in the 3D view are text fields too, but FreeCAD
passes letter keys from them to the 3D view until a number is typed, so sketch keys (X for construction)
work in the middle of a shape. `EditContextObserver` switches the keymap context while a sketch or an
assembly is being edited.
"""

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui  # FreeCAD's PySide shim

from studio.interaction.keymap import SequenceMatcher, normalize


def _value(enum) -> int:
    """The integer of a Qt enum or flag (PySide6 enums are Python enums)."""
    return enum.value if hasattr(enum, "value") else int(enum)


Qt = QtCore.Qt
_MODIFIER_KEYS = {_value(k) for k in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr,
                                      Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock, Qt.Key_unknown)}
_MODIFIER_NAMES = tuple((_value(flag), name) for flag, name in (
    (Qt.ControlModifier, "Ctrl"), (Qt.AltModifier, "Alt"), (Qt.ShiftModifier, "Shift"), (Qt.MetaModifier, "Meta")))
_BACKTAB, _TAB, _SHIFT = _value(Qt.Key_Backtab), _value(Qt.Key_Tab), _value(Qt.ShiftModifier)
_SHORTCUT_OVERRIDE = _value(QtCore.QEvent.ShortcutOverride)
_KEY_PRESS = _value(QtCore.QEvent.KeyPress)

# Object being edited -> keymap context (ADR 0008 point 2).
EDIT_CONTEXTS = {
    "Sketcher::SketchObject": "SketcherWorkbench",
    "Assembly::AssemblyObject": "AssemblyWorkbench",
}


def chord_from_key(key: int, modifiers: int):
    """The keymap text of a key press ("Shift+F"), or None for a modifier key alone."""
    if key in _MODIFIER_KEYS or key == 0:
        return None
    if key == _BACKTAB:  # Qt's name for Shift+Tab
        key, modifiers = _TAB, modifiers | _SHIFT
    names = [name for flag, name in _MODIFIER_NAMES if modifiers & flag]
    text = QtGui.QKeySequence(key).toString(QtGui.QKeySequence.PortableText)
    try:
        return normalize("+".join(names + [text]))
    except ValueError:
        return None


def chord_from_event(event):
    return chord_from_key(event.key(), _value(event.modifiers()))


def _live_is_active(command: str) -> bool:
    """Whether FreeCAD's command is active now. A command whose module isn't loaded yet counts as
    active: pressing its key loads it (docs/adr/0007)."""
    live = FreeCADGui.Command.get(command)
    if live is None:
        return True
    try:
        return bool(live.isActive())
    except Exception:
        return False  # let the key through rather than guess


class ShortcutHandler:
    def __init__(self, keymap_factory, service, is_active=_live_is_active):
        """`keymap_factory()` builds the Keymap when the first key arrives (not during startup).
        `is_active(command)`: like Qt with a disabled action, a key whose command is inactive is
        left to the widget. FreeCAD binds Esc to Std_ToggleNavigation, active only in a rare
        editing mode; otherwise Esc must reach the tool or task panel, which cancel with it."""
        self._keymap_factory = keymap_factory
        self._keymap = None
        self._service = service
        self._is_active = is_active
        self._contexts = []
        self._matcher = None
        self._filter = None

    def install(self):
        import StudioGui  # Studio's C++ helpers

        if self._filter is None:
            self._filter = StudioGui.add_key_filter(self._on_key)

    def remove(self):
        import StudioGui

        if self._filter is not None:
            StudioGui.remove_key_filter(self._filter)
            self._filter = None

    @property
    def contexts(self) -> list:
        """The active keymap contexts, most specific first (Global is implied)."""
        return list(self._contexts)

    def set_contexts(self, contexts):
        self._contexts = list(contexts)
        self._matcher = None

    def reload(self):
        """Re-read the keymap (after the user changed bindings)."""
        self._keymap = None
        self._matcher = None

    def _active(self):
        if self._matcher is None:
            if self._keymap is None:
                self._keymap = self._keymap_factory()
            self._matcher = SequenceMatcher(self._keymap.active_bindings(self._contexts))
        return self._matcher

    def _on_key(self, kind: int, key: int, modifiers: int) -> bool:
        """Called by the C++ key filter; True claims the key."""
        if kind not in (_SHORTCUT_OVERRIDE, _KEY_PRESS):
            return False
        chord = chord_from_key(key, modifiers)
        if chord is None:
            return False
        try:
            matcher = self._active()
        except Exception as exc:
            FreeCAD.Console.PrintError(f"Studio shortcuts: could not load the keymap: {exc}\n")
            return False
        state, command = matcher.peek(chord)
        if state == "run" and not self._is_active(command):
            state = "none"
        if kind == _SHORTCUT_OVERRIDE:
            return state != "none"  # the C++ filter accepts it: the key press comes to us next
        if state == "none":
            matcher.reset()
            return False
        state, command = matcher.feed(chord)
        if state == "run":
            # Run outside the event filter: commands may open dialogs or task panels.
            QtCore.QTimer.singleShot(0, lambda: self._run(command))
        return True

    def _run(self, command):
        try:
            self._service.run(command)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"Studio shortcut: {command} failed: {exc}\n")


class EditContextObserver:
    """A FreeCADGui document observer: reports the keymap context while an object is edited."""

    def __init__(self, on_change):
        self._on_change = on_change

    def slotInEdit(self, view_provider):
        type_id = getattr(getattr(view_provider, "Object", None), "TypeId", "")
        context = EDIT_CONTEXTS.get(type_id)
        self._on_change([context] if context else [])

    def slotResetEdit(self, view_provider):
        self._on_change([])


class _SessionService:
    """The session's command service, created on first use rather than during startup."""

    def run(self, name):
        from studio.shell import app

        app.command_service().run(name)

    @property
    def catalog(self):
        from studio.shell import app

        return app.command_service().catalog


_handler = None


def install_once():
    """Installs the session's shortcut handler and edit-context observer (once)."""
    global _handler
    if _handler is None:
        from studio.interaction.keymap import Keymap
        from studio.shell import app

        service = _SessionService()
        _handler = ShortcutHandler(lambda: Keymap(service.catalog, app.settings()), service)
        _handler.install()
        FreeCADGui.addDocumentObserver(EditContextObserver(_handler.set_contexts))
    return _handler
