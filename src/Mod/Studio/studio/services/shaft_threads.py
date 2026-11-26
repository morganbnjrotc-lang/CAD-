# SPDX-License-Identifier: LGPL-2.1-or-later
"""A Thread tool for round faces, like Fusion's (PLAN 3.20, docs/adr/0014).

`make(body, feature, face, units)` adds a Thread feature to the body for one of `feature`'s round faces. Its
size starts as the standard size whose major diameter is nearest the face's (`nearest`: the units'
standards first, then any within 2 %), from FreeCAD's own thread tables (`sizes`, read through a scratch
Hole, so the numbers are the Hole tool's).

The feature is Part Design's scripted cutting feature with `ThreadFeature` as its proxy:
- **cosmetic** (the start): the solid stays as it is; the app shows the face as threaded;
- **Modeled**: the thread's groove (ISO 68-1 / Unified basic profile, 60°: a P/8 crest, a P/4 root, 5H/8
  deep) swept along a helix and cut from the solid, kept within the face's own length (so it never cuts into
  a shoulder past it), full length or a Length from its end (Reversed: from the other end), LeftHanded on
  request; a Fit (mm, as the Fit box's) turns the shaft that much smaller across, looser for 3D printing.
The size's major diameter and pitch are kept on the feature, so a recompute needs no table.
"""

import math
from dataclasses import dataclass

import FreeCAD
import Part

STANDARDS = {
    "inches": ("UNC", "UNF", "UNEF", "ISOMetricProfile", "ISOMetricFineProfile"),
    "millimeters": ("ISOMetricProfile", "ISOMetricFineProfile", "UNC", "UNF", "UNEF"),
}
NAMES = {"UNC": "UNC, US coarse", "UNF": "UNF, US fine", "UNEF": "UNEF, US extra fine",
         "ISOMetricProfile": "ISO metric", "ISOMetricFineProfile": "ISO metric fine"}
CLOSE = 0.02  # a size within 2 % of the face's diameter fits it
# FreeCAD's Unified thread pitches, mm (FeatureHole.cpp's table: a Hole has no Python property for its
# pitch). ISO metric sizes carry theirs in their name ("M8x1.25").
UTS_PITCH = {
    "UNC": {"#1": 0.397, "#2": 0.454, "#3": 0.529, "#4": 0.635, "#5": 0.635, "#6": 0.794, "#8": 0.794, "#10": 1.058, "#12": 1.058, "1/4": 1.27, "5/16": 1.411, "3/8": 1.588, "7/16": 1.814, "1/2": 1.954, "9/16": 2.117, "5/8": 2.309, "3/4": 2.54, "7/8": 2.822, "1": 3.175, "1 1/8": 3.628, "1 1/4": 3.628, "1 3/8": 4.233, "1 1/2": 4.233, "1 3/4": 5.08, "2": 5.644, "2 1/4": 5.644, "2 1/2": 6.35, "2 3/4": 6.35, "3": 6.35, "3 1/4": 6.35, "3 1/2": 6.35, "3 3/4": 6.35, "4": 6.35},
    "UNF": {"#0": 0.317, "#1": 0.353, "#2": 0.397, "#3": 0.454, "#4": 0.529, "#5": 0.577, "#6": 0.635, "#8": 0.706, "#10": 0.794, "#12": 0.907, "1/4": 0.907, "5/16": 1.058, "3/8": 1.058, "7/16": 1.27, "1/2": 1.27, "9/16": 1.411, "5/8": 1.411, "3/4": 1.588, "7/8": 1.814, "1": 2.117, "1 1/8": 2.117, "1 3/16": 1.588, "1 1/4": 2.117, "1 3/8": 2.117, "1 1/2": 2.117},
    "UNEF": {"#12": 0.794, "1/4": 0.794, "5/16": 0.794, "3/8": 0.794, "7/16": 0.907, "1/2": 0.907, "9/16": 1.058, "5/8": 1.058, "11/16": 1.058, "3/4": 1.27, "13/16": 1.27, "7/8": 1.27, "15/16": 1.27, "1": 1.27, "1 1/16": 1.411, "1 1/8": 1.411, "1 1/4": 1.411, "1 5/16": 1.411, "1 3/8": 1.411, "1 7/16": 1.411, "1 1/2": 1.411, "1 9/16": 1.411, "1 5/8": 1.411, "1 11/16": 1.411},
}
GROUP = "Thread"


@dataclass(frozen=True)
class Size:
    name: str
    diameter: float  # major, mm
    pitch: float  # mm


_tables = {}


def standards(units):
    return STANDARDS.get(units, STANDARDS["millimeters"])


def sizes(standard):
    """The standard's sizes, as FreeCAD's Hole tool has them (read once through a scratch Hole)."""
    if standard not in _tables:
        doc = FreeCAD.newDocument("StudioThreadTables", "StudioThreadTables", True, True)
        try:
            hole = doc.addObject("PartDesign::Hole", "Hole")
            hole.ThreadType = standard
            table = []
            for name in hole.getEnumerationsOfProperty("ThreadSize"):
                hole.ThreadSize = name
                table.append(Size(name, hole.ThreadDiameter.Value, _pitch(standard, name)))
            _tables[standard] = tuple(table)
        finally:
            FreeCAD.closeDocument(doc.Name)
    return _tables[standard]


def _pitch(standard, name):
    if standard in UTS_PITCH:
        return UTS_PITCH[standard][name]
    return float(name.split("x")[1])  # "M8x1.25"


def size(standard, name):
    return next(s for s in sizes(standard) if s.name == name)


def nearest(diameter, units):
    """(standard, size name) for a round face `diameter` mm across."""
    best = None
    for standard in standards(units):
        candidate = min(sizes(standard), key=lambda s: abs(s.diameter - diameter))
        off = abs(candidate.diameter - diameter) / diameter
        if off <= CLOSE:
            return standard, candidate.name
        if best is None or off < best[0]:
            best = (off, standard, candidate.name)
    return best[1], best[2]


def round_face(feature, face):
    """The face `face` ("Face3") of `feature` if it is round (a cylinder's), else ValueError."""
    shape = feature.Shape.getElement(face)
    if shape.ShapeType != "Face" or shape.Surface.__class__.__name__ != "Cylinder":
        raise ValueError(f"{face} of {feature.Label} isn't round")
    return shape


def set_size(thread, standard, name):
    """Gives the thread a standard and size (and their diameter and pitch)."""
    chosen = size(standard, name)
    thread.ThreadType = standard
    thread.ThreadSize = [s.name for s in sizes(standard)]
    thread.ThreadSize = name
    thread.ThreadDiameter = chosen.diameter
    thread.ThreadPitch = chosen.pitch


def make(body, feature, face, units):
    """A Thread on `feature`'s round face `face`, its size picked from the face's diameter."""
    round_ = round_face(feature, face)
    thread = body.newObject("PartDesign::FeatureSubtractivePython", "Thread")
    ThreadFeature(thread)
    thread.Face = (feature, [face])
    standard, name = nearest(2 * round_.Surface.Radius, units)
    set_size(thread, standard, name)
    return thread


def span(thread, face):
    """Where along the face's axis the thread runs (from, to), in the face's own parameter: full length, or
    `Length` from its end (`Reversed`: from the other end)."""
    v0, v1 = face.ParameterRange[2:]
    length = v1 - v0 if thread.FullLength else min(thread.Length.Value, v1 - v0)
    return (v0, v0 + length) if thread.Reversed else (v1 - length, v1)


def groove(radius, pitch, start, end, left_handed=False, fit=0.0):
    """The cutting tool of a modeled thread on a shaft of `radius` around the Z axis, between `start` and
    `end` along it: the groove swept along a helix, with the shaft turned `fit` smaller across."""
    outer = radius - fit / 2  # the thread's major radius
    h = math.sqrt(3) / 2 * pitch  # the fundamental triangle's height
    root = outer - 5 * h / 8
    margin = 0.08 * pitch  # out past the surface, for a clean cut (a turn's groove stays clear of the next)
    side = 7 * pitch / 16 + margin * math.tan(math.radians(30))
    z0 = start - pitch  # one turn more at each end: the tool is trimmed to [start, end]
    mid = z0 + pitch / 2
    corners = [FreeCAD.Vector(radius + margin, 0, mid - side), FreeCAD.Vector(root, 0, mid - pitch / 8),
               FreeCAD.Vector(root, 0, mid + pitch / 8), FreeCAD.Vector(radius + margin, 0, mid + side)]
    profile = Part.makePolygon(corners + corners[:1])
    height = end - start + 2 * pitch
    helix = Part.makeHelix(pitch, height, radius, 0, left_handed)
    helix.translate(FreeCAD.Vector(0, 0, z0))
    sweep = Part.Wire(helix).makePipeShell([profile], True, True)
    tool = sweep
    if fit > 1e-9:
        # out past the groove's outside: surfaces that coincide make booleans fail
        sleeve = Part.makeCylinder(radius + 1.5 * margin, height).cut(Part.makeCylinder(outer, height))
        sleeve.translate(FreeCAD.Vector(0, 0, z0))
        tool = tool.fuse(sleeve)
    span = Part.makeCylinder(radius + 2 * margin, end - start)
    span.translate(FreeCAD.Vector(0, 0, start))
    return tool.common(span)


class ThreadFeature:
    """The proxy of a Thread feature (PartDesign::FeatureSubtractivePython)."""

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

        add("App::PropertyLinkSub", "Face", "The round face threaded")
        add("App::PropertyEnumeration", "ThreadType", "The thread's standard")
        obj.ThreadType = list(NAMES)
        add("App::PropertyEnumeration", "ThreadSize", "The thread's size in its standard")
        add("App::PropertyLength", "ThreadDiameter", "The size's major diameter")
        add("App::PropertyLength", "ThreadPitch", "The size's pitch")
        add("App::PropertyBool", "Modeled", "Cut the thread's groove (otherwise cosmetic: the solid as it is)", False)
        add("App::PropertyBool", "FullLength", "The face's whole length", True)
        add("App::PropertyLength", "Length", "How far from the face's end, when not full length", 10.0)
        add("App::PropertyBool", "Reversed", "From the face's other end", False)
        add("App::PropertyBool", "LeftHanded", "A left-handed thread", False)
        add("App::PropertyDistance", "Fit", "How much smaller across than standard (+ looser), for 3D printing", 0.0)
        for name in ("ThreadDiameter", "ThreadPitch"):
            obj.setEditorMode(name, 1)  # read-only: they follow the size

    def execute(self, obj):
        base = obj.BaseFeature.Shape.copy() if obj.BaseFeature is not None else Part.Shape()
        if not obj.Modeled:
            obj.AddSubShape = Part.Shape()
            obj.Shape = base
            return
        link, names = obj.Face
        face = round_face(link, names[0])
        surface = face.Surface
        start, end = span(obj, face)
        tool = groove(surface.Radius, obj.ThreadPitch.Value, start, end, obj.LeftHanded, obj.Fit.Value)
        tool.Placement = FreeCAD.Placement(surface.Center, FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), surface.Axis))
        obj.AddSubShape = tool
        obj.Shape = base.cut(tool)

    def onDocumentRestored(self, obj):
        self.add_properties(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None
