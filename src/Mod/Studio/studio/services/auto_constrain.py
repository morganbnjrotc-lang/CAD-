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
conflicting, nothing moved); it stops once nothing is free. Tries are what the time goes to, and a solve
covers the whole sketch: so each shape (geometry connected through shared points, points on curves or the
user's constraints, which shares no solver parameters with the rest) is tried on its own, on a scratch
sketch in a temporary hidden document holding only that shape and its constraints, and what it keeps is
added to the sketch at once (80 lines: 7.4 s tried in the sketch, well under a second this way). A shape
tied to outside geometry (external edges, which a scratch sketch doesn't have) is tried in the sketch
itself, skipped once it has nothing free left. All in one undo step. The user's own constraints stay; a
sketch the solver already reports problems in is left alone (`SketchHasProblems`). Points count as the
same within `TOLERANCE`: things drawn with the sketch tools' snapping are exact.
"""

import math
from dataclasses import dataclass, field

import FreeCAD
import Sketcher

TOLERANCE = 1e-6  # mm
H_AXIS, V_AXIS = -1, -2  # FreeCAD's geometry ids for the sketch's axes; the origin is (H_AXIS, START)
EXTERNAL_LAST, GEO_UNDEF = -3, -2000  # outside geometry has ids -3 and below; -2000 is "none"
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
        by_shape, in_sketch = _by_shape(sketch, groups, _candidates(sketch))
        kept = _tried_alone(sketch, groups, by_shape)
        if kept:
            first = len(sketch.Constraints)
            sketch.addConstraint(kept)  # solves once
            if sketch.solve() != 0 or _problems(sketch) or _moved(sketch, before):  # not expected: try in the sketch
                for index in reversed(range(first, len(sketch.Constraints))):
                    sketch.delConstraint(index)
                sketch.solve()
                in_sketch = [c for shape in by_shape.values() for c in shape] + in_sketch
                kept = []
        kept += _tried_in(sketch, groups, in_sketch, before)
        result.added = [(c.Type, (c.First, c.Second)) for c in kept]
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


# -- trying them, shape by shape ---------------------------------------------------------------------
def _shape_of(constraint, groups):
    return next((groups[g] for g in (constraint.First, constraint.Second) if g in groups), None)


def _outside(constraint) -> bool:
    """Whether a constraint involves outside (external) geometry: ids -3 and below."""
    return any(EXTERNAL_LAST >= g > GEO_UNDEF for g in (constraint.First, constraint.Second, constraint.Third))


def _by_shape(sketch, groups, candidates):
    """({shape: its candidates, in order}, the candidates to try in the sketch itself: those of shapes tied
    to outside geometry)."""
    tied = {groups[g] for c in sketch.Constraints if _outside(c) for g in (c.First, c.Second, c.Third) if g in groups}
    by_shape, in_sketch = {}, []
    for constraint in candidates:
        shape = _shape_of(constraint, groups)
        if shape is None or shape in tied:
            in_sketch.append(constraint)
        else:
            by_shape.setdefault(shape, []).append(constraint)
    return by_shape, in_sketch


def _renumbered(constraint, ids):
    """`constraint` with its geometry ids (not the axes, origin or outside geometry) changed through `ids`."""
    for attr in ("First", "Second", "Third"):
        g = getattr(constraint, attr)
        if g >= 0:
            setattr(constraint, attr, ids[g])
    return constraint


def _tried_alone(sketch, groups, by_shape) -> list:
    """The candidates kept, each shape tried on a scratch sketch holding only it (with the sketch's ids)."""
    if not by_shape:
        return []
    geometry = list(sketch.Geometry)
    constraints = list(sketch.Constraints)
    kept = []
    scratch = _Scratch()
    try:
        for shape, candidates in by_shape.items():
            members = [g for g in range(len(geometry)) if groups[g] == shape]
            local = {g: n for n, g in enumerate(members)}
            back = {n: g for g, n in local.items()}
            scratch.load([geometry[g] for g in members], [sketch.getConstruction(g) for g in members],
                         [_renumbered(c, local) for c in constraints if _shape_of(c, groups) == shape])
            for constraint in scratch.keep([_renumbered(c, local) for c in candidates]):
                kept.append(_renumbered(constraint, back))
    finally:
        scratch.close()
    return kept


class _Scratch:
    """A sketch in a temporary hidden document (not in the model tree, nothing to undo), one shape at a time."""

    def __init__(self):
        self.doc = FreeCAD.newDocument("StudioFullyConstrain", "Fully Constrain", True, True)
        self.doc.UndoMode = 0
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Scratch")

    def load(self, geometry, construction, constraints):
        sketch = self.sketch
        sketch.deleteAllGeometry()
        for g, c in zip(geometry, construction):
            sketch.addGeometry(g, c)
        if constraints:
            sketch.addConstraint(constraints)
        sketch.solve()

    def keep(self, candidates) -> list:
        sketch = self.sketch
        before = _points(sketch)
        kept = []
        for constraint in candidates:
            if sketch.DoF == 0:
                break
            if _try(sketch, constraint, before):
                kept.append(constraint)
        return kept

    def close(self):
        FreeCAD.closeDocument(self.doc.Name)


def _tried_in(sketch, groups, candidates, before) -> list:
    """The candidates kept, tried in the sketch itself; one is skipped without solving when its shape has
    nothing free left."""
    kept = []
    for constraint in candidates:
        if sketch.DoF == 0:
            break
        if not _still_free(sketch, constraint, groups):
            continue
        if _try(sketch, constraint, before):
            kept.append(constraint)
    return kept


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
    same_place = _same_place_pairs(points)
    joints = list(_joints(geometry, same_place))
    # joined ends; a smooth joint (line into arc, arc into arc) as FreeCAD's endpoint tangency, which
    # joins the ends too (an edge tangency on top of joined ends is degenerate for the solver)
    for a, b in joints:
        if _tangent_joint(geometry[a[0]], geometry[b[0]], points[a]):
            yield Sketcher.Constraint("Tangent", a[0], a[1], b[0], b[1])
        else:
            yield Sketcher.Constraint("Coincident", a[0], a[1], b[0], b[1])
    joined = {frozenset(pair) for pair in joints}
    for a, b in same_place:  # other points at the same place: shared centers, sketch points
        if a[0] != b[0] and frozenset((a, b)) not in joined:
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
    reaches = [_reach(g) for g in geometry]
    for key, point in points.items():
        for curve_id in _curves_at(reaches, point):
            if curve_id != key[0] and not _is_end(reaches[curve_id], point):
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
    for a, b in _same_place_pairs(points):
        join(a[0], b[0])
    reaches = [_reach(g) for g in geometry]
    for key, point in points.items():
        for curve_id in _curves_at(reaches, point):
            join(key[0], curve_id)
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


# Points against curves, many times over in a big sketch: each curve's reach in plain numbers, read from
# FreeCAD's geometry once (each read makes new objects), with a box to rule most points out quickly.
@dataclass(frozen=True)
class _Reach:
    box: tuple  # (x min, y min, x max, y max), TOLERANCE added
    line: tuple = ()  # (start x, start y, dx, dy, length)
    circle: tuple = ()  # (center x, center y, radius)
    arc: tuple = ()  # (first parameter, last parameter)
    ends: tuple = ()  # ((x, y), ...)


def _reach(curve):
    """What `curve` covers, or None for a curve no point is tested against (points, ellipses, splines)."""
    kind = curve.TypeId
    t = TOLERANCE
    if kind == "Part::GeomLineSegment":
        a, b = curve.StartPoint, curve.EndPoint
        dx, dy = b.x - a.x, b.y - a.y
        length = math.hypot(dx, dy)
        if length <= t:
            return None
        return _Reach((min(a.x, b.x) - t, min(a.y, b.y) - t, max(a.x, b.x) + t, max(a.y, b.y) + t),
                      line=(a.x, a.y, dx, dy, length), ends=((a.x, a.y), (b.x, b.y)))
    if kind in ("Part::GeomCircle", "Part::GeomArcOfCircle"):
        c, radius = curve.Center, curve.Radius
        box = (c.x - radius - t, c.y - radius - t, c.x + radius + t, c.y + radius + t)
        if kind == "Part::GeomCircle":
            return _Reach(box, circle=(c.x, c.y, radius))
        a, b = curve.StartPoint, curve.EndPoint
        return _Reach(box, circle=(c.x, c.y, radius), arc=(curve.FirstParameter, curve.LastParameter),
                      ends=((a.x, a.y), (b.x, b.y)))
    return None


def _on(reach, x, y) -> bool:
    """Whether the point (x, y) lies on the curve of `reach`."""
    x0, y0, x1, y1 = reach.box
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    if reach.line:
        sx, sy, dx, dy, length = reach.line
        vx, vy = x - sx, y - sy
        along = (vx * dx + vy * dy) / length
        across = abs(vx * dy - vy * dx) / length
        return across <= TOLERANCE and -TOLERANCE <= along <= length + TOLERANCE
    cx, cy, radius = reach.circle
    if abs(math.hypot(x - cx, y - cy) - radius) > TOLERANCE:
        return False
    if not reach.arc:
        return True
    first, last = reach.arc
    angle = math.atan2(y - cy, x - cx)
    while angle < first - 1e-9:
        angle += 2 * math.pi
    return angle <= last + 1e-9


def _curves_at(reaches, point):
    """The ids of the curves `point` lies on."""
    x, y = point.x, point.y
    return [i for i, reach in enumerate(reaches) if reach is not None and _on(reach, x, y)]


def _is_end(reach, point) -> bool:
    return any(math.hypot(point.x - ex, point.y - ey) <= TOLERANCE for ex, ey in reach.ends)


def _same_place_pairs(points):
    """Pairs (a, b) of the points' keys at the same place, a before b in `points`' order, in that order: a
    sweep along x instead of every pair (the time went there in big sketches)."""
    keys = list(points)
    order = {k: n for n, k in enumerate(keys)}
    xy = {k: (points[k].x, points[k].y) for k in keys}
    by_x = sorted(keys, key=lambda k: xy[k][0])
    pairs = []
    for n, a in enumerate(by_x):
        ax, ay = xy[a]
        for b in by_x[n + 1:]:
            bx, by = xy[b]
            if bx - ax > TOLERANCE:
                break
            if math.hypot(ax - bx, ay - by) <= TOLERANCE:
                pairs.append((a, b) if order[a] < order[b] else (b, a))
    pairs.sort(key=lambda pair: (order[pair[0]], order[pair[1]]))
    return pairs


def _joints(geometry, same_place):
    """Pairs of end points of different curves at the same place (from `_same_place_pairs`)."""
    def end(key):
        return key[1] in (START, END) and geometry[key[0]].TypeId != "Part::GeomPoint"

    for a, b in same_place:
        if a[0] != b[0] and end(a) and end(b):
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
