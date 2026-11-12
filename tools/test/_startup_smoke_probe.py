# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe for startup_smoke.py. Do not run directly.

Waits for startup to settle, records observable app state to STUDIO_SMOKE_OUT as JSON, then exits
without saving preferences.
"""

import json
import os

import FreeCAD
import FreeCADGui
from PySide import QtCore

SETTLE_MS = 1500  # let deferred startup work (Start page, migrations) finish


def report():
    workbench = FreeCADGui.activeWorkbench()
    state = {
        "active_workbench": workbench.name() if workbench else None,
        "start_workbench_config": FreeCAD.ConfigGet("StartWorkbench"),
        "autoload_module_pref": FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/General"
        ).GetString("AutoloadModule"),
        "user_parameter_file": FreeCAD.ConfigGet("UserParameter"),
    }
    with open(os.environ["STUDIO_SMOKE_OUT"], "w", encoding="utf-8") as f:
        json.dump(state, f)
    os._exit(0)


QtCore.QTimer.singleShot(SETTLE_MS, report)
