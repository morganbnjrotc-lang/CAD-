# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where FreeCAD's Tasks panel floats (PLAN 3.10).

The panel (a sketch's tools, Extrude's length, a fillet's edges) floats at the right of the 3D view. FreeCAD
makes it as tall as the view under the navigation cube and 352 px wide; the user found that tall and
skinny and asked for "medium, and slightly wider". Studio keeps it under the cube, about two thirds as
tall as the room there (never shorter than MIN_HEIGHT while there is room) and WIDTH wide.

FreeCAD lays its floating panels out from parameters (BaseApp/MainWindow/DockWindows/OverlayRight):
`Width`, and `Offset2`, the room it leaves free below the panel. It lays every panel out again whenever
one of them changes, so `FreeCADTasksPanel` writes them only when they change. The width is Studio's
once; after that it's the user's (FreeCAD saves it when the user drags the panel's edge).
"""

import FreeCAD

from studio.services.settings import Setting, Settings

OVERLAY = "User parameter:BaseApp/MainWindow/DockWindows/OverlayRight"
WIDTH = 420  # px, a fifth wider than FreeCAD's 352
SHARE = 0.65  # of the room under the navigation cube
MIN_HEIGHT = 360  # px
CUBE_GAP = 10  # px FreeCAD keeps between the navigation cube and the panel
WIDTH_SET = Setting("Layout/TasksPanelWidthSet", False)


def bottom_gap(area_height: int, cube: int) -> int:
    """The room to leave below the panel in a 3D area `area_height` px tall, the cube `cube` px."""
    room = area_height - (cube + CUBE_GAP)
    panel = max(MIN_HEIGHT, round(room * SHARE))
    return max(0, room - panel)


class FreeCADTasksPanel:
    """Writes the panel's size into FreeCAD's parameters for its floating right panel (`overlay`)."""

    def __init__(self, overlay: str = OVERLAY, settings: Settings | None = None):
        self._overlay = overlay
        self._settings = settings or Settings()

    def apply(self, area_height: int, cube: int) -> bool:
        """Sizes the panel for the 3D area's height; True if a parameter changed."""
        group = FreeCAD.ParamGet(self._overlay)
        changed = False
        if not self._settings.get(WIDTH_SET):
            self._settings.set(WIDTH_SET, True)
            if group.GetInt("Width", 0) != WIDTH:
                group.SetInt("Width", WIDTH)
                changed = True
        gap = bottom_gap(area_height, cube)
        if group.GetInt("Offset2", 0) != gap:
            group.SetInt("Offset2", gap)
            changed = True
        return changed
