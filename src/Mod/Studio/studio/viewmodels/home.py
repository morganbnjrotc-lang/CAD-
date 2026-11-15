# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home page's cards (PLAN 2.8): one per recent file, most recent first.

The time shown is when the file was last saved (FreeCAD's list doesn't record when it was opened),
worded the way a person would say it: "Saved 2 hours ago", "Saved yesterday", "Saved 5 Oct 2026".
No Qt here; the shell draws the page.
"""

import datetime
import time
from dataclasses import dataclass
from pathlib import Path

_KINDS = {".fcstd": "FreeCAD", ".step": "STEP", ".stp": "STEP", ".iges": "IGES", ".igs": "IGES",
          ".stl": "STL", ".brep": "BREP", ".obj": "OBJ", ".dxf": "DXF", ".svg": "SVG"}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def saved_when(modified: float, now: float) -> str:
    age = max(0.0, now - modified)
    if age < 60:
        return "Saved just now"
    if age < 3600:
        return f"Saved {_plural(int(age // 60), 'minute')} ago"
    then = datetime.date.fromtimestamp(modified)
    days = (datetime.date.fromtimestamp(now) - then).days
    if days == 0:
        return f"Saved {_plural(int(age // 3600), 'hour')} ago"
    if days == 1:
        return "Saved yesterday"
    if days < 7:
        return f"Saved {days} days ago"
    return f"Saved {then.day} {_MONTHS[then.month - 1]} {then.year}"


@dataclass(frozen=True)
class Card:
    path: str
    title: str  # file name without extension
    folder: str  # the folder's own name
    kind: str  # "FreeCAD", "STEP", ...
    exists: bool
    when: str


class Home:
    def __init__(self, recent_files, now=time.time):
        self._recent = recent_files
        self._now = now

    def cards(self) -> list:
        now = self._now()
        cards = []
        for item in self._recent.files():
            path = Path(item.path)
            suffix = path.suffix.lower()
            kind = _KINDS.get(suffix, suffix[1:].upper() or "File")
            when = saved_when(item.modified, now) if item.exists else "File not found"
            cards.append(Card(item.path, path.stem, path.parent.name, kind, item.exists, when))
        return cards

    def remove(self, path: str) -> None:
        self._recent.remove(path)
