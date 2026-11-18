# SPDX-License-Identifier: LGPL-2.1-or-later
"""Inches or millimeters (PLAN 3.1): the user's choice, and FreeCAD's unit settings that carry it out.

FreeCAD stores every size in millimeters and shows it through a unit schema: "Imperial decimal" shows
"2.50 in", the way Fusion does (its "US customary" switches to "thou" for small sizes). The choice
follows Windows' measurement system unless the user picks one (`UNITS`).

FreeCAD keeps a unit system in each document too, and switches to it when a document becomes active
(unless `IgnoreProjectSchema` is set) or when one of its properties changes status
(`Gui::Document::slotChangePropertyEditor`, which ignores that setting). So that the user's choice
holds everywhere, also in files saved in other units, `FreeCADUnits` sets both and gives open documents
the user's units (`apply`, `adopt`). Only how sizes show and how typed numbers read changes.
"""

import FreeCAD

from studio.services.settings import Setting

UNITS = Setting("Units/System", "system", choices=("system", "inches", "millimeters"))
SCHEMAS = {"inches": "ImperialDecimal", "millimeters": "Internal"}
FREECAD_UNITS = "User parameter:BaseApp/Preferences/Units"


def resolve(choice: str, windows_uses_inches: bool) -> str:
    """"inches" or "millimeters" for a choice ("system" follows Windows)."""
    if choice == "system":
        return "inches" if windows_uses_inches else "millimeters"
    return choice


def schema_index(units: str) -> int:
    return FreeCAD.Units.listSchemas().index(SCHEMAS[units])


def _unit_system(doc) -> int:
    return doc.getEnumerationsOfProperty("UnitSystem").index(doc.UnitSystem)


class FreeCADUnits:
    """Writes the units into FreeCAD's unit settings (under `root`), uses them now (`set_schema`) and
    gives the open documents (`documents`) the same units."""

    def __init__(self, root: str = FREECAD_UNITS, set_schema=None, documents=None):
        self._root = root
        self._set_schema = set_schema or FreeCAD.Units.setSchema
        self._documents = documents or (lambda: FreeCAD.listDocuments().values())
        self.schema = None  # the schema index once applied

    def apply(self, units: str) -> int:
        index = schema_index(units)
        group = FreeCAD.ParamGet(self._root)
        group.SetInt("UserSchema", index)  # new documents get it
        group.SetBool("IgnoreProjectSchema", True)
        self.schema = index
        self._set_schema(index)
        for doc in list(self._documents()):
            self.adopt(doc)
        return index

    def adopt(self, doc) -> bool:
        """Gives `doc` the user's units; True if they changed. Nothing before the first `apply`."""
        if self.schema is None or _unit_system(doc) == self.schema:
            return False
        doc.UnitSystem = self.schema
        return True
