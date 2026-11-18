# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching like Fusion (PLAN 3.2–3.4): Studio's adjustments to FreeCAD's sketch tools.

FreeCAD's tools already show size boxes while drawing ("on-view parameters"): a typed size becomes a
dimension, Tab moves to the next box, Return finishes. Studio makes typing into those boxes replace the
whole text, unit included (StudioGui.install_size_box_typing): FreeCAD keeps the unit after the typed
number, so "50 mm" became "50 mm in", read as 50 in.
"""

import FreeCAD

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
