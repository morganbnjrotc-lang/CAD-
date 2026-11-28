# 0016 — Emboss on a round face, like Fusion's

- **Status:** accepted (2026-11-27: Phase 4's "text on curved surfaces + extrude in or out", built Fusion's way
  as the user has picked for each tool so far; the user tried it on the sunflower's stem 2026-11-28: "great
  success")
- **Date:** 2026-11-27

## Context

The roadmap asks for sketches mapped onto and wrapped around faces, text on surfaces, extruded in or out
(README; PLAN 4.3, 4.4). FreeCAD has nothing for it (the Curves addon wraps, differently); Part Design's
features work on flat sketches only. Fusion's Emboss: pick sketch profiles (text too) and a face, a depth,
Emboss (raised) or Deboss (cut in), the profiles wrapped onto the face.

A cylinder is developable: it unrolls flat without stretching. Measured 2026-11-27 (headless): a sketch's
curves taken as B-splines, their poles mapped linearly from the sketch plane to the cylinder's unrolled
coordinates (around / radius, along the axis) and built as curves on the cylinder (`Geom2d` curves on the
surface) keep their lengths exactly (a 10 mm line, a circle's circumference, to 1e-6); the faces they bound,
thickened along the radius (`makeOffsetShape`), give exact volumes (a 10 mm square raised 1 mm on a 20 mm
radius: 102.5 mm³, cut: 97.5 mm³); text wraps and fuses into one solid.

## Decision

1. **A sketch on a plane along the face** (parallel to its axis: through it, tangent to it, or offset) is
   wrapped as seen along its normal, onto the side of the face it looks at; across the sketch becomes around
   the face, along it stays along the axis. A plane crossing the axis is refused with a message.
2. **Exact wrap**, as measured: poles mapped, curves built on the cylinder, closed shapes with their holes
   (a letter O stays a ring) as faces on it, thickened along the radius.
3. **Part Design features in the body**, Studio's own: **Emboss** (`PartDesign::FeatureAdditivePython`, adds)
   and **Deboss** (`…SubtractivePython`, cuts), with the sketch (`Profile`), the face (`Face`) and the
   `Depth`. Part Design's patterns add or cut a feature's shape by its kind, so the kind follows the choice:
   switching Emboss/Deboss replaces the feature in its place.
4. **Off the face is an error**: raised shapes that don't join the body, or a cut that takes nothing, fail the
   feature with a message, never a body that looks embossed and isn't.
5. **The tool** (`Studio_Emboss`, on the toolbar for a sketch, and under Create): pick the sketch, then the
   round face (or both before); a panel with the depth and Emboss/Deboss, the result shown as it changes.
6. **Cones** (added 2026-11-28, PLAN 4.4): a cone unrolls into a slice of a ring, and no flat rectangle maps
   onto one keeping every length. Studio keeps what text needs: across the sketch becomes a **level circle**
   around the cone (a baseline stays level) and along it goes **up the cone's slope** (letters stand on the
   cone's lines), lengths kept up the slope and around the cone at the **sketch's middle height**; elsewhere
   lengths around scale with the cone's radius there (a shape a little wider toward the wide end). In the
   cone's own coordinates (angle, distance up the slope) that map is still linear, so the same exact pole
   mapping does it. Measured on a cone sloping 14°: a 10 mm square at mid-height (15 mm radius) raised 1 mm
   adds 100 · (1 + cos 14° / 30) mm³ to 1e-4, for a cone narrowing upward and one widening; the cylinder is the
   same map with no slope. Heights away from the middle land a little nearer it than in the sketch (8 mm up
   the slope rises 8 · cos 14° = 7.76 mm), since lengths up the slope are kept.
7. **Any other face is projected onto** (added 2026-11-28, PLAN 4.4): flat faces, domes, rounded edges and
   free-form shapes don't unroll. The sketch, from any plane, is projected along its normal onto the face, on
   the side it looks at (from the sketch's plane on); the face's patches inside the shapes' prism are thickened
   along the face's normal, as wrapped shapes are, so letters on a dome stand out of it rather than straight up,
   and shapes stretch where the face slopes away from the sketch (1 / cos of the angle on a flat face). The kind
   of face decides: cylinders and cones wrap, the rest project, with no setting; the panel says which. Measured
   (headless, exact): a 10 mm square raised 1 mm on a flat face adds 100 mm³, from a plane tilted 30° 115.47 mm³;
   a 6 mm circle over a 20 mm dome's top, the shell over the cap it covers (2π/3 (1 − cos θ)(21³ − 20³), raised;
   20³ − 19³, cut). OCC gives a patch around a sphere's pole thickened as a closed, inside-out shell instead
   of a solid; made a solid, it is oriented and exact. Before, a flat face was refused ("isn't round"); now it is
   projected onto, and only what isn't a face is refused.
8. **A pick on the emboss itself** (or on a feature after it) while its panel is open picks the face under the
   point on the shape the emboss is made on: the emboss never points at itself, which would loop.

## Consequences

- Cylinders and cones are wrapped (lengths kept), every other face projected onto (stretched where it slopes away).
- Another Studio feature type in documents: opening one needs Studio (the proxies), as any Python feature does.
- Curved outlines are thickened by OCC with approximated sides: volumes within ~0.01 %, not to the last digit.
