# SPDX-License-Identifier: LGPL-2.1-or-later
"""Inches or millimeters (PLAN 3.1): the choice, and FreeCAD's unit settings that carry it out."""

import unittest
import uuid

import FreeCAD

from studio.services import units
from studio.services.settings import Settings

TEST_PARENT = "User parameter:BaseApp/Preferences/Mod/Studio/Tests"


def schema(name):
    return FreeCAD.Units.listSchemas().index(name)


class Choice(unittest.TestCase):
    def test_follows_windows_by_default(self):
        self.assertEqual(units.UNITS.default, "system")
        self.assertEqual(units.resolve("system", windows_uses_inches=True), "inches")
        self.assertEqual(units.resolve("system", windows_uses_inches=False), "millimeters")

    def test_a_picked_unit_ignores_windows(self):
        self.assertEqual(units.resolve("inches", windows_uses_inches=False), "inches")
        self.assertEqual(units.resolve("millimeters", windows_uses_inches=True), "millimeters")

    def test_choices(self):
        self.assertEqual(units.UNITS.choices, ("system", "inches", "millimeters"))
        name = "Units" + uuid.uuid4().hex[:8]
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        settings = Settings(f"{TEST_PARENT}/{name}")
        settings.set(units.UNITS, "inches")
        self.assertEqual(settings.get(units.UNITS), "inches")
        with self.assertRaises(ValueError):
            settings.set(units.UNITS, "furlongs")


class Schemas(unittest.TestCase):
    """Sizes read the way Fusion shows them: "2.50 in", "63.50 mm"."""

    def test_inches_are_decimal_inches(self):
        self.assertEqual(units.schema_index("inches"), schema("ImperialDecimal"))
        translated = FreeCAD.Units.schemaTranslate(FreeCAD.Units.Quantity("63.5 mm"), units.schema_index("inches"))
        self.assertEqual(translated[0], "2.50 in")
        # Small sizes stay in inches (FreeCAD's "US customary" switches to "thou").
        translated = FreeCAD.Units.schemaTranslate(FreeCAD.Units.Quantity("0.635 mm"), units.schema_index("inches"))
        self.assertTrue(translated[0].endswith(" in"), translated[0])

    def test_millimeters_are_freecads_standard(self):
        self.assertEqual(units.schema_index("millimeters"), schema("Internal"))


class FreeCADUnitSettings(unittest.TestCase):
    """Written into a test copy of FreeCAD's unit settings; the schema in use is recorded, not changed."""

    def setUp(self):
        name = "Units" + uuid.uuid4().hex[:8]
        self.path = f"{TEST_PARENT}/{name}"
        self.addCleanup(lambda: FreeCAD.ParamGet(TEST_PARENT).RemGroup(name))
        self.group = FreeCAD.ParamGet(self.path)
        self.schemas = []
        self.docs = []
        self.freecad = units.FreeCADUnits(root=self.path, set_schema=self.schemas.append,
                                          documents=lambda: self.docs)

    def new_doc(self, unit_system):
        doc = FreeCAD.newDocument("Units" + uuid.uuid4().hex[:8])
        self.addCleanup(FreeCAD.closeDocument, doc.Name)
        doc.UnitSystem = unit_system
        return doc

    def test_new_parts_get_the_units(self):
        # FreeCAD gives a new document the unit system in UserSchema.
        self.freecad.apply("inches")
        self.assertEqual(self.group.GetInt("UserSchema", -1), schema("ImperialDecimal"))
        self.freecad.apply("millimeters")
        self.assertEqual(self.group.GetInt("UserSchema", -1), schema("Internal"))

    def test_the_units_are_used_now(self):
        self.freecad.apply("inches")
        self.assertEqual(self.schemas, [schema("ImperialDecimal")])

    def test_every_part_shows_the_users_units(self):
        # Not each file's own: FreeCAD switches to a document's units when it becomes active unless
        # IgnoreProjectSchema is set.
        self.freecad.apply("inches")
        self.assertTrue(self.group.GetBool("IgnoreProjectSchema", False))

    def test_open_parts_take_the_units(self):
        # FreeCAD also switches to a document's units when one of its properties changes status
        # (Gui::Document::slotChangePropertyEditor, which ignores IgnoreProjectSchema): a part saved in
        # millimeters would turn the app back to millimeters while the user edits it.
        metric = self.new_doc(schema("Internal"))
        self.docs.append(metric)
        self.freecad.apply("inches")
        self.assertEqual(metric.getEnumerationsOfProperty("UnitSystem").index(metric.UnitSystem),
                         schema("ImperialDecimal"))

    def test_a_part_opened_later_takes_the_units(self):
        self.freecad.apply("inches")
        metric = self.new_doc(schema("Internal"))
        self.assertTrue(self.freecad.adopt(metric))
        self.assertEqual(metric.getEnumerationsOfProperty("UnitSystem").index(metric.UnitSystem),
                         schema("ImperialDecimal"))
        self.assertFalse(self.freecad.adopt(metric), "already in the user's units")

    def test_before_a_choice_a_part_keeps_its_units(self):
        metric = self.new_doc(schema("Internal"))
        self.assertFalse(self.freecad.adopt(metric))
        self.assertEqual(metric.getEnumerationsOfProperty("UnitSystem").index(metric.UnitSystem), schema("Internal"))
