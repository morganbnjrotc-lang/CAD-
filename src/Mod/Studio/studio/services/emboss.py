# SPDX-License-Identifier: LGPL-2.1-or-later
"""Emboss on a round face, like Fusion's (PLAN 4.3, docs/adr/0016).

A sketch drawn on a plane along a round face (parallel to its axis: through it, tangent to it or offset from
it) is wrapped onto the face as the face would unroll: across the sketch becomes around the face, along it
stays along the axis. A cylinder unrolls without stretching, so every length in the sketch is kept on the face,
slanted ones too. The sketch is wrapped as seen along its normal, onto the side of the face it looks at; its
closed shapes (text's letters with their holes) are raised from the face by a depth (an **Emboss**, adding)
or cut into it (a **Deboss**, cutting), as a Part Design feature in the body.

How: each sketch curve, as a B-spline, has its poles mapped to the face's unrolled coordinates (around / radius,
along the axis): the map is linear on the sketch plane, so the curve on the face is exact. The wrapped faces
are thickened along the face's normal (outward for an emboss, inward for a deboss) and fused with the body or
cut from it. Raised material that doesn't join the body, or a cut that takes nothing, is an error: the sketch
is off the face.
"""

import math

import FreeCAD
import Part

V = FreeCAD.Vector
GROUP = "Emboss"
ADD, CUT = "PartDesign::FeatureAdditivePython", "PartDesign::FeatureSubtractivePython"
NAMES = {ADD: "Emboss", CUT: "Deboss"}


def round_face(feature, face):
    """The face `face` ("Face3") of `feature` if it is round (a cylinder's), else ValueError."""
    shape = feature.Shape.getElement(face)
    if shape.ShapeType != "Face" or shape.Surface.__class__.__name__ != "Cylinder":
        raise ValueError(f"{face} of {feature.Label} isn't round")
    return shape


def _body_of(obj):
    parent = obj.getParentGeoFeatureGroup() if hasattr(obj, "getParentGeoFeatureGroup") else None
    return parent


class _Unrolling:
    """The face's unrolled coordinates for a sketch: (around, along) of a point, and back to the face."""

    def __init__(self, profile, feature, face):
        surface = round_face(feature, face).Surface
        self.radius = surface.Radius
        self.origin = V(surface.Center)
        self.axis = V(surface.Axis).normalize()
        # the sketch's own coordinates, in the coordinates of the face's feature (its body)
        body = _body_of(feature)
        inverse = body.getGlobalPlacement().inverse() if body is not None else FreeCAD.Placement()
        self.sketch = inverse.multiply(profile.getGlobalPlacement())
        normal = self.sketch.Rotation.multVec(V(0, 0, 1))
        if abs(normal.dot(self.axis)) > 1e-6:
            raise ValueError("Draw the sketch on a plane along the round face (through its axis, tangent to it "
                             "or offset from it): this one crosses it")
        self.facing = (normal - self.axis * normal.dot(self.axis)).normalize()  # where the wrap lands
        self.around = self.axis.cross(self.facing)
        frame = FreeCAD.Matrix(self.facing.x, self.around.x, self.axis.x, self.origin.x,
                               self.facing.y, self.around.y, self.axis.y, self.origin.y,
                               self.facing.z, self.around.z, self.axis.z, self.origin.z,
                               0, 0, 0, 1)
        self.placement = FreeCAD.Placement(frame)  # the unrolled cylinder's (axis Z, angle 0 on X) into place
        self.surface = Part.Cylinder()
        self.surface.Radius = self.radius

    def uv(self, local):
        """A point of the sketch (its own coordinates) as (angle, along the axis) on the face."""
        point = self.sketch.multVec(local) - self.origin
        return FreeCAD.Base.Vector2d(point.dot(self.around) / self.radius, point.dot(self.axis))

    def edge(self, edge):
        """`edge` of the sketch (its own coordinates) wrapped onto the unrolled cylinder."""
        curve = edge.Curve
        if isinstance(curve, Part.BSplineCurve):
            spline = curve.copy()
            if edge.FirstParameter > spline.FirstParameter + 1e-12 or edge.LastParameter < spline.LastParameter - 1e-12:
                spline.segment(edge.FirstParameter, edge.LastParameter)
        else:
            spline = curve.toBSpline(edge.FirstParameter, edge.LastParameter)
        wrapped = Part.Geom2d.BSplineCurve2d()
        wrapped.buildFromPolesMultsKnots([self.uv(p) for p in spline.getPoles()], spline.getMultiplicities(),
                                         spline.getKnots(), spline.isPeriodic(), spline.Degree,
                                         spline.getWeights() if spline.isRational() else None)
        return wrapped.toShape(self.surface, wrapped.FirstParameter, wrapped.LastParameter)

    def wire(self, wire):
        return Part.Wire(Part.__sortEdges__([self.edge(e) for e in wire.Edges]))


def _flat(profile):
    """The sketch's shape in its own coordinates."""
    shape = profile.Shape.copy()
    shape.Placement = FreeCAD.Placement()
    return shape


def wrapped_edges(profile, feature, face):
    """The sketch's edges wrapped onto `feature`'s round face `face`, in the feature's coordinates."""
    unrolling = _Unrolling(profile, feature, face)
    edges = []
    for edge in _flat(profile).Edges:
        wrapped = unrolling.edge(edge)
        wrapped.Placement = unrolling.placement
        edges.append(wrapped)
    return edges


def _face_on(unrolling, flat_wire):
    """The region a closed sketch wire bounds, on the unrolled cylinder (as large as it is flat)."""
    area = Part.Face(flat_wire).Area
    wire = unrolling.wire(flat_wire)
    for candidate in (wire, Part.Wire(list(reversed(wire.Edges)))):
        face = Part.Face(unrolling.surface, candidate)
        if face.isValid() and abs(face.Area - area) <= 1e-4 * max(area, 1.0):
            return face
    raise RuntimeError("A shape of the sketch couldn't be wrapped onto the face")


def _thick(face, depth, outward):
    """`face` thickened `depth` along the cylinder's radius, outward or inward."""
    solid = face.makeOffsetShape(depth, 1e-6, fill=True)
    center = solid.CenterOfMass
    if (math.hypot(center.x, center.y) > face.Surface.Radius) != outward:
        solid = face.makeOffsetShape(-depth, 1e-6, fill=True)
    return solid


def tool(profile, feature, face, depth, cut=False):
    """The material an emboss adds (or a deboss cuts), in the feature's coordinates."""
    unrolling = _Unrolling(profile, feature, face)
    flat = _flat(profile)
    closed = [w for w in flat.Wires if w.isClosed()]
    if not closed:
        raise RuntimeError("The sketch has no closed shapes to emboss")
    regions = Part.makeFace(closed, "Part::FaceMakerBullseye")  # each with its holes (an O's middle)
    solids = []
    for region in regions.Faces:
        solid = _thick(_face_on(unrolling, region.OuterWire), depth, not cut)
        holes = [_thick(_face_on(unrolling, w), depth, not cut) for w in region.Wires if not w.isSame(region.OuterWire)]
        solids.append(solid.cut(holes) if holes else solid)
    shape = solids[0].fuse(solids[1:]) if len(solids) > 1 else solids[0]
    shape.Placement = unrolling.placement
    return shape


class EmbossFeature:
    """The proxy of an Emboss (PartDesign::FeatureAdditivePython) or Deboss (…SubtractivePython)."""

    def __init__(self, obj):
        obj.Proxy = self
        self.add_properties(obj)

    @staticmethod
    def add_properties(obj):
        def add(kind, name, doc, value=None):
            if not hasattr(obj, name):
                obj.addProperty(kind, name, GROUP, doc)
                if value is not None:
                    setattr(obj, name, value)

        add("App::PropertyLink", "Profile", "The sketch wrapped onto the face")
        add("App::PropertyLinkSub", "Face", "The round face")
        add("App::PropertyLength", "Depth", "How far the shapes stand out of the face, or are cut into it", 1.0)

    def execute(self, obj):
        base = obj.BaseFeature.Shape.copy() if obj.BaseFeature is not None else Part.Shape()
        link, names = obj.Face
        cut = obj.TypeId == CUT
        try:
            shape = tool(obj.Profile, link, names[0], obj.Depth.Value, cut)
            result = base.cut(shape) if cut else base.fuse(shape).removeSplitter()
        except Part.OCCError as e:
            raise RuntimeError(f"The emboss couldn't be made ({e})") from e
        if cut and base.Volume - result.Volume < 0.01 * shape.Volume:
            raise RuntimeError("Nothing was cut: the sketch is off the face")
        if not cut and len(result.Solids) > max(len(base.Solids), 1):
            raise RuntimeError("Some of the shapes stand apart: the sketch is off the face")
        obj.AddSubShape = shape
        obj.Shape = result

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make(body, profile, feature, face, depth=1.0, cut=False):
    """An Emboss (or with `cut`, a Deboss) of `profile` on `feature`'s round face `face`, `depth` deep."""
    round_face(feature, face)
    kind = CUT if cut else ADD
    emboss = body.newObject(kind, NAMES[kind])
    EmbossFeature(emboss)
    emboss.Profile = profile
    emboss.Face = (feature, [face])
    emboss.Depth = depth
    return emboss


def set_cut(emboss, cut):
    """The same emboss raising (`cut` False) or cutting: Part Design's features either add or cut, so it is
    replaced by one of the other kind, in its place in the body; returns it."""
    kind = CUT if cut else ADD
    if emboss.TypeId == kind:
        return emboss
    doc, body = emboss.Document, emboss.getParentGeoFeatureGroup()
    other = doc.addObject(kind, NAMES[kind])
    EmbossFeature(other)
    other.Profile, other.Face, other.Depth = emboss.Profile, emboss.Face, emboss.Depth
    was_tip = body.Tip == emboss
    body.insertObject(other, emboss, True)
    body.removeObject(emboss)
    doc.removeObject(emboss.Name)
    if was_tip:
        body.Tip = other
    return other
