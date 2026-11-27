# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Text panel's model (PLAN 4.1, docs/adr/0015): studio.viewmodels.text_panel. No Qt.

A new text starts as "Text" in the font and height used last (Arial and a quarter inch, or 5 mm, the first
time), its box fitted to it; an edited text starts as it is. Picking another family keeps the style when the
family has it, else takes the nearest; the font, style and height used are remembered for the next text.
"""

import unittest
import uuid

import FreeCAD

from studio.services import fonts
from studio.services.settings import Settings
from studio.services.sketch_text import TextBox
from studio.viewmodels.text_panel import TextPanel

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


def font(family, style, weight=400, italic=False):
    return fonts.Font(family=family, style=style, weight=weight, italic=italic, path=f"{family}-{style}.ttf",
                      units_per_em=1000, ascender=800, descender=-200, line_gap=0, cap_height=700, x_height=500,
                      embeddable=True)


INSTALLED = [font("Arial", "Regular"), font("Arial", "Italic", 400, True), font("Arial", "Bold", 700),
             font("Arial", "Bold Italic", 700, True), font("Bahnschrift", "Regular"),
             font("Zed", "Light", 300), font("Zed", "Black", 900), font("Zed", "Black Italic", 900, True)]


class Panel(unittest.TestCase):
    def setUp(self):
        name = "TextPanel" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))

    def panel(self, found=INSTALLED, units="inches", box=None):
        return TextPanel(found, units, self.settings, box)

    def test_a_new_text(self):
        panel = self.panel()
        b = panel.box
        self.assertEqual((b.text, b.family, b.style), ("Text", "Arial", "Regular"))
        self.assertAlmostEqual(b.height, 0.25 * 25.4)
        self.assertTrue(b.fit)
        self.assertEqual(panel.font.path, "Arial-Regular.ttf")
        self.assertFalse(panel.editing)

    def test_in_millimeters_5_mm(self):
        self.assertAlmostEqual(self.panel(units="millimeters").box.height, 5.0)

    def test_the_families_and_their_styles(self):
        panel = self.panel()
        self.assertEqual(panel.families, ["Arial", "Bahnschrift", "Zed"])
        self.assertEqual(panel.styles, ["Regular", "Italic", "Bold", "Bold Italic"])

    def test_without_arial_the_first_family(self):
        panel = self.panel(found=INSTALLED[4:])
        self.assertEqual((panel.box.family, panel.box.style), ("Bahnschrift", "Regular"))

    def test_a_family_without_regular_starts_with_its_nearest(self):
        panel = self.panel(found=INSTALLED[5:])
        self.assertEqual((panel.box.family, panel.box.style), ("Zed", "Light"))

    def test_another_family_keeps_the_style(self):
        panel = self.panel()
        panel.set_style("Bold Italic")
        panel.set_family("Arial")
        self.assertEqual(panel.box.style, "Bold Italic")

    def test_or_takes_the_nearest(self):
        panel = self.panel()
        panel.set_style("Bold Italic")
        panel.set_family("Zed")
        self.assertEqual((panel.box.family, panel.box.style), ("Zed", "Black Italic"))
        self.assertEqual(panel.styles, ["Light", "Black", "Black Italic"])
        panel.set_family("Bahnschrift")
        self.assertEqual(panel.box.style, "Regular")
        self.assertEqual(panel.font.path, "Bahnschrift-Regular.ttf")

    def test_the_rest_of_the_settings(self):
        panel = self.panel()
        panel.set_text("Lesleigh\nsun flower")
        panel.set_height(12.7)
        panel.set_align("center")
        panel.set_valign("middle")
        panel.set_spacing(1.2)
        b = panel.box
        self.assertEqual((b.text, b.height, b.align, b.valign, b.spacing), ("Lesleigh\nsun flower", 12.7, "center",
                                                                            "middle", 1.2))

    def test_a_height_must_be_more_than_nothing(self):
        panel = self.panel()
        self.assertFalse(panel.set_height(0))
        self.assertFalse(panel.set_spacing(-1))
        self.assertAlmostEqual(panel.box.height, 0.25 * 25.4)
        self.assertEqual(panel.box.spacing, 1.0)

    def test_a_box_of_its_own_size(self):
        # fitting off keeps the size the box had (the text's), then the box's own width and depth
        panel = self.panel()
        panel.set_fit(False, width=30.0, depth=8.0)
        self.assertEqual((panel.box.fit, panel.box.width, panel.box.depth), (False, 30.0, 8.0))
        panel.set_width(50.0)
        panel.set_depth(20.0)
        self.assertEqual((panel.box.width, panel.box.depth), (50.0, 20.0))
        self.assertFalse(panel.set_width(0))

    def test_remembered_for_the_next_text(self):
        panel = self.panel()
        panel.set_family("Zed")
        panel.set_style("Black")
        panel.set_height(10.0)
        panel.remember()
        again = self.panel(units="millimeters")
        self.assertEqual((again.box.family, again.box.style, again.box.height), ("Zed", "Black", 10.0))

    def test_a_remembered_font_since_removed(self):
        panel = self.panel()
        panel.set_family("Zed")
        panel.remember()
        self.assertEqual(self.panel(found=INSTALLED[:5]).box.family, "Arial")

    def test_editing_a_text(self):
        text = TextBox("Hi", "Arial", "Bold", 6.0, 40.0, 10.0, "right", "bottom", 1.1, False)
        panel = self.panel(box=text)
        self.assertTrue(panel.editing)
        self.assertEqual(panel.box, text)
        self.assertEqual(panel.font.path, "Arial-Bold.ttf")
        self.assertEqual(panel.missing, "")

    def test_editing_a_text_whose_font_is_missing(self):
        text = TextBox("Hi", "Comic Sans MS", "Bold", 6.0, 40.0, 10.0)
        panel = self.panel(box=text)
        self.assertIsNone(panel.font)
        self.assertEqual(panel.missing, "Comic Sans MS Bold isn't on this computer: pick another font to change "
                                        "the text")
        panel.set_family("Arial")
        self.assertEqual((panel.box.family, panel.box.style, panel.missing), ("Arial", "Bold", ""))
