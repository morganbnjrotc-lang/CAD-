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
from studio.services.settings import Setting, Settings
from studio.viewmodels.context_toolbar import TOOLS, WAYS, ContextToolbar, Selected, selection_kind
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
        self.assertEqual(self.labels("nothing"), ["New Sketch", "New Body", "Pattern", "Import", "Measure", "Search"])
        self.assertEqual(self.labels("sketch"), ["Extrude", "Cut", "Revolve", "Hole", "Edit Sketch"])
        self.assertEqual(self.labels("face"), ["Sketch on Face", "Fillet", "Chamfer", "Shell", "Draft", "Measure"])
        self.assertEqual(self.labels("edge"), ["Fillet", "Chamfer", "Measure", "Fit Selection"])
        self.assertEqual(self.labels("geometry"), ["Fillet", "Chamfer", "Measure", "Fit Selection"])
        self.assertEqual(self.labels("feature"), ["Pattern", "Fit Selection"])
        self.assertEqual(self.labels("editing"),
                         ["Line", "Rectangle", "Circle", "Arc", "Polygon", "Slot", "Spline", "Ellipse", "Point",
                          "Text", "Pattern", "Construction", "Dimension", "Fully Constrain", "Close Sketch"])

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


class Ways(unittest.TestCase):
    """Sketch tools that draw a shape more than one way, picked from a drop-down (PLAN 3.12)."""

    def setUp(self):
        name = "Ways" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.catalog = CommandCatalog.load()
        self.toolbar = ContextToolbar(self.catalog, None, self.settings)

    def button(self, label, toolbar=None):
        return next(b for b in (toolbar or self.toolbar).buttons("editing") if b.label == label)

    def test_every_way_fusion_and_freecad_share(self):
        ways = {b.label: [w.label for w in b.ways] for b in self.toolbar.buttons("editing") if b.ways}
        self.assertEqual(ways, {
            "Line": ["Line", "Lines and Arcs", "Center Point Line"],
            "Rectangle": ["2-Point Rectangle", "Center Rectangle", "3-Point Rectangle", "3-Point Center Rectangle",
                          "Rounded Rectangle"],
            "Circle": ["Center Diameter Circle", "3-Point Circle", "2-Point Circle", "2-Tangent Circle",
                       "3-Tangent Circle"],
            "Arc": ["Center Point Arc", "3-Point Arc", "Tangent Arc"],
            "Polygon": ["Inscribed Polygon", "Triangle", "Square", "Hexagon", "Circumscribed Polygon",
                        "Edge Polygon"],
            "Slot": ["Center to Center Slot", "Center Point Arc Slot", "Overall Slot", "Center Point Slot"],
            "Spline": ["Fit Point Spline", "Control Point Spline"],
            "Ellipse": ["Center Ellipse", "3-Point Ellipse", "Elliptical Arc"],
            "Pattern": ["Rectangular Pattern", "Circular Pattern", "Mirror"],
        })

    def test_patterns_in_the_model_too(self):
        # The user asked for patterns "both in sketches and regular modeling" (2026-11-19). With nothing
        # selected FreeCAD patterns the whole part; with a feature selected, that feature.
        for kind in ("nothing", "feature"):
            pattern = next(b for b in self.toolbar.buttons(kind) if b.label == "Pattern")
            self.assertEqual([(w.command, w.label) for w in pattern.ways],
                             [("PartDesign_LinearPattern", "Rectangular Pattern"),
                              ("PartDesign_PolarPattern", "Circular Pattern"), ("PartDesign_Mirrored", "Mirror")])

    def test_sketch_patterns_start_with_three_elements_and_need_geometry_selected(self):
        # FreeCAD's Move and Rotate start with 1 element (a plain move); Fusion's patterns with 3. They
        # work on the geometry selected first; without it FreeCAD stops with a warning dialog.
        pattern = self.button("Pattern")
        ways = {w.label: (w.command, w.settings) for w in pattern.ways}
        self.assertEqual(ways["Rectangular Pattern"], ("Sketcher_Translate", ((1, 3),)))
        self.assertEqual(ways["Circular Pattern"], ("Sketcher_Rotate", ((1, 3),)))
        self.assertEqual(ways["Mirror"], ("Sketcher_Symmetry", ()))
        self.assertTrue(pattern.needs_selection)
        self.assertEqual(pattern.settings, ((1, 3),))  # the way it draws now
        self.assertFalse(self.button("Line").needs_selection)

    def test_every_way_is_a_catalog_command(self):
        for ways in WAYS.values():
            for way in ways:
                with self.subTest(way=way.label):
                    self.catalog.get(way.command)

    def test_ways_freecad_has_no_command_for_start_its_rectangle_in_another_method(self):
        rectangle = {w.label: (w.command, w.method) for w in self.button("Rectangle").ways}
        self.assertEqual(rectangle["2-Point Rectangle"], ("Sketcher_CreateRectangle", 0))
        self.assertEqual(rectangle["Center Rectangle"], ("Sketcher_CreateRectangle_Center", 0))
        self.assertEqual(rectangle["3-Point Rectangle"], ("Sketcher_CreateRectangle", 2))
        self.assertEqual(rectangle["3-Point Center Rectangle"], ("Sketcher_CreateRectangle", 3))
        line = {w.label: (w.command, w.method) for w in self.button("Line").ways}
        self.assertEqual(line["Center Point Line"], ("Sketcher_CreateLine", 3))  # added to FreeCAD's Line
        circle = {w.label: (w.command, w.method) for w in self.button("Circle").ways}
        self.assertEqual(circle["2-Point Circle"], ("Sketcher_CreateCircle", 2))  # added to FreeCAD's Circle
        self.assertEqual(circle["2-Tangent Circle"], ("Sketcher_CreateCircle", 3))
        self.assertEqual(circle["3-Tangent Circle"], ("Sketcher_CreateCircle", 4))
        polygon = {w.label: (w.command, w.method) for w in self.button("Polygon").ways}
        self.assertEqual(polygon["Circumscribed Polygon"], ("Sketcher_CreateHexagon", 1))
        self.assertEqual(polygon["Edge Polygon"], ("Sketcher_CreateHexagon", 2))
        slot = {w.label: (w.command, w.method) for w in self.button("Slot").ways}
        self.assertEqual(slot["Overall Slot"], ("Sketcher_CreateSlot", 1))
        self.assertEqual(slot["Center Point Slot"], ("Sketcher_CreateSlot", 2))
        arc = {w.label: (w.command, w.method) for w in self.button("Arc").ways}
        self.assertEqual(arc["Tangent Arc"], ("Sketcher_CreateArc", 2))

    def test_a_tool_starts_with_its_first_way(self):
        rectangle = self.button("Rectangle")
        self.assertEqual((rectangle.command, rectangle.method), ("Sketcher_CreateRectangle", 0))
        self.assertEqual(rectangle.way, 0)
        self.assertTrue(rectangle.tooltip.startswith("2-Point Rectangle\n"), rectangle.tooltip)

    def test_then_it_draws_the_way_picked_last_also_next_time(self):
        self.toolbar.choose("Sketcher_CreateRectangle", 2)
        for toolbar in (self.toolbar, ContextToolbar(self.catalog, None, self.settings)):
            rectangle = self.button("Rectangle", toolbar)
            self.assertEqual((rectangle.command, rectangle.method, rectangle.way), ("Sketcher_CreateRectangle", 2, 2))
            self.assertTrue(rectangle.tooltip.startswith("3-Point Rectangle\n"), rectangle.tooltip)
            self.assertEqual(rectangle.label, "Rectangle")

    def test_the_button_shows_the_ways_icon(self):
        self.toolbar.choose("Sketcher_CreateRectangle", 1)
        self.assertEqual(self.button("Rectangle").icon, self.catalog.get("Sketcher_CreateRectangle_Center").icon)

    def test_new_ways_come_last_so_a_remembered_way_stays_the_same(self):
        # The way picked last is stored by its place in the list (Toolbar/Ways/<tool>). Ways added after
        # the user picked one go at the end; these were the lists the user first had (2026-11-18).
        first = {"Sketcher_CreateLine": ["Line", "Lines and Arcs"],
                 "Sketcher_CreateCircle": ["Center Diameter Circle", "3-Point Circle"],
                 "Sketcher_CreateArc": ["Center Point Arc", "3-Point Arc"],
                 "Sketcher_CreateRegularPolygon": ["Inscribed Polygon", "Triangle", "Square", "Hexagon"],
                 "Sketcher_CreateSlot": ["Center to Center Slot", "Center Point Arc Slot"]}
        for tool, labels in first.items():
            with self.subTest(tool=tool):
                self.assertEqual([w.label for w in WAYS[tool]][:len(labels)], labels)

    def test_a_way_remembered_that_no_longer_exists_falls_back_to_the_first(self):
        self.toolbar.choose("Sketcher_CreateCircle", 1)
        self.settings.set(Setting("Toolbar/Ways/Sketcher_CreateCircle", 0), 9)
        self.assertEqual(self.button("Circle").way, 0)

    def test_tools_with_one_way_have_no_list(self):
        self.assertEqual(self.button("Point").ways, ())
        self.assertEqual(self.button("Dimension").ways, ())


class Switches(unittest.TestCase):
    """Construction is a switch (PLAN 3.13): its button shows whether new geometry is construction."""

    def setUp(self):
        name = "Switches" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.catalog = CommandCatalog.load()
        self.on = set()

    def button(self, label, toolbar):
        return next(b for b in toolbar.buttons("editing", ["SketcherWorkbench"]) if b.label == label)

    def test_the_construction_button_shows_whether_construction_is_on(self):
        toolbar = ContextToolbar(self.catalog, is_on=lambda command: command in self.on)
        self.assertIs(self.button("Construction", toolbar).checked, False)
        self.on.add("Studio_Construction")
        self.assertIs(self.button("Construction", toolbar).checked, True)

    def test_other_tools_are_not_switches(self):
        toolbar = ContextToolbar(self.catalog, is_on=lambda command: True)
        self.assertIsNone(self.button("Line", toolbar).checked)
        self.assertIsNone(self.button("Dimension", toolbar).checked)

    def test_without_a_way_to_tell_a_switch_shows_off(self):
        self.assertIs(self.button("Construction", ContextToolbar(self.catalog)).checked, False)

    def test_x_is_on_the_construction_button(self):
        toolbar = ContextToolbar(self.catalog, Keymap(self.catalog, self.settings))
        self.assertEqual(self.button("Construction", toolbar).shortcut, "X")


if __name__ == "__main__":
    unittest.main()
