# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's line icons (ADR 0010, PLAN 2.9 step 4): studio.services.icons.

One drawing per tool or feature type in Resources/icons/line, all in one style. FreeCAD's places (the
model tree, the menus) get them under FreeCAD's own icon names; Studio's surfaces (toolbar, palette)
draw them in the mode's text color.
"""

import os
import unittest
import xml.etree.ElementTree as ET

from studio.services import icons, theme
from studio.services.commands import CommandCatalog
from studio.viewmodels.context_toolbar import TOOLS

SVG = "{http://www.w3.org/2000/svg}"
SHAPES = {f"{SVG}{tag}" for tag in ("path", "circle", "ellipse", "rect", "g")}


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


class Drawings(unittest.TestCase):
    def files(self):
        return sorted(f for f in os.listdir(icons.ICON_DIR) if f.endswith(".svg"))

    def test_one_style_24_px_grid_one_stroke_neutral_grey(self):
        self.assertGreaterEqual(len(self.files()), 40)
        for name in self.files():
            root = ET.parse(os.path.join(icons.ICON_DIR, name)).getroot()
            with self.subTest(icon=name):
                self.assertEqual(root.get("viewBox"), "0 0 24 24")
                self.assertEqual(root.get("fill"), "none")
                self.assertEqual(root.get("stroke"), theme.ICON_NEUTRAL)
                self.assertEqual(root.get("stroke-width"), icons.STROKE)
                for element in root.iter():
                    if element is root:
                        continue
                    self.assertIn(element.tag, SHAPES)
                    self.assertIsNone(element.get("fill"))  # line icons: no fills, one color
                    self.assertIsNone(element.get("stroke"))

    def test_every_drawing_is_used_and_every_name_has_one(self):
        used = set(icons.FREECAD_ICONS.values()) | set(icons.STUDIO_ONLY.values())
        self.assertEqual({stem(f) for f in self.files()}, used)


class Names(unittest.TestCase):
    def test_every_toolbar_tool_has_a_line_icon(self):
        catalog = CommandCatalog.load()
        for kind, tools in TOOLS.items():
            for command, _label in tools:
                with self.subTest(kind=kind, command=command):
                    self.assertIsNotNone(icons.line_icon(stem(catalog.get(command).icon)))

    def test_the_model_trees_feature_types_have_line_icons(self):
        names = {name for names in icons.freecad_registrations().values() for name in names}
        tree = ["PartDesign_Body.svg", "Sketcher_Sketch", "PartDesign_Pad.svg", "PartDesign_Pocket.svg",
                "PartDesign_Revolution.svg", "PartDesign_Groove.svg", "PartDesign_Hole.svg", "PartDesign_Fillet",
                "PartDesign_Chamfer", "PartDesign_Thickness", "PartDesign_Draft", "PartDesign_Mirrored",
                "PartDesign_LinearPattern", "PartDesign_PolarPattern", "PartDesign_MultiTransform",
                "PartDesign_Plane.svg", "PartDesign_Line.svg", "PartDesign_Point.svg", "Std_Plane", "Std_Axis",
                "Std_Point", "Std_CoordinateSystem", "TreeItemVisible", "TreeItemInvisible", "Document"]
        self.assertEqual([name for name in tree if name not in names], [])

    def test_freecad_gets_each_name_with_and_without_svg(self):
        # Commands ask for "PartDesign_Pad", the model tree for "PartDesign_Pad.svg".
        registrations = icons.freecad_registrations()
        extrude = registrations[icons.icon_path("extrude")]
        self.assertIn("PartDesign_Pad", extrude)
        self.assertIn("PartDesign_Pad.svg", extrude)

    def test_studios_own_icon_name_stays_freecads(self):
        # The palette command's icon is called "Studio", like the workbench: only Studio's surfaces
        # show it as a magnifier.
        names = {name for names in icons.freecad_registrations().values() for name in names}
        self.assertNotIn("Studio", names)
        self.assertEqual(icons.line_icon("Studio"), icons.icon_path("search"))

    def test_unknown_names_have_none(self):
        self.assertIsNone(icons.line_icon("Part_Box"))
        self.assertIsNone(icons.line_icon(None))
