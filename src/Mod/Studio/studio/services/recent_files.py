# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD's recent-files list (PLAN 2.8), so the Home page and FreeCAD's File menu always agree.

FreeCAD keeps it in its parameters: "MRU0", "MRU1", ... (most recent first) and "RecentFiles", the
number of entries to keep. FreeCAD's File > Recent Files menu holds its own copy and reloads it
when "RecentFiles" is written, so `remove` rewrites the list and then writes that key.

FreeCAD keeps 4 recent files by default, too few to fill the Home page: `raise_limit_once` raises
it to HOME_COUNT once per profile, so a smaller size picked later in Preferences > General stays.
"""

import os
import re
from dataclasses import dataclass

import FreeCAD

from studio.services.settings import Setting

GROUP = "User parameter:BaseApp/Preferences/RecentFiles"
DEFAULT_COUNT = 4  # FreeCAD's own default number of recent files
HOME_COUNT = 12  # Studio's: enough cards to fill the Home page
LIMIT_RAISED = Setting("Home/RecentFilesLimitRaised", False)
_MRU = re.compile(r"MRU(\d+)$")


@dataclass(frozen=True)
class RecentFile:
    path: str
    exists: bool
    modified: float | None  # last saved, seconds since the epoch; None if the file is gone


def _key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


class RecentFiles:
    def __init__(self, group_path: str = GROUP):
        self._path = group_path

    def _group(self):
        return FreeCAD.ParamGet(self._path)

    def _entries(self):
        return [(int(m.group(1)), name, value)
                for kind, name, value in self._group().GetContents() or []
                if kind == "String" and (m := _MRU.match(name))]

    def limit(self) -> int:
        """How many files FreeCAD keeps in the list."""
        return self._group().GetInt("RecentFiles", DEFAULT_COUNT)

    def paths(self) -> list:
        """Most recent first. Sorted by number: MRU10 comes after MRU9. A file listed twice
        (FreeCAD writes "C:/dir/a.FCStd", another tool "c:\\dir\\a.fcstd") shows once."""
        result, seen = [], set()
        for _, _, value in sorted(self._entries()):
            if value and _key(value) not in seen:
                seen.add(_key(value))
                result.append(value)
        return result

    def files(self) -> list:
        result = []
        for path in self.paths():
            exists = os.path.isfile(path)
            result.append(RecentFile(path, exists, os.path.getmtime(path) if exists else None))
        return result

    def remove(self, path: str) -> None:
        paths = self.paths()
        kept = [p for p in paths if _key(p) != _key(path)]
        if len(kept) == len(paths):
            return
        group = self._group()
        for _, name, _ in self._entries():
            group.RemString(name)
        for index, kept_path in enumerate(kept):
            group.SetString(f"MRU{index}", kept_path)
        group.SetInt("RecentFiles", group.GetInt("RecentFiles", DEFAULT_COUNT))  # FreeCAD's menu reloads


def raise_limit_once(recent: RecentFiles, settings) -> None:
    """Keeps at least HOME_COUNT recent files. Once per profile: later choices are the user's."""
    if settings.get(LIMIT_RAISED):
        return
    if recent.limit() < HOME_COUNT:
        recent._group().SetInt("RecentFiles", HOME_COUNT)  # FreeCAD's menu grows to match
    settings.set(LIMIT_RAISED, True)
