# SPDX-License-Identifier: LGPL-2.1-or-later
"""The installed fonts by name and style (PLAN 4.1, docs/adr/0015): studio.services.fonts.

Read from the font files themselves (their `name`, `head`, `hhea` and `OS/2` tables), headless: family and
style as Windows shows them, weight and slant to order the styles, the metrics the text layout needs, and
whether the font's license lets it be kept in a file for editing (PLAN 4.2).

The test font is Noto Sans Regular (tests/visual/fonts, SIL Open Font License), copied next to the tests by
the build; a few tests read fonts every Windows has.
"""

import os
import shutil
import struct
import tempfile
import unittest

import Part

from studio.services import fonts

NOTO = os.path.join(os.path.dirname(__file__), "fonts", "NotoSans-Regular.ttf")
WINDOWS_FONTS = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")


def outline_height(font_file, text, size=100.0):
    """The height of `text`'s outline drawn by Part (FreeType), independent of studio.services.fonts."""
    folder, name = os.path.split(font_file)
    chars = Part.makeWireString(text, folder + "/", name, size)
    return Part.Compound([w for c in chars for w in c]).BoundBox.YLength


def with_fs_type(path, folder, fs_type):
    """A copy of the font at `path` whose embedding permission (OS/2 fsType) is `fs_type`."""
    data = bytearray(open(path, "rb").read())
    count = struct.unpack(">H", data[4:6])[0]
    for i in range(count):
        tag, _, offset, _ = struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])
        if tag == b"OS/2":
            data[offset + 8:offset + 10] = struct.pack(">H", fs_type)
    copy = os.path.join(folder, f"fs{fs_type}.ttf")
    open(copy, "wb").write(bytes(data))  # the table's checksum is left stale: readers don't check it
    return copy


def as_collection(path, folder):
    """`path` (a .ttf) wrapped as a one-font collection (.ttc): its table offsets moved past the header."""
    data = bytearray(open(path, "rb").read())
    header = 12 + 4
    count = struct.unpack(">H", data[4:6])[0]
    for i in range(count):
        at = 12 + 16 * i + 8
        offset = struct.unpack(">I", data[at:at + 4])[0]
        data[at:at + 4] = struct.pack(">I", offset + header)
    ttc = os.path.join(folder, "collection.ttc")
    open(ttc, "wb").write(b"ttcf" + struct.pack(">HHII", 1, 0, 1, header) + bytes(data))
    return ttc


class ReadingAFont(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(NOTO), "the test font isn't next to the tests: rebuild")
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def test_family_and_style(self):
        font = fonts.read(NOTO)
        self.assertEqual((font.family, font.style), ("Noto Sans", "Regular"))
        self.assertEqual((font.weight, font.italic), (400, False))
        self.assertEqual(font.name, "Noto Sans Regular")
        self.assertEqual(font.path, NOTO)

    def test_cap_height_matches_the_outline(self):
        # the capitals' height over the font's units, as the outline of "H" is drawn
        font = fonts.read(NOTO)
        drawn = outline_height(NOTO, "H") / outline_height(NOTO, "x")
        self.assertAlmostEqual(font.cap_height / font.x_height, drawn, places=2)

    def test_line_spacing(self):
        font = fonts.read(NOTO)
        self.assertEqual(font.line_spacing, font.ascender - font.descender + font.line_gap)
        self.assertGreater(font.line_spacing, font.cap_height)

    def test_a_font_that_allows_embedding(self):
        self.assertTrue(fonts.read(NOTO).embeddable)  # SIL OFL: fsType 0, installable
        self.assertTrue(fonts.read(with_fs_type(NOTO, self.folder, 8)).embeddable)  # editable

    def test_fonts_that_dont(self):
        self.assertFalse(fonts.read(with_fs_type(NOTO, self.folder, 2)).embeddable)  # restricted
        self.assertFalse(fonts.read(with_fs_type(NOTO, self.folder, 4)).embeddable)  # preview and print only
        self.assertFalse(fonts.read(with_fs_type(NOTO, self.folder, 0x200)).embeddable)  # bitmaps only

    def test_a_collections_first_font(self):
        # FreeCAD draws only a collection's first font (FreeType face 0), so that's the one listed
        font = fonts.read(as_collection(NOTO, self.folder))
        self.assertEqual((font.family, font.style), ("Noto Sans", "Regular"))

    def test_not_a_font(self):
        junk = os.path.join(self.folder, "junk.ttf")
        open(junk, "wb").write(b"not a font at all")
        self.assertIsNone(fonts.read(junk))
        self.assertIsNone(fonts.read(os.path.join(self.folder, "missing.ttf")))


@unittest.skipUnless(os.path.exists(os.path.join(WINDOWS_FONTS, "arialbd.ttf")), "Windows' fonts")
class WindowsFonts(unittest.TestCase):
    def test_bold(self):
        font = fonts.read(os.path.join(WINDOWS_FONTS, "arialbd.ttf"))
        self.assertEqual((font.family, font.style, font.weight), ("Arial", "Bold", 700))

    def test_the_typographic_family(self):
        # Segoe UI Semibold calls itself family "Segoe UI Semibold", style "Regular" for old programs; its
        # typographic names, which Windows' font list shows, are "Segoe UI", "Semibold"
        font = fonts.read(os.path.join(WINDOWS_FONTS, "seguisb.ttf"))
        self.assertEqual((font.family, font.style), ("Segoe UI", "Semibold"))


class InstalledFonts(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)

    def test_the_fonts_in_folders(self):
        shutil.copy(NOTO, self.folder)
        open(os.path.join(self.folder, "readme.txt"), "w").write("not a font")
        open(os.path.join(self.folder, "broken.otf"), "wb").write(b"\0" * 64)
        found = fonts.installed([self.folder])
        self.assertEqual([f.name for f in found], ["Noto Sans Regular"])

    def test_the_same_font_twice_is_listed_once(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        shutil.copy(NOTO, self.folder)
        shutil.copy(NOTO, other)
        found = fonts.installed([self.folder, other])
        self.assertEqual(len(found), 1)
        self.assertEqual(os.path.dirname(found[0].path), self.folder)  # the first folder's

    def test_a_missing_folder(self):
        self.assertEqual(fonts.installed([os.path.join(self.folder, "nothing here")]), [])

    def test_windows_and_the_users_fonts(self):
        local = os.environ.get("LOCALAPPDATA")
        expected = [WINDOWS_FONTS] + ([os.path.join(local, "Microsoft", "Windows", "Fonts")] if local else [])
        self.assertEqual([os.path.normcase(f) for f in fonts.folders()],
                         [os.path.normcase(f) for f in expected if os.path.isdir(f)])

    def test_families_with_their_styles_in_order(self):
        def font(family, style, weight, italic):
            return fonts.Font(family=family, style=style, weight=weight, italic=italic, path="", units_per_em=1000,
                              ascender=800, descender=-200, line_gap=0, cap_height=700, x_height=500,
                              embeddable=True)

        listed = [font("Zed", "Regular", 400, False), font("Arial", "Bold Italic", 700, True),
                  font("Arial", "Regular", 400, False), font("Arial", "Light", 300, False),
                  font("Arial", "Italic", 400, True), font("Arial", "Bold", 700, False)]
        families = fonts.families(listed)
        self.assertEqual(list(families), ["Arial", "Zed"])
        self.assertEqual([f.style for f in families["Arial"]], ["Light", "Regular", "Italic", "Bold", "Bold Italic"])

    def test_found_by_family_and_style(self):
        shutil.copy(NOTO, self.folder)
        found = fonts.installed([self.folder])
        self.assertEqual(fonts.find("noto sans", "regular", found).path, os.path.join(self.folder, "NotoSans-Regular.ttf"))
        self.assertIsNone(fonts.find("Noto Sans", "Bold", found))
