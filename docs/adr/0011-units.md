# 0011 — Units: the user's choice everywhere

- **Status:** accepted (2026-11-17: the user works in inches and asked for it; the details below follow from
  "I prefer to work in inches")
- **Date:** 2026-11-17

## Context

PLAN 3.1. FreeCAD stores every size in millimeters and shows it through a *unit schema* ("Standard" shows
`63.50 mm`, "Imperial decimal" `2.50 in`, "US customary" `2.50"` and `31.25 thou` for small sizes). There
are three places a schema comes from:

1. The preference `Units/UserSchema`: what new documents get, and what is used with no document open.
2. Each document's `UnitSystem` property, saved in the file. FreeCAD switches the whole app to it when the
   document becomes active, unless the preference `Units/IgnoreProjectSchema` is set.
3. `Gui::Document::slotChangePropertyEditor`, run when a property's *status* changes (shown, hidden,
   read-only; Part Design does it as features are edited), switches the app to the document's
   `UnitSystem` **without** checking `IgnoreProjectSchema`.

So in FreeCAD a file saved in millimeters shows in millimeters even for a user who picked inches, and
setting `IgnoreProjectSchema` alone doesn't hold: editing such a file flips the app back to millimeters.
Fusion keeps units per design as well, with a default for new designs.

## Decision

1. **One choice for the whole app:** ☰ › Units: *Follow Windows*, *Inches*, *Millimeters*
   (`studio/services/units.py`, `studio/shell/units.py`). *Follow Windows* (the default) uses Windows'
   region measurement system: US → inches, otherwise millimeters. Inches are FreeCAD's "Imperial decimal"
   (`2.50 in`, as Fusion shows them); millimeters are FreeCAD's standard schema.
2. **It holds everywhere,** also in files saved in other units: Studio writes `UserSchema`, sets
   `IgnoreProjectSchema`, and gives every open document the user's `UnitSystem`, including files opened
   later (on activation, which every opened file goes through). Then even (3) above switches to the user's
   units. A file just opened is not marked modified for it.
3. **No core change.** The one-line fix to (3) (check `IgnoreProjectSchema` there) would be an upstream fix
   worth offering; Studio doesn't need it.

## Consequences

- A file the user saves records the user's units in its `UnitSystem`. Sizes themselves are stored in
  millimeters either way, so nothing about the geometry changes.
- FreeCAD's own unit menu (the size label in the status bar) still exists. A schema picked there applies
  to the active document until it is activated again; Studio's choice comes back then. Studio's menu is
  the one to use.
- Sizes typed without a unit read in the user's units (`2` is 2 in when working in inches); a typed unit
  (`50 mm`) is converted.
- The visual baselines are taken in inches (the Units setting, not the machine's region).
