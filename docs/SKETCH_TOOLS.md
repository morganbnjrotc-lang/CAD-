# Ways to draw: Studio, Fusion, Inventor, AutoCAD

The comparison behind PLAN 3.12 (2026-11-18). The user asked for more than one way to draw each shape:
"the rectangle only has one selection, the classic corners pull… like what Fusion and Inventor have".
Names are Fusion's where it has the way. Sources: Autodesk's Fusion and Inventor help (sketch create
tools, slots, polygons, rectangles), AutoCAD's CIRCLE, ARC and POLYGON commands, and FreeCAD's sketcher
in this tree (`src/Mod/Sketcher/Gui`, `DrawSketchHandler*.h`).

**On Studio's toolbar** means the way is in the drop-down under the tool (the button draws the way picked
last). Everything FreeCAD's sketcher has is also in Search tools. **Added** means Studio added the way to
FreeCAD's sketch tools (2026-11-19, approved by the user; [CORE_PATCHES.md](CORE_PATCHES.md)).

| Shape | Fusion | Inventor | AutoCAD | On Studio's toolbar | Missing |
|---|---|---|---|---|---|
| Line | Line; drag off an end for a tangent arc | Line; drag off an end for an arc | Line, Polyline | Line; Lines and Arcs (M switches the next segment to an arc); Center Point Line (added: SolidWorks' Midpoint Line, which the user asked for) | — |
| Rectangle | 2-Point, 3-Point, Center | Two Point, Three Point, Two Point Center, Three Point Center | Rectangle (two corners; chamfered, filleted) | 2-Point, Center, 3-Point, 3-Point Center, Rounded | — |
| Circle | Center Diameter, 2-Point, 3-Point, 2-Tangent, 3-Tangent | Center Point, Tangent (to three lines) | Center Radius, Center Diameter, 2-Point, 3-Point, Tan Tan Radius, Tan Tan Tan | Center Diameter, 3-Point; 2-Point, 2-Tangent, 3-Tangent (added) | — |
| Arc | 3-Point, Center Point, Tangent | Three Point, Center Point, Tangent | 11 ways (start, center, end, angle, length, radius, direction; Continue) | Center Point, 3-Point; Tangent (added: from the end of a line or arc) | — |
| Polygon | Circumscribed, Inscribed, Edge | Inscribed, Circumscribed | Inscribed, Circumscribed, Edge | Inscribed (any number of sides); Triangle, Square, Hexagon; Circumscribed and Edge (added; six sides to start, U and J change it) | — |
| Slot | Center to Center, Overall, Center Point, Three Point Arc, Center Point Arc | the same five | — | Center to Center, Center Point Arc; Overall and Center Point (added) | **Three Point Arc** |
| Spline | Fit Point, Control Point | Interpolation, Control Vertex; Equation Curve, Bridge Curve | Fit, Control Vertices | Fit Point, Control Point | Equation and bridge curves (later) |
| Ellipse | Ellipse (center, axes) | Ellipse | Center, Axis End, Elliptical Arc | Center, 3-Point, Elliptical Arc | — |
| Conic | Conic Curve (ends, apex, rho) | — | — | (hyperbolic and parabolic arcs, in Search tools) | Conic Curve (later) |
| Point, Text | Point, Text | Point, Text | Point, Text | Point, Text | — |

Editing tools (Trim, Extend, Split, Offset, Fillet and Chamfer, Mirror, patterns, Move, Rotate, Scale,
projecting edges) are all in FreeCAD's sketcher; they aren't on Studio's sketch toolbar yet.

## How the added ways work

FreeCAD's sketch tools are built on a framework of drawing methods: each tool has a list of methods (its
panel's first list, which the M key steps through) and size boxes that take typed values. The added ways
are new methods of the existing tools, so they have size boxes, automatic constraints and FreeCAD's
undo like the others. Studio's own module can't build them: the framework's panel class
(`SketcherToolDefaultWidget`) isn't exported from FreeCAD's Sketcher library.

- **Center Point Line:** a construction point at the middle; the line's ends are symmetric about it. A
  typed length is the whole line.
- **2-Point Circle:** the clicks are a diameter's ends; a typed size is the diameter (or the radius, if
  FreeCAD's preferences dimension circles by radius).
- **2-Tangent Circle:** pick two lines (or an axis), then where the circle sits: its center is on the line
  halfway between them, in the corner the pointer is in, nearest the pointer; a typed size sets it there.
  Two Tangent constraints hold it.
- **3-Tangent Circle:** pick three lines. Of the circles touching all three (a triangle's inscribed and
  escribed ones), it takes one touching each line within its segment, else the one nearest the pointer.
- **Tangent Arc:** the first click must be the end of a line or an arc; the arc carries on its direction
  and turns towards the second click. One Tangent constraint, end to end, holds it (and makes them meet).
  Typed: radius and sweep.
- **Circumscribed Polygon:** the second click is the middle of a side; a typed size is the distance from
  the center to it (half the size across the flats). FreeCAD's construction circle through the corners
  keeps the polygon regular; a second one, touching the side through the click, holds the size.
- **Edge Polygon:** two corners of one side, the polygon on the left going from the first (AutoCAD's
  way). Typed: the side's length and direction.
- **Overall Slot:** the clicks are the slot's ends; a construction centerline from end to end carries the
  overall length. **Center Point Slot:** the middle, then one end's center; a construction point in the
  middle, the arcs' centers symmetric about it.

Still missing: the Three Point Arc slot. Tangent circles touch lines only (as Fusion's); tangency to
circles and arcs could come later.
