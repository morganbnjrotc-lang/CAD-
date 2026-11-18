# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click Fully Constrain (PLAN 3.4), like Fusion's AutoConstrain: adds what a sketch is missing so it
is fully defined, without moving anything.

Every constraint offered is one the drawing already satisfies, so solving moves nothing. They are tried in
the order a person would add them:

1. the shapes' own relations: joined points, points on the origin or an axis, horizontal and vertical
   lines, points on a line or circle, tangent joints, square corners;
2. sizes: circle diameters, arc radii and sweeps, line lengths, then the angle of slanted lines;
3. positions from the origin (horizontal and vertical distances).

Each is added, the sketch solved, and kept only if the solver accepts it (nothing redundant or
conflicting, nothing moved); it stops once nothing is free. A candidate is skipped without solving when the
shape it belongs to (geometry connected through shared points or points on curves) has nothing free left:
each solve covers the whole sketch, so tries are what the time goes to. All in one undo step. The user's own
constraints stay; a sketch the solver already reports problems in is left alone (`SketchHasProblems`).
Points count as the same within `TOLERANCE`: things drawn with the sketch tools' snapping are exact.
"""

import math
from dataclasses import dataclass, field

import FreeCAD
import Sketcher

TOLERANCE = 1e-6  # mm
H_AXIS, V_AXIS = -1, -2  # FreeCAD's geometry ids for the sketch's axes; the origin is (H_AXIS, START)
START, END, CENTER = 1, 2, 3
TRANSACTION = "Fully Constrain"


class SketchHasProblems(Exception):
    """The sketch has conflicting, redundant or malformed constraints, or doesn't solve."""


@dataclass
class Result:
    added: list = field(default_factory=list)  # (type, geometry ids) per constraint added
    dof_before: int = 0
    dof_after: int = 0


def fully_constrain(sketch) -> Result:
    if sketch.solve() != 0 or _problems(sketch):
        raise SketchHasProblems(
            "The sketch has conflicting or redundant constraints; fix those first."
        )
    result = Result(dof_before=sketch.DoF, dof_after=sketch.DoF)
    if sketch.DoF == 0:
        return result
    doc = sketch.Document
    doc.openTransaction(TRANSACTION)
    try:
        before = _points(sketch)
        groups = _groups(sketch)
        for constraint in _candidates(sketch):
            if sketch.DoF == 0:
                break
            if not _still_free(sketch, constraint, groups):
                continue
            if _try(sketch, constraint, before):
                result.added.append((constraint.Type, (constraint.First, constraint.Second)))
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    result.dof_after = sketch.DoF
    return result


def summary(result: Result) -> str:
    """One line for the status bar."""
    count = len(result.added)
    added = f"{count} constraint" + ("" if count == 1 else "s")
    if result.dof_after == 0:
        return f"Fully constrained: added {added}" if count else "Already fully constrained"
    left = f"{result.dof_after} degree" + (" of freedom is" if result.dof_after == 1 else "s of freedom are")
    return f"Added {added}; {left} left (ellipses and splines aren't sized automatically)"


# -- trying one -----------------------------------------------------------------------------------
def _problems(sketch) -> bool:
    return bool(sketch.ConflictingConstraints or sketch.RedundantConstraints
                or sketch.PartiallyRedundantConstraints or sketch.MalformedConstraints)


def _try(sketch, constraint, before) -> bool:
    dof = sketch.DoF
    index = sketch.addConstraint(constraint)
    status = sketch.solve()
    if status == 0 and not _problems(sketch) and sketch.DoF < dof and not _moved(sketch, before):
        return True
    sketch.delConstraint(index)
    sketch.solve()
    return False


def _moved(sketch, before) -> bool:
    return any((a - b).Length > TOLERANCE for a, b in zip(before.values(), _points(sketch).values()))


# -- the sketch's points --------------------------------------------------------------------------
def _positions(geometry):
    """The point positions a geometry has (FreeCAD's PointPos numbers)."""
    kind = geometry.TypeId
    if kind == "Part::GeomLineSegment":
        return (START, END)
    if kind == "Part::GeomArcOfCircle":
        return (CENTER, START, END)
    if kind in ("Part::GeomCircle", "Part::GeomEllipse"):
        return (CENTER,)
    if kind == "Part::GeomPoint":
        return (START,)
    return ()


def _points(sketch) -> dict:
    """{(geometry id, position): Vector} for every point of the sketch's own geometry."""
    points = {}
    for geo_id, geometry in enumerate(sketch.Geometry):
        for pos in _positions(geometry):
            points[(geo_id, pos)] = sketch.getPoint(geo_id, pos)
    return points


def _same(a, b) -> bool:
    return (a - b).Length <= TOLERANCE


# -- the candidates, in order -----------------------------------------------------------------------
def _candidates(sketch):
    geometry = list(sketch.Geometry)
    points = _points(sketch)
    lines = [i for i, g in enumerate(geometry) if g.TypeId == "Part::GeomLineSegment"]
    origin = FreeCAD.Vector(0, 0, 0)

    # 1. the shapes' own relations
    keys = list(points)
    joints = list(_joints(geometry, points))
    # joined ends; a smooth joint (line into arc, arc into arc) as FreeCAD's endpoint tangency, which
    # joins the ends too (an edge tangency on top of joined ends is degenerate for the solver)
    for a, b in joints:
        if _tangent_joint(geometry[a[0]], geometry[b[0]], points[a]):
            yield Sketcher.Constraint("Tangent", a[0], a[1], b[0], b[1])
        else:
            yield Sketcher.Constraint("Coincident", a[0], a[1], b[0], b[1])
    joined = {frozenset(pair) for pair in joints}
    for n, a in enumerate(keys):  # other points at the same place: shared centers, sketch points
        for b in keys[n + 1:]:
            if a[0] != b[0] and frozenset((a, b)) not in joined and _same(points[a], points[b]):
                yield Sketcher.Constraint("Coincident", a[0], a[1], b[0], b[1])
    for key in keys:
        if _same(points[key], origin):
            yield Sketcher.Constraint("Coincident", key[0], key[1], H_AXIS, START)
    for i in lines:
        d = _direction(geometry[i])
        if abs(d.y) <= TOLERANCE * max(1.0, d.Length):
            yield Sketcher.Constraint("Horizontal", i)
        elif abs(d.x) <= TOLERANCE * max(1.0, d.Length):
            yield Sketcher.Constraint("Vertical", i)
    for a, b in joints:
        if a[0] in lines and b[0] in lines and _square(geometry[a[0]], geometry[b[0]]):
            yield Sketcher.Constraint("Perpendicular", a[0], b[0])
    for key, point in points.items():
        for curve_id, curve in enumerate(geometry):
            if curve_id != key[0] and _on_curve(curve, point) and not _at_end(curve, point):
                yield Sketcher.Constraint("PointOnObject", key[0], key[1], curve_id)
    for key, point in points.items():
        if abs(point.y) <= TOLERANCE and not _same(point, origin):
            yield Sketcher.Constraint("PointOnObject", key[0], key[1], H_AXIS)
        if abs(point.x) <= TOLERANCE and not _same(point, origin):
            yield Sketcher.Constraint("PointOnObject", key[0], key[1], V_AXIS)

    # 2. sizes
    for i, g in enumerate(geometry):
        if g.TypeId == "Part::GeomCircle":
            yield Sketcher.Constraint("Diameter", i, 2 * g.Radius)
        elif g.TypeId == "Part::GeomArcOfCircle":
            yield Sketcher.Constraint("Radius", i, g.Radius)
            yield Sketcher.Constraint("Angle", i, g.LastParameter - g.FirstParameter)
    for i in lines:
        yield Sketcher.Constraint("Distance", i, geometry[i].length())
    for i in lines:
        d = _direction(geometry[i])
        if not _axis_aligned(d):
            yield Sketcher.Constraint("Angle", i, math.atan2(d.y, d.x))

    # 3. positions from the origin: centers first, then the other points in drawing order
    ordered = sorted(keys, key=lambda k: (k[1] != CENTER, k[0], k[1]))
    for geo_id, pos in ordered:
        point = points[(geo_id, pos)]
        if point.x >= 0:
            yield Sketcher.Constraint("DistanceX", H_AXIS, START, geo_id, pos, point.x)
        else:
            yield Sketcher.Constraint("DistanceX", geo_id, pos, H_AXIS, START, -point.x)
        if point.y >= 0:
            yield Sketcher.Constraint("DistanceY", H_AXIS, START, geo_id, pos, point.y)
        else:
            yield Sketcher.Constraint("DistanceY", geo_id, pos, H_AXIS, START, -point.y)


# -- shapes: geometry connected through shared points, points on curves, or the user's constraints ------
def _groups(sketch) -> dict:
    """{geometry id: group id}; geometry in different groups shares no solver parameters."""
    geometry = list(sketch.Geometry)
    parent = list(range(len(geometry)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(a, b):
        if 0 <= a < len(parent) and 0 <= b < len(parent):
            parent[find(a)] = find(b)

    points = _points(sketch)
    keys = list(points)
    for n, a in enumerate(keys):
        for b in keys[n + 1:]:
            if _same(points[a], points[b]):
                join(a[0], b[0])
        for curve_id, curve in enumerate(geometry):
            if curve_id != a[0] and _on_curve(curve, points[a]):
                join(a[0], curve_id)
    for c in sketch.Constraints:
        join(c.First, c.Second)
        join(c.First, c.Third)
    return {i: find(i) for i in range(len(geometry))}


def _still_free(sketch, constraint, groups) -> bool:
    involved = {groups[g] for g in (constraint.First, constraint.Second) if g in groups}
    if not involved:
        return True
    free = {groups[g] for g, _pos in sketch.getGeometryWithDependentParameters() if g in groups}
    return bool(involved & free)


# -- geometry tests -----------------------------------------------------------------------------------
def _axis_aligned(d) -> bool:
    return abs(d.x) <= TOLERANCE * max(1.0, d.Length) or abs(d.y) <= TOLERANCE * max(1.0, d.Length)


def _direction(line):
    return line.EndPoint - line.StartPoint


def _on_curve(curve, point) -> bool:
    kind = curve.TypeId
    if kind == "Part::GeomLineSegment":
        d = _direction(curve)
        length = d.Length
        if length <= TOLERANCE:
            return False
        v = point - curve.StartPoint
        along = v.dot(d) / length
        across = abs(v.x * d.y - v.y * d.x) / length
        return across <= TOLERANCE and -TOLERANCE <= along <= length + TOLERANCE
    if kind in ("Part::GeomCircle", "Part::GeomArcOfCircle"):
        if abs((point - curve.Center).Length - curve.Radius) > TOLERANCE:
            return False
        if kind == "Part::GeomCircle":
            return True
        angle = math.atan2(point.y - curve.Center.y, point.x - curve.Center.x)
        first, last = curve.FirstParameter, curve.LastParameter
        while angle < first - 1e-9:
            angle += 2 * math.pi
        return angle <= last + 1e-9
    return False


def _at_end(curve, point) -> bool:
    ends = []
    if curve.TypeId in ("Part::GeomLineSegment", "Part::GeomArcOfCircle"):
        ends = [curve.StartPoint, curve.EndPoint]
    return any(_same(point, e) for e in ends)


def _joints(geometry, points):
    """Pairs of end points of different curves at the same place."""
    ends = [k for k in points if k[1] in (START, END) and geometry[k[0]].TypeId != "Part::GeomPoint"]
    for n, a in enumerate(ends):
        for b in ends[n + 1:]:
            if a[0] != b[0] and _same(points[a], points[b]):
                yield a, b


def _tangent_at(curve, point):
    """The curve's direction at one of its points (not normalized), or None."""
    if curve.TypeId == "Part::GeomLineSegment":
        return _direction(curve)
    if curve.TypeId == "Part::GeomArcOfCircle":
        r = point - curve.Center
        return FreeCAD.Vector(-r.y, r.x, 0)
    return None


def _tangent_joint(a, b, point) -> bool:
    if "Part::GeomArcOfCircle" not in (a.TypeId, b.TypeId):
        return False
    ta, tb = _tangent_at(a, point), _tangent_at(b, point)
    if ta is None or tb is None or ta.Length <= TOLERANCE or tb.Length <= TOLERANCE:
        return False
    return abs(ta.x * tb.y - ta.y * tb.x) / (ta.Length * tb.Length) <= 1e-7


def _square(a, b) -> bool:
    da, db = _direction(a), _direction(b)
    if da.Length <= TOLERANCE or db.Length <= TOLERANCE:
        return False
    axis_aligned = all(abs(d.x) <= TOLERANCE or abs(d.y) <= TOLERANCE for d in (da, db))
    return not axis_aligned and abs(da.dot(db)) / (da.Length * db.Length) <= 1e-7
