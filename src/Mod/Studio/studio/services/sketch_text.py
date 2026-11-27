# SPDX-License-Identifier: LGPL-2.1-or-later
"""Text in sketches, laid out by Studio (PLAN 4.1, docs/adr/0015).

A **text box** (`TextBox`): lines as typed, in a font named by family and style, its capitals `height` tall
whatever the word (FreeCAD's own Text stretches each word to its line), lines `spacing` times the font's line
spacing apart, aligned left, center or right and top, middle or bottom in a box `width` by `depth`.

In the sketch the letters' outlines (Part's `makeWireString`: FreeType, with kerning) are geometry held by a
sketch **Group** to its **frame**: a construction line along the box's bottom edge, from the box's corner.
The solver moves only the frame; the letters and the box's other three edges (construction) follow it rigidly,
scaled with its length. The frame carries the text's settings (a `GeometryStringExtension` named
`StudioText`), so a text is found from its geometry wherever it sits in the sketch's lists, and edited again:
an edit rebuilds the letters around the same frame, keeping the user's constraints on it.

Each change is one undo step of its own, or, with `step=False`, part of the caller's (a tool panel's preview:
FreeCAD counts an opened step as open only once something in it changed).
"""

import base64
import dataclasses
import json
import math
import os
import re
from dataclasses import dataclass

import FreeCAD
import Part
import Sketcher

SETTINGS = "StudioText"  # the frame's extension
CALIBRATION = 100.0  # the size the capitals are measured at
ALIGN = ("left", "center", "right")
VALIGN = ("top", "middle", "bottom")

V = FreeCAD.Vector


@dataclass(frozen=True)
class TextBox:
    text: str
    family: str
    style: str
    height: float  # the capitals', mm
    width: float  # the box's, mm: the frame's length
    depth: float  # the box's height, mm
    align: str = "left"
    valign: str = "top"
    spacing: float = 1.0  # times the font's line spacing
    fit: bool = False  # the box sized to the text (width and depth are then the text's)


_cap_scale = {}  # font file → the capitals' drawn height per unit of makeWireString's size


def _draw(line, font, size):
    folder, name = os.path.split(font.path)
    chars = Part.makeWireString(line, folder + "/", name, size)
    return [wire for char in chars for wire in char]


def _caps(font):
    """The capitals' height drawn at makeWireString's size 1: its size isn't the em or the capitals' height
    (FreeCAD scales by the font's line height and hints at a fixed size), so it is measured on a capital."""
    if font.path not in _cap_scale:
        for capital in "HIEX1":
            wires = _draw(capital, font, CALIBRATION)
            if wires:
                _cap_scale[font.path] = Part.Compound(wires).BoundBox.YLength / CALIBRATION
                break
        else:
            raise ValueError(f"{font.name} has no capitals to size text by")
    return _cap_scale[font.path]


def _geometry(edge):
    """`edge` as sketch geometry: a line segment or a B-spline."""
    curve = edge.Curve
    if isinstance(curve, (Part.Line, Part.LineSegment)):
        return Part.LineSegment(edge.Vertexes[0].Point, edge.Vertexes[-1].Point)
    if not isinstance(curve, Part.BSplineCurve):
        edge = edge.toNurbs().Edges[0]
        curve = edge.Curve
    spline = curve.copy()
    if edge.FirstParameter > spline.FirstParameter + 1e-12 or edge.LastParameter < spline.LastParameter - 1e-12:
        spline.segment(edge.FirstParameter, edge.LastParameter)
    return spline


def _pitch(box, font):
    """From one line's baseline to the next."""
    return box.height * font.line_spacing / font.cap_height * box.spacing


def _drawn(box, font):
    """Each line drawn, at the size giving the capitals the box's height: [(line number, wires, ink box)]."""
    size = box.height / _caps(font)
    drawn = []
    for i, line in enumerate(box.text.split("\n")):
        wires = _draw(line, font, size) if line.strip() else []
        if wires:
            drawn.append((i, wires, Part.Compound(wires).BoundBox))
    return drawn


def fit(box, font):
    """`box` sized to its text when it fits (`box.fit`): as wide as its widest line, as deep as from the
    capitals' top to the last line's baseline; an empty text, a square of the height."""
    if not box.fit:
        return box
    drawn = _drawn(box, font)
    lines = box.text.count("\n") + 1
    width = max(ink.XLength for _, _, ink in drawn) if drawn else box.height
    return dataclasses.replace(box, width=width, depth=box.height + (lines - 1) * _pitch(box, font))


def _letters(box, font):
    """The letters' sketch geometry, in the box's own coordinates (its corner at 0, 0, its width along x)."""
    cap = box.height
    pitch = _pitch(box, font)
    last = box.text.count("\n") * pitch
    first = {"top": box.depth - cap, "bottom": last, "middle": (box.depth - cap + last) / 2}[box.valign]
    letters = []
    for i, wires, ink in _drawn(box, font):
        dx = {"left": -ink.XMin, "center": box.width / 2 - (ink.XMin + ink.XMax) / 2,
              "right": box.width - ink.XMax}[box.align]
        for wire in wires:
            wire = wire.copy()
            wire.translate(V(dx, first - i * pitch, 0))
            letters += [_geometry(e) for e in wire.Edges if e.Length > 1e-9]
    return letters


def _box_edges(box):
    w, d = box.width, box.depth
    return [Part.LineSegment(V(0, 0, 0), V(0, d, 0)), Part.LineSegment(V(0, d, 0), V(w, d, 0)),
            Part.LineSegment(V(w, 0, 0), V(w, d, 0))]


def _encode(box):
    # base64: FreeCAD writes a geometry's text into the file without escaping it, and a quote, an ampersand or
    # an angle bracket there makes the whole sketch unreadable on reopen
    data = json.dumps(dataclasses.asdict(box), ensure_ascii=False)
    return base64.b64encode(data.encode("utf-8")).decode("ascii")


def _decode(value):
    data = json.loads(base64.b64decode(value).decode("utf-8"))
    names = {f.name for f in dataclasses.fields(TextBox)}
    return TextBox(**{k: v for k, v in data.items() if k in names})


def _placement(corner, angle):
    return FreeCAD.Placement(V(corner[0], corner[1], 0), FreeCAD.Rotation(V(0, 0, 1), angle))


def _check(box):
    if box.align not in ALIGN or box.valign not in VALIGN:
        raise ValueError(f"alignment {box.align}, {box.valign}: one of {ALIGN} and one of {VALIGN}")
    if box.height <= 0 or box.width <= 0 or box.depth <= 0 or box.spacing <= 0:
        raise ValueError("a text's height, box and spacing are more than zero")


def _members_for(sketch, frame, box, font, placement):
    """Adds the box's edges and the letters around `frame`, placed by `placement`, and the Group holding them."""
    matrix = placement.toMatrix()
    edges, letters = _box_edges(box), _letters(box, font)
    for geometry in edges + letters:
        geometry.transform(matrix)
    first = len(sketch.Geometry)
    sketch.addGeometry(edges, True)
    if letters:
        sketch.addGeometry(letters, False)
    ids = list(range(first, first + len(edges) + len(letters)))
    sketch.addConstraint(Sketcher.Constraint("Group", [x for g in [frame] + ids for x in (g, 0)]))


class _Step:
    """One undo step of its own, unless `step` is False (the caller's step, such as a tool panel's preview) or a
    step with changes is already open."""

    def __init__(self, sketch, name, step=True):
        self.doc, self.name, self.step = sketch.Document, name, step

    def __enter__(self):
        self.own = self.step and not self.doc.HasPendingTransaction
        if self.own:
            self.doc.openTransaction(self.name)

    def __exit__(self, kind, *_):
        if self.own:
            if kind is None:
                self.doc.commitTransaction()
            else:
                self.doc.abortTransaction()
        return False


def add(sketch, box, font, corner=(0.0, 0.0), angle=0.0, step=True):
    """Adds the text `box` in `font` with the box's corner at `corner` (sketch coordinates), turned `angle`
    degrees; returns its frame's index."""
    _check(box)
    box = fit(box, font)
    placement = _placement(corner, angle)
    with _Step(sketch, "Text", step):
        line = Part.LineSegment(V(0, 0, 0), V(box.width, 0, 0))
        line.transform(placement.toMatrix())
        line.setExtension(Part.GeometryStringExtension(_encode(box), SETTINGS))
        frame = sketch.addGeometry(line, True)
        _members_for(sketch, frame, box, font, placement)
    return frame


def frames(sketch):
    """The frames of the sketch's texts, in order."""
    return [i for i, g in enumerate(sketch.Geometry) if g.hasExtensionOfName(SETTINGS)]


_ELEMENTS = re.compile(r'ElementIds="([^"]*)"')


def members(sketch, frame):
    """The geometry `frame` holds: the box's other edges and the letters."""
    for constraint in sketch.Constraints:
        if constraint.Type != "Group":
            continue
        found = _ELEMENTS.search(constraint.Content)
        ids = [int(i) for i in found.group(1).split()] if found else []
        if ids and ids[0] == frame:
            return ids[1:]
    return []


def read(sketch, frame):
    """The text at `frame`, sized as it is now (a frame made longer makes it bigger), or None: not a text."""
    line = sketch.Geometry[frame]
    if not line.hasExtensionOfName(SETTINGS):
        return None
    box = _decode(line.getExtensionOfName(SETTINGS).Value)
    scale = line.length() / box.width
    if abs(scale - 1) < 1e-9:
        return box
    return dataclasses.replace(box, height=box.height * scale, width=box.width * scale, depth=box.depth * scale)


def edit(sketch, frame, box, font, step=True):
    """Gives the text at `frame` the settings `box`, at the same place and angle, its frame `box.width` long
    and keeping the constraints on it; returns the frame's index (it moves when letters stood before it)."""
    _check(box)
    box = fit(box, font)
    with _Step(sketch, "Edit Text", step):
        old = members(sketch, frame)
        if old:
            sketch.delGeometries(old)
            frame -= sum(1 for i in old if i < frame)
        geometry = sketch.Geometry
        line = geometry[frame]
        start = line.StartPoint
        angle = math.degrees(math.atan2(line.EndPoint.y - start.y, line.EndPoint.x - start.x))
        direction = (line.EndPoint - start).normalize()
        line.EndPoint = start + direction * box.width
        line.setExtension(Part.GeometryStringExtension(_encode(box), SETTINGS))
        sketch.Geometry = geometry
        _members_for(sketch, frame, box, font, _placement((start.x, start.y), angle))
    return frame


def remove(sketch, frame, step=True):
    """Deletes the text at `frame`: its letters, box and frame."""
    with _Step(sketch, "Delete Text", step):
        sketch.delGeometries(sorted(members(sketch, frame) + [frame]))
