# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs inside FreeCAD.exe for run_visual.py. Do not run directly.

Captures Studio's main screens in the mode the profile starts in: Home, a model with a face selected,
a sketch being edited. Writes <screen>.png files and masks.json (per screen: the 3D view's rectangle to
leave out, and the Tasks panel's rectangle inside it to compare all the same) to STUDIO_VISUAL_OUT, then
reports to STUDIO_BENCH_OUT and exits without saving preferences.

The window is a fixed 1280 x 800 placed off the screen, so the mouse can't hover anything in it, and the
app's font is the vendored Noto Sans.
"""

import json
import os

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets  # FreeCAD's PySide shim

OUT = os.environ["STUDIO_VISUAL_OUT"]
MODEL = os.environ["STUDIO_VISUAL_MODEL"]
FONT = os.environ["STUDIO_VISUAL_FONT"]
SIZE = (1280, 800)
mw = FreeCADGui.getMainWindow()
masks, report = {}, {"screens": []}


def later(ms, step):
    QtCore.QTimer.singleShot(ms, step)


def settle():
    for _ in range(5):
        QtWidgets.QApplication.processEvents()


def capture(name, mask=None):
    from studio.shell import window

    if window.current() is not None:
        window.current()._update_enabled()  # the toolbar's enabled states, now rather than on its timer
    if mask:  # a document is open: the Model panel shows
        steady_panel()
    mw.statusBar().clearMessage()  # e.g. "Preselected: …" depends on the mouse
    settle()
    picture = mw.grab()
    picture.save(os.path.join(OUT, f"{name}.png"))
    masks[name] = {"mask": [mask] if mask else [], "keep": [tasks_rect()] if mask and tasks_rect() else []}
    report["screens"].append(name)


def steady_panel():
    """The divider between the model tree and the properties: where the Model panel's first layout
    puts it depends on timing (it reappears when Home hides), so set it."""
    from studio.shell import window

    splitter = window.current().model_panel().findChild(QtWidgets.QSplitter)
    if splitter is not None:
        total = sum(splitter.sizes())
        splitter.setSizes([total * 9 // 20, total - total * 9 // 20])


def tasks_rect():
    """The Tasks panel floating at the right of the 3D view (FreeCAD's "OverlayRight"), if shown. A probe
    may look FreeCAD's widgets up with a document open: it ends with os._exit (docs/BASELINE.md)."""
    overlay = mw.findChild(QtWidgets.QTabWidget, "OverlayRight")
    if overlay is None or not overlay.isVisible():
        return None
    corner = overlay.mapTo(mw, QtCore.QPoint(0, 0))
    return [corner.x(), corner.y(), overlay.width(), overlay.height()]


def view_rect():
    """The 3D view (the main area's viewport), in window coordinates. Looked up on the main area,
    which the probe found before any document opened (docs/BASELINE.md)."""
    viewport = area.viewport()
    corner = viewport.mapTo(mw, QtCore.QPoint(0, 0))
    return [corner.x(), corner.y(), viewport.width(), viewport.height()]


def use_test_font():
    """The vendored Noto Sans (tests/visual/fonts) instead of the system's font: the same text on every
    machine, CI's included."""
    from PySide import QtGui

    family = QtGui.QFontDatabase.applicationFontFamilies(QtGui.QFontDatabase.addApplicationFont(FONT))
    if not family:
        raise RuntimeError(f"could not load {FONT}")
    font = QtGui.QFont(family[0])
    font.setPointSizeF(QtWidgets.QApplication.font().pointSizeF())
    QtWidgets.QApplication.setFont(font)
    report["font"] = family[0]


def start():
    use_test_font()
    mw.showNormal()
    mw.setGeometry(-4000, 100, *SIZE)  # off the screen: no hover from wherever the mouse is
    report["geometry"] = [mw.x(), mw.y(), mw.width(), mw.height()]
    wait_for_home(0)


def wait_for_home(tries):
    from studio.shell import home

    page = home.current()
    if (page is None or not page.isVisible() or not page.previews_loaded) and tries < 50:
        later(100, lambda: wait_for_home(tries + 1))
        return
    later(300, home_screen)


def home_screen():
    capture("home")
    doc = FreeCAD.openDocument(MODEL)
    FreeCADGui.SendMsgToActiveView("ViewFit")
    later(1500, lambda: model_screen(doc))


def model_screen(doc):
    body = next(o for o in doc.Objects if o.TypeId == "PartDesign::Body")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Tip.Name, "Face1")
    later(1500, lambda: (capture("model", view_rect()), sketch_screen(doc)))


def sketch_screen(doc):
    sketch = next(o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.activeDocument().setEdit(sketch.Name)
    later(2500, lambda: (capture("sketch", view_rect()), finish()))


def finish():
    with open(os.path.join(OUT, "masks.json"), "w", encoding="utf-8") as f:
        json.dump(masks, f, indent=1)
    with open(os.environ["STUDIO_BENCH_OUT"], "w", encoding="utf-8") as f:
        json.dump(report, f)
    os._exit(0)  # no preferences saved, nothing left for FreeCAD's shutdown to trip over


area = mw.findChild(QtWidgets.QMdiArea)  # now, before any document is open
later(1500, start)
