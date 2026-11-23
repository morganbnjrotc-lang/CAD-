# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every tool in Fusion's groups on the top bar, and tools pinned to the toolbar (studio.viewmodels.tool_groups,
PLAN 3.17, the user's pick 2026-11-22).

The user: "I like our current setup but it lacks a lot of features that have to be searched for. Autodesk's
organization is nice but it leaves the screen too busy." The toolbar keeps following the selection; the
top bar gets Fusion's group words as menus holding every tool: Create, Modify, Construct, Inspect, Insert,
and while sketching Create, Modify, Constrain, Inspect. A tool picked from a group can be pinned to the
toolbar for that kind of selection (faces, sketches…).
"""

import os
import unittest
import uuid

import FreeCAD

from studio.interaction.keymap import Keymap
from studio.services import icons
from studio.services.commands import CommandCatalog
from studio.services.settings import Settings
from studio.viewmodels.context_toolbar import TOOLS, WAYS, ContextToolbar
from studio.viewmodels.tool_groups import KIND_WORDS, MenuItem, SubMenu, ToolGroups

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
# On the toolbar but not tools of a group: a panel's own buttons, leaving the sketch, search, a view tool.
NOT_IN_GROUPS = {"Studio_Finish", "Studio_Cancel", "Sketcher_LeaveSketch", "Studio_CommandPalette",
                 "Std_ViewFitSelection"}


class _WithGroups(unittest.TestCase):
    def setUp(self):
        name = "Groups" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.catalog = CommandCatalog.load()
        self.keymap = Keymap(self.catalog, self.settings)
        self.toolbar = ContextToolbar(self.catalog, self.keymap, self.settings)
        self.groups = ToolGroups(self.catalog, self.toolbar, self.keymap, self.settings)

    def items(self, sketching, label):
        group = next(g for g in self.groups.groups(sketching) if g.label == label)
        return [i for i in group.items if i is not None]  # None: a separator

    def flat(self, sketching):
        """Every tool in the groups, side menus opened."""
        for group in self.groups.groups(sketching):
            for item in group.items:
                if isinstance(item, SubMenu):
                    yield from item.items
                elif item is not None:
                    yield item

    def labels(self, sketching, label):
        return [i.label for i in self.items(sketching, label)]


class Groups(_WithGroups):
    # -- the groups ---------------------------------------------------------------------------------
    def test_fusions_group_words(self):
        self.assertEqual([g.label for g in self.groups.groups(False)],
                         ["Create", "Modify", "Construct", "Inspect", "Insert"])
        self.assertEqual([g.label for g in self.groups.groups(True)], ["Create", "Modify", "Constrain", "Inspect"])

    def test_every_tool_is_a_catalog_command(self):
        for sketching in (False, True):
            for item in self.flat(sketching):
                with self.subTest(sketching=sketching, command=item.command):
                    self.catalog.get(item.command)

    def test_every_tool_on_the_toolbar_is_in_a_group(self):
        for kind, tools in TOOLS.items():
            sketching = kind == "editing"
            commands = {i.command for i in self.flat(sketching)}
            for command, _ in tools:
                if command not in NOT_IN_GROUPS:
                    with self.subTest(kind=kind, command=command):
                        self.assertIn(command, commands)

    def test_no_tool_twice_in_a_group(self):
        for sketching in (False, True):
            for group in self.groups.groups(sketching):
                keys = [i.key for i in group.items if isinstance(i, MenuItem)]
                keys += [i.key for s in group.items if isinstance(s, SubMenu) for i in s.items]
                with self.subTest(sketching=sketching, group=group.label):
                    self.assertEqual(len(keys), len(set(keys)), keys)

    def test_create(self):
        self.assertEqual(self.labels(False, "Create")[:7],
                         ["New Sketch", "Extrude", "Revolve", "Sweep", "Loft", "Helix", "Hole"])

    def test_plain_names_and_freecads_in_the_tooltip(self):
        extrude = next(i for i in self.flat(False) if i.command == "PartDesign_Pad")
        self.assertEqual(extrude.label, "Extrude")
        self.assertIn("FreeCAD: Pad", extrude.tooltip)
        self.assertTrue(extrude.icon.endswith("PartDesign_Pad.svg"), extrude.icon)

    def test_the_active_shortcut(self):
        extrude = next(i for i in self.flat(False) if i.command == "PartDesign_Pad")
        self.assertEqual(extrude.shortcut, "E")

    def test_a_tool_drawing_several_ways_lists_them_in_a_side_menu(self):
        create = self.items(True, "Create")
        rectangle = next(i for i in create if i.label == "Rectangle")
        self.assertIsInstance(rectangle, SubMenu)
        self.assertEqual([w.label for w in rectangle.items], [w.label for w in WAYS["Sketcher_CreateRectangle"]])
        three_point = rectangle.items[2]
        self.assertEqual((three_point.command, three_point.method, three_point.tool, three_point.way),
                         ("Sketcher_CreateRectangle", 2, "Sketcher_CreateRectangle", 2))

    def test_box_cylinder_and_the_other_primitives(self):
        # one FreeCAD command makes them all, told which by its item number
        primitives = next(i for i in self.items(False, "Create") if i.label == "Primitive")
        self.assertEqual([p.label for p in primitives.items],
                         ["Box", "Cylinder", "Sphere", "Cone", "Ellipsoid", "Torus", "Prism", "Wedge"])
        self.assertEqual({p.command for p in primitives.items}, {"PartDesign_CompPrimitiveAdditive"})
        self.assertEqual([p.index for p in primitives.items], list(range(8)))
        self.assertTrue(primitives.items[1].icon.endswith("PartDesign_AdditiveCylinder.svg"), primitives.items[1].icon)

    def test_every_icon_is_in_the_build(self):
        # FreeCAD's icons from Studio's copies (Resources/command_icons), shown before their module loads;
        # Studio's own drawings (a way FreeCAD has no command for) by name
        root = os.path.join(FreeCAD.getHomePath(), "Mod", "Studio", "Resources", "command_icons")
        for sketching in (False, True):
            for item in self.flat(sketching):
                with self.subTest(item=item.label):
                    self.assertTrue(item.icon, "no icon")
                    if item.icon.startswith("src/"):
                        path = os.path.join(root, *item.icon.removeprefix("src/").split("/"))
                    else:
                        path = icons.line_icon(item.icon)
                    self.assertTrue(path and os.path.exists(path), path)

    def test_constrain_while_sketching(self):
        self.assertEqual(self.labels(True, "Constrain")[:2], ["Dimension", "Fully Constrain"])
        self.assertIn("Coincident", self.labels(True, "Constrain"))

    def test_a_tool_needing_sketch_geometry_says_so(self):
        move = next(i for i in self.flat(True) if i.command == "Sketcher_Move")
        self.assertTrue(move.needs_selection)
        self.assertIn("Select the sketch geometry first", move.tooltip)

    def test_every_sketch_tool_freecad_stops_without_a_selection_waits_for_one(self):
        # FreeCAD shows a "Wrong selection" dialog (or does nothing) when these start with nothing selected
        waiting = {i.command for i in self.flat(True) if i.needs_selection}
        self.assertEqual(waiting, {
            "Sketcher_Translate", "Sketcher_Rotate", "Sketcher_Symmetry", "Sketcher_Move", "Sketcher_Copy",
            "Sketcher_Scale", "Sketcher_Offset", "Sketcher_JoinCurves", "Sketcher_RemoveAxesAlignment",
            "Sketcher_ToggleDrivingConstraint", "Sketcher_ToggleActiveConstraint"})

    def test_a_constraint_tool_asks_for_constraints(self):
        driving = next(i for i in self.flat(True) if i.command == "Sketcher_ToggleDrivingConstraint")
        self.assertIn("Select the constraints first", driving.tooltip)


class Pins(_WithGroups):
    def item(self, command, sketching=False, index=-1):
        return next(i for i in self.flat(sketching) if i.command == command and i.index == index)

    def pinned(self, kind):
        return [b.label for b in self.groups.pinned_buttons(kind)]

    def test_nothing_pinned_at_first(self):
        for kind in TOOLS:
            self.assertEqual(self.pinned(kind), [], kind)

    def test_a_tool_pinned_for_faces_shows_for_faces_only(self):
        self.assertTrue(self.groups.pin("face", self.item("PartDesign_Boolean").key))
        self.assertEqual(self.pinned("face"), ["Combine"])
        self.assertEqual(self.pinned("edge"), [])
        self.assertTrue(self.groups.is_pinned("face", self.item("PartDesign_Boolean").key))

    def test_pinned_tools_in_the_order_pinned(self):
        self.groups.pin("face", self.item("PartDesign_Boolean").key)
        self.groups.pin("face", self.item("Part_CheckGeometry").key)
        self.assertEqual(self.pinned("face"), ["Combine", "Check Geometry"])

    def test_unpinned(self):
        key = self.item("PartDesign_Boolean").key
        self.groups.pin("face", key)
        self.assertTrue(self.groups.unpin("face", key))
        self.assertEqual(self.pinned("face"), [])
        self.assertFalse(self.groups.unpin("face", key))

    def test_remembered(self):
        self.groups.pin("sketch", self.item("PartDesign_Groove").key)
        again = ToolGroups(self.catalog, self.toolbar, self.keymap, Settings(root=self.settings.root))
        self.assertEqual([b.label for b in again.pinned_buttons("sketch")], ["Revolve Cut"])

    def test_not_twice(self):
        key = self.item("PartDesign_Boolean").key
        self.assertTrue(self.groups.pin("face", key))
        self.assertFalse(self.groups.pin("face", key))
        self.assertEqual(self.pinned("face"), ["Combine"])

    def test_a_tool_already_on_the_toolbar_for_that_selection_isnt_pinned(self):
        self.assertFalse(self.groups.pin("face", self.item("PartDesign_Fillet").key))
        self.assertEqual(self.pinned("face"), [])

    def test_a_pinned_button_runs_like_the_menu_item(self):
        cylinder = self.item("PartDesign_CompPrimitiveAdditive", index=1)
        self.groups.pin("nothing", cylinder.key)
        button = self.groups.pinned_buttons("nothing")[0]
        self.assertEqual((button.command, button.index, button.label, button.pinned),
                         ("PartDesign_CompPrimitiveAdditive", 1, "Cylinder", True))
        self.assertEqual(button.icon, cylinder.icon)

    def test_a_pinned_way_draws_that_way(self):
        rectangle = next(i for i in self.items(True, "Create") if i.label == "Rectangle")
        self.groups.pin("editing", rectangle.items[2].key)
        button = self.groups.pinned_buttons("editing")[0]
        self.assertEqual((button.label, button.command, button.method), ("3-Point Rectangle", "Sketcher_CreateRectangle", 2))

    def test_a_pin_no_longer_offered_is_left_out(self):
        self.settings.set(self.groups.pins_setting("face"), "No_SuchCommand;PartDesign_Boolean")
        self.assertEqual(self.pinned("face"), ["Combine"])

    def test_words_for_each_kind(self):
        self.assertEqual(set(KIND_WORDS), set(TOOLS))
        self.assertEqual(KIND_WORDS["face"], "for faces")
