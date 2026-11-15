# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's line icons in the app (studio.services.icons, ADR 0010, PLAN 2.9 step 4).

`register_once` puts the drawings into FreeCAD's icon cache under FreeCAD's own names, before FreeCAD
builds its menus and model tree; they show there in the neutral grey. Studio's own surfaces draw them in
the mode's text color (`line_icon`).
"""

import os

from PySide import QtGui  # FreeCAD's PySide shim

from studio.services import icons

_registered = False
_tinted = {}


def register_once():
    """Studio's drawings under FreeCAD's icon names (once). Called from InitGui.py: an icon FreeCAD has
    already put on a button or in the tree keeps its old look."""
    global _registered
    if not _registered:
        import time

        import FreeCAD
        import StudioGui  # in C++: FreeCAD's icon cache has no Python API that replaces an entry

        start = time.perf_counter()
        count = StudioGui.add_icons(icons.freecad_registrations())
        FreeCAD.Console.PrintLog(f"Studio: {count} line icons in {(time.perf_counter() - start) * 1000:.1f} ms\n")
        _registered = True


def tinted(path, color, size=64):
    """The drawing at `path` in one color (cached)."""
    key = (path, color)
    if key not in _tinted:
        pixmap = QtGui.QIcon(path).pixmap(size, size)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QtGui.QColor(color))
        painter.end()
        _tinted[key] = QtGui.QIcon(pixmap)
    return _tinted[key]


def line_icon(catalog_icon, look):
    """Studio's drawing for a command (its catalog icon, "src/Mod/.../Name.svg") in the look's text
    color; None if Studio has no drawing for it or no look (a FreeCAD stylesheet supplies the colors)."""
    if look is None or not catalog_icon:
        return None
    path = icons.line_icon(os.path.basename(catalog_icon))
    return tinted(path, look.text) if path else None
