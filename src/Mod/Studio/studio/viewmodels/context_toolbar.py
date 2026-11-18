# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar that follows the selection (docs/adr/0009).

The shell reports the selection as `Selected` items (object type, sub-elements such as "Face3") and
the type of the object being edited, if any. `selection_kind` sorts that into one kind; `TOOLS` lists
the tools for each kind; `ContextToolbar` turns them into buttons with plain names, icons, the
active shortcut and FreeCAD's name in the tooltip, plus a status-bar hint. No Qt here.
"""

from dataclasses import dataclass

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
                ("Sketcher_CreateArc", "Arc"), ("Sketcher_Dimension", None), ("Studio_FullyConstrain", None),
                ("Sketcher_LeaveSketch", "Close Sketch")],
}


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


class ContextToolbar:
    def __init__(self, catalog, keymap=None):
        self._catalog = catalog
        self._keymap = keymap

    def _key(self, command, contexts) -> str:
        if self._keymap is None:
            return ""
        return next((s for s, c in self._keymap.active_bindings(contexts).items() if c == command), "")

    def buttons(self, kind: str, contexts=()) -> list:
        result = []
        for command, label in TOOLS[kind]:
            info = self._catalog.get(command)
            label = label or display_title(info)
            freecad_name = clean_title(info.menu_text)
            tooltip = info.tooltip + (f"\nFreeCAD: {freecad_name}" if freecad_name != label else "")
            result.append(ToolButton(command, label, info.icon, self._key(command, contexts), tooltip))
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
