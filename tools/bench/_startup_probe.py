# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe (passed as a command-line macro) for bench_startup.py.

Once the Qt event loop is running (main window shown and idle) it records the wall-clock time and
process memory to the JSON file named in STUDIO_BENCH_OUT, then exits immediately without saving
preferences.
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

from PySide import QtCore  # FreeCAD's PySide shim


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _memory():
    if sys.platform != "win32":
        return {}
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = wt.HANDLE
    get_info = kernel32.K32GetProcessMemoryInfo
    get_info.argtypes = [wt.HANDLE, ctypes.POINTER(_ProcessMemoryCounters), wt.DWORD]
    get_info.restype = wt.BOOL
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not get_info(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return {
        "working_set_mb": counters.WorkingSetSize / 2**20,
        "private_mb": counters.PagefileUsage / 2**20,
    }


def _report():
    result = {"ready": time.time(), **_memory()}
    with open(os.environ["STUDIO_BENCH_OUT"], "w", encoding="utf-8") as f:
        json.dump(result, f)
    os._exit(0)  # skip shutdown so preferences/recent files are never written


QtCore.QTimer.singleShot(0, _report)
