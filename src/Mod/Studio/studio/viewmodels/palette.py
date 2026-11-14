# SPDX-License-Identifier: LGPL-2.1-or-later
"""Command palette (PLAN 2.5): type part of a tool's name, get the best matches first.

Searches every command in the catalog, loaded or not (docs/adr/0007), and shows each command's
active shortcut (docs/adr/0008). Ranking, best first, per query word: the title starts with it, a
word of the title starts with it, the title contains it, a word of the command's name or category
starts with it, the tooltip contains it, or its letters appear in order in the title (closer
together ranks higher). Every word must match. Ties go to recently used commands, then to shorter
titles, then to catalog order. An empty query lists recently used commands first.

No Qt here; the shell draws the palette.
"""

import re
from dataclasses import dataclass

from studio.services.settings import Setting
from studio.viewmodels.tool_names import clean_title, display_title  # noqa: F401 (clean_title re-exported)

_CATEGORIES = {
    None: "General", "SketcherWorkbench": "Sketcher", "PartDesignWorkbench": "Part Design",
    "PartWorkbench": "Part", "AssemblyWorkbench": "Assembly", "TechDrawWorkbench": "TechDraw",
    "CAMWorkbench": "CAM", "SpreadsheetWorkbench": "Spreadsheet",
}
_WORD = re.compile(r"[a-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")


def category_of(workbench) -> str:
    return _CATEGORIES.get(workbench) or workbench.removesuffix("Workbench")


def _is_dropdown_group(name: str) -> bool:
    return "_Comp" in name or name.endswith("Group")


@dataclass(frozen=True)
class PaletteItem:
    command: str
    title: str
    category: str
    detail: str  # tooltip
    shortcut: str  # the first active key sequence, "" if none
    icon: str | None


class _Entry:
    """An item's text, prepared once for matching."""

    def __init__(self, info, order):
        self.info, self.order = info, order
        self.title = display_title(info)
        self.category = category_of(info.workbench)
        self.title_lower = self.title.lower()
        # A plain name (Extrude) keeps FreeCAD's (Pad) as a second name to find it by.
        self.names = list(dict.fromkeys([self.title_lower, clean_title(info.menu_text).lower()]))
        self.title_words = [w for name in self.names for w in _WORD.findall(name)]
        self.name_words = [w.lower() for w in _CAMEL.findall(info.name.replace("_", " "))]
        self.category_words = _WORD.findall(self.category.lower())
        self.tooltip = info.tooltip.lower()

    def score(self, word: str):
        if any(name.startswith(word) for name in self.names):
            return 300
        if any(w.startswith(word) for w in self.title_words):
            return 200
        if any(word in name for name in self.names):
            return 120
        if any(w.startswith(word) for w in self.name_words):
            return 100
        if any(w.startswith(word) for w in self.category_words):
            return 60
        if word in self.tooltip:
            return 40
        spans = [s for s in (_span(word, name) for name in self.names) if s is not None]
        span = min(spans) if spans else None
        if span is not None and len(word) > 1:
            return 20 + 20 * len(word) / span
        return None


def _span(word: str, text: str):
    """Length of the shortest stretch of `text` holding the letters of `word` in order, or None."""
    best = None
    start = text.find(word[0])
    while start != -1:
        position = start
        for letter in word[1:]:
            position = text.find(letter, position + 1)
            if position == -1:
                return best
        span = position - start + 1
        best = span if best is None else min(best, span)
        start = text.find(word[0], start + 1)
    return best


class Palette:
    RECENT = Setting("Palette/Recent", "")
    RECENT_LIMIT = 8

    def __init__(self, catalog, keymap, settings):
        self._keymap = keymap
        self._settings = settings
        chosen = {}
        for order, info in enumerate(catalog.commands()):
            entry = _Entry(info, order)
            key = (entry.title_lower, entry.category)
            kept = chosen.get(key)
            if kept is None or (_is_dropdown_group(kept.info.name) and not _is_dropdown_group(info.name)):
                chosen[key] = entry
        self._entries = sorted(chosen.values(), key=lambda e: e.order)
        self._by_name = {e.info.name: e for e in self._entries}

    def _shortcuts(self, contexts) -> dict:
        if self._keymap is None:
            return {}
        first = {}
        for sequence, command in self._keymap.active_bindings(contexts).items():
            first.setdefault(command, sequence)
        return first

    def _item(self, entry, shortcuts) -> PaletteItem:
        info = entry.info
        return PaletteItem(info.name, entry.title, entry.category, info.tooltip,
                           shortcuts.get(info.name, ""), info.icon)

    def items(self, contexts=()) -> list:
        shortcuts = self._shortcuts(contexts)
        return [self._item(e, shortcuts) for e in self._entries]

    def recent(self) -> list:
        stored = self._settings.get(self.RECENT).split("\n")
        return [name for name in stored if name in self._by_name][: self.RECENT_LIMIT]

    def record_use(self, command: str) -> None:
        names = [command] + [name for name in self.recent() if name != command]
        self._settings.set(self.RECENT, "\n".join(names[: self.RECENT_LIMIT]))

    def search(self, query: str, contexts=(), limit: int = 50) -> list:
        shortcuts = self._shortcuts(contexts)
        recent = {name: rank for rank, name in enumerate(self.recent())}
        words = query.lower().split()
        if not words:
            ordered = [self._by_name[name] for name in recent]
            ordered += [e for e in self._entries if e.info.name not in recent]
            return [self._item(e, shortcuts) for e in ordered[:limit]]
        whole = " ".join(words)
        ranked = []
        for entry in self._entries:
            total = 0
            for word in words:
                score = entry.score(word)
                if score is None:
                    break
                total += score
            else:
                if whole in entry.names:
                    total += 1000
                ranked.append((-total, recent.get(entry.info.name, len(recent)), len(entry.title), entry.order, entry))
        ranked.sort(key=lambda row: row[:4])
        return [self._item(row[4], shortcuts) for row in ranked[:limit]]
