# SPDX-License-Identifier: LGPL-2.1-or-later
"""Typed settings on FreeCAD's parameter store (PLAN 2.2).

A `Setting` is declared where it is used, with a built-in default whose type is the setting's type:

    EXTRUDE_DISTANCE = Setting("Tools/Extrude/Distance", 10.0)
    settings.get(EXTRUDE_DISTANCE)          # 10.0 until the user sets a value
    settings.set(EXTRUDE_DISTANCE, 25.0)    # e.g. right-click a field -> "Make default"
    settings.reset(EXTRUDE_DISTANCE)        # back to the built-in default

User values live in FreeCAD's parameter store (user.cfg) under `Settings.root`, one group per path
segment of the key. A stored value of the wrong type, or no longer one of the choices (e.g. after
the setting changed in a newer version), is ignored and the built-in default applies.

FreeCAD writes decimals with 12 digits after the point, so values smaller than about 5e-13 are
stored as 0; integers are 32-bit.
"""

import math
import re
from dataclasses import dataclass

import FreeCAD

ROOT = "User parameter:BaseApp/Preferences/Mod/Studio"

# Python type -> (FreeCAD parameter kind used in Get*/Set*/Rem*, type name in GetContents()).
_KINDS = {bool: ("Bool", "Boolean"), int: ("Int", "Integer"), float: ("Float", "Float"), str: ("String", "String")}
_NAME = re.compile(r"[A-Za-z0-9_]+")
_INT_RANGE = (-(2**31), 2**31 - 1)  # FreeCAD stores integers as 32-bit `long` on Windows


@dataclass(frozen=True)
class Setting:
    """One typed setting. `key` is a path of plain names ("Tools/Extrude/Distance"); the type of
    `default` (bool, int, float or str) is the setting's type. Text settings may list `choices`."""

    key: str
    default: object
    choices: tuple = ()

    def __post_init__(self):
        if type(self.default) not in _KINDS:
            raise TypeError(f"{self.key}: unsupported setting type {type(self.default).__name__}")
        if not all(_NAME.fullmatch(part) for part in self.key.split("/")):
            raise ValueError(f"setting key must be names joined by '/': {self.key!r}")
        if self.choices:
            if type(self.default) is not str:
                raise TypeError(f"{self.key}: choices are only for text settings")
            if self.default not in self.choices:
                raise ValueError(f"{self.key}: default {self.default!r} is not one of {self.choices}")

    @property
    def type(self) -> type:
        return type(self.default)

    def check(self, value):
        """`value` converted to this setting's type; TypeError/ValueError if it doesn't fit."""
        wanted = self.type
        if wanted is float and type(value) is int:
            value = float(value)
        if type(value) is not wanted:  # exact: bool is an int subclass, but not a valid int here
            raise TypeError(f"{self.key} takes {wanted.__name__}, got {type(value).__name__}")
        if wanted is int and not _INT_RANGE[0] <= value <= _INT_RANGE[1]:
            raise ValueError(f"{self.key}: {value} is outside the 32-bit range FreeCAD stores")
        if wanted is float and not math.isfinite(value):
            raise ValueError(f"{self.key}: {value} is not a finite number")
        if self.choices and value not in self.choices:
            raise ValueError(f"{self.key}: {value!r} is not one of {self.choices}")
        return value


class Settings:
    """Reads and writes `Setting`s under `root` in FreeCAD's parameter store."""

    def __init__(self, root: str = ROOT):
        self.root = root

    def _group_and_name(self, setting: Setting):
        path, _, name = setting.key.rpartition("/")
        return FreeCAD.ParamGet(f"{self.root}/{path}" if path else self.root), name

    def _stored(self, setting: Setting):
        """(True, value) if a usable user value is stored, else (False, None)."""
        group, name = self._group_and_name(setting)
        stored_type = _KINDS[setting.type][1]
        for entry_type, entry_name, value in group.GetContents() or []:
            if entry_name == name and entry_type == stored_type:
                try:
                    return True, setting.check(value)
                except (TypeError, ValueError):
                    return False, None
        return False, None

    def get(self, setting: Setting):
        found, value = self._stored(setting)
        return value if found else setting.default

    def is_overridden(self, setting: Setting) -> bool:
        return self._stored(setting)[0]

    def set(self, setting: Setting, value) -> None:
        value = setting.check(value)
        group, name = self._group_and_name(setting)
        getattr(group, "Set" + _KINDS[setting.type][0])(name, value)

    def reset(self, setting: Setting) -> None:
        group, name = self._group_and_name(setting)
        getattr(group, "Rem" + _KINDS[setting.type][0])(name)
