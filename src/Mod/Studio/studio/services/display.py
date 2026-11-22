# SPDX-License-Identifier: LGPL-2.1-or-later
"""Display presets (PLAN 3.8): how the 3D view draws the model, and perspective or orthographic.

Each style is one of FreeCAD's draw styles (the 3D viewer's override mode), and the presets add a look on
top of it, drawn by Studio (StudioGui.set_look): **Pretty** keeps the edges and adds shadows on a floor
under the model; **Gray Box** draws every part in one neutral gray, without edges, with shadows;
**Realistic** keeps the parts' own colors, without edges, with shadows and highlights. The choice is a
Studio setting (each style's `key`: the draw style's name for the plain ones, as stored before the presets
came), so every document's view follows it, also after a restart.
"""

from dataclasses import dataclass, field

from studio.services.settings import Setting


@dataclass(frozen=True)
class Look:
    """What Studio draws on top of FreeCAD's draw style."""

    shadows: bool = False  # Coin's shadows, on a floor under the model
    gray: bool = False  # every part in one neutral gray
    shiny: bool = False  # highlights on the parts' own colors


@dataclass(frozen=True)
class Style:
    label: str
    mode: str  # FreeCAD's draw style (View3DInventorViewer::setOverrideMode)
    name: str = ""  # the key, when it isn't the draw style's name
    look: Look = field(default_factory=Look)

    @property
    def key(self) -> str:
        return self.name or self.mode


STYLES = (
    Style("Shaded with Edges", "As Is"),
    Style("Shaded", "Shaded"),
    Style("Hidden Line", "Hidden Line"),
    Style("Wireframe", "Wireframe"),
    Style("Pretty", "As Is", "Pretty", Look(shadows=True)),
    Style("Gray Box", "Shaded", "Gray Box", Look(shadows=True, gray=True)),
    Style("Realistic", "Shaded", "Realistic", Look(shadows=True, shiny=True)),
)
PRESETS = tuple(s for s in STYLES if s.look != Look())
STYLE = Setting("Display/Style", "As Is", choices=tuple(s.key for s in STYLES))
PERSPECTIVE = Setting("Display/Perspective", False)


class Display:
    def __init__(self, settings):
        self._settings = settings

    def style(self) -> str:
        """The chosen style's key."""
        return self._settings.get(STYLE)

    def current(self) -> Style:
        return next(s for s in STYLES if s.key == self.style())

    def set_style(self, key: str) -> None:
        self._settings.set(STYLE, key)  # ValueError for a style not offered

    def perspective(self) -> bool:
        return self._settings.get(PERSPECTIVE)

    def set_perspective(self, on: bool) -> None:
        self._settings.set(PERSPECTIVE, bool(on))
