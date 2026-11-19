# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar that follows the selection (docs/adr/0009).

The shell reports the selection as `Selected` items (object type, sub-elements such as "Face3") and
the type of the object being edited, if any. `selection_kind` sorts that into one kind; `TOOLS` lists
the tools for each kind; `ContextToolbar` turns them into buttons with plain names, icons, the
active shortcut and FreeCAD's name in the tooltip, plus a status-bar hint. No Qt here.

Sketch tools that draw a shape more than one way (`WAYS`, PLAN 3.12) list the ways in a drop-down, as
Fusion and Inventor do; the button draws the way picked last (`choose`), remembered in the settings.
Switches (`SWITCHES`: Construction, PLAN 3.13) show whether they are on.
"""

from dataclasses import dataclass

from studio.services.settings import Setting
from studio.viewmodels.tool_names import clean_title, display_title

SKETCH = "Sketcher::SketchObject"

# Kind of selection -> (command, label if the toolbar names it differently from display_title).
TOOLS = {
    "nothing": [("PartDesign_NewSketch", None), ("PartDesign_Body", None), ("Std_Import", None),
                ("Std_Measure", None), ("Studio_CommandPalette", "Search")],
    "sketch": [("PartDesign_Pad", None), ("PartDesign_Pocket", None), ("PartDesign_Revolution", None),
               ("PartDesign_Hole", None), ("Sketcher_EditSketch", None)],
    "face": [("PartDesign_NewSketch", "Sketch on Face"), ("PartDesign_Fillet", None), ("PartDesign_Chamfer", None),
             ("PartDesign_Thickness", None), ("PartDesign_Draft", None), ("Std_Measure", None)],
    "edge": [("PartDesign_Fillet", None), ("PartDesign_Chamfer", None), ("Std_Measure", None),
             ("Std_ViewFitSelection", None)],
    "geometry": [("PartDesign_Fillet", None), ("PartDesign_Chamfer", None), ("Std_Measure", None),
                 ("Std_ViewFitSelection", None)],
    "feature": [("PartDesign_Mirrored", None), ("PartDesign_LinearPattern", None), ("PartDesign_PolarPattern", None),
                ("Std_ViewFitSelection", None)],
    "editing": [("Sketcher_CreateLine", None), ("Sketcher_CreateRectangle", None), ("Sketcher_CreateCircle", "Circle"),
                ("Sketcher_CreateArc", "Arc"), ("Sketcher_CreateRegularPolygon", "Polygon"),
                ("Sketcher_CreateSlot", None), ("Sketcher_CreateBSplineByInterpolation", "Spline"),
                ("Sketcher_CreateEllipseByCenter", "Ellipse"), ("Sketcher_CreatePoint", None),
                ("Sketcher_CreateText", None), ("Studio_Construction", None), ("Sketcher_Dimension", None),
                ("Studio_FullyConstrain", None), ("Sketcher_LeaveSketch", "Close Sketch")],
}

# Tools that are switches: their button stays lit while on (PLAN 3.13; the shell says which are on).
SWITCHES = frozenset({"Studio_Construction"})


@dataclass(frozen=True)
class Way:
    """One way to draw a shape: a FreeCAD command, and the drawing method its tool panel starts in (the
    index in the panel's first list) when FreeCAD has no command that starts in it."""

    command: str
    label: str
    method: int = 0
    icon: str = ""  # Studio's drawing, for a way FreeCAD has no command (and so no icon) for


# Tool (its command in TOOLS) -> the ways it draws, the default first; Fusion's names for them.
WAYS = {
    "Sketcher_CreateLine": (Way("Sketcher_CreateLine", "Line"),
                            Way("Sketcher_CreatePolyline", "Lines and Arcs")),  # M switches to arcs
    "Sketcher_CreateRectangle": (Way("Sketcher_CreateRectangle", "2-Point Rectangle"),
                                 Way("Sketcher_CreateRectangle_Center", "Center Rectangle"),
                                 Way("Sketcher_CreateRectangle", "3-Point Rectangle", 2, "rectangle-3-point"),
                                 Way("Sketcher_CreateRectangle", "3-Point Center Rectangle", 3,
                                     "rectangle-3-point-center"),
                                 Way("Sketcher_CreateOblong", "Rounded Rectangle")),
    "Sketcher_CreateCircle": (Way("Sketcher_CreateCircle", "Center Diameter Circle"),
                              Way("Sketcher_Create3PointCircle", "3-Point Circle")),
    "Sketcher_CreateArc": (Way("Sketcher_CreateArc", "Center Point Arc"),
                           Way("Sketcher_Create3PointArc", "3-Point Arc")),
    "Sketcher_CreateRegularPolygon": (Way("Sketcher_CreateRegularPolygon", "Inscribed Polygon"),
                                      Way("Sketcher_CreateTriangle", "Triangle"),
                                      Way("Sketcher_CreateSquare", "Square"),
                                      Way("Sketcher_CreateHexagon", "Hexagon")),
    "Sketcher_CreateSlot": (Way("Sketcher_CreateSlot", "Center to Center Slot"),
                            Way("Sketcher_CreateArcSlot", "Center Point Arc Slot")),
    "Sketcher_CreateBSplineByInterpolation": (Way("Sketcher_CreateBSplineByInterpolation", "Fit Point Spline"),
                                              Way("Sketcher_CreateBSpline", "Control Point Spline")),
    "Sketcher_CreateEllipseByCenter": (Way("Sketcher_CreateEllipseByCenter", "Center Ellipse"),
                                       Way("Sketcher_CreateEllipseBy3Points", "3-Point Ellipse"),
                                       Way("Sketcher_CreateArcOfEllipse", "Elliptical Arc")),
}


def _way_setting(tool: str) -> Setting:
    return Setting(f"Toolbar/Ways/{tool}", 0)


@dataclass(frozen=True)
class Selected:
    type_id: str
    subs: tuple = ()


def _sub_kind(sub: str) -> str:
    for prefix, kind in (("Face", "face"), ("Edge", "edge"), ("Vertex", "vertex")):
        if sub.startswith(prefix):
            return kind
    return "other"


def selection_kind(selected, editing=None) -> str:
    """One of TOOLS' kinds for the selection and the type of the object in edit (or None)."""
    if editing == SKETCH:
        return "editing"
    if not selected:
        return "nothing"
    if all(s.type_id == SKETCH for s in selected):
        return "sketch"
    if all(s.subs for s in selected):
        kinds = {_sub_kind(sub) for s in selected for sub in s.subs}
        return {frozenset({"face"}): "face", frozenset({"edge"}): "edge"}.get(frozenset(kinds), "geometry")
    if all(not s.subs and s.type_id.startswith("PartDesign::") and s.type_id != "PartDesign::Body" for s in selected):
        return "feature"
    return "nothing"


@dataclass(frozen=True)
class ToolButton:
    command: str
    label: str
    icon: str | None  # source SVG path from the catalog
    shortcut: str  # first active key sequence, "" if none
    tooltip: str
    method: int = 0  # the drawing method to start the command's tool in (Way.method)
    ways: tuple = ()  # the tool's Ways when it draws more than one way; `way` is the one the button draws
    way: int = 0
    tool: str = ""  # the tool's command in TOOLS, for `choose`
    checked: bool | None = None  # a switch (SWITCHES): whether it is on; None: not a switch


class ContextToolbar:
    def __init__(self, catalog, keymap=None, settings=None, is_on=None):
        """`is_on(command) -> bool` tells whether a switch is on (SWITCHES); without it they show off."""
        self._catalog = catalog
        self._keymap = keymap
        self._settings = settings
        self._is_on = is_on

    def choose(self, tool: str, way: int):
        """The user picked `way` from `tool`'s list: the button draws it from now on."""
        if self._settings is not None:
            self._settings.set(_way_setting(tool), way)

    def way_icon(self, way: Way) -> str:
        """The icon a way shows: Studio's drawing for it, else its command's."""
        return way.icon or self._catalog.get(way.command).icon

    def _chosen(self, tool: str) -> int:
        way = self._settings.get(_way_setting(tool)) if self._settings is not None else 0
        return way if 0 <= way < len(WAYS[tool]) else 0

    def _key(self, command, contexts) -> str:
        if self._keymap is None:
            return ""
        return next((s for s, c in self._keymap.active_bindings(contexts).items() if c == command), "")

    def buttons(self, kind: str, contexts=()) -> list:
        result = []
        for tool, label in TOOLS[kind]:
            label = label or display_title(self._catalog.get(tool))
            ways, way = WAYS.get(tool, ()), 0
            command, method, title = tool, 0, label
            if ways:
                way = self._chosen(tool)
                command, method, title = ways[way].command, ways[way].method, ways[way].label
            info = self._catalog.get(command)
            icon = self.way_icon(ways[way]) if ways else info.icon
            freecad_name = clean_title(info.menu_text)
            tooltip = info.tooltip + (f"\nFreeCAD: {freecad_name}" if freecad_name != title else "")
            if ways:
                tooltip = f"{title}\n{tooltip}"
            checked = None
            if command in SWITCHES:
                checked = bool(self._is_on(command)) if self._is_on is not None else False
            result.append(ToolButton(command, label, icon, self._key(command, contexts), tooltip,
                                     method, ways, way, tool, checked))
        return result

    def hint(self, kind: str, contexts=()) -> str:
        search = self._key("Studio_CommandPalette", contexts)
        if kind == "nothing":
            return "Select a sketch, face or edge to see its tools" + (
                f", or press {search} to search every tool" if search else "")
        if kind == "sketch":
            extrude = self._key("PartDesign_Pad", contexts)
            return f"Press {extrude} to extrude the selected sketch" if extrude else \
                "Extrude turns the selected sketch into a solid"
        if kind == "editing":
            return "Esc stops the current tool" + (f"  ·  {search} searches every tool" if search else "")
        return {
            "face": "Sketch on Face starts a new sketch on the selected face",
            "edge": "Fillet rounds the selected edges; Chamfer bevels them",
            "geometry": "Fillet and Chamfer work on the selected edges and faces",
            "feature": "Mirror or pattern the selected feature",
        }[kind]
