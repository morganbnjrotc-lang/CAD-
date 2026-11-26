# SPDX-License-Identifier: LGPL-2.1-or-later
"""The command palette window (studio.shell.palette), PLAN 2.5.

Opened with S or Ctrl+K (Studio_CommandPalette). Type to filter; Up/Down choose; Enter runs; Esc
closes. Runs through a recording fake service, except the wiring test at the end.
"""

import os
import unittest
import uuid

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.interaction.keymap import Keymap
from studio.services.commands import CommandCatalog
from studio.services.settings import Settings
from studio.shell.palette import PaletteWindow, icon_file
from studio.viewmodels.palette import Palette

from ..test_palette import CATALOG
from .test_shortcuts import settle

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


class FakeService:
    def __init__(self):
        self.ran = []

    def run(self, name):
        self.ran.append(name)


def key(widget, code):
    for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        QtWidgets.QApplication.sendEvent(widget, QtGui.QKeyEvent(kind, code, QtCore.Qt.NoModifier))


class PaletteWindowTest(unittest.TestCase):
    def setUp(self):
        name = "PaletteWindow" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        catalog = CommandCatalog(CATALOG)
        self.palette = Palette(catalog, Keymap(catalog, self.settings), self.settings)
        self.service = FakeService()
        self.window = PaletteWindow(self.palette, self.service, FreeCADGui.getMainWindow())
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)

    def shown(self):
        return [self.window.results.topLevelItem(i).data(0, QtCore.Qt.UserRole)
                for i in range(self.window.results.topLevelItemCount())]

    def test_typing_filters_and_enter_runs_the_best_match(self):
        self.window.open()
        self.window.search.setText("pad")
        self.assertEqual(self.shown()[0], "PartDesign_Pad")
        key(self.window.search, QtCore.Qt.Key_Return)
        settle()
        self.assertEqual(self.service.ran, ["PartDesign_Pad"])
        self.assertFalse(self.window.isVisible())

    def test_arrow_keys_choose_another_match(self):
        self.window.open()
        self.window.search.setText("dimension")
        self.assertEqual(self.shown(), ["Sketcher_Dimension", "TechDraw_Dimension"])
        key(self.window.search, QtCore.Qt.Key_Down)
        key(self.window.search, QtCore.Qt.Key_Return)
        settle()
        self.assertEqual(self.service.ran, ["TechDraw_Dimension"])

    def test_escape_closes_without_running_anything(self):
        self.window.open()
        self.window.search.setText("pad")
        key(self.window.search, QtCore.Qt.Key_Escape)
        settle()
        self.assertEqual(self.service.ran, [])
        self.assertFalse(self.window.isVisible())

    def test_rows_show_title_category_and_shortcut(self):
        self.window.open()
        self.window.search.setText("fit all")
        row = self.window.results.topLevelItem(0)
        self.assertEqual([row.text(c) for c in range(3)], ["Fit All", "General", "Shift+F"])

    def test_tools_with_a_studio_drawing_show_it_in_the_text_color(self):
        from studio.services import theme

        from .test_appearance import ink, near

        catalog = CommandCatalog.load()  # the shipped one: the test catalog's commands have no icons
        window = PaletteWindow(Palette(catalog, Keymap(catalog, self.settings), self.settings), self.service,
                               FreeCADGui.getMainWindow())
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        for p in (theme.DARK, theme.LIGHT):
            window.restyle(p)
            window.open()
            window.search.setText("pad")
            row = window.results.topLevelItem(0)
            self.assertEqual(row.data(0, QtCore.Qt.UserRole), "PartDesign_Pad")
            color = ink(row.icon(0).pixmap(32, 32).toImage())
            self.assertTrue(near(color, p.text), f"{p.name}: {color}")

    def test_reopening_starts_empty_with_recently_used_first(self):
        self.window.open()
        self.window.search.setText("pocket")
        key(self.window.search, QtCore.Qt.Key_Return)
        settle()
        self.window.open()
        self.assertEqual(self.window.search.text(), "")
        self.assertEqual(self.shown()[0], "PartDesign_Pocket")


class Icons(unittest.TestCase):
    def test_catalog_icons_are_installed_with_studio(self):
        # The catalog names each icon's source SVG; the build copies them next to Studio so the
        # palette shows icons of commands whose module isn't loaded yet.
        path = icon_file("src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg")
        self.assertTrue(os.path.isfile(path), path)
        self.assertIsNone(icon_file(None))

    def test_a_command_studio_has_no_drawing_for_shows_in_one_color(self):
        # FreeCAD's icon in the text color until its phase gets a drawing (the user's pick, 2026-11-26:
        # "the icons need to be updated to match the new aesthetic, also in the search")
        from studio.services import theme
        from studio.shell import palette

        FreeCADGui.runCommand("Studio_CommandPalette")
        settle()
        window = palette.current_window()
        self.addCleanup(window.close)
        for look in (theme.LIGHT, theme.DARK):
            window.restyle(look)
            window.search.setText("")  # typed again: the rows are made in this look
            window.search.setText("Print")  # Std_Print: FreeCAD's printer, in its colors
            settle()
            rows = [window.results.topLevelItem(i) for i in range(window.results.topLevelItemCount())]
            row = next(r for r in rows if r.data(0, QtCore.Qt.UserRole) == "Std_Print")
            # plain colors: a premultiplied image's pixels read darker where they are see-through
            image = row.icon(0).pixmap(32, 32).toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
            pixels = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())]
            colors = {c.name() for c in pixels if c.alpha() > 160}
            self.assertTrue(colors, "no icon")
            # one color: shrinking the icon to 32 px rounds each pixel's by a few units, FreeCAD's printer
            # in its own colors is far from the text color
            from .test_appearance import near

            off = {c for c in colors if not near(c, QtGui.QColor(look.text).name(), units=8)}
            self.assertEqual(off, set(), f"{look.name}: text {look.text}, icon {sorted(colors)}")


class Wiring(unittest.TestCase):
    def test_s_and_ctrl_k_open_the_palette_from_the_studio_command(self):
        from studio.interaction.keymap import GLOBAL, STUDIO_DEFAULTS
        from studio.shell import palette, shortcuts

        self.assertIsNotNone(FreeCADGui.Command.get("Studio_CommandPalette"))
        self.assertEqual(STUDIO_DEFAULTS[GLOBAL]["S"], "Studio_CommandPalette")
        self.assertEqual(STUDIO_DEFAULTS[GLOBAL]["Ctrl+K"], "Studio_CommandPalette")
        self.assertIsNotNone(shortcuts._handler)

        FreeCADGui.runCommand("Studio_CommandPalette")
        settle()
        window = palette.current_window()
        self.addCleanup(window.close)
        self.assertTrue(window.isVisible())
