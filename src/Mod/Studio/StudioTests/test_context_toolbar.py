# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar that follows the selection (studio.viewmodels.context_toolbar), docs/adr/0009.

The shell reports what is selected (object types and sub-elements such as "Face3") and whether a
sketch is being edited; the view-model sorts that into one kind of selection and lists the tools for
it, with plain names, icons, active shortcuts and a status-bar hint.
"""

import unittest
import uuid

import FreeCAD

from studio.interaction.keymap import Keymap
from studio.services.commands import CommandCatalog
from studio.services.settings import Settings
from studio.viewmodels.context_toolbar import TOOLS, ContextToolbar, Selected, selection_kind
from studio.viewmodels.tool_names import PLAIN_NAMES, display_title

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
SKETCH, PAD, BODY = "Sketcher::SketchObject", "PartDesign::Pad", "PartDesign::Body"


class Kinds(unittest.TestCase):
    def kind(self, *selected, editing=None):
        return selection_kind([Selected(*s) for s in selected], editing)

    def test_nothing_selected(self):
        self.assertEqual(self.kind(), "nothing")

    def test_editing_a_sketch_wins_over_any_selection(self):
        self.assertEqual(self.kind((PAD, ("Face3",)), editing=SKETCH), "editing")
        self.assertEqual(self.kind(editing=SKETCH), "editing")

    def test_other_objects_in_edit_do_not_count_as_sketching(self):
        self.assertEqual(self.kind(editing=PAD), "nothing")

    def test_sketches(self):
        self.assertEqual(self.kind((SKETCH,)), "sketch")
        self.assertEqual(self.kind((SKETCH,), (SKETCH,)), "sketch")
        self.assertEqual(self.kind((SKETCH, ("Edge1",))), "sketch")  # clicked the sketch in 3D

    def test_faces_edges_and_mixtures(self):
        self.assertEqual(self.kind((PAD, ("Face3",))), "face")
        self.assertEqual(self.kind((PAD, ("Face3", "Face5"))), "face")
        self.assertEqual(self.kind((PAD, ("Edge1",)), (PAD, ("Edge7",))), "edge")
        self.assertEqual(self.kind((PAD, ("Face3", "Edge1"))), "geometry")
        self.assertEqual(self.kind((PAD, ("Vertex2",))), "geometry")

    def test_a_feature_picked_in_the_tree(self):
        self.assertEqual(self.kind((PAD,)), "feature")
        self.assertEqual(self.kind(("PartDesign::Pocket",), (PAD,)), "feature")

    def test_anything_else_offers_the_starting_tools(self):
        self.assertEqual(self.kind((BODY,)), "nothing")
        self.assertEqual(self.kind((SKETCH,), (PAD,)), "nothing")
        self.assertEqual(self.kind(("App::Part",)), "nothing")


class Names(unittest.TestCase):
    def test_plain_names_for_freecads_unusual_ones(self):
        self.assertEqual(PLAIN_NAMES["PartDesign_Pad"], "Extrude")
        self.assertEqual(PLAIN_NAMES["PartDesign_Pocket"], "Cut")
        self.assertEqual(PLAIN_NAMES["PartDesign_Thickness"], "Shell")
        self.assertEqual(PLAIN_NAMES["PartDesign_Groove"], "Revolve Cut")

    def test_every_renamed_command_exists(self):
        catalog = CommandCatalog.load()
        for name in PLAIN_NAMES:
            with self.subTest(name=name):
                catalog.get(name)

    def test_display_title_falls_back_to_freecads_cleaned_name(self):
        catalog = CommandCatalog.load()
        self.assertEqual(display_title(catalog.get("PartDesign_Pad")), "Extrude")
        self.assertEqual(display_title(catalog.get("Std_ViewFitAll")), "Fit All")


class Buttons(unittest.TestCase):
    def setUp(self):
        name = "Toolbar" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.catalog = CommandCatalog.load()
        self.keymap = Keymap(self.catalog, self.settings)
        self.toolbar = ContextToolbar(self.catalog, self.keymap)

    def labels(self, kind, contexts=()):
        return [b.label for b in self.toolbar.buttons(kind, contexts)]

    def test_tools_for_each_kind(self):
        self.assertEqual(self.labels("nothing"), ["New Sketch", "New Body", "Import", "Measure", "Search"])
        self.assertEqual(self.labels("sketch"), ["Extrude", "Cut", "Revolve", "Hole", "Edit Sketch"])
        self.assertEqual(self.labels("face"), ["Sketch on Face", "Fillet", "Chamfer", "Shell", "Draft", "Measure"])
        self.assertEqual(self.labels("edge"), ["Fillet", "Chamfer", "Measure", "Fit Selection"])
        self.assertEqual(self.labels("geometry"), ["Fillet", "Chamfer", "Measure", "Fit Selection"])
        self.assertEqual(self.labels("feature"), ["Mirror", "Linear Pattern", "Polar Pattern", "Fit Selection"])
        self.assertEqual(self.labels("editing"),
                         ["Line", "Rectangle", "Circle", "Arc", "Dimension", "Fully Constrain", "Close Sketch"])

    def test_every_tool_is_a_catalog_command(self):
        for kind, tools in TOOLS.items():
            for command, _ in tools:
                with self.subTest(kind=kind, command=command):
                    self.catalog.get(command)

    def test_buttons_carry_command_icon_active_shortcut_and_freecads_name(self):
        extrude = self.toolbar.buttons("sketch")[0]
        self.assertEqual(extrude.command, "PartDesign_Pad")
        self.assertEqual(extrude.shortcut, "E")
        self.assertTrue(extrude.icon.endswith("PartDesign_Pad.svg"), extrude.icon)
        self.assertIn("FreeCAD: Pad", extrude.tooltip)
        line = self.toolbar.buttons("editing", ["SketcherWorkbench"])[0]
        self.assertEqual(line.shortcut, "G, L")

    def test_unknown_kind_is_an_error(self):
        with self.assertRaises(KeyError):
            self.toolbar.buttons("teleport")

    def test_a_hint_for_every_kind(self):
        for kind in TOOLS:
            with self.subTest(kind=kind):
                self.assertTrue(self.toolbar.hint(kind))

    def test_the_sketch_hint_names_the_key_extrude_is_on(self):
        self.assertIn("E", self.toolbar.hint("sketch"))
        self.keymap.set_sequences("PartDesign_Pad", ["Ctrl+E"])
        self.assertIn("Ctrl+E", self.toolbar.hint("sketch"))
        self.keymap.set_sequences("PartDesign_Pad", [])
        self.assertNotIn("Press", self.toolbar.hint("sketch"))


if __name__ == "__main__":
    unittest.main()
