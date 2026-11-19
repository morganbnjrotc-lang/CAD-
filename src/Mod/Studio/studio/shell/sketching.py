# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching like Fusion (PLAN 3.2–3.4): Studio's adjustments to FreeCAD's sketch tools.

FreeCAD's tools already show size boxes while drawing ("on-view parameters"): a typed size becomes a
dimension, Tab moves to the next box, Return finishes. Studio makes typing into a size box replace the
whole text, unit included (StudioGui.install_size_box_typing), there and in task panels (Pad's length):
FreeCAD keeps the unit after the typed number, so "50 mm" became "50 mm in", read as 50 in while drawing
and ignored in a task panel.

Fully Constrain (Studio_FullyConstrain, PLAN 3.4) runs studio.services.auto_constrain on the sketch being
edited and says what it did in the status bar (through FreeCAD's console, which FreeCAD shows there).

Ways to draw FreeCAD has no command for (a 3-point rectangle, PLAN 3.12) start its tool and pick the way
in the tool's panel, the list FreeCAD's M key steps through (`use_method`).
"""

import FreeCAD
import FreeCADGui

from studio.services import auto_constrain

last_message = ""  # what Fully Constrain last said, for tests

_installed = False


def install_once():
    global _installed
    if _installed:
        return
    _installed = True
    try:
        import StudioGui
    except ImportError as exc:
        FreeCAD.Console.PrintWarning(f"Studio: sketch typing unchanged ({exc})\n")
        return
    StudioGui.install_size_box_typing()


def sketch_in_edit():
    """The sketch being edited, or None."""
    document = FreeCADGui.ActiveDocument
    view_provider = document.getInEdit() if document is not None else None
    target = getattr(view_provider, "Object", None)
    return target if getattr(target, "TypeId", None) == "Sketcher::SketchObject" else None


def use_method(method: int) -> bool:
    """Switches the sketch tool just started to its drawing method `method` (its panel's first list)."""
    import StudioGui  # Studio's C++ helpers: Python wrappers of FreeCAD's panels abort at exit

    if StudioGui.set_drawing_method(method):
        return True
    FreeCAD.Console.PrintWarning(f"Studio: no sketch tool to switch to drawing method {method}\n")
    return False


def fully_constrain():
    global last_message
    sketch = sketch_in_edit()
    if sketch is None:
        return
    try:
        last_message = auto_constrain.summary(auto_constrain.fully_constrain(sketch))
    except auto_constrain.SketchHasProblems as problem:
        last_message = str(problem)
        FreeCAD.Console.PrintWarning(last_message + "\n")
        return
    FreeCAD.Console.PrintMessage(last_message + "\n")
