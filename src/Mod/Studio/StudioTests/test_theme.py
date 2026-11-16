# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's look (ADR 0010, PLAN 2.9): two palettes, the mode, and FreeCAD's color settings.

studio.services.theme holds the light and dark colors, picks the mode (Windows' or the user's), and
writes the 3D view and sketch colors into FreeCAD's settings without overwriting colors the user set.
"""

import colorsys
import unittest
import uuid

import FreeCAD

from studio.services import theme
from studio.services.settings import Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


def hue(color):
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


class Mode(unittest.TestCase):
    def setUp(self):
        name = "Theme" + uuid.uuid4().hex[:8]
        self.settings = Settings(f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))

    def test_follows_windows_by_default(self):
        self.assertEqual(self.settings.get(theme.MODE), "system")
        self.assertEqual(theme.current_mode(self.settings, system_is_dark=True), "dark")
        self.assertEqual(theme.current_mode(self.settings, system_is_dark=False), "light")

    def test_a_mode_the_user_picks_wins_over_windows(self):
        self.settings.set(theme.MODE, "light")
        self.assertEqual(theme.current_mode(self.settings, system_is_dark=True), "light")
        self.settings.set(theme.MODE, "dark")
        self.assertEqual(theme.current_mode(self.settings, system_is_dark=False), "dark")

    def test_palette_per_mode(self):
        self.assertIs(theme.palette("light"), theme.LIGHT)
        self.assertIs(theme.palette("dark"), theme.DARK)
        with self.assertRaises(ValueError):
            theme.palette("sepia")


class Palettes(unittest.TestCase):
    PANELS = ("window", "panel")

    def test_the_users_accents_teal_in_light_orange_in_dark(self):
        self.assertTrue(160 <= hue(theme.LIGHT.accent) <= 190, theme.LIGHT.accent)
        self.assertTrue(15 <= hue(theme.DARK.accent) <= 35, theme.DARK.accent)

    def test_text_reads_on_every_panel(self):  # WCAG AA for normal text: 4.5:1
        for p in (theme.LIGHT, theme.DARK):
            for surface in self.PANELS:
                for text in ("text", "muted"):
                    ratio = theme.contrast(getattr(p, text), getattr(p, surface))
                    self.assertGreaterEqual(ratio, 4.5, f"{p.name}: {text} on {surface} is {ratio:.2f}:1")

    def test_button_text_reads_on_the_accent(self):
        for p in (theme.LIGHT, theme.DARK):
            ratio = theme.contrast(p.on_accent, p.accent)
            self.assertGreaterEqual(ratio, 4.5, f"{p.name}: {ratio:.2f}:1")

    def test_selected_rows_are_a_soft_accent_with_readable_text(self):
        for p in (theme.LIGHT, theme.DARK):
            self.assertNotEqual(p.selection, p.accent)
            self.assertGreaterEqual(theme.contrast(p.text, p.selection), 4.5, p.name)

    def test_the_accent_stands_out_from_the_panels(self):  # WCAG AA for UI parts: 3:1
        for p in (theme.LIGHT, theme.DARK):
            for surface in self.PANELS:
                self.assertGreaterEqual(theme.contrast(p.accent, getattr(p, surface)), 3.0, p.name)

    def test_one_icon_grey_reads_in_both_modes(self):
        # FreeCAD caches the icons it draws (tree, menus), so they can't change with the mode (ADR 0010).
        for p in (theme.LIGHT, theme.DARK):
            for surface in self.PANELS:
                ratio = theme.contrast(theme.ICON_NEUTRAL, getattr(p, surface))
                self.assertGreaterEqual(ratio, 3.0, f"{p.name} {surface}: {ratio:.2f}:1")

    def test_soft_gradient_light_at_the_top(self):
        for p in (theme.LIGHT, theme.DARK):
            self.assertGreater(theme.luminance(p.view_top), theme.luminance(p.view_bottom), p.name)


class Colors(unittest.TestCase):
    def test_packs_colors_the_way_freecad_stores_them(self):
        self.assertEqual(theme.rgba("#00ABFF"), 0x00ABFFFF)
        self.assertEqual(theme.rgba("#333365"), 859006463)  # FreeCAD's default gradient top

    def test_mix(self):
        self.assertEqual(theme.mix("#000000", "#FFFFFF", 0.5), "#808080")
        self.assertEqual(theme.mix("#102030", "#102030", 0.3), "#102030")


class QtStyle(unittest.TestCase):
    """Fusion is set before the GUI starts (Init.py), so FreeCAD builds its window in it."""

    def setUp(self):
        name = "MainWindow" + uuid.uuid4().hex[:8]
        self.path = f"{TEST_PARENT}/{name}"
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.group = FreeCAD.ParamGet(self.path)

    def test_fusion_when_nothing_was_picked(self):
        self.assertTrue(theme.default_to_fusion(self.path, environ={}))
        self.assertEqual(self.group.GetString("QtStyle", ""), "Fusion")

    def test_a_style_the_user_picked_stays(self):
        self.group.SetString("QtStyle", "Windows")
        environ = {}
        self.assertFalse(theme.default_to_fusion(self.path, environ))
        self.assertEqual(self.group.GetString("QtStyle", ""), "Windows")
        self.assertNotIn("QT_STYLE_OVERRIDE", environ)

    def test_a_freecad_stylesheet_keeps_its_own_style(self):
        self.group.SetString("StyleSheet", "FreeCAD.qss")
        environ = {}
        self.assertFalse(theme.default_to_fusion(self.path, environ))
        self.assertEqual(self.group.GetString("QtStyle", ""), "")
        self.assertNotIn("QT_STYLE_OVERRIDE", environ)

    # FreeCAD builds its window first and applies the style in its preferences after. Built in
    # Windows 11's own style and then switched to Fusion, Qt leaves the model tree's and the property
    # editor's backgrounds unpainted. Qt starts in the style QT_STYLE_OVERRIDE names, read when FreeCAD
    # creates its application, which is after Init.py.
    def test_qt_starts_in_fusion(self):
        environ = {}
        theme.default_to_fusion(self.path, environ)
        self.assertEqual(environ.get("QT_STYLE_OVERRIDE"), "Fusion")

    def test_qt_starts_in_fusion_on_later_starts_too(self):
        self.group.SetString("QtStyle", "Fusion")  # what the first start wrote
        environ = {}
        theme.default_to_fusion(self.path, environ)
        self.assertEqual(environ.get("QT_STYLE_OVERRIDE"), "Fusion")

    def test_a_style_override_already_given_stays(self):
        environ = {"QT_STYLE_OVERRIDE": "windowsvista"}
        theme.default_to_fusion(self.path, environ)
        self.assertEqual(environ["QT_STYLE_OVERRIDE"], "windowsvista")


class FreeCADColorSettings(unittest.TestCase):
    """The 3D view and sketch colors, written into a test copy of FreeCAD's preferences."""

    def setUp(self):
        name = "Prefs" + uuid.uuid4().hex[:8]
        self.root = f"{TEST_PARENT}/{name}"
        self.settings = Settings(f"{TEST_PARENT}/{name}/Studio")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.colors = theme.FreeCADColors(self.settings, root=self.root)
        self.view = FreeCAD.ParamGet(f"{self.root}/View")

    def test_soft_gradient_background(self):
        self.colors.apply(theme.LIGHT)
        self.assertTrue(self.view.GetBool("Gradient", False))
        self.assertFalse(self.view.GetBool("Simple", True))
        self.assertFalse(self.view.GetBool("RadialGradient", True))
        self.assertEqual(self.view.GetUnsigned("BackgroundColor2", 0), theme.rgba(theme.LIGHT.view_top))
        self.assertEqual(self.view.GetUnsigned("BackgroundColor3", 0), theme.rgba(theme.LIGHT.view_bottom))

    def test_selection_uses_the_accent_and_hover_differs(self):
        self.colors.apply(theme.DARK)
        self.assertEqual(self.view.GetUnsigned("SelectionColor", 0), theme.rgba(theme.DARK.accent))
        self.assertNotEqual(self.view.GetUnsigned("HighlightColor", 0), self.view.GetUnsigned("SelectionColor", 0))

    def test_model_and_sketch_colors(self):
        self.colors.apply(theme.LIGHT)
        self.assertEqual(self.view.GetUnsigned("DefaultShapeColor", 0), theme.rgba(theme.LIGHT.model))
        self.assertEqual(self.view.GetUnsigned("DefaultShapeLineColor", 0), theme.rgba(theme.LIGHT.model_edge))
        self.assertEqual(self.view.GetUnsigned("FullyConstrainedColor", 0), theme.rgba(theme.LIGHT.sketch_done))
        self.assertEqual(self.view.GetUnsigned("ConstructionColor", 0), theme.rgba(theme.LIGHT.sketch_construction))
        grid = FreeCAD.ParamGet(f"{self.root}/Mod/Sketcher/General")
        self.assertEqual(grid.GetUnsigned("GridLineColor", 0), theme.rgba(theme.LIGHT.sketch_grid))

    def test_the_tree_marks_edited_and_active_items_with_the_accent(self):
        self.colors.apply(theme.DARK)
        tree = FreeCAD.ParamGet(f"{self.root}/TreeView")
        self.assertEqual(tree.GetUnsigned("TreeEditColor", 0), theme.rgba(theme.DARK.selection))
        active = tree.GetUnsigned("TreeActiveColor", 0)
        self.assertNotIn(active, (0, theme.rgba(theme.DARK.selection)))

    def test_status_and_report_text_reads_in_both_modes(self):
        # FreeCAD's message color (status bar, Report view) defaults to black: unreadable in dark.
        output = FreeCAD.ParamGet(f"{self.root}/OutputWindow")
        for p in (theme.DARK, theme.LIGHT):
            self.colors.apply(p)
            self.assertEqual(output.GetUnsigned("colorText", 0), theme.rgba(p.text), p.name)

    def test_switching_mode_rewrites_the_colors(self):
        self.colors.apply(theme.LIGHT)
        self.colors.apply(theme.DARK)
        self.assertEqual(self.view.GetUnsigned("BackgroundColor2", 0), theme.rgba(theme.DARK.view_top))

    def test_a_color_the_user_changed_stays(self):
        self.colors.apply(theme.LIGHT)
        mine = theme.rgba("#FF00FF")
        self.view.SetUnsigned("SelectionColor", mine)  # picked in Preferences > Display
        written = self.colors.apply(theme.DARK)
        self.assertEqual(self.view.GetUnsigned("SelectionColor", 0), mine)
        self.assertNotIn("View/SelectionColor", written)
        self.assertIn("View/BackgroundColor2", written)

    def test_a_color_the_user_set_back_to_studios_is_studios_again(self):
        self.colors.apply(theme.LIGHT)
        self.view.SetUnsigned("SelectionColor", theme.rgba("#FF00FF"))
        self.view.SetUnsigned("SelectionColor", theme.rgba(theme.LIGHT.accent))
        self.colors.apply(theme.DARK)
        self.assertEqual(self.view.GetUnsigned("SelectionColor", 0), theme.rgba(theme.DARK.accent))

    def test_first_run_takes_over_freecads_values(self):
        self.view.SetUnsigned("SelectionColor", theme.rgba("#00ABFF"))  # e.g. from FreeCAD's Light pack
        self.colors.apply(theme.LIGHT)
        self.assertEqual(self.view.GetUnsigned("SelectionColor", 0), theme.rgba(theme.LIGHT.accent))

    def test_nothing_to_write_when_nothing_changed(self):
        self.colors.apply(theme.LIGHT)
        self.assertEqual(self.colors.apply(theme.LIGHT), [])
