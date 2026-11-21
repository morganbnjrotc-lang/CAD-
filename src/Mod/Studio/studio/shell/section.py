# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click section view in the app (PLAN 3.7; studio.services.section picks the plane).

The toolbar's Section cuts the 3D view: on the flat face picked first, keeping the part behind it, or
through the middle of the model, keeping the half away from the viewer. An arrow on the plane (Extrude's,
in the accent color) drags it along its normal. A second click turns it off. Only the view is cut: the
model doesn't change. The plane and the arrow are StudioGui's (C++), in FreeCAD's 3D view.
"""

import FreeCAD
import FreeCADGui

from studio.services import section


def is_on() -> bool:
    import StudioGui

    return StudioGui.section_plane() is not None


def toggle():
    import StudioGui

    if is_on():
        StudioGui.section_off()
    else:
        start = _starting_plane()
        if start is not None:
            (point, normal), size = start
            StudioGui.section(point.x, point.y, point.z, normal.x, normal.y, normal.z, size)
    from studio.shell import window

    if window.current() is not None:
        window.current().schedule_refresh()  # the button shows whether it is on


def _starting_plane():
    """((point, normal), model size) for the active document, or None if it shows nothing."""
    document = FreeCADGui.ActiveDocument
    if document is None:
        return None
    box = _shown_bounds(document.Document)
    if box is None:
        return None
    for picked in FreeCADGui.Selection.getSelectionEx():
        for sub in picked.SubObjects:
            if getattr(sub, "ShapeType", "") == "Face":
                plane = section.on_face(sub)
                if plane is not None:
                    return plane, box.DiagonalLength
    looking = document.ActiveView.getViewDirection()
    return section.through_middle(box, looking), box.DiagonalLength


def _shown_bounds(doc):
    box = FreeCAD.BoundBox()
    for obj in doc.Objects:
        shape = getattr(obj, "Shape", None)
        view_object = getattr(obj, "ViewObject", None)
        if shape is None or shape.isNull() or view_object is None or not view_object.isVisible():
            continue
        if obj.getParentGeoFeatureGroup() is not None and obj.TypeId != "PartDesign::Body":
            continue  # inside a body the body shows its result
        box.add(shape.BoundBox)
    return box if box.isValid() else None
