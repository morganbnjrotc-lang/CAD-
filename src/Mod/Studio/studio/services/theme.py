# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's look (ADR 0010): two palettes, the mode, and FreeCAD's 3D view and sketch colors.

One design with a light and a dark set of colors. The accent is teal in light and orange in dark (the
user's choice). The mode follows Windows unless the user picks one (`MODE`).

FreeCAD keeps the 3D view's and the sketch editor's colors in its own settings (`View/...`,
`Mod/Sketcher/General/...`). `FreeCADColors.apply` writes the palette's colors there and remembers what
it wrote, so a color the user later changes in Preferences is left alone.
"""

from dataclasses import dataclass

import FreeCAD

from studio.services.settings import Setting

MODE = Setting("Appearance/Mode", "system", choices=("system", "light", "dark"))
FREECAD_PREFERENCES = "User parameter:BaseApp/Preferences"
MAIN_WINDOW = FREECAD_PREFERENCES + "/MainWindow"
# Icons FreeCAD draws (tree, menus) are cached and can't follow the mode: one grey that reads on both.
ICON_NEUTRAL = "#7F8996"


@dataclass(frozen=True)
class Palette:
    name: str
    window: str  # bars and the area around panels
    panel: str  # panels, fields' surroundings, Home
    field: str
    border: str
    text: str
    muted: str  # secondary text
    faint: str  # decoration only, not for text
    hover: str
    thumb: str  # behind file previews
    accent: str
    on_accent: str  # text on an accent-colored button
    view_top: str  # 3D background, soft gradient
    view_bottom: str
    view_flat: str  # 3D background when the user picks a plain color
    model: str
    model_edge: str
    sketch_edge: str
    sketch_done: str  # fully constrained
    sketch_construction: str
    sketch_grid: str
    sketch_grid_major: str

    @property
    def preselect(self) -> str:
        """The 3D highlight under the mouse: a lighter accent, so it differs from the selection."""
        return mix(self.accent, "#FFFFFF", 0.35)

    @property
    def selection(self) -> str:
        """Selected rows, hovered menu items, the item being edited: the accent softened into the panel."""
        return mix(self.accent, self.panel, 0.82 if self.name == "light" else 0.70)


LIGHT = Palette(
    name="light",
    window="#F6F7F9", panel="#FFFFFF", field="#F4F6F8", border="#E0E4E9",
    text="#1C222B", muted="#5E6774", faint="#9AA3AE", hover="#ECEFF3", thumb="#EEF1F4",
    accent="#0A7D73", on_accent="#FFFFFF",
    view_top="#F8F9FB", view_bottom="#D2D8DF", view_flat="#E7EBEF",
    model="#BFC6CE", model_edge="#363E49",
    sketch_edge="#1C222B", sketch_done="#16924C", sketch_construction="#5D7FB9",
    sketch_grid="#CDD4DC", sketch_grid_major="#B8C1CB",
)
DARK = Palette(
    name="dark",
    window="#1A1D22", panel="#202328", field="#272B31", border="#30353C",
    text="#E4E7EB", muted="#A0A8B3", faint="#69717C", hover="#2A2F36", thumb="#2A2E34",
    accent="#F28D47", on_accent="#1A1D22",
    view_top="#3B4149", view_bottom="#1F2227", view_flat="#2B3036",
    model="#A9B0B8", model_edge="#14171B",
    sketch_edge="#E4E7EB", sketch_done="#4AD181", sketch_construction="#8EA9DA",
    sketch_grid="#3A4048", sketch_grid_major="#4A515A",
)
_PALETTES = {"light": LIGHT, "dark": DARK}


def current_mode(settings, system_is_dark: bool) -> str:
    """"light" or "dark": the user's pick, or Windows' when the setting is "system"."""
    chosen = settings.get(MODE)
    if chosen == "system":
        return "dark" if system_is_dark else "light"
    return chosen


def default_to_fusion(main_window: str = MAIN_WINDOW) -> bool:
    """Picks Qt's Fusion style unless the user picked a style or a FreeCAD stylesheet.

    Called from Init.py, before the GUI starts, so FreeCAD builds its window in Fusion instead of
    restyling it later (measured: a live switch costs ~0.2 s on the first start).
    """
    group = FreeCAD.ParamGet(main_window)
    if group.GetString("QtStyle", "") or group.GetString("StyleSheet", ""):
        return False
    group.SetString("QtStyle", "Fusion")
    return True


def palette(mode: str) -> Palette:
    try:
        return _PALETTES[mode]
    except KeyError:
        raise ValueError(f"no palette for mode {mode!r}") from None


# -- colors ------------------------------------------------------------------------------------
def _channels(color: str):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def rgba(color: str) -> int:
    """"#RRGGBB" as FreeCAD stores colors: one unsigned number 0xRRGGBBAA, opaque."""
    r, g, b = _channels(color)
    return (r << 24) | (g << 16) | (b << 8) | 0xFF


def mix(a: str, b: str, t: float) -> str:
    """`a` moved a fraction `t` of the way to `b`."""
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(_channels(a), _channels(b)))


def luminance(color: str) -> float:
    def linear(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in _channels(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio, 1 to 21."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# -- FreeCAD's settings -------------------------------------------------------------------------
def freecad_settings(p: Palette) -> list:
    """(group, name, value) for each FreeCAD setting the palette sets; value is a bool or a color."""
    view = [
        ("Simple", False), ("Gradient", True), ("RadialGradient", False), ("UseBackgroundColorMid", False),
        ("BackgroundColor", p.view_flat), ("BackgroundColor2", p.view_top), ("BackgroundColor3", p.view_bottom),
        ("DefaultShapeColor", p.model), ("DefaultShapeLineColor", p.model_edge),
        ("DefaultShapeVertexColor", p.model_edge),
        ("HighlightColor", p.preselect), ("SelectionColor", p.accent),
        ("SketchEdgeColor", p.sketch_edge), ("SketchVertexColor", p.sketch_edge),
        ("EditedEdgeColor", p.sketch_edge), ("EditedVertexColor", p.sketch_edge),
        ("ConstructionColor", p.sketch_construction),
        ("FullyConstrainedColor", p.sketch_done), ("FullyConstraintElementColor", p.sketch_done),
        ("ConstrainedDimColor", p.accent), ("ConstrainedIcoColor", p.accent),
        ("CursorTextColor", p.text), ("CursorCrosshairColor", p.text), ("CreateLineColor", p.text),
    ]
    sketcher = [("GridLineColor", p.sketch_grid), ("GridDivLineColor", p.sketch_grid_major)]
    # Tree rows: the item being edited (e.g. a sketch) and the active body.
    tree = [("TreeEditColor", p.selection), ("TreeActiveColor", mix(p.accent, p.panel, 0.9))]
    return ([("View", n, v) for n, v in view] + [("Mod/Sketcher/General", n, v) for n, v in sketcher]
            + [("TreeView", n, v) for n, v in tree])


def _as_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"#{rgba(value):08X}"


def _read(group, name: str, value):
    """The stored value as text, or None if FreeCAD has none yet."""
    if isinstance(value, bool):
        if group.GetBool(name, True) != group.GetBool(name, False):
            return None
        return "true" if group.GetBool(name, False) else "false"
    if group.GetUnsigned(name, 0) != group.GetUnsigned(name, 1):
        return None
    return f"#{group.GetUnsigned(name, 0):08X}"


def _write(group, name: str, value) -> None:
    if isinstance(value, bool):
        group.SetBool(name, value)
    else:
        group.SetUnsigned(name, rgba(value))


class FreeCADColors:
    """Writes a palette into FreeCAD's settings under `root`, keeping colors the user changed.

    Studio records each value it writes (setting `Appearance/Written/<group>/<name>`). A stored value
    that differs from Studio's record was changed by the user, so it stays.
    """

    def __init__(self, settings, root: str = FREECAD_PREFERENCES):
        self._settings, self._root = settings, root

    def apply(self, p: Palette) -> list:
        """Returns the settings written, as "group/name"."""
        written = []
        for group_path, name, value in freecad_settings(p):
            group = FreeCAD.ParamGet(f"{self._root}/{group_path}")
            record = Setting(f"Appearance/Written/{group_path}/{name}", "")
            last, current, wanted = self._settings.get(record), _read(group, name, value), _as_text(value)
            if last and current is not None and current != last:
                continue  # changed by the user since Studio wrote it
            if current != wanted:
                _write(group, name, value)
                written.append(f"{group_path}/{name}")
            if last != wanted:
                self._settings.set(record, wanted)
        return written
