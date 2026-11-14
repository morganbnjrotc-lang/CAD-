# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keyboard shortcuts in the shell (studio.shell.shortcuts), docs/adr/0008-keymap-contexts.md.

Studio claims the keys its keymap binds through an application-wide event filter (as FreeCAD's own
ShortcutManager does), so a shortcut works before its command's module is loaded and never fights
FreeCAD's menu actions. Key events are sent straight to widgets, so the tests don't depend on which
window Windows considers active. The command service is a fake that records what would run.
"""

import types
import unittest
import uuid

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.interaction.keymap import Keymap
from studio.services.commands import CommandCatalog
from studio.services.settings import Settings
from studio.shell.shortcuts import EditContextObserver, ShortcutHandler, chord_from_event

from ..test_keymap import CATALOG

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


class FakeService:
    def __init__(self):
        self.ran = []
        self.catalog = CommandCatalog(CATALOG)

    def run(self, name):
        self.ran.append(name)


def key_event(kind, key, modifiers=QtCore.Qt.NoModifier, text=""):
    return QtGui.QKeyEvent(kind, key, modifiers, text)


def press(widget, key, modifiers=QtCore.Qt.NoModifier, text=""):
    """What Qt does for a key press: ShortcutOverride first, then KeyPress if nobody took it as a
    shortcut. Returns whether the override was accepted (the key was claimed)."""
    override = key_event(QtCore.QEvent.ShortcutOverride, key, modifiers, text)
    override.ignore()
    QtWidgets.QApplication.sendEvent(widget, override)
    QtWidgets.QApplication.sendEvent(widget, key_event(QtCore.QEvent.KeyPress, key, modifiers, text))
    QtWidgets.QApplication.sendEvent(widget, key_event(QtCore.QEvent.KeyRelease, key, modifiers, text))
    return override.isAccepted()


def settle():
    for _ in range(3):
        QtWidgets.QApplication.processEvents()


class Chords(unittest.TestCase):
    def test_key_events_become_keymap_text(self):
        Qt = QtCore.Qt
        cases = [
            ((Qt.Key_E, Qt.NoModifier), "E"),
            ((Qt.Key_F, Qt.ShiftModifier), "Shift+F"),
            ((Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier), "Ctrl+Shift+Z"),
            ((Qt.Key_F11, Qt.NoModifier), "F11"),
            ((Qt.Key_Escape, Qt.NoModifier), "Esc"),
            ((Qt.Key_Backtab, Qt.ShiftModifier), "Shift+Tab"),  # Qt reports Shift+Tab as Backtab
            ((Qt.Key_3, Qt.KeypadModifier), "3"),
        ]
        for (key, modifiers), expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(chord_from_event(key_event(QtCore.QEvent.KeyPress, key, modifiers)), expected)

    def test_modifier_keys_alone_are_not_chords(self):
        for key in (QtCore.Qt.Key_Shift, QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            with self.subTest(key=key):
                self.assertIsNone(chord_from_event(key_event(QtCore.QEvent.KeyPress, key)))


def detach_session_handler(testcase):
    """Take the session's real handler (installed when Studio activates) out of the way, so a
    test's synthetic key presses can't run real commands."""
    from studio.shell import shortcuts

    session = shortcuts._handler  # never create it here: SessionShortcuts checks Studio did
    if session is not None:
        session.remove()
        testcase.addCleanup(session.install)


class Handler(unittest.TestCase):
    def setUp(self):
        detach_session_handler(self)
        name = "Shortcuts" + uuid.uuid4().hex[:8]
        settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.service = FakeService()
        self.handler = ShortcutHandler(lambda: Keymap(self.service.catalog, settings), self.service)
        self.handler.install()
        self.addCleanup(self.handler.remove)
        main_window = FreeCADGui.getMainWindow()
        self.target = QtWidgets.QWidget(main_window)  # stands in for the 3D view
        self.addCleanup(self.target.deleteLater)

    def test_a_bound_key_runs_its_command(self):
        self.assertTrue(press(self.target, QtCore.Qt.Key_E, text="e"))
        settle()
        self.assertEqual(self.service.ran, ["PartDesign_Pad"])

    def test_shift_f_fits_all(self):
        press(self.target, QtCore.Qt.Key_F, QtCore.Qt.ShiftModifier, "F")
        settle()
        self.assertEqual(self.service.ran, ["Std_ViewFitAll"])

    def test_unbound_keys_are_left_alone(self):
        self.assertFalse(press(self.target, QtCore.Qt.Key_Q, text="q"))
        settle()
        self.assertEqual(self.service.ran, [])

    def test_typing_in_a_text_field_never_triggers_shortcuts(self):
        field = QtWidgets.QLineEdit(FreeCADGui.getMainWindow())
        self.addCleanup(field.deleteLater)
        press(field, QtCore.Qt.Key_E, text="e")  # the field itself claims printable keys (Qt's way)
        settle()
        self.assertEqual(self.service.ran, [])
        self.assertEqual(field.text(), "e")

    def test_contexts_change_what_keys_mean(self):
        self.handler.set_contexts(["SketcherWorkbench"])
        press(self.target, QtCore.Qt.Key_E, text="e")
        press(self.target, QtCore.Qt.Key_G, text="g")
        press(self.target, QtCore.Qt.Key_L, text="l")
        self.handler.set_contexts([])
        press(self.target, QtCore.Qt.Key_E, text="e")
        self.assertFalse(press(self.target, QtCore.Qt.Key_G, text="g"))
        settle()
        self.assertEqual(self.service.ran, ["Sketcher_ConstrainEqual", "Sketcher_CreateLine", "PartDesign_Pad"])

    def test_keys_freecads_menu_actions_also_have_are_claimed_and_run_once(self):
        # "V, F" is also on FreeCAD's View menu action. Studio claims both keys (so Qt never hands
        # them to that action) and runs the command itself, once (ADR 0008 point 7).
        self.assertTrue(press(self.target, QtCore.Qt.Key_V, text="v"))
        self.assertTrue(press(self.target, QtCore.Qt.Key_F, text="f"))
        settle()
        self.assertEqual(self.service.ran, ["Std_ViewFitAll"])

    def test_nothing_is_claimed_while_a_modal_dialog_is_open(self):
        dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
        dialog.setModal(True)
        dialog.show()
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        settle()
        self.assertFalse(press(self.target, QtCore.Qt.Key_E, text="e"))
        settle()
        self.assertEqual(self.service.ran, [])

    def test_windows_outside_the_main_window_are_left_alone(self):
        floating = QtWidgets.QWidget()  # e.g. a separate tool window
        self.addCleanup(floating.deleteLater)
        self.assertFalse(press(floating, QtCore.Qt.Key_E, text="e"))
        settle()
        self.assertEqual(self.service.ran, [])

    def test_a_failing_command_does_not_break_later_keys(self):
        def run(name):
            self.service.ran.append(name)
            raise RuntimeError("command failed")

        self.service.run = run
        press(self.target, QtCore.Qt.Key_E, text="e")
        settle()
        press(self.target, QtCore.Qt.Key_F, text="f")
        settle()
        self.assertEqual(self.service.ran, ["PartDesign_Pad", "Std_ViewFitSelection"])


class SessionShortcuts(unittest.TestCase):
    """The handler Studio installs when its workbench activates, with the real keymap."""

    def test_studio_installs_it_and_shift_f_reaches_the_session_command_service(self):
        from studio.shell import app, shortcuts

        self.assertIsNotNone(shortcuts._handler, "not installed when Studio activated")
        service = app.command_service()
        ran = []
        service.run = ran.append  # record instead of running
        self.addCleanup(delattr, service, "run")
        target = QtWidgets.QWidget(FreeCADGui.getMainWindow())
        self.addCleanup(target.deleteLater)

        self.assertTrue(press(target, QtCore.Qt.Key_F, QtCore.Qt.ShiftModifier, "F"))
        settle()

        self.assertEqual(ran, ["Std_ViewFitAll"])


class EditContexts(unittest.TestCase):
    def test_editing_a_sketch_or_an_assembly_switches_context(self):
        contexts = []
        observer = EditContextObserver(lambda active: contexts.append(list(active)))

        def provider(type_id):
            return types.SimpleNamespace(Object=types.SimpleNamespace(TypeId=type_id))

        observer.slotInEdit(provider("Sketcher::SketchObject"))
        observer.slotResetEdit(provider("Sketcher::SketchObject"))
        observer.slotInEdit(provider("Assembly::AssemblyObject"))
        observer.slotInEdit(provider("PartDesign::Pad"))  # no context of its own
        self.assertEqual(contexts, [["SketcherWorkbench"], [], ["AssemblyWorkbench"], []])
