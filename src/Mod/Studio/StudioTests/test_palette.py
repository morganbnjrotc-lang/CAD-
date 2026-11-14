# SPDX-License-Identifier: LGPL-2.1-or-later
"""Command palette view-model (studio.viewmodels.palette), PLAN 2.5.

Type part of a tool's name, get the best matches first, run one. Searches every catalog command,
loaded or not (docs/adr/0007). Shows each command's active shortcut (docs/adr/0008).
"""

import time
import unittest
import uuid

import FreeCAD

from studio.interaction.keymap import Keymap
from studio.services.commands import CommandCatalog
from studio.services.settings import Settings
from studio.viewmodels.palette import Palette, clean_title

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


def command(name, workbench, menu, tooltip="", shortcut=""):
    return {"name": name, "workbench": workbench, "menu_text": menu, "tooltip": tooltip, "shortcut": shortcut,
            "icon": None}


CATALOG = {
    "freecad": "27.1.0",
    "workbenches": [{"name": n, "class": ""} for n in ("SketcherWorkbench", "PartDesignWorkbench", "TechDrawWorkbench")],
    "commands": [
        command("Std_Undo", None, "&Undo", "Undoes the previous action", "Ctrl+Z"),
        command("Std_SaveAs", None, "Save &As...", "Saves the document under a new name"),
        command("Std_ViewFitAll", None, "&Fit All", "Fits the whole content on the screen", "V, F"),
        command("Std_ViewFitSelection", None, "Fit &Selection", "Fits the selected content"),
        command("Std_Save", None, "&Save", "Saves the document", "Ctrl+S"),
        command("Std_SaveGroup", None, "Save", "Save options"),  # a dropdown group named like a tool
        command("Sketcher_NewSketch", "SketcherWorkbench", "New Sketch", "Creates a new sketch"),
        command("Sketcher_CreateLine", "SketcherWorkbench", "Line", "Creates a line", "G, L"),
        command("Sketcher_CompCreateRectangles", "SketcherWorkbench", "Rectangle", "Rectangles"),
        command("Sketcher_CreateRectangle", "SketcherWorkbench", "Rectangle", "Creates a rectangle", "G, R"),
        command("Sketcher_Dimension", "SketcherWorkbench", "Dimension", "Constrains with a dimension", "D"),
        command("PartDesign_Pad", "PartDesignWorkbench", "Pad", "Extrudes a sketch"),
        command("PartDesign_Pocket", "PartDesignWorkbench", "Pocket", "Cuts a sketch into the solid"),
        command("PartDesign_SubtractivePad", "PartDesignWorkbench", "Subtractive Pad-like Cut", "x"),
        command("TechDraw_Dimension", "TechDrawWorkbench", "Dimension", "Inserts a dimension", "D"),
    ],
}


class PaletteTestCase(unittest.TestCase):
    def setUp(self):
        name = "Palette" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.catalog = CommandCatalog(CATALOG)
        self.palette = Palette(self.catalog, Keymap(self.catalog, self.settings), self.settings)

    def names(self, query, **kwargs):
        return [item.command for item in self.palette.search(query, **kwargs)]


class Items(PaletteTestCase):
    def test_titles_without_accelerator_marks_or_trailing_dots(self):
        cases = {"&Undo": "Undo", "Save &As...": "Save As", "Fit &Selection": "Fit Selection",
                 "Copy && Paste": "Copy & Paste", "Export…": "Export", "Line": "Line"}
        for given, expected in cases.items():
            with self.subTest(given=given):
                self.assertEqual(clean_title(given), expected)

    def test_each_item_has_title_category_detail_and_active_shortcut(self):
        items = {item.command: item for item in self.palette.items()}
        fit = items["Std_ViewFitAll"]
        self.assertEqual((fit.title, fit.category, fit.detail, fit.shortcut),
                         ("Fit All", "General", "Fits the whole content on the screen", "Shift+F"))
        self.assertEqual(items["PartDesign_Pad"].category, "Part Design")
        self.assertEqual(items["PartDesign_Pad"].shortcut, "E")
        self.assertEqual(items["Sketcher_Dimension"].shortcut, "")  # D only while sketching

    def test_shortcuts_follow_the_active_context(self):
        items = {item.command: item for item in self.palette.items(contexts=["SketcherWorkbench"])}
        self.assertEqual(items["Sketcher_Dimension"].shortcut, "D")

    def test_one_entry_per_title_in_a_category_preferring_the_tool_over_a_dropdown_group(self):
        commands = [item.command for item in self.palette.items()]
        self.assertIn("Sketcher_CreateRectangle", commands)
        self.assertNotIn("Sketcher_CompCreateRectangles", commands)
        self.assertIn("Std_Save", commands)
        self.assertNotIn("Std_SaveGroup", commands)
        # Same title, different categories: both stay.
        self.assertIn("Sketcher_Dimension", commands)
        self.assertIn("TechDraw_Dimension", commands)


class Ranking(PaletteTestCase):
    def test_title_start_beats_word_start_beats_substring_beats_scattered_letters(self):
        self.assertEqual(self.names("pad")[:2], ["PartDesign_Pad", "PartDesign_SubtractivePad"])
        self.assertEqual(self.names("sel")[0], "Std_ViewFitSelection")  # word start
        self.assertEqual(self.names("ocke"), ["PartDesign_Pocket"])  # substring
        self.assertEqual(self.names("pkt")[0], "PartDesign_Pocket")  # letters in order, closest first

    def test_every_word_of_the_query_must_match(self):
        self.assertEqual(self.names("fit all")[0], "Std_ViewFitAll")
        self.assertEqual(self.names("pad zzz"), [])

    def test_category_words_narrow_the_search(self):
        self.assertEqual(self.names("sketch dim"), ["Sketcher_Dimension"])
        self.assertEqual(self.names("techdraw dim"), ["TechDraw_Dimension"])

    def test_case_and_surrounding_spaces_do_not_matter(self):
        self.assertEqual(self.names("  UNDO "), ["Std_Undo"])

    def test_tooltip_words_are_a_last_resort(self):
        self.assertEqual(self.names("extrudes"), ["PartDesign_Pad"])

    def test_limit(self):
        self.assertEqual(len(self.palette.search("e", limit=3)), 3)


class Recent(PaletteTestCase):
    def test_empty_query_lists_recent_commands_first(self):
        self.palette.record_use("PartDesign_Pocket")
        self.palette.record_use("Std_Undo")
        self.assertEqual(self.names("")[:2], ["Std_Undo", "PartDesign_Pocket"])

    def test_recent_use_breaks_ties_between_equal_matches(self):
        self.assertEqual(self.names("dimension")[0], "Sketcher_Dimension")
        self.palette.record_use("TechDraw_Dimension")
        self.assertEqual(self.names("dimension")[0], "TechDraw_Dimension")

    def test_remembered_between_sessions_most_recent_first_without_repeats(self):
        for name in ("Std_Undo", "PartDesign_Pad", "Std_Undo"):
            self.palette.record_use(name)
        again = Palette(self.catalog, Keymap(self.catalog, self.settings), self.settings)
        self.assertEqual(again.recent(), ["Std_Undo", "PartDesign_Pad"])

    def test_keeps_only_the_last_few_and_forgets_unknown_commands(self):
        for item in self.catalog.commands():
            self.palette.record_use(item.name)
        self.assertEqual(len(self.palette.recent()), Palette.RECENT_LIMIT)
        self.settings.set(Palette.RECENT, "Gone_Command\nStd_Undo")
        self.assertEqual(Palette(self.catalog, None, self.settings).recent(), ["Std_Undo"])


class ShippedCatalog(unittest.TestCase):
    def setUp(self):
        name = "Palette" + uuid.uuid4().hex[:8]
        settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        catalog = CommandCatalog.load()
        self.palette = Palette(catalog, Keymap(catalog, settings), settings)

    def test_common_tools_come_first(self):
        top = lambda query: self.palette.search(query)[0].command
        self.assertEqual(top("pad"), "PartDesign_Pad")
        self.assertEqual(top("fit all"), "Std_ViewFitAll")
        self.assertEqual(top("new sketch"), "Sketcher_NewSketch")
        self.assertEqual(top("undo"), "Std_Undo")

    def test_searching_every_command_is_fast(self):
        start = time.perf_counter()
        for query in ("p", "pa", "pad", "fit", "sketch line", "xyz"):
            self.palette.search(query)
        self.assertLess((time.perf_counter() - start) / 6, 0.05, "a search took over 50 ms on average")


if __name__ == "__main__":
    unittest.main()
