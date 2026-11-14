# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe (passed as a command-line macro) for bench_startup.py.

Once the Qt event loop is running (main window shown and idle) it records the wall-clock time and
process memory to the JSON file named in STUDIO_BENCH_OUT, then exits immediately without saving
preferences.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide import QtCore  # noqa: E402  (FreeCAD's PySide shim)

from benchlib import process_memory  # noqa: E402


def _report():
    result = {"ready": time.time(), **process_memory()}
    with open(os.environ["STUDIO_BENCH_OUT"], "w", encoding="utf-8") as f:
        json.dump(result, f)
    os._exit(0)  # skip shutdown so preferences/recent files are never written


QtCore.QTimer.singleShot(0, _report)
