# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe for generate_command_catalog.py. Do not run directly.

Once the app is idle after startup: records the commands available from startup, then activates
each workbench in STUDIO_CATALOG_WORKBENCHES (comma-separated) in order and records the commands
its first activation registered. Writes JSON to STUDIO_BENCH_OUT and exits without saving
preferences.
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore  # FreeCAD's PySide shim


def _infos(names):
    """getInfo() of each command, with the shortcut it declares: getInfo() reports the shortcut of
    the command's button, so a command that no menu or toolbar shows would seem to have none."""
    import StudioGui  # Studio's C++ helpers
    from studio.interaction.keymap import normalize

    infos = []
    for name in sorted(names):
        info = Gui.Command.get(name).getInfo()
        declared = StudioGui.declared_shortcut(name)  # as written in FreeCAD: "A,C", "SHIFT+H"
        try:
            info["shortcut"] = normalize(declared)
        except ValueError:
            info["shortcut"] = declared  # the keymap test on the shipped catalog will name it
        infos.append(info)
    return infos


def _run():
    result = {"freecad": "{}.{}.{}".format(*App.Version()[:3]), "workbenches": [], "missing": []}
    active = Gui.activeWorkbench()
    result["start_workbench"] = active.name() if active else None
    try:
        before = set(Gui.Command.listAll())
        result["core"] = _infos(before)
        available = Gui.listWorkbenches()
        for name in [n for n in os.environ["STUDIO_CATALOG_WORKBENCHES"].split(",") if n]:
            if name not in available:
                result["missing"].append(name)
                continue
            Gui.activateWorkbench(name)
            after = set(Gui.Command.listAll())
            result["workbenches"].append(
                {"name": name, "class": Gui.getWorkbench(name).GetClassName(), "commands": _infos(after - before)}
            )
            before = after
    except Exception:
        result["error"] = traceback.format_exc()
    with open(os.environ["STUDIO_BENCH_OUT"], "w", encoding="utf-8") as f:
        json.dump(result, f)
    os._exit(0)  # skip shutdown so preferences are never written


QtCore.QTimer.singleShot(0, _run)
