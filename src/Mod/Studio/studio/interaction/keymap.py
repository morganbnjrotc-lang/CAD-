# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keymap: which command a key sequence runs (docs/adr/0008-keymap-contexts.md).

A binding is (context, key sequence) -> catalog command. `GLOBAL` is always active; a workbench's
context (named after the workbench) while doing that kind of work, e.g. editing a sketch. Lookups
go from the most specific active context to Global.

Per context, bindings come from three sources, strongest first: the user's (one setting per context
and command: "Keymap/<Context>/<Command>", sequences separated by line breaks, empty = unbound),
Studio's defaults, and FreeCAD's own shortcuts (in the context of the command's workbench; commands
available from startup in Global). Two commands on the same sequence in one context, or a sequence
that starts another one there ("V" and "V, F": Qt would wait for a second key), are conflicts: the
stronger source wins, then the earlier entry, and the loser is reported.

Key sequences are text in a canonical form (`normalize`): "Ctrl+Shift+Z", "V, F", "Ctrl++".
No Qt here; the shell installs the bindings and runs commands through the command service.
"""

import re
from dataclasses import dataclass

from studio.services.commands import CommandCatalog
from studio.services.settings import Setting, Settings

GLOBAL = "Global"

STUDIO_DEFAULTS = {
    GLOBAL: {
        "E": "PartDesign_Pad",  # extrude; a direct-manipulation extrude tool replaces it in Phase 3
        "F": "Std_ViewFitSelection",  # focus the selection
        "Shift+F": "Std_ViewFitAll",
        # The command palette (PLAN 2.5): S like Fusion 360 (while sketching S is Sketcher's own),
        # Ctrl+K everywhere. Chosen by the user, 2026-11-14.
        "S": "Studio_CommandPalette",
        "Ctrl+K": "Studio_CommandPalette",
    }
}

MAX_CHORDS = 4  # what Qt's QKeySequence holds
_SEPARATOR = "\n"  # between sequences in a stored user binding; no key is a line break
_MODIFIERS = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift", "meta": "Meta", "win": "Meta",
              "cmd": "Meta"}
_ORDER = ("Ctrl", "Alt", "Shift", "Meta")
_NAMED = {name.lower(): name for name in (
    "Esc", "Tab", "Backtab", "Backspace", "Return", "Enter", "Ins", "Del", "Pause", "Print", "Home", "End",
    "Left", "Up", "Right", "Down", "PgUp", "PgDown", "Space", "Menu")}
_NAMED.update({"escape": "Esc", "delete": "Del", "insert": "Ins", "pageup": "PgUp", "pagedown": "PgDown"})
_FUNCTION_KEY = re.compile(r"f([1-9]|[12][0-9]|3[0-5])")
_CHORD_BREAK = re.compile(r"(?<!\+),\s*")  # a comma right after "+" is the key itself ("Ctrl+,")


def _key(token: str) -> str:
    if len(token) == 1 and not token.isspace():
        return token.upper()
    lower = token.lower()
    if lower in _NAMED:
        return _NAMED[lower]
    if _FUNCTION_KEY.fullmatch(lower):
        return lower.upper()
    raise ValueError(f"unknown key {token!r}")


def _chord(text: str) -> str:
    text = text.strip()
    if text == "+":
        modifiers, key = "", "+"
    elif text.endswith("++"):
        modifiers, key = text[:-2], "+"
    elif not text or text.endswith("+"):
        raise ValueError(f"missing key in {text!r}")
    else:
        modifiers, _, key = text.rpartition("+")
    names = []
    for token in filter(None, modifiers.split("+")) if modifiers else ():
        name = _MODIFIERS.get(token.strip().lower())
        if name is None or name in names:
            raise ValueError(f"bad modifier {token!r} in {text!r}")
        names.append(name)
    return "+".join(sorted(names, key=_ORDER.index) + [_key(key.strip())])


def normalize(sequence: str) -> str:
    """Canonical text of a key sequence: "shift+f" -> "Shift+F", "v,f" -> "V, F". "" stays "".
    Raises ValueError for anything Qt couldn't read back as the same keys."""
    if not sequence.strip():
        return ""
    chords = _CHORD_BREAK.split(sequence.strip())
    if len(chords) > MAX_CHORDS:
        raise ValueError(f"at most {MAX_CHORDS} keys in a sequence: {sequence!r}")
    return ", ".join(_chord(chord) for chord in chords)


def _clashes(a: str, b: str) -> bool:
    """Same sequence, or one starts the other ("V" and "V, F")."""
    return a == b or a.startswith(b + ", ") or b.startswith(a + ", ")


class SequenceMatcher:
    """Turns key presses (one normalized chord at a time) into commands.

    `bindings` ({sequence: command}, e.g. Keymap.active_bindings()) may not contain a sequence that
    starts another one, which active_bindings() guarantees; so a complete sequence can run at once
    and no timeout is needed to tell "V" from "V, F".
    """

    def __init__(self, bindings: dict):
        for a in bindings:
            for b in bindings:
                if a != b and _clashes(a, b):
                    raise ValueError(f"{a!r} starts {b!r}")
        self._bindings = dict(bindings)
        self._prefixes = {", ".join(s.split(", ")[:n]) for s in bindings for n in range(1, s.count(", ") + 1)}
        self.pending = ""

    def _state(self, chord: str):
        sequence = f"{self.pending}, {chord}" if self.pending else chord
        if sequence in self._bindings:
            return "run", sequence
        if sequence in self._prefixes:
            return "wait", sequence
        return "none", sequence

    def peek(self, chord: str):
        """What `feed(chord)` would return, without consuming the key."""
        state, sequence = self._state(chord)
        if state == "none" and self.pending:
            sequence = chord  # a dead end: the key on its own
            state = "run" if chord in self._bindings else "wait" if chord in self._prefixes else "none"
        return (state, self._bindings[sequence]) if state == "run" else (state, None)

    def wants(self, chord: str) -> bool:
        """Whether `chord` would be used now (completing or continuing a sequence, or starting a
        new one after a dead end), without consuming it."""
        return self.peek(chord)[0] != "none"

    def feed(self, chord: str):
        """("run", command) when `chord` completes a sequence, ("wait", None) when it continues
        one, ("none", None) when it is not a bound key. After a dead end the pending keys are
        dropped and `chord` is tried on its own."""
        state, sequence = self._state(chord)
        if state == "none" and self.pending:
            self.pending = ""
            state, sequence = self._state(chord)
        if state == "run":
            self.pending = ""
            return "run", self._bindings[sequence]
        if state == "wait":
            self.pending = sequence
            return "wait", None
        self.pending = ""
        return "none", None

    def reset(self) -> None:
        self.pending = ""


@dataclass(frozen=True)
class Conflict:
    context: str
    sequence: str
    winner: str
    loser: str


class Keymap:
    def __init__(self, catalog: CommandCatalog, settings: Settings):
        self._catalog = catalog
        self._settings = settings
        self._contexts = [GLOBAL] + catalog.workbenches()
        self._user = {context: {} for context in self._contexts}
        for context in self._contexts:
            for name in self._settings.names(f"Keymap/{context}"):
                try:
                    self._catalog.get(name)
                    stored = self._settings.get(self._setting(context, name))
                    self._user[context][name] = [normalize(s) for s in stored.split(_SEPARATOR) if s]
                except (KeyError, ValueError):
                    continue  # a command that no longer exists, or text that isn't a key sequence
        self._rebuild()

    def contexts(self) -> list:
        return list(self._contexts)

    @staticmethod
    def _setting(context: str, command: str) -> Setting:
        return Setting(f"Keymap/{context}/{command}", "")

    def _context_of(self, command: str, context) -> str:
        info = self._catalog.get(command)  # KeyError for an unknown command
        context = context or info.workbench or GLOBAL
        if context not in self._contexts:
            raise KeyError(context)
        return context

    def _rebuild(self):
        self._bindings, self._conflicts = {}, []
        for context in self._contexts:
            user = self._user[context]
            candidates = [(s, c) for c, sequences in user.items() for s in sequences]
            candidates += [(s, c) for s, c in STUDIO_DEFAULTS.get(context, {}).items() if c not in user]
            candidates += [
                (normalize(info.shortcut), info.name)
                for info in self._catalog.commands()
                if info.shortcut and (info.workbench or GLOBAL) == context and info.name not in user
            ]
            table = {}
            for sequence, command in candidates:
                rival = next((s for s in table if _clashes(s, sequence)), None)
                if rival is None:
                    table[sequence] = command
                elif table[rival] != command:
                    self._conflicts.append(Conflict(context, sequence, table[rival], command))
            self._bindings[context] = table

    def bindings(self, context: str = GLOBAL) -> dict:
        """{sequence: command} of one context."""
        return dict(self._bindings[context])

    def active_bindings(self, active=()) -> dict:
        """{sequence: command} while the `active` contexts (most specific first) and Global are
        active. A sequence from a less specific context is left out if it clashes with one from a
        more specific context, so a key never has two meanings."""
        merged = {}
        for context in [c for c in active if c != GLOBAL] + [GLOBAL]:
            for sequence, command in self._bindings[context].items():
                if not any(_clashes(sequence, taken) for taken in merged):
                    merged[sequence] = command
        return merged

    def resolve(self, sequence: str, active=()):
        """The command `sequence` runs while `active` contexts are active; None if nothing."""
        return self.active_bindings(active).get(normalize(sequence))

    def sequences(self, command: str, context=None) -> list:
        """Sequences bound to `command` in `context` (default: the context of its workbench)."""
        context = self._context_of(command, context)
        return [s for s, c in self._bindings[context].items() if c == command]

    def conflicts(self) -> list:
        return list(self._conflicts)

    def set_sequences(self, command: str, sequences, context=None) -> None:
        """The user's binding: `sequences` replace the defaults of `command` in `context`;
        an empty list unbinds it."""
        context = self._context_of(command, context)
        normalized = list(dict.fromkeys(s for s in (normalize(s) for s in sequences) if s))
        self._settings.set(self._setting(context, command), _SEPARATOR.join(normalized))
        self._user[context][command] = normalized
        self._rebuild()

    def reset(self, command: str, context=None) -> None:
        """Back to the defaults for `command` in `context`."""
        context = self._context_of(command, context)
        self._settings.reset(self._setting(context, command))
        self._user[context].pop(command, None)
        self._rebuild()
