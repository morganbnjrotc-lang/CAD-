# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe (passed as a command-line macro) for bench_open.py.

Once the app is idle after startup, opens STUDIO_BENCH_FILE the way File > Open does
(`FreeCADGui.loadFile`) and waits until the event loop is idle again, with the document shown.
Records what loaded, closes the document and opens it a second time in the same process. Writes
the result as JSON to STUDIO_BENCH_OUT and exits without saving preferences.

FreeCAD asks for STEP import settings in a modal dialog until the user ticks "don't show again".
The probe turns that dialog off first, so it measures a user who has done that and kept the
default settings. Any other modal dialog (e.g. "Recomputation required") would wait for a click
forever; it is reported as an error instead.
"""

import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import FreeCADGui as Gui  # noqa: E402
from PySide import QtCore, QtWidgets  # noqa: E402  (FreeCAD's PySide shim)

from benchlib import process_memory  # noqa: E402

PATH = os.environ["STUDIO_BENCH_FILE"]
result = {}


def _finish(**extra):
    result.update(extra)
    with open(os.environ["STUDIO_BENCH_OUT"], "w", encoding="utf-8") as f:
        json.dump(result, f)
    os._exit(0)  # skip shutdown so preferences/recent files are never written


def _guarded(fn):
    def call():
        try:
            fn()
        except Exception:
            _finish(error=traceback.format_exc())

    return call


def _check_for_dialogs():
    dialog = QtWidgets.QApplication.activeModalWidget()
    if dialog is not None:
        text = dialog.text() if hasattr(dialog, "text") else ""
        _finish(error=f"modal dialog {dialog.windowTitle()!r} stopped the load: {text}")


def _open(then):
    before = set(App.listDocuments())
    start = time.perf_counter()
    Gui.loadFile(PATH)
    # Fires once the event queue is empty: the new document's view has been shown and painted.
    QtCore.QTimer.singleShot(0, _guarded(lambda: then(time.perf_counter() - start, before)))


def _new_document(before):
    new = [doc for name, doc in App.listDocuments().items() if name not in before]
    if len(new) != 1:
        raise RuntimeError(f"expected 1 new document after opening {PATH}, got {len(new)}")
    return new[0]


def _contents(doc):
    objects = doc.Objects
    return {
        "objects": len(objects),
        # An object whose Python module can't be imported still loads, with an empty Proxy.
        "missing_proxies": [
            o.Name for o in objects if "Proxy" in o.PropertiesList and o.Proxy is None
        ],
        "faces": sum(len(o.Shape.Faces) for o in objects if o.isDerivedFrom("Part::Feature")),
    }


def _opened(seconds, before):
    doc = _new_document(before)
    result.update(open_s=seconds, memory_after_open=process_memory(), **_contents(doc))
    App.closeDocument(doc.Name)
    QtCore.QTimer.singleShot(0, _guarded(lambda: _open(_reopened)))


def _reopened(seconds, before):
    _new_document(before)
    _finish(reopen_s=seconds)


def _start():
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Part/STEP").SetBool(
        "VisibleImportDialog", False
    )
    result["memory_before_open"] = process_memory()
    watchdog = QtCore.QTimer(Gui.getMainWindow())  # parented, so it lives as long as the window
    watchdog.timeout.connect(_check_for_dialogs)
    watchdog.start(200)
    _open(_opened)


QtCore.QTimer.singleShot(0, _guarded(_start))
