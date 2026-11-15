# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's look in the running app (studio.shell.appearance, ADR 0010, PLAN 2.9).

Qt's Fusion style with Studio's palette, FreeCAD's 3D and sketch colors, following Windows' light or
dark mode unless the user picks one in the ☰ menu. Most tests use their own Appearance with a stand-in
for Windows' mode and a test copy of FreeCAD's color settings; the session tests check the one Studio
sets up.
"""

import unittest
import uuid

import FreeCAD
from PySide import QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import theme
from studio.services.settings import Settings
from studio.shell.appearance import Appearance

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
WINDOW = QtGui.QPalette.Window


def window_color():
    return QtWidgets.QApplication.palette().color(WINDOW).name().upper()


def restore_session_look():
    from studio.shell import appearance

    if appearance.current() is not None:
        appearance.current().apply()


class AppearanceTest(unittest.TestCase):
    def setUp(self):
        name = "Appearance" + uuid.uuid4().hex[:8]
        self.root = f"{TEST_PARENT}/{name}"
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.addCleanup(restore_session_look)
        self.settings = Settings(f"{self.root}/Studio")
        self.windows_dark = False
        self.freecad_stylesheet = False
        self.appearance = Appearance(
            self.settings,
            theme.FreeCADColors(self.settings, root=f"{self.root}/Prefs"),
            system_is_dark=lambda: self.windows_dark,
            freecad_stylesheet=lambda: self.freecad_stylesheet,
        )
        self.view = FreeCAD.ParamGet(f"{self.root}/Prefs/View")

    def test_follows_windows(self):
        self.windows_dark = True
        self.appearance.apply()
        self.assertEqual(self.appearance.mode, "dark")
        self.assertEqual(window_color(), theme.DARK.window)
        self.assertEqual(self.view.GetUnsigned("BackgroundColor2", 0), theme.rgba(theme.DARK.view_top))
        self.windows_dark = False
        self.appearance.system_scheme_changed()  # Windows switched to light while the app runs
        self.assertEqual(self.appearance.mode, "light")
        self.assertEqual(window_color(), theme.LIGHT.window)

    def test_a_picked_mode_ignores_windows(self):
        self.appearance.set_mode("dark")
        self.assertEqual(self.settings.get(theme.MODE), "dark")
        self.windows_dark = False
        self.appearance.system_scheme_changed()
        self.assertEqual(self.appearance.mode, "dark")
        self.assertEqual(window_color(), theme.DARK.window)

    def test_selected_rows_use_a_soft_accent_with_readable_text(self):
        self.appearance.set_mode("light")
        palette = QtWidgets.QApplication.palette()
        highlight = palette.color(QtGui.QPalette.Highlight).name().upper()
        text = palette.color(QtGui.QPalette.HighlightedText).name().upper()
        self.assertNotEqual(highlight, theme.LIGHT.accent)
        self.assertGreaterEqual(theme.contrast(text, highlight), 4.5)

    def test_a_freecad_stylesheet_the_user_picked_keeps_its_colors(self):
        self.freecad_stylesheet = True
        mine = QtGui.QPalette(QtWidgets.QApplication.palette())
        mine.setColor(WINDOW, QtGui.QColor("#123456"))
        QtWidgets.QApplication.setPalette(mine)
        self.appearance.set_mode("dark")
        self.assertEqual(window_color(), "#123456")
        self.assertEqual(self.view.GetUnsigned("SelectionColor", 0), theme.rgba(theme.DARK.accent))  # 3D still ours

    def test_appearance_menu(self):
        menu = self.appearance.build_menu()
        self.addCleanup(menu.deleteLater)
        self.assertEqual(menu.title(), "Appearance")
        actions = {a.text(): a for a in menu.actions()}
        self.assertEqual(list(actions), ["Follow Windows", "Light", "Dark"])
        self.assertTrue(actions["Follow Windows"].isChecked())
        actions["Dark"].trigger()
        self.assertEqual(self.settings.get(theme.MODE), "dark")
        self.assertEqual(window_color(), theme.DARK.window)
        menu.aboutToShow.emit()
        self.assertEqual([a.text() for a in menu.actions() if a.isChecked()], ["Dark"])


class SessionAppearance(unittest.TestCase):
    def setUp(self):
        from studio.shell import appearance

        self.appearance = appearance.current()

    def test_studio_uses_fusion_and_its_palette(self):
        self.assertIsNotNone(self.appearance, "Studio did not set up its look")
        self.assertEqual(QtWidgets.QApplication.style().name().lower(), "fusion")
        self.assertEqual(window_color(), theme.palette(self.appearance.mode).window)

    def test_the_3d_view_uses_the_palette(self):
        view = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        p = theme.palette(self.appearance.mode)
        self.assertTrue(view.GetBool("Gradient", False))
        self.assertEqual(view.GetUnsigned("SelectionColor", 0), theme.rgba(p.accent))

    def test_the_menu_offers_appearance(self):
        from studio.shell import window

        menu = QtWidgets.QMenu()
        self.addCleanup(menu.deleteLater)
        window.current()._fill_menu(menu)
        titles = [a.text() for a in menu.actions() if a.menu() is not None]
        self.assertIn("Appearance", titles)
