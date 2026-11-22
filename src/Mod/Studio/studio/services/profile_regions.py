# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picking a sketch's regions while Extrude is open, like Fusion (PLAN 3.16).

A sketch's regions are the areas its closed shapes enclose. FreeCAD makes each one a face that can be picked
in the 3D view ("InternalFace1"…, the sketch's `InternalShape`), and Part Design's Extrude, Cut, Revolve and
Revolve Cut take either the whole sketch (`Profile` with no names, or "") or the regions named in their `Profile`.
The two differ: the whole sketch leaves out a shape inside another one (a circle in a square is a hole),
while regions are taken as they are (the square's region and the circle's together make the full square).

`taken(feature)` tells which regions a feature takes; `toggle(feature, n)` adds region n or takes it out,
the way a click on a region does while the feature's panel is open. The caller recomputes.
"""

import re

import FreeCAD
import Part

KINDS = {"PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Revolution", "PartDesign::Groove"}
SKETCH = "Sketcher::SketchObject"
_REGION = re.compile(r"(?:^|[.,])InternalFace(\d+)$")
_TOLERANCE = 1e-6


def region(name: str):
    """The region number a picked or stored name is ("InternalFace3" → 3; FreeCAD's long names end with
    it), or None if the name isn't a region."""
    found = _REGION.search(name or "")
    return int(found.group(1)) if found else None


def sketch_of(feature):
    """The sketch the feature takes its profile from, or None."""
    if getattr(feature, "TypeId", "") not in KINDS:
        return None
    profile = feature.Profile
    sketch = profile[0] if profile else None
    return sketch if getattr(sketch, "TypeId", "") == SKETCH else None


def _regions(sketch):
    shape = sketch.InternalShape
    return [] if shape.isNull() else shape.Faces


def _point_inside(face):
    """A point inside the face: its centre of mass can lie in a hole (a ring's), the middle of the
    biggest triangle FreeCAD splits it into can't."""
    points, triangles = face.tessellate(max(face.BoundBox.DiagonalLength / 100, 1e-3))

    def area(t):
        a, b, c = (points[i] for i in t)
        return (b - a).cross(c - a).Length

    a, b, c = (points[i] for i in max(triangles, key=area))
    return (a + b + c) * (1 / 3)


def _whole(sketch):
    """The regions the whole sketch takes: those inside the faces its closed shapes make, as Part Design
    makes them (FreeCAD's Bullseye face maker: a shape inside another is a hole, one inside that an island)."""
    shape = sketch.Shape.copy()
    shape.Placement = FreeCAD.Placement()  # in the sketch's own frame, as its regions are
    wires = [w for w in shape.Wires if w.isClosed()]
    if not wires:
        return set()
    faces = Part.makeFace(wires, "Part::FaceMakerBullseye")
    return {n for n, face in enumerate(_regions(sketch), 1)
            if faces.isInside(_point_inside(face), _TOLERANCE, True)}


def taken(feature):
    """The numbers of the regions the feature takes, or None when its profile isn't a sketch or names
    something other than regions (edges, a sketch's points)."""
    sketch = sketch_of(feature)
    if sketch is None:
        return None
    names = [name for name in feature.Profile[1] if name]  # Part Design's command stores [""] for none
    if not names:
        return _whole(sketch)
    numbers = {region(name) for name in names}
    return None if None in numbers else numbers


def toggle(feature, number) -> bool:
    """Adds region `number` of the feature's sketch, or takes it out; False if nothing changed: not a region
    of the sketch, a profile that isn't regions, or the last region (a profile with none is the whole
    sketch to FreeCAD)."""
    regions = taken(feature)
    if regions is None or not 1 <= number <= len(_regions(sketch_of(feature))):
        return False
    regions = regions ^ {number}
    if not regions:
        return False
    feature.Profile = (feature.Profile[0], [f"InternalFace{n}" for n in sorted(regions)])
    return True
