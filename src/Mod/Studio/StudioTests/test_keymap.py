# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keymap (studio.interaction.keymap), docs/adr/0008-keymap-contexts.md / PLAN 2.4.

A binding is (context, key sequence) -> catalog command. Global is always active; a workbench's
context while doing that kind of work (sketching -> SketcherWorkbench). Lookups go from the most
specific active context to Global. Defaults: FreeCAD's shortcuts in their command's context, plus
Studio's E / F / Shift+F in Global; the user's bindings override both.
"""

import unittest
import uuid

import FreeCAD

from studio.interaction.keymap import GLOBAL, STUDIO_DEFAULTS, Keymap, SequenceMatcher, normalize
from studio.services.commands import CommandCatalog
from studio.services.settings import Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


def command(name, workbench, shortcut=""):
    return {"name": name, "workbench": workbench, "menu_text": name, "tooltip": "", "shortcut": shortcut,
            "icon": None}


CATALOG = {
    "freecad": "27.1.0",
    "workbenches": [{"name": "SketcherWorkbench", "class": ""}, {"name": "PartDesignWorkbench", "class": ""},
                    {"name": "AssemblyWorkbench", "class": ""}],
    "commands": [
        command("Std_Undo", None, "Ctrl+Z"),
        command("Std_ViewFitAll", None, "V, F"),
        command("Std_ViewFitSelection", None, "V, S"),
        command("Std_ViewZoomIn", None, "Ctrl++"),
        command("Sketcher_ConstrainEqual", "SketcherWorkbench", "E"),
        command("Sketcher_Dimension", "SketcherWorkbench", "D"),
        command("Sketcher_CreateLine", "SketcherWorkbench", "G, L"),
        command("Sketcher_ToggleGrid", "SketcherWorkbench", "V"),  # prefix of Global's "V, F"
        command("PartDesign_Pad", "PartDesignWorkbench"),
        command("Assembly_CreateView", "AssemblyWorkbench", "E"),
        command("Assembly_JointFixed", "AssemblyWorkbench", "F"),
        command("Assembly_JointFixedToo", "AssemblyWorkbench", "F"),  # clashes with the one above
    ],
}


class Normalize(unittest.TestCase):
    def test_canonical_form(self):
        cases = {
            "shift+f": "Shift+F", "ctrl+shift+z": "Ctrl+Shift+Z", "Shift+Ctrl+Z": "Ctrl+Shift+Z",
            "alt+shift+ctrl+meta+x": "Ctrl+Alt+Shift+Meta+X", "v,f": "V, F", "V, F": "V, F",
            "g, 3, a": "G, 3, A", "Ctrl++": "Ctrl++", "Ctrl+,": "Ctrl+,", "Ctrl+-": "Ctrl+-",
            "esc": "Esc", "ESCAPE": "Esc", "delete": "Del", "f11": "F11", "alt+return": "Alt+Return",
            "ctrl+shift+tab": "Ctrl+Shift+Tab", "shift+left": "Shift+Left", "space": "Space", "": "",
        }
        for given, expected in cases.items():
            with self.subTest(given=given):
                self.assertEqual(normalize(given), expected)

    def test_malformed_sequences_are_refused(self):
        for given in ("Ctrl+Ctrl+A", "Ctrl+", "Shift+", "Foo", "Ctrl+Foo", "A, B, C, D, E", "A,,B", "F99"):
            with self.subTest(given=given), self.assertRaises(ValueError):
                normalize(given)

    def test_every_freecad_default_in_the_shipped_catalog_is_understood(self):
        for info in CommandCatalog.load().commands():
            if info.shortcut:
                with self.subTest(command=info.name):
                    self.assertEqual(normalize(normalize(info.shortcut)), normalize(info.shortcut))


class KeymapTestCase(unittest.TestCase):
    def setUp(self):
        name = "Keymap" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.catalog = CommandCatalog(CATALOG)
        self.keymap = Keymap(self.catalog, self.settings)


class Defaults(KeymapTestCase):
    def test_studio_defaults_in_global(self):
        # E / F / Shift+F from PLAN 2.4; S and Ctrl+K open the command palette (the user's choice for
        # 2.5: S like Fusion 360 outside sketches, where S is Sketcher's; Ctrl+K everywhere).
        self.assertEqual(STUDIO_DEFAULTS, {GLOBAL: {
            "E": "PartDesign_Pad", "F": "Std_ViewFitSelection", "Shift+F": "Std_ViewFitAll",
            "S": "Studio_CommandPalette", "Ctrl+K": "Studio_CommandPalette"}})

    def test_global_keys_work_everywhere(self):
        self.assertEqual(self.keymap.resolve("E"), "PartDesign_Pad")
        self.assertEqual(self.keymap.resolve("Shift+F"), "Std_ViewFitAll")
        self.assertEqual(self.keymap.resolve("ctrl+z"), "Std_Undo")  # input is normalized

    def test_freecad_shortcuts_are_kept_next_to_studios(self):
        self.assertEqual(self.keymap.sequences("Std_ViewFitAll"), ["Shift+F", "V, F"])
        self.assertEqual(self.keymap.resolve("V, F"), "Std_ViewFitAll")

    def test_a_workbench_context_wins_while_active(self):
        self.assertEqual(self.keymap.resolve("E", ["SketcherWorkbench"]), "Sketcher_ConstrainEqual")
        self.assertEqual(self.keymap.resolve("E", ["AssemblyWorkbench"]), "Assembly_CreateView")
        self.assertEqual(self.keymap.resolve("Shift+F", ["SketcherWorkbench"]), "Std_ViewFitAll")

    def test_workbench_keys_do_nothing_outside_their_context(self):
        self.assertIsNone(self.keymap.resolve("D"))
        self.assertEqual(self.keymap.resolve("D", ["SketcherWorkbench"]), "Sketcher_Dimension")

    def test_contexts_are_global_then_the_catalog_workbenches(self):
        self.assertEqual(self.keymap.contexts(),
                         [GLOBAL, "SketcherWorkbench", "PartDesignWorkbench", "AssemblyWorkbench"])


class Conflicts(KeymapTestCase):
    def test_same_key_twice_in_one_context_is_reported_and_the_earlier_wins(self):
        self.assertEqual(self.keymap.resolve("F", ["AssemblyWorkbench"]), "Assembly_JointFixed")
        found = [(c.context, c.sequence, c.winner, c.loser) for c in self.keymap.conflicts()]
        self.assertIn(("AssemblyWorkbench", "F", "Assembly_JointFixed", "Assembly_JointFixedToo"), found)

    def test_a_context_overriding_global_is_not_a_conflict(self):
        reported = {(c.context, c.sequence) for c in self.keymap.conflicts()}
        self.assertNotIn(("SketcherWorkbench", "E"), reported)

    def test_active_bindings_drop_global_sequences_a_context_key_would_make_ambiguous(self):
        # In a sketch, "V" toggles the grid; Global's "V, F" must not make Qt wait for a second key.
        active = self.keymap.active_bindings(["SketcherWorkbench"])
        self.assertEqual(active["V"], "Sketcher_ToggleGrid")
        self.assertNotIn("V, F", active)
        self.assertNotIn("V, S", active)
        self.assertEqual(active["Shift+F"], "Std_ViewFitAll")
        self.assertEqual(self.keymap.active_bindings()["V, F"], "Std_ViewFitAll")

    def test_prefix_clash_inside_one_context_is_reported(self):
        keymap = Keymap(CommandCatalog(dict(CATALOG, commands=CATALOG["commands"] + [
            command("Sketcher_Grid2", "SketcherWorkbench", "V, G")])), self.settings)
        found = {(c.context, c.sequence, c.loser) for c in keymap.conflicts()}
        self.assertIn(("SketcherWorkbench", "V, G", "Sketcher_Grid2"), found)


class UserBindings(KeymapTestCase):
    def test_user_binding_replaces_the_defaults_and_is_stored(self):
        self.keymap.set_sequences("Std_ViewFitAll", ["ctrl+shift+a"])
        self.assertEqual(self.keymap.sequences("Std_ViewFitAll"), ["Ctrl+Shift+A"])
        self.assertIsNone(self.keymap.resolve("Shift+F"))
        again = Keymap(self.catalog, self.settings)  # next session
        self.assertEqual(again.resolve("Ctrl+Shift+A"), "Std_ViewFitAll")

    def test_rebinding_a_command_replaces_its_studio_default_wherever_it_lives(self):
        # E (Extrude = PartDesign_Pad) is a Studio default in Global, though Pad belongs to Part
        # Design's context: rebinding Extrude must take E away, not add a second key.
        self.keymap.set_sequences("PartDesign_Pad", ["Ctrl+E"])
        self.assertIsNone(self.keymap.resolve("E"))
        self.assertEqual(self.keymap.resolve("Ctrl+E"), "PartDesign_Pad")

    def test_several_sequences_for_one_command(self):
        self.keymap.set_sequences("PartDesign_Pad", ["E", "P, D"])
        self.assertEqual(Keymap(self.catalog, self.settings).sequences("PartDesign_Pad"), ["E", "P, D"])

    def test_unbinding_removes_every_sequence(self):
        self.keymap.set_sequences("Std_ViewFitAll", [])
        self.assertEqual(self.keymap.sequences("Std_ViewFitAll"), [])
        self.assertIsNone(Keymap(self.catalog, self.settings).resolve("V, F"))

    def test_user_key_wins_over_a_default_and_the_loser_is_reported(self):
        self.keymap.set_sequences("Std_Undo", ["F"])
        self.assertEqual(self.keymap.resolve("F"), "Std_Undo")
        found = [(c.context, c.sequence, c.winner, c.loser) for c in self.keymap.conflicts()]
        self.assertIn((GLOBAL, "F", "Std_Undo", "Std_ViewFitSelection"), found)

    def test_reset_brings_the_defaults_back(self):
        self.keymap.set_sequences("Std_ViewFitAll", [])
        self.keymap.reset("Std_ViewFitAll")
        self.assertEqual(Keymap(self.catalog, self.settings).sequences("Std_ViewFitAll"), ["Shift+F", "V, F"])

    def test_any_command_can_be_bound_in_any_context(self):
        self.keymap.set_sequences("Sketcher_Dimension", ["Ctrl+D"], context=GLOBAL)
        self.assertEqual(self.keymap.resolve("Ctrl+D"), "Sketcher_Dimension")
        self.assertEqual(self.keymap.resolve("D", ["SketcherWorkbench"]), "Sketcher_Dimension")

    def test_bad_input_is_refused_and_nothing_is_stored(self):
        with self.assertRaises(KeyError):
            self.keymap.set_sequences("PartDesign_Teleport", ["T"])
        with self.assertRaises(KeyError):
            self.keymap.set_sequences("Std_Undo", ["U"], context="NoSuchContext")
        with self.assertRaises(ValueError):
            self.keymap.set_sequences("Std_Undo", ["Ctrl+Foo"])
        self.assertEqual(self.settings.names(f"Keymap/{GLOBAL}"), [])
        self.assertEqual(self.keymap.sequences("Std_Undo"), ["Ctrl+Z"])


class Matching(unittest.TestCase):
    """SequenceMatcher: keys arrive one chord at a time; a sequence runs when complete."""

    BINDINGS = {"E": "PartDesign_Pad", "G, L": "Sketcher_CreateLine", "G, 3, A": "Sketcher_Arc3",
                "Ctrl+Z": "Std_Undo"}

    def setUp(self):
        self.matcher = SequenceMatcher(self.BINDINGS)

    def test_single_key_runs_at_once(self):
        self.assertEqual(self.matcher.feed("E"), ("run", "PartDesign_Pad"))
        self.assertEqual(self.matcher.pending, "")

    def test_a_sequence_waits_then_runs(self):
        self.assertEqual(self.matcher.feed("G"), ("wait", None))
        self.assertEqual(self.matcher.pending, "G")
        self.assertEqual(self.matcher.feed("L"), ("run", "Sketcher_CreateLine"))
        self.assertEqual(self.matcher.feed("G"), ("wait", None))
        self.assertEqual(self.matcher.feed("3"), ("wait", None))
        self.assertEqual(self.matcher.feed("A"), ("run", "Sketcher_Arc3"))

    def test_unbound_key_is_not_ours(self):
        self.assertEqual(self.matcher.feed("Q"), ("none", None))
        self.assertEqual(self.matcher.feed("Ctrl+S"), ("none", None))

    def test_a_dead_end_drops_the_pending_keys_and_tries_the_key_on_its_own(self):
        self.assertEqual(self.matcher.feed("G"), ("wait", None))
        self.assertEqual(self.matcher.feed("E"), ("run", "PartDesign_Pad"))
        self.assertEqual(self.matcher.feed("G"), ("wait", None))
        self.assertEqual(self.matcher.feed("Q"), ("none", None))
        self.assertEqual(self.matcher.pending, "")

    def test_reset_forgets_pending_keys(self):
        self.matcher.feed("G")
        self.matcher.reset()
        self.assertEqual(self.matcher.feed("L"), ("none", None))

    def test_wants_says_whether_a_key_would_be_used_without_consuming_it(self):
        self.assertTrue(self.matcher.wants("E"))
        self.assertTrue(self.matcher.wants("G"))
        self.assertFalse(self.matcher.wants("L"))  # only after G
        self.matcher.feed("G")
        self.assertTrue(self.matcher.wants("L"))
        self.assertEqual(self.matcher.pending, "G")

    def test_peek_tells_what_a_key_would_do_without_consuming_it(self):
        self.assertEqual(self.matcher.peek("E"), ("run", "PartDesign_Pad"))
        self.assertEqual(self.matcher.peek("G"), ("wait", None))
        self.assertEqual(self.matcher.peek("Q"), ("none", None))
        self.matcher.feed("G")
        self.assertEqual(self.matcher.peek("L"), ("run", "Sketcher_CreateLine"))
        self.assertEqual(self.matcher.peek("E"), ("run", "PartDesign_Pad"))  # dead end, then E alone
        self.assertEqual(self.matcher.pending, "G")

    def test_refuses_bindings_where_one_sequence_starts_another(self):
        with self.assertRaises(ValueError):
            SequenceMatcher({"V": "A", "V, F": "B"})


class ShippedCatalog(unittest.TestCase):
    def test_studio_defaults_name_real_commands(self):
        catalog = CommandCatalog.load()
        for context, bindings in STUDIO_DEFAULTS.items():
            for sequence, name in bindings.items():
                with self.subTest(sequence=sequence):
                    self.assertEqual(catalog.get(name).name, name)


if __name__ == "__main__":
    unittest.main()
