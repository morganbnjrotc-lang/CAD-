# SPDX-License-Identifier: LGPL-2.1-or-later
"""Right-click a tool's field → Make Default (PLAN 3.6): studio.services.field_defaults.

The value a size box shows becomes what that box starts with the next time the tool makes a new
feature (Part Design's Extrude starts at FreeCAD's fixed 10 mm otherwise). Kept per feature type and
field, through Studio's settings service, in the field's own unit's base (millimeters, degrees).
"""

import unittest
import uuid

import FreeCAD

from studio.services.field_defaults import FieldDefaults
from studio.services.settings import Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"
PAD, FILLET = "PartDesign::Pad", "PartDesign::Fillet"


class Defaults(unittest.TestCase):
    def setUp(self):
        name = "FieldDefaults" + uuid.uuid4().hex[:8]
        self.settings = Settings(root=f"{TEST_PARENT}/{name}")
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.defaults = FieldDefaults(self.settings)

    def test_nothing_until_the_user_makes_a_default(self):
        self.assertEqual(self.defaults.for_feature(PAD), {})
        self.assertIsNone(self.defaults.get(PAD, "lengthEdit"))

    def test_a_default_made_is_what_the_feature_starts_with(self):
        self.defaults.make(PAD, "lengthEdit", 12.7)
        self.assertEqual(self.defaults.for_feature(PAD), {"lengthEdit": 12.7})
        self.assertAlmostEqual(self.defaults.get(PAD, "lengthEdit"), 12.7)

    def test_each_feature_type_keeps_its_own(self):
        self.defaults.make(PAD, "lengthEdit", 12.7)
        self.defaults.make(FILLET, "filletRadius", 1.5)
        self.assertEqual(self.defaults.for_feature(FILLET), {"filletRadius": 1.5})
        self.assertEqual(self.defaults.for_feature(PAD), {"lengthEdit": 12.7})

    def test_several_fields_of_one_feature(self):
        self.defaults.make(PAD, "lengthEdit", 25.4)
        self.defaults.make(PAD, "taperEdit", 2.0)
        self.assertEqual(self.defaults.for_feature(PAD), {"lengthEdit": 25.4, "taperEdit": 2.0})

    def test_making_it_again_replaces_it(self):
        self.defaults.make(PAD, "lengthEdit", 12.7)
        self.defaults.make(PAD, "lengthEdit", 6.35)
        self.assertEqual(self.defaults.for_feature(PAD), {"lengthEdit": 6.35})

    def test_forget_goes_back_to_freecads_start(self):
        self.defaults.make(PAD, "lengthEdit", 12.7)
        self.defaults.forget(PAD, "lengthEdit")
        self.assertEqual(self.defaults.for_feature(PAD), {})

    def test_kept_across_sessions(self):
        self.defaults.make(PAD, "lengthEdit", 0.1234567)
        again = FieldDefaults(Settings(root=self.settings.root))
        self.assertAlmostEqual(again.get(PAD, "lengthEdit"), 0.1234567, places=9)

    def test_negative_and_zero_values(self):
        self.defaults.make(PAD, "offsetEdit", -2.5)
        self.defaults.make(PAD, "taperEdit", 0.0)
        self.assertEqual(self.defaults.for_feature(PAD), {"offsetEdit": -2.5, "taperEdit": 0.0})

    def test_names_that_settings_cannot_hold_are_refused(self):
        with self.assertRaises(ValueError):
            self.defaults.make(PAD, "length edit", 1.0)
