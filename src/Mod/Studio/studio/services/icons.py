# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's line icons (ADR 0010, PLAN 2.9 step 4).

One drawing per tool or feature type in Resources/icons/line: a 24 px grid, one stroke weight, no fills,
the neutral grey `theme.ICON_NEUTRAL`. Two uses:

- FreeCAD's places (the model tree, the ☰ menus, FreeCAD's dialogs) find icons by name. Studio puts
  its drawings into FreeCAD's icon cache under those names (`freecad_registrations`), so they show in
  the neutral grey that reads in both modes. Tools without a Studio drawing keep FreeCAD's icon.
- Studio's own surfaces (toolbar, palette) look a drawing up by FreeCAD's icon name (`line_icon`) and
  draw it in the mode's text color.
"""

import os

STROKE = "1.75"
ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "Resources", "icons", "line")

# FreeCAD's icon name (a command's pixmap, a model-tree object's, FreeCAD's own) -> Studio's drawing.
FREECAD_ICONS = {
    # Sketches
    "Sketcher_NewSketch": "sketch-new",
    "Sketcher_Sketch": "sketch",
    "Sketcher_EditSketch": "sketch",
    "Sketcher_LeaveSketch": "close-sketch",
    "Sketcher_CreateLine": "line",
    "Sketcher_CreateRectangle": "rectangle",
    "Sketcher_CreateCircle": "circle",
    "Sketcher_CreateArc": "arc",
    # The sketch tools' ways to draw (PLAN 3.12): each way its own drawing, rings where the user clicks.
    "Sketcher_CreatePolyline": "line-arc",
    "Sketcher_CreateRectangle_Center": "rectangle-center",
    "Sketcher_CreateOblong": "rectangle-rounded",
    "Sketcher_Create3PointCircle": "circle-3-point",
    "Sketcher_Create3PointArc": "arc-3-point",
    "Sketcher_CreateRegularPolygon": "polygon",
    "Sketcher_CreateTriangle": "triangle",
    "Sketcher_CreateSquare": "square",
    "Sketcher_CreateHexagon": "hexagon",
    "Sketcher_CreateSlot": "slot",
    "Sketcher_CreateArcSlot": "slot-arc",
    "Sketcher_CreateBSplineByInterpolation": "spline",
    "Sketcher_CreateBSpline": "spline-control",
    "Sketcher_CreateEllipseByCenter": "ellipse",
    "Sketcher_CreateEllipse_3points": "ellipse-3-point",
    "Sketcher_CreateElliptical_Arc": "ellipse-arc",
    "Sketcher_CreatePoint": "point",
    "Sketcher_CreateText": "text",
    "Sketcher_ToggleConstruction": "construction",  # also Studio's Construction switch (PLAN 3.13)
    # The sketch's patterns, drawn as the model's (the toolbar's Pattern drop-down shows both)
    "Sketcher_Translate": "pattern-linear",
    "Sketcher_Rotate": "pattern-polar",
    "Sketcher_Symmetry": "mirror",
    "Constraint_Dimension": "dimension",
    # Sketcher constraints: the sketch panel's Constraints list and the constraint tools. A driven
    # (reference) constraint shares its driving one's drawing. The Elements list keeps FreeCAD's icons:
    # their colors say which part of an element a row is, and FreeCAD recolors them for construction
    # and external geometry.
    "Constraint_PointOnPoint": "constraint-coincident",
    "Constraint_PointOnObject": "constraint-point-on-object",
    "Constraint_Horizontal": "constraint-horizontal",
    "Constraint_Vertical": "constraint-vertical",
    "Constraint_Parallel": "constraint-parallel",
    "Constraint_Perpendicular": "constraint-perpendicular",
    "Constraint_Tangent": "constraint-tangent",
    "Constraint_EqualLength": "constraint-equal",
    "Constraint_Symmetric": "constraint-symmetric",
    "Constraint_Block": "constraint-block",
    "Constraint_Lock": "constraint-lock",
    "Constraint_Length": "constraint-distance",
    "Constraint_Length_Driven": "constraint-distance",
    "Constraint_HorizontalDistance": "dimension",
    "Constraint_HorizontalDistance_Driven": "dimension",
    "Constraint_VerticalDistance": "constraint-distance-vertical",
    "Constraint_VerticalDistance_Driven": "constraint-distance-vertical",
    "Constraint_Radius": "constraint-radius",
    "Constraint_Radius_Driven": "constraint-radius",
    "Constraint_Diameter": "constraint-diameter",
    "Constraint_Diameter_Driven": "constraint-diameter",
    "Constraint_InternalAngle": "constraint-angle",
    "Constraint_InternalAngle_Driven": "constraint-angle",
    "Constraint_SnellsLaw": "constraint-refraction",
    "Constraint_SnellsLaw_Driven": "constraint-refraction",
    "Constraint_InternalAlignment": "constraint-alignment",
    "Constraint_InternalAlignment_Ellipse_MajorAxis": "constraint-alignment",
    "Constraint_InternalAlignment_Ellipse_MinorAxis": "constraint-alignment",
    "Constraint_Ellipse_Axis_Angle": "constraint-alignment",
    "Constraint_Ellipse_Major_Radius": "constraint-alignment",
    "Constraint_Ellipse_Minor_Radius": "constraint-alignment",
    "Sketcher_CreateLineAngleLength": "constraint-angle",  # also the Constraints panel's header
    # Part Design features
    "PartDesign_Body": "body",
    "PartDesign_BaseFeature": "base-feature",
    "PartDesign_Pad": "extrude",
    "PartDesign_Pocket": "cut",
    "PartDesign_Revolution": "revolve",
    "PartDesign_Groove": "revolve-cut",
    "PartDesign_Hole": "hole",
    "PartDesign_Fillet": "fillet",
    "PartDesign_Chamfer": "chamfer",
    "PartDesign_Thickness": "shell",
    "PartDesign_Draft": "draft",
    "PartDesign_Mirrored": "mirror",
    "PartDesign_LinearPattern": "pattern-linear",
    "PartDesign_PolarPattern": "pattern-polar",
    "PartDesign_MultiTransform": "pattern-multi",
    "PartDesign_AdditiveLoft": "loft",
    "PartDesign_SubtractiveLoft": "loft-cut",
    "PartDesign_AdditivePipe": "sweep",
    "PartDesign_SubtractivePipe": "sweep-cut",
    "PartDesign_AdditiveHelix": "helix",
    "PartDesign_SubtractiveHelix": "helix-cut",
    "PartDesign_Boolean": "boolean",
    "PartDesign_ShapeBinder": "binder",
    "PartDesign_SubShapeBinder": "binder",
    # Reference geometry: Part Design's datums and FreeCAD's origin
    "PartDesign_Plane": "plane",
    "Std_Plane": "plane",
    "PartDesign_Line": "axis",
    "Std_Axis": "axis",
    "PartDesign_Point": "point",
    "Std_Point": "point",
    "PartDesign_CoordinateSystem": "origin",
    "Std_CoordinateSystem": "origin",
    # The model tree
    "TreeItemVisible": "eye",
    "TreeItemInvisible": "eye-off",
    "Document": "document",
    # Files, editing, view
    "document-new": "file-new",
    "document-open": "file-open",
    "document-save": "file-save",
    "edit-undo": "undo",
    "edit-redo": "redo",
    "Std_Import": "import",
    "umf-measurement": "measure",
    "zoom-selection": "fit-selection",
    "zoom-all": "fit-all",
}

# Only on Studio's surfaces: the command palette's icon is called "Studio", like the workbench.
STUDIO_ONLY = {"Studio": "search", "fully-constrain": "fully-constrain",
               "finish": "finish", "cancel": "cancel",  # a task panel's buttons on the toolbar (PLAN 3.5)
               "section": "section",  # the section view (PLAN 3.7)
               # ways to draw FreeCAD has no command for (studio.viewmodels.context_toolbar.WAYS)
               "rectangle-3-point": "rectangle-3-point", "rectangle-3-point-center": "rectangle-3-point-center",
               "line-center": "line-center", "circle-2-point": "circle-2-point",
               "polygon-circumscribed": "polygon-circumscribed", "polygon-edge": "polygon-edge",
               "slot-overall": "slot-overall", "slot-center": "slot-center", "arc-tangent": "arc-tangent",
               "circle-2-tangent": "circle-2-tangent", "circle-3-tangent": "circle-3-tangent",
               "slot-arc-3-point": "slot-arc-3-point"}


def icon_path(drawing: str) -> str:
    return os.path.join(ICON_DIR, drawing + ".svg")


def line_icon(freecad_name):
    """Studio's drawing for a FreeCAD icon name (with or without ".svg"), or None."""
    if not freecad_name:
        return None
    name = freecad_name[:-4] if freecad_name.endswith(".svg") else freecad_name
    drawing = FREECAD_ICONS.get(name) or STUDIO_ONLY.get(name)
    return icon_path(drawing) if drawing else None


def freecad_registrations() -> dict:
    """{drawing's path: [FreeCAD icon names]}. Each name also with ".svg": commands ask for
    "PartDesign_Pad", the model tree for "PartDesign_Pad.svg"."""
    registrations = {}
    for name, drawing in FREECAD_ICONS.items():
        registrations.setdefault(icon_path(drawing), []).extend([name, name + ".svg"])
    return registrations
