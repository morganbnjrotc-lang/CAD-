# SPDX-License-Identifier: LGPL-2.1-or-later
"""Command catalog and command service (docs/adr/0007-lazy-loading-command-catalog.md).

The palette, keymap and contextual toolbar show entries from the `CommandCatalog` (generated from
the build by tools/studio/generate_command_catalog.py) and run them through a `CommandService`. It
loads a command's workbench the first time one of its commands is used, then runs the real FreeCAD
command, so startup never has to load the modules whose tools the environment offers.

FreeCAD's GUI sits behind `CommandBackend`; the shell implements it (services stay headless).
"""

import json
from dataclasses import dataclass
from pathlib import Path

CATALOG_FILE = Path(__file__).with_name("command_catalog.json")


@dataclass(frozen=True)
class CommandInfo:
    name: str
    workbench: str | None  # None: available from startup
    menu_text: str
    tooltip: str
    shortcut: str
    icon: str | None  # source SVG, relative to the repository root


class CommandCatalog:
    def __init__(self, data: dict):
        self._workbenches = [w["name"] for w in data["workbenches"]]
        known = set(self._workbenches)
        self._commands = {}
        for entry in data["commands"]:
            info = CommandInfo(**{field: entry[field] for field in CommandInfo.__dataclass_fields__})
            if info.workbench is not None and info.workbench not in known:
                raise ValueError(f"{info.name}: unknown workbench {info.workbench!r}")
            self._commands[info.name] = info

    @classmethod
    def load(cls, path: Path = CATALOG_FILE) -> "CommandCatalog":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def get(self, name: str) -> CommandInfo:
        return self._commands[name]

    def commands(self) -> list:
        return list(self._commands.values())

    def workbenches(self) -> list:
        """Workbench names in catalog (warm-up) order."""
        return list(self._workbenches)


class CommandBackend:
    """What the service needs from FreeCAD's GUI. Implemented by the shell."""

    def load_workbench(self, name: str) -> None:
        """Make the workbench's commands exist (FreeCAD's first-activation work), without
        switching to it. Must be harmless if the workbench is already loaded."""
        raise NotImplementedError

    def run(self, command: str, index: int = 0) -> None:
        """Run a registered FreeCAD command (`index`: which item of a command making several things)."""
        raise NotImplementedError


class CommandService:
    def __init__(self, catalog: CommandCatalog, backend: CommandBackend):
        self.catalog = catalog
        self._backend = backend
        self._loaded = set()

    def is_loaded(self, workbench: str) -> bool:
        return workbench in self._loaded

    def ensure_loaded(self, workbench: str) -> None:
        if workbench not in self.catalog.workbenches():
            raise KeyError(workbench)
        if workbench not in self._loaded:
            self._backend.load_workbench(workbench)  # may raise: then it is tried again next time
            self._loaded.add(workbench)

    def run(self, name: str, index: int = -1) -> None:
        """Runs a command, loading its workbench first if needed; `index`: one item of a command making
        several things (Part Design's primitives), as FreeCAD's runCommand takes it."""
        info = self.catalog.get(name)
        if info.workbench is not None:
            self.ensure_loaded(info.workbench)
        if index >= 0:
            self._backend.run(name, index)
        else:
            self._backend.run(name)
