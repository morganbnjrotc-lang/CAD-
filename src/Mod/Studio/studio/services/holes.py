# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click hole chamfer (PLAN 3.9): a hole's opening edges and a chamfer size to start with.

A Part Design hole starts on its sketch's plane, one hole at each circle (or point) of the sketch. Its
openings are the round edges of the result on that plane, around those centers: the hole's own edge, or
its counterbore's or countersink's. Where a through hole comes out isn't on that plane.
"""

import FreeCAD
import Part

TOLERANCE = 1e-6  # mm


def _centers_and_plane(hole):
    sketch = hole.Profile[0]
    placement = sketch.getGlobalPlacement()
    centers = []
    for geometry in sketch.Geometry:
        if geometry.TypeId == "Part::GeomCircle":
            centers.append(placement.multVec(geometry.Center))
        elif geometry.TypeId == "Part::GeomPoint":
            centers.append(placement.multVec(FreeCAD.Vector(geometry.X, geometry.Y, geometry.Z)))
    normal = placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
    return centers, placement.Base, normal


def opening_edges(hole):
    """Names ("Edge7") of the edges where the hole's holes open, in the hole feature's shape."""
    if getattr(hole, "TypeId", "") != "PartDesign::Hole" or hole.Shape.isNull() or not hole.Profile:
        return []
    centers, origin, normal = _centers_and_plane(hole)
    shape = Part.getShape(hole)  # where it shows: the body's placement applied, as the sketch's
    names = []
    for index, edge in enumerate(shape.Edges):
        curve = edge.Curve
        if curve.TypeId != "Part::GeomCircle":
            continue
        if abs((curve.Center - origin).dot(normal)) > TOLERANCE:
            continue  # not on the face the hole starts from
        if any((curve.Center - center).Length < TOLERANCE for center in centers):
            names.append(f"Edge{index + 1}")
    return names


def chamfer_size(hole) -> float:
    """A tenth of the hole's diameter, at least 0.2 mm (mm)."""
    return max(round(hole.Diameter.Value * 0.1, 3), 0.2)
