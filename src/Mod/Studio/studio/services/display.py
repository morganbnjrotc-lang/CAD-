# SPDX-License-Identifier: LGPL-2.1-or-later
"""Display presets (PLAN 3.8): how the 3D view draws the model, and perspective or orthographic.

Each style is one of FreeCAD's draw styles (the 3D viewer's override mode). The choice is a Studio
setting, so every document's view follows it, also after a restart. Shadows ("pretty") and material
looks ("realistic") would need FreeCAD's renderer to draw them; they aren't offered yet.
"""

from dataclasses import dataclass

from studio.services.settings import Setting


@dataclass(frozen=True)
class Style:
    label: str
    mode: str  # FreeCAD's draw style (View3DInventorViewer::setOverrideMode)


STYLES = (Style("Shaded with Edges", "As Is"), Style("Shaded", "Shaded"), Style("Hidden Line", "Hidden Line"),
          Style("Wireframe", "Wireframe"))
STYLE = Setting("Display/Style", "As Is", choices=tuple(s.mode for s in STYLES))
PERSPECTIVE = Setting("Display/Perspective", False)


class Display:
    def __init__(self, settings):
        self._settings = settings

    def style(self) -> str:
        return self._settings.get(STYLE)

    def set_style(self, mode: str) -> None:
        self._settings.set(STYLE, mode)  # ValueError for a style not offered

    def perspective(self) -> bool:
        return self._settings.get(PERSPECTIVE)

    def set_perspective(self, on: bool) -> None:
        self._settings.set(PERSPECTIVE, bool(on))
