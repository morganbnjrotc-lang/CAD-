# 0014 — A Thread tool for round faces, like Fusion's

- **Status:** accepted (2026-11-26: the user asked "is adding threads to a cylinder an option" and picked "like
  Fusion": cosmetic by default, a Modeled choice, threads modeled on export, the Fit box works on them)
- **Date:** 2026-11-26

## Context

FreeCAD threads only holes (Part Design's Hole: cosmetic, shown with a thread texture, or modeled). A shaft,
a bolt or a screw-on cap's outside has no thread tool; addons (Fasteners, ThreadProfile) do it differently each.
Fusion's Thread: click a round face, the size is picked from its diameter, cosmetic unless Modeled is ticked,
full length or a length from the face's end, right or left handed, internal faces too. Studio already models a
hole's cosmetic threads on export (PLAN 3.9) and offers a Fit box (an allowance for 3D printing) on a threaded
hole.

## Decision

1. **A Part Design feature in the body**, Studio's own (`PartDesign::FeatureSubtractivePython` with a Studio
   proxy), named Thread in the model tree. It refers to the round face it threads (a link to the feature and
   the face, which FreeCAD's naming keeps through edits where it can).
2. **The size comes from the face**: the standard size whose major diameter is nearest the face's diameter, in
   the units' standard first (inches: UNC, then UNF, UNEF; millimeters: ISO metric, then fine), from FreeCAD's
   own thread tables (read through a scratch Hole: the same numbers as the Hole tool). The user can pick
   another standard or size.
3. **Cosmetic by default**: the solid doesn't change; the face shows FreeCAD's thread texture, as a cosmetic
   hole thread does. **Modeled** cuts the thread's groove (ISO 68-1 / Unified profile, 60°) along a helix
   from the face's end, full length or a length; left handed on request. The thread is **its size's**: when
   the user picks a size smaller than the face (a 0.56 in stem threaded 1/2-13, to screw into a 1/2-13 hole),
   the face is turned down to the size's major diameter along the thread, as on a lathe; the rest of the face
   stays. A modeled thread whose cut takes nothing is an error, never a smooth face passed off as threaded.
4. **Export models it** (with the holes' threads, PLAN 3.9), and **the Fit box** applies: a positive fit makes
   an outside thread smaller (looser), as it makes a hole bigger.

## Consequences

- One more Studio feature type in documents: opening such a file needs Studio (the proxy), as any Python
  feature does; without it the feature shows its last shape.
- Modeled threads are slow to compute and heavy to draw; cosmetic is the default for that reason.
- Inside faces (holes) keep the Hole tool's threads for now.
- The groove is swept along FreeCAD's long helix (one edge a turn), as the Hole tool's modeled threads are: a single approximated helix (Part.makeHelix) made sweeps whose cut silently took nothing, or failed, for about half the standard sizes and lengths (found 2026-11-26, the user's first export).
