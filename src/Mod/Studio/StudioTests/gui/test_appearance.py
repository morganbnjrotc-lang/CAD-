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
from PySide import QtCore, QtGui, QtWidgets  # FreeCAD's PySide shim

from studio.services import theme
from studio.services.settings import Settings
from studio.shell.appearance import Appearance

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
WINDOW = QtGui.QPalette.Window


def window_color():
    return QtWidgets.QApplication.palette().color(WINDOW).name().upper()


def pixel(widget, x, y):
    """The color the widget draws at (x, y), rendered off screen."""
    image = widget.grab().toImage()
    return image.pixelColor(x, y).name().upper()


def ink(image):
    """The color of an icon's strokes (a QImage): the average of its pixels, weighted by how opaque
    each is. Thin strokes are anti-aliased (FreeCAD's 12 px title icons have hardly a fully opaque
    pixel), and turning a premultiplied color back into a plain one rounds by a unit or two."""
    sums, weight = [0, 0, 0], 0
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            a = color.alpha()
            if a:
                sums = [sums[0] + color.red() * a, sums[1] + color.green() * a, sums[2] + color.blue() * a]
                weight += a
    return "#" + "".join(f"{round(s / weight):02X}" for s in sums) if weight else None


def near(a, b, units=3):
    """Two "#RRGGBB" colors within `units` per channel (see ink)."""
    if a is None or b is None:
        return False
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= units for i in (1, 3, 5))


def panel_style():
    """What FreeCAD's panels show, read in C++ (StudioGui): Python wrappers of some FreeCAD widgets
    make FreeCAD abort when it exits (docs/BASELINE.md), so the tests don't look them up either."""
    import StudioGui

    return StudioGui.panel_style()


def restore_session_look():
    from studio.shell import appearance

    if appearance.current() is not None:
        appearance.current().apply()


class _OwnAppearance(unittest.TestCase):
    """An Appearance of the test's own: a stand-in for Windows' mode, a test copy of the color settings."""

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


class AppearanceTest(_OwnAppearance):
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

    def test_studios_widgets_follow_the_look(self):
        seen = []
        self.appearance.set_mode("dark")
        self.appearance.follow(seen.append)
        self.assertEqual(seen, [theme.DARK])  # right away
        self.appearance.set_mode("light")
        self.assertEqual(seen, [theme.DARK, theme.LIGHT])

    def test_under_a_freecad_stylesheet_studios_widgets_keep_its_colors(self):
        seen = []
        self.freecad_stylesheet = True
        self.appearance.apply()
        self.appearance.follow(seen.append)
        self.assertEqual(seen, [None])  # None: draw with the app's palette, no colors of Studio's

    def test_a_deleted_widget_stops_following(self):
        label = QtWidgets.QLabel()
        self.appearance.apply()
        self.appearance.follow(lambda p: label.setText(p.name))
        label.deleteLater()
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        self.appearance.set_mode("dark")  # must not raise


class FreeCADPanels(_OwnAppearance):
    """FreeCAD's own panels, styled where the palette alone can't reach (the session's window)."""

    def test_property_group_rows_stand_out_and_read(self):
        for p in (theme.DARK, theme.LIGHT):
            self.appearance.set_mode(p.name)
            rows = panel_style()["group_rows"]
            self.assertTrue(rows)
            for background, text in rows:
                self.assertNotIn(background, (p.panel, p.window), p.name)
                ratio = theme.contrast(text, background)
                self.assertGreaterEqual(ratio, 4.5, f"{p.name}: group text {text} on {background} is {ratio:.2f}:1")

    def test_the_property_area_is_flat(self):
        # Fusion draws a tab box's frame a shade lighter than the panel: a grey box in dark mode.
        self.appearance.apply()
        flat = panel_style()["flat_property_area"]
        self.assertTrue(flat)
        self.assertTrue(all(flat))

    def test_status_bar_text_follows_a_switch(self):
        # FreeCAD gives its status bar a stylesheet (to color its messages); under one, Qt keeps each
        # label's palette as it was, so after a switch the labels kept the old mode's text color.
        for p in (theme.DARK, theme.LIGHT):
            self.appearance.set_mode(p.name)
            labels = panel_style()["status_labels"]
            self.assertTrue(labels)
            self.assertEqual({name: color for name, color in labels if color != p.text}, {}, p.name)

    def test_panel_title_buttons_are_drawn_in_the_secondary_text_color(self):
        for p in (theme.DARK, theme.LIGHT):
            self.appearance.set_mode(p.name)
            icons = panel_style()["title_icons"]
            self.assertEqual(set(icons), {"OBTN Float", "OBTN Overlay", "OBTN Close"})
            for name, png in icons.items():
                color = ink(QtGui.QImage.fromData(png))
                self.assertTrue(near(color, p.muted), f"{p.name}: {name} is {color}")


class SessionAppearance(unittest.TestCase):
    def setUp(self):
        from studio.shell import appearance

        self.appearance = appearance.current()

    def test_studio_uses_fusion_and_its_palette(self):
        self.assertIsNotNone(self.appearance, "Studio did not set up its look")
        self.assertEqual(QtWidgets.QApplication.style().name().lower(), "fusion")
        self.assertEqual(window_color(), theme.palette(self.appearance.mode).window)

    def test_freecads_lists_paint_their_background(self):
        # The model tree and the property editors on the palette's list color. Built in Windows 11's
        # own style and then switched to Fusion, Qt left them unpainted: on Windows 11 only, they
        # showed the window color behind them (caught by the visual baselines on CI's Windows Server).
        views = panel_style()["views"]
        self.assertTrue(views)
        self.assertEqual([name for name, painted in views if not painted], [])

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


class StudioWidgets(unittest.TestCase):
    """Studio's own bars in the session's window, in each mode."""

    def setUp(self):
        from studio.shell import window

        self.addCleanup(restore_session_look)
        self.window = window.current()

    def test_bars_use_the_palette(self):
        for p in (theme.DARK, theme.LIGHT):
            self.window.restyle(p)
            for bar in (self.window.top_bar, self.window.tools):
                self.assertEqual(pixel(bar, bar.width() // 2, 2), p.window, f"{p.name}: {bar.objectName()}")

    def test_search_looks_like_a_field(self):
        button = self.window.search_button
        for p in (theme.DARK, theme.LIGHT):
            self.window.restyle(p)
            self.assertEqual(pixel(button, 8, button.height() // 2), p.field, p.name)

    def test_the_hint_is_secondary_text(self):
        hint = self.window.hint
        for p in (theme.DARK, theme.LIGHT):
            self.window.restyle(p)
            self.assertEqual(hint.palette().color(hint.foregroundRole()).name().upper(), p.muted, p.name)
