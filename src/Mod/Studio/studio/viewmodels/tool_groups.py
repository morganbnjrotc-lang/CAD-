# SPDX-License-Identifier: LGPL-2.1-or-later
"""Every tool in Fusion's groups on the top bar, and tools pinned to the toolbar (PLAN 3.17, docs/adr/0013).

The toolbar follows the selection (context_toolbar) and shows a few tools; the rest had to be searched for.
The top bar now has Fusion's group words as menus holding every tool: Create, Modify, Construct, Inspect,
Insert, and while sketching Create, Modify, Constrain, Inspect. A tool drawing more than one way lists its
ways in a side menu, as Part Design's primitives (one FreeCAD command for all, told which by an item number).
A tool from a group can be pinned to the toolbar for one kind of selection (faces, sketches…): it shows
after that kind's tools, remembered in the settings by the item's `key`. No Qt here.
"""

from dataclasses import dataclass

from studio.services.settings import Setting
from studio.viewmodels.context_toolbar import NEEDS_SELECTION, TOOLS, WAYS, ToolButton, selection_hint
from studio.viewmodels.tool_names import clean_title, display_title

ICONS = "src/Mod/PartDesign/Gui/Resources/icons/"
PRIMITIVES = ("Box", "Cylinder", "Sphere", "Cone", "Ellipsoid", "Torus", "Prism", "Wedge")  # FreeCAD's order

# Words for the kinds of selection (context_toolbar.TOOLS), as in "Pin to toolbar for faces".
KIND_WORDS = {
    "nothing": "when nothing is selected",
    "sketch": "for sketches",
    "face": "for faces",
    "edge": "for edges",
    "geometry": "for faces and edges",
    "feature": "for features",
    "hole": "for holes",
    "task": "while a panel is open",
    "editing": "while sketching",
}


@dataclass(frozen=True)
class Tool:
    """A group's entry: a command, its name when the group says it differently, and for a command making
    several things (Part Design's primitives), the item number and that item's icon."""

    command: str
    label: str = ""
    index: int = -1
    icon: str = ""


@dataclass(frozen=True)
class Side:
    """A side menu: a few tools under one name. `ways` names a tool of context_toolbar.WAYS instead."""

    label: str
    tools: tuple = ()
    ways: str = ""


def _primitives(command, kind, suffix=""):
    return tuple(Tool(command, name + suffix, n, f"{ICONS}PartDesign_{kind}{name}.svg")
                 for n, name in enumerate(PRIMITIVES))


def _ways(tool, label=""):
    return Side(label, ways=tool)


_ = None  # a separator

MODEL = (
    ("Create", (
        Tool("PartDesign_NewSketch"),
        _,
        Tool("PartDesign_Pad"), Tool("PartDesign_Revolution"), Tool("PartDesign_AdditivePipe"),
        Tool("PartDesign_AdditiveLoft"), Tool("PartDesign_AdditiveHelix", "Helix"), Tool("PartDesign_Hole"),
        Tool("Studio_Thread"),
        Side("Primitive", _primitives("PartDesign_CompPrimitiveAdditive", "Additive")),
        _,
        Tool("PartDesign_Pocket"), Tool("PartDesign_Groove"), Tool("PartDesign_SubtractivePipe"),
        Tool("PartDesign_SubtractiveLoft"), Tool("PartDesign_SubtractiveHelix", "Helix Cut"),
        Side("Primitive Cut", _primitives("PartDesign_CompPrimitiveSubtractive", "Subtractive")),
        _,
        Side("Pattern", (Tool("PartDesign_LinearPattern", "Rectangular Pattern"),
                         Tool("PartDesign_PolarPattern", "Circular Pattern"), Tool("PartDesign_Mirrored", "Mirror"),
                         Tool("PartDesign_PathPattern"), Tool("PartDesign_PointPattern"),
                         Tool("PartDesign_MultiTransform"))),
        Side("Gear", (Tool("PartDesign_InvoluteGear"), Tool("PartDesign_Sprocket"))),
        _,
        Tool("PartDesign_Body"),
    )),
    ("Modify", (
        Tool("PartDesign_Fillet"), Tool("PartDesign_Chamfer"), Tool("PartDesign_Thickness"), Tool("PartDesign_Draft"),
        Tool("Studio_HoleChamfer"), Tool("PartDesign_Defeaturing", "Remove Faces"),
        _,
        Tool("PartDesign_Boolean", "Combine"), Tool("Std_TransformManip", "Move"),
        # Part Design's Duplicate has no icon of its own: FreeCAD's general one
        Tool("PartDesign_DuplicateSelection", "Duplicate", icon="src/Gui/Icons/Std_DuplicateSelection.svg"), Tool("Sketcher_EditSketch"),
        _,
        Tool("Std_SetAppearance", "Appearance"), Tool("Std_SetMaterial", "Material"),
        _,
        Tool("PartDesign_MoveTip"), Tool("PartDesign_MoveFeature", "Move to Another Body"),
        Tool("PartDesign_MoveFeatureInTree", "Move Later in the Tree"),
        _,
        Tool("Std_Delete", "Delete"),
    )),
    ("Construct", (
        Tool("PartDesign_Plane", "Plane"), Tool("PartDesign_Line", "Axis"), Tool("PartDesign_Point", "Point"),
        Tool("PartDesign_CoordinateSystem", "Coordinate System"),
        _,
        Tool("PartDesign_ShapeBinder"), Tool("PartDesign_SubShapeBinder"), Tool("PartDesign_Clone"),
    )),
    ("Inspect", (
        Tool("Std_Measure", "Measure"), Tool("Studio_Section"), Tool("Std_MassProperties"),
        Tool("Part_CheckGeometry"),
    )),
    ("Insert", (
        Tool("Std_Import", "Import"), Tool("Std_Export", "Export"),
        _,
        Tool("Spreadsheet_CreateSheet", "Spreadsheet"),
    )),
)

SKETCH = (
    ("Create", (
        _ways("Sketcher_CreateLine"), _ways("Sketcher_CreateRectangle"), _ways("Sketcher_CreateCircle", "Circle"),
        _ways("Sketcher_CreateArc", "Arc"), _ways("Sketcher_CreateRegularPolygon", "Polygon"),
        _ways("Sketcher_CreateSlot"), _ways("Sketcher_CreateBSplineByInterpolation", "Spline"),
        _ways("Sketcher_CreateEllipseByCenter", "Ellipse"),
        Side("Conic", (Tool("Sketcher_CreateArcOfParabola"), Tool("Sketcher_CreateArcOfHyperbola"))),
        Tool("Sketcher_CreatePoint"), Tool("Sketcher_CreateText"),
        _,
        Tool("Sketcher_CreateFillet"), Tool("Sketcher_CreateChamfer"), Tool("Sketcher_Offset"),
        _ways("Sketcher_Translate", "Pattern"),
        _,
        Tool("Sketcher_Projection", "Project"), Tool("Sketcher_Intersection", "Intersect"),
        Tool("Sketcher_CarbonCopy"),
    )),
    ("Modify", (
        Tool("Sketcher_Trimming", "Trim"), Tool("Sketcher_Extend", "Extend"), Tool("Sketcher_Split", "Split"),
        Tool("Sketcher_JoinCurves", "Join"),
        _,
        Tool("Sketcher_Move", "Move"), Tool("Sketcher_Copy", "Copy"), Tool("Sketcher_Rotate", "Rotate"),
        Tool("Sketcher_Scale", "Scale"), Tool("Sketcher_Symmetry", "Mirror"),
        _,
        Tool("Studio_Construction"), Tool("Sketcher_RemoveAxesAlignment"),
        _,
        Tool("Std_Delete", "Delete"), Tool("Sketcher_DeleteAllGeometry"),
    )),
    ("Constrain", (
        Tool("Sketcher_Dimension"), Tool("Studio_FullyConstrain"),
        _,
        Tool("Sketcher_ConstrainCoincidentUnified", "Coincident"), Tool("Sketcher_ConstrainHorizontal", "Horizontal"),
        Tool("Sketcher_ConstrainVertical", "Vertical"), Tool("Sketcher_ConstrainParallel", "Parallel"),
        Tool("Sketcher_ConstrainPerpendicular", "Perpendicular"), Tool("Sketcher_ConstrainTangent", "Tangent"),
        Tool("Sketcher_ConstrainEqual", "Equal"), Tool("Sketcher_ConstrainSymmetric", "Symmetric"),
        Tool("Sketcher_ConstrainBlock", "Fix"), Tool("Sketcher_ConstrainLock", "Lock Position"),
        Side("Dimensions", (Tool("Sketcher_ConstrainDistance", "Distance"),
                            Tool("Sketcher_ConstrainDistanceX", "Horizontal Distance"),
                            Tool("Sketcher_ConstrainDistanceY", "Vertical Distance"),
                            Tool("Sketcher_ConstrainRadius", "Radius"), Tool("Sketcher_ConstrainDiameter", "Diameter"),
                            Tool("Sketcher_ConstrainAngle", "Angle"))),
        _,
        Tool("Sketcher_ToggleDrivingConstraint", "Driving or Reference"),
        Tool("Sketcher_ToggleActiveConstraint", "Turn Constraints On or Off"),
        Tool("Sketcher_DeleteAllConstraints"),
    )),
    ("Inspect", (
        Tool("Sketcher_SelectElementsWithDoFs", "Show Unconstrained"),
        Tool("Sketcher_SelectConflictingConstraints"), Tool("Sketcher_SelectRedundantConstraints"),
        Tool("Sketcher_ValidateSketch"),
        _,
        Tool("Sketcher_ViewSketch", "Look at Sketch"), Tool("Sketcher_ViewSection", "Section View"),
        Tool("Std_Measure", "Measure"),
    )),
)


def key_of(command, index=-1, method=0) -> str:
    """What a pin remembers of a tool: its command, and its item or drawing method when it has one."""
    if index >= 0:
        return f"{command}#{index}"
    return f"{command}@{method}" if method else command


@dataclass(frozen=True)
class MenuItem:
    command: str
    label: str
    icon: str | None
    shortcut: str
    tooltip: str
    index: int = -1  # the item of a command making several things (FreeCAD's runCommand index)
    method: int = 0  # the drawing method to start the tool in (context_toolbar.Way.method)
    settings: tuple = ()  # context_toolbar.Way.settings
    tool: str = ""  # the tool of context_toolbar.WAYS this is a way of, for its `choose`
    way: int = -1  # which way
    needs_selection: bool = False  # works on sketch geometry selected first

    @property
    def key(self) -> str:
        return key_of(self.command, self.index, self.method)


@dataclass(frozen=True)
class SubMenu:
    label: str
    icon: str | None
    items: tuple


@dataclass(frozen=True)
class Group:
    label: str
    items: tuple  # MenuItem, SubMenu, or None for a separator


class ToolGroups:
    def __init__(self, catalog, toolbar, keymap=None, settings=None):
        """`toolbar`: the ContextToolbar, for the tools each kind of selection already shows and the
        ways' icons."""
        self._catalog = catalog
        self._toolbar = toolbar
        self._keymap = keymap
        self._settings = settings

    # -- the groups ------------------------------------------------------------------------------
    @staticmethod
    def labels(sketching: bool) -> list:
        """The groups' names, without building their tools (the top bar follows each selection)."""
        return [label for label, _ in (SKETCH if sketching else MODEL)]

    def groups(self, sketching: bool, contexts=()) -> list:
        """The top bar's groups: while sketching (a sketch in edit), or modeling."""
        keys = self._keys(contexts)
        return [Group(label, tuple(self._entry(e, keys) for e in entries))
                for label, entries in (SKETCH if sketching else MODEL)]

    def _keys(self, contexts) -> dict:
        """{command: its first active key sequence}."""
        keys = {}
        if self._keymap is not None:
            for sequence, command in self._keymap.active_bindings(contexts).items():
                keys.setdefault(command, sequence)
        return keys

    def _entry(self, entry, keys):
        if entry is None:
            return None
        if isinstance(entry, Tool):
            return self._item(entry, keys)
        if entry.ways:
            ways = WAYS[entry.ways]
            label = entry.label or display_title(self._catalog.get(entry.ways))
            items = tuple(self._item(Tool(w.command, w.label, icon=self._toolbar.way_icon(w)), keys,
                                     method=w.method, settings=w.settings, of=entry.ways, way=n)
                          for n, w in enumerate(ways))
            return SubMenu(label, items[0].icon, items)
        items = tuple(self._item(t, keys) for t in entry.tools)
        return SubMenu(entry.label, items[0].icon, items)

    def _item(self, tool, keys, method=0, settings=(), of="", way=-1):
        info = self._catalog.get(tool.command)
        label = tool.label or display_title(info)
        freecad_name = clean_title(info.menu_text)
        tooltip = info.tooltip + (f"\nFreeCAD: {freecad_name}" if freecad_name != label else "")
        needs = tool.command in NEEDS_SELECTION
        if needs:
            tooltip += "\n" + selection_hint(tool.command)
        return MenuItem(tool.command, label, tool.icon or info.icon, keys.get(tool.command, ""), tooltip,
                        tool.index, method, settings, of, way, needs)

    def _all_items(self, contexts=()):
        for sketching in (False, True):
            for group in self.groups(sketching, contexts):
                for item in group.items:
                    if isinstance(item, SubMenu):
                        yield from item.items
                    elif item is not None:
                        yield item

    # -- pins --------------------------------------------------------------------------------------
    @staticmethod
    def pins_setting(kind) -> Setting:
        return Setting(f"Toolbar/Pins/{kind}", "")

    def _pins(self, kind) -> list:
        if self._settings is None:
            return []
        return [k for k in self._settings.get(self.pins_setting(kind)).split(";") if k]

    def is_pinned(self, kind, key) -> bool:
        return key in self._pins(kind)

    def can_pin(self, kind, key) -> bool:
        """Whether the group's tool `key` isn't on the toolbar for `kind` yet (pinned, or one of that kind's
        own tools)."""
        own = {command for command, _ in TOOLS[kind]}
        return self._settings is not None and key not in own and key not in self._pins(kind)

    def pin(self, kind, key) -> bool:
        """Pins the group's tool `key` to the toolbar for `kind`; False if it is already there."""
        if not self.can_pin(kind, key):
            return False
        self._settings.set(self.pins_setting(kind), ";".join(self._pins(kind) + [key]))
        return True

    def unpin(self, kind, key) -> bool:
        pins = self._pins(kind)
        if key not in pins:
            return False
        self._settings.set(self.pins_setting(kind), ";".join(k for k in pins if k != key))
        return True

    def pinned_buttons(self, kind, contexts=()) -> list:
        """The toolbar's buttons for the tools pinned for `kind`, in the order pinned; pins of tools no
        longer in a group are left out."""
        pins = self._pins(kind)
        if not pins:
            return []  # the usual case, on every change of selection: nothing to build
        items = {}
        for item in self._all_items(contexts):
            items.setdefault(item.key, item)
        result = []
        for key in pins:
            item = items.get(key)
            if item is not None:
                result.append(ToolButton(item.command, item.label, item.icon, item.shortcut, item.tooltip,
                                         item.method, settings=item.settings,
                                         needs_selection=item.needs_selection, index=item.index, pinned=True))
        return result
