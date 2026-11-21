# SPDX-License-Identifier: LGPL-2.1-or-later
"""Right-click a tool's field → Make Default (PLAN 3.6, the FizCAD demo's "Make default").

The value a size box shows becomes what that box starts with the next time its tool makes a new feature
(Part Design's Extrude otherwise starts at FreeCAD's fixed 10 mm). Kept per feature type and field (the
box's object name in FreeCAD's panel, e.g. "lengthEdit"), in the box's own unit's base: millimeters for
a size, degrees for an angle. Stored through the settings service under `Defaults/<feature type>`.
"""

from studio.services.settings import Setting

GROUP = "Defaults"


def _group(kind: str) -> str:
    return f"{GROUP}/{kind.replace('::', '_')}"  # "PartDesign::Pad" -> Defaults/PartDesign_Pad


class FieldDefaults:
    def __init__(self, settings):
        self._settings = settings

    def _setting(self, kind: str, field: str) -> Setting:
        return Setting(f"{_group(kind)}/{field}", 0.0)  # ValueError for a name settings can't hold

    def make(self, kind: str, field: str, value: float) -> None:
        self._settings.set(self._setting(kind, field), float(value))

    def forget(self, kind: str, field: str) -> None:
        self._settings.reset(self._setting(kind, field))

    def get(self, kind: str, field: str):
        """The default made for this field, or None."""
        setting = self._setting(kind, field)
        return self._settings.get(setting) if self._settings.is_overridden(setting) else None

    def for_feature(self, kind: str) -> dict:
        """{field: value} for every default made for this feature type."""
        result = {}
        for field in self._settings.names(_group(kind)):
            value = self.get(kind, field)
            if value is not None:
                result[field] = value
        return result
