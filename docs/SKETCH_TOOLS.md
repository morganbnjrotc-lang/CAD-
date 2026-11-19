# Ways to draw: Studio, Fusion, Inventor, AutoCAD

The comparison behind PLAN 3.12 (2026-11-18). The user asked for more than one way to draw each shape:
"the rectangle only has one selection, the classic corners pull… like what Fusion and Inventor have".
Names are Fusion's where it has the way. Sources: Autodesk's Fusion and Inventor help (sketch create
tools, slots, polygons, rectangles), AutoCAD's CIRCLE, ARC and POLYGON commands, and FreeCAD's sketcher
in this tree (`src/Mod/Sketcher/Gui`, `DrawSketchHandler*.h`).

**On Studio's toolbar** means the way is in the drop-down under the tool (the button draws the way picked
last). Everything FreeCAD's sketcher has is also in Search tools.

| Shape | Fusion | Inventor | AutoCAD | On Studio's toolbar (FreeCAD has it) | Missing |
|---|---|---|---|---|---|
| Line | Line; drag off an end for a tangent arc | Line; drag off an end for an arc | Line, Polyline | Line; Lines and Arcs (M switches the next segment to an arc) | — |
| Rectangle | 2-Point, 3-Point, Center | Two Point, Three Point, Two Point Center, Three Point Center | Rectangle (two corners; chamfered, filleted) | 2-Point, Center, 3-Point, 3-Point Center, Rounded | — |
| Circle | Center Diameter, 2-Point, 3-Point, 2-Tangent, 3-Tangent | Center Point, Tangent (to three lines) | Center Radius, Center Diameter, 2-Point, 3-Point, Tan Tan Radius, Tan Tan Tan | Center Diameter, 3-Point | **2-Point, 2-Tangent, 3-Tangent** |
| Arc | 3-Point, Center Point, Tangent | Three Point, Center Point, Tangent | 11 ways (start, center, end, angle, length, radius, direction; Continue) | Center Point, 3-Point; tangent arcs inside Lines and Arcs | **Tangent Arc** as its own way |
| Polygon | Circumscribed, Inscribed, Edge | Inscribed, Circumscribed | Inscribed, Circumscribed, Edge | Inscribed (any number of sides); Triangle, Square, Hexagon | **Circumscribed, Edge** |
| Slot | Center to Center, Overall, Center Point, Three Point Arc, Center Point Arc | the same five | — | Center to Center, Center Point Arc | **Overall, Center Point, Three Point Arc** |
| Spline | Fit Point, Control Point | Interpolation, Control Vertex; Equation Curve, Bridge Curve | Fit, Control Vertices | Fit Point, Control Point | Equation and bridge curves (later) |
| Ellipse | Ellipse (center, axes) | Ellipse | Center, Axis End, Elliptical Arc | Center, 3-Point, Elliptical Arc | — |
| Conic | Conic Curve (ends, apex, rho) | — | — | (hyperbolic and parabolic arcs, in Search tools) | Conic Curve (later) |
| Point, Text | Point, Text | Point, Text | Point, Text | Point, Text | — |

Editing tools (Trim, Extend, Split, Offset, Fillet and Chamfer, Mirror, patterns, Move, Rotate, Scale,
projecting edges) are all in FreeCAD's sketcher; they aren't on Studio's sketch toolbar yet.

## Building the missing ways

FreeCAD's sketch tools are built on a framework of drawing methods: each tool has a list of methods (its
panel's first list, which the M key steps through) and size boxes that take typed values. The missing
ways belong in that framework as new methods of the existing tools (Circle: 2-Point, 2-Tangent,
3-Tangent; Polygon: Circumscribed, Edge; Slot: Overall, Center Point; Arc Slot: Three Point Arc; Arc:
Tangent). Studio's own module can't build them there: the framework's panel class
(`SketcherToolDefaultWidget`) isn't exported from FreeCAD's Sketcher library, so a tool made outside it
would have no size boxes. Building them means editing FreeCAD's Sketcher (logged in CORE_PATCHES.md),
which waits for the user's go-ahead.
