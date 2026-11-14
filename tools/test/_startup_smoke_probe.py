# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe for startup_smoke.py. Do not run directly.

Waits for startup to settle (STUDIO_SMOKE_MODE "lazy") or for background warm-up to finish
("warm"), records observable app state to STUDIO_SMOKE_OUT as JSON, then exits without saving
preferences.
"""

import json
import os
import time

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

SETTLE_MS = 1500  # let deferred startup work (Start page, migrations) finish
WARMUP_TIMEOUT_S = 30
MODE = os.environ.get("STUDIO_SMOKE_MODE", "lazy")


def open_dialogs():
    """Titles of dialogs on screen, modal or not. A dialog opened with show() leaves the event
    loop running, so the app looks started even while a new user is looking at the dialog."""
    return [
        w.windowTitle()
        for w in QtWidgets.QApplication.topLevelWidgets()
        if isinstance(w, QtWidgets.QDialog) and w.isVisible()
    ]


def early_commands():
    """Commands of the catalog's workbenches that exist already (ADR 0007: none should)."""
    from studio.services.commands import CommandCatalog

    return [
        c.name
        for c in CommandCatalog.load().commands()
        if c.workbench is not None and FreeCADGui.Command.get(c.name) is not None
    ][:20]


def warmup_state():
    from studio.shell import warmup

    current = warmup.current()
    if current is None:
        return None
    return {"done": current.done, "loaded": current.loaded, "failed": current.failed,
            "planned": current.planned}


def report():
    workbench = FreeCADGui.activeWorkbench()
    state = {
        "active_workbench": workbench.name() if workbench else None,
        "dialogs": open_dialogs(),
        "start_workbench_config": FreeCAD.ConfigGet("StartWorkbench"),
        "autoload_module_pref": FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/General"
        ).GetString("AutoloadModule"),
        "user_parameter_file": FreeCAD.ConfigGet("UserParameter"),
    }
    if MODE == "lazy":
        state["early_commands"] = early_commands()
    else:
        state["warmup"] = warmup_state()
        state["cam_loaded"] = FreeCADGui.Command.get("CAM_Job") is not None
    with open(os.environ["STUDIO_SMOKE_OUT"], "w", encoding="utf-8") as f:
        json.dump(state, f)
    os._exit(0)


_deadline = time.monotonic() + WARMUP_TIMEOUT_S


def wait_for_warmup():
    state = warmup_state()
    if (state and state["done"]) or time.monotonic() > _deadline:
        report()
    else:
        QtCore.QTimer.singleShot(100, wait_for_warmup)


QtCore.QTimer.singleShot(SETTLE_MS, report if MODE == "lazy" else wait_for_warmup)
