# SPDX-License-Identifier: LGPL-2.1-or-later
"""Settings service (studio.services.settings), PLAN 2.2.

Typed preferences on FreeCAD's parameter store: every setting has a built-in default, a user value
overrides it, and "Make default" on a field stores the field's current value as the user value.
Runs against the real parameter store, each test under its own throwaway group.
"""

import math
import unittest
import uuid

import FreeCAD

from studio.services.settings import Setting, Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


class SettingsTestCase(unittest.TestCase):
    def setUp(self):
        name = "Settings" + uuid.uuid4().hex[:8]
        self.root = f"{TEST_PARENT}/{name}"
        self.settings = Settings(root=self.root)

        def remove_group():
            FreeCAD.ParamGet(TEST_PARENT).RemGroup(name)
            parent, _, leaf = TEST_PARENT.rpartition("/")
            if FreeCAD.ParamGet(TEST_PARENT).IsEmpty():
                FreeCAD.ParamGet(parent).RemGroup(leaf)

        self.addCleanup(remove_group)

    def stored(self, key):
        """What FreeCAD's parameter store holds for `key`: [(type, name, value)]."""
        group_path, _, name = key.rpartition("/")
        group = FreeCAD.ParamGet(f"{self.root}/{group_path}" if group_path else self.root)
        return [entry for entry in group.GetContents() or [] if entry[1] == name]


class DefaultsAndOverrides(SettingsTestCase):
    def test_built_in_default_until_the_user_sets_a_value(self):
        distance = Setting("Tools/Extrude/Distance", 10.0)
        self.assertEqual(self.settings.get(distance), 10.0)
        self.assertFalse(self.settings.is_overridden(distance))

    def test_user_value_overrides_default_and_is_stored_in_freecads_parameters(self):
        distance = Setting("Tools/Extrude/Distance", 10.0)
        self.settings.set(distance, 25.5)  # "Make default" on the field
        self.assertEqual(self.settings.get(distance), 25.5)
        self.assertTrue(self.settings.is_overridden(distance))
        self.assertEqual(self.stored("Tools/Extrude/Distance"), [("Float", "Distance", 25.5)])

    def test_user_value_survives_a_new_service_instance(self):
        # Another part of the app (or the next session) reads the same parameter store.
        warmup = Setting("Commands/WarmUp", True)
        self.settings.set(warmup, False)
        self.assertIs(Settings(root=self.root).get(warmup), False)

    def test_reset_goes_back_to_the_built_in_default(self):
        distance = Setting("Tools/Extrude/Distance", 10.0)
        self.settings.set(distance, 25.5)
        self.settings.reset(distance)
        self.assertEqual(self.settings.get(distance), 10.0)
        self.assertFalse(self.settings.is_overridden(distance))
        self.assertEqual(self.stored("Tools/Extrude/Distance"), [])

    def test_reset_of_a_setting_never_set_is_harmless(self):
        self.settings.reset(Setting("Never/Set", 1))

    def test_setting_the_default_value_still_counts_as_the_users_choice(self):
        # If we later change the built-in default, a user who chose the old value keeps it.
        steps = Setting("View/ZoomSteps", 5)
        self.settings.set(steps, 5)
        self.assertTrue(self.settings.is_overridden(steps))


class Types(SettingsTestCase):
    def test_each_supported_type_round_trips_with_its_type(self):
        cases = [
            (Setting("T/Flag", False), True, "Boolean"),
            (Setting("T/Count", 3), -7, "Integer"),
            (Setting("T/Size", 1.5), 0.25, "Float"),
            (Setting("T/Name", "mm"), "Ünïcode ✓", "String"),
        ]
        for setting, value, stored_type in cases:
            with self.subTest(key=setting.key):
                self.settings.set(setting, value)
                got = self.settings.get(setting)
                self.assertEqual(got, value)
                self.assertIs(type(got), type(setting.default))
                self.assertEqual(self.stored(setting.key)[0][0], stored_type)

    def test_whole_number_accepted_for_a_decimal_setting(self):
        size = Setting("T/Size", 1.5)
        self.settings.set(size, 4)
        self.assertEqual(self.settings.get(size), 4.0)
        self.assertIs(type(self.settings.get(size)), float)

    def test_wrong_type_is_refused_and_nothing_is_stored(self):
        cases = [
            (Setting("T/Count", 3), "3"),
            (Setting("T/Count", 3), 2.5),
            (Setting("T/Count", 3), True),  # bool is an int subclass in Python; still refused
            (Setting("T/Size", 1.5), True),
            (Setting("T/Flag", False), 1),
            (Setting("T/Name", "mm"), 5),
        ]
        for setting, value in cases:
            with self.subTest(key=setting.key, value=value):
                with self.assertRaises(TypeError):
                    self.settings.set(setting, value)
                self.assertEqual(self.stored(setting.key), [])

    def test_integer_must_fit_freecads_32_bit_storage(self):
        count = Setting("T/Count", 3)
        for value in (2**31, -(2**31) - 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.settings.set(count, value)
        self.settings.set(count, 2**31 - 1)
        self.assertEqual(self.settings.get(count), 2**31 - 1)

    def test_decimals_keep_the_precision_settings_need(self):
        # FreeCAD writes decimals with 12 digits after the point ("{:.12f}" in Parameter.cpp), so
        # only values below ~5e-13 are lost. Pin what real settings use: mm lengths, tolerances.
        size = Setting("T/Size", 1.5)
        for value in (1e-7, 0.1 + 0.2, 123456.789, -2.5e-4):
            with self.subTest(value=value):
                self.settings.set(size, value)
                self.assertTrue(math.isclose(self.settings.get(size), value, rel_tol=1e-5))

    def test_decimal_must_be_finite(self):
        size = Setting("T/Size", 1.5)
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.settings.set(size, value)

    def test_unsupported_default_type_is_refused(self):
        for default in ([1], None, (1,), {"a": 1}):
            with self.subTest(default=default), self.assertRaises(TypeError):
                Setting("T/Bad", default)

    def test_value_stored_with_another_type_is_ignored(self):
        # E.g. an older version stored this setting as an integer and it is now a decimal.
        size = Setting("T/Size", 1.5)
        FreeCAD.ParamGet(f"{self.root}/T").SetInt("Size", 7)
        self.assertEqual(self.settings.get(size), 1.5)
        self.assertFalse(self.settings.is_overridden(size))


class Choices(SettingsTestCase):
    def test_only_listed_choices_can_be_set(self):
        style = Setting("View/Projection", "perspective", choices=("perspective", "orthographic"))
        self.settings.set(style, "orthographic")
        self.assertEqual(self.settings.get(style), "orthographic")
        with self.assertRaises(ValueError):
            self.settings.set(style, "fisheye")

    def test_stored_value_that_is_no_longer_a_choice_falls_back_to_the_default(self):
        old = Setting("View/Projection", "perspective", choices=("perspective", "isometric"))
        self.settings.set(old, "isometric")
        new = Setting("View/Projection", "perspective", choices=("perspective", "orthographic"))
        self.assertEqual(self.settings.get(new), "perspective")
        self.assertFalse(self.settings.is_overridden(new))

    def test_default_must_be_one_of_the_choices(self):
        with self.assertRaises(ValueError):
            Setting("View/Projection", "fisheye", choices=("perspective", "orthographic"))

    def test_choices_only_for_text_settings(self):
        with self.assertRaises(TypeError):
            Setting("T/Count", 1, choices=(1, 2))


class Keys(SettingsTestCase):
    def test_key_is_a_path_of_plain_names(self):
        for key in ("", "/Lead", "Trail/", "Double//Slash", "Has Space/X", "Dot.Name/X", "Ümlaut/X"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                Setting(key, 1)

    def test_single_name_key_lives_directly_under_the_root(self):
        top = Setting("Top", 1)
        self.settings.set(top, 2)
        self.assertEqual(self.stored("Top"), [("Integer", "Top", 2)])

    def test_default_root_is_studios_preference_group(self):
        self.assertEqual(Settings().root, "User parameter:BaseApp/Preferences/Mod/Studio")


if __name__ == "__main__":
    unittest.main()
