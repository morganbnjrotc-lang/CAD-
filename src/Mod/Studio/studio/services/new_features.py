# SPDX-License-Identifier: LGPL-2.1-or-later
"""What a feature made in Studio starts as (PLAN 3.18).

**Names.** FreeCAD names a new Part Design feature after its type (Pad, Pad001, Groove…), and the model tree
shows that name. The toolbar calls the tools Extrude, Cut, Revolve Cut… (docs/adr/0009): a feature made now
gets that name too (`rename`), FreeCAD numbering the second one (Extrude001) as it does its own. Only when it
still has FreeCAD's own name: one given by a script, or by the user, stays; features read from a file keep
theirs (the user's pick, 2026-11-26). Features FreeCAD already names as the toolbar does (Fillet, Hole…) aren't
touched.

**Holes.** A new Part Design hole has no thread standard. It starts in the user's units' (the user's pick):
UNC 1/4 in inches, ISO metric M6x1.0 in millimeters (`start_hole`), still a plain drilled hole until the user
picks Tap drill or Threaded.
"""

import re

PLAIN = {
    "PartDesign::Pad": "Extrude",
    "PartDesign::Pocket": "Cut",
    "PartDesign::Revolution": "Revolve",
    "PartDesign::Groove": "Revolve Cut",
    "PartDesign::Thickness": "Shell",
    "PartDesign::AdditivePipe": "Sweep",
    "PartDesign::SubtractivePipe": "Sweep Cut",
    "PartDesign::AdditiveLoft": "Loft",
    "PartDesign::SubtractiveLoft": "Loft Cut",
    "PartDesign::AdditiveHelix": "Helix",
    "PartDesign::SubtractiveHelix": "Helix Cut",
    "PartDesign::Boolean": "Combine",
    "PartDesign::LinearPattern": "Rectangular Pattern",
    "PartDesign::PolarPattern": "Circular Pattern",
    "PartDesign::Mirrored": "Mirror",
    "PartDesign::Defeaturing": "Remove Faces",
}
HOLE_START = {"inches": ("UNC", "1/4"), "millimeters": ("ISOMetricProfile", "M6x1.0")}


def plain_label(feature):
    """Studio's name for a feature that still has FreeCAD's own (its type, numbered), or None."""
    plain = PLAIN.get(getattr(feature, "TypeId", ""))
    if plain is None:
        return None
    freecads = feature.TypeId.split("::")[1]
    if feature.Label != feature.Name or not re.fullmatch(re.escape(freecads) + r"\d*", feature.Name):
        return None
    return plain


def rename(feature) -> bool:
    """Gives a feature Studio's name (FreeCAD numbers it if taken); False if it keeps its own."""
    plain = plain_label(feature)
    if plain is None:
        return False
    feature.Label = plain
    return True


def start_hole(hole, units) -> bool:
    """A hole without a thread standard starts in `units`' ("inches" or "millimeters"); False if it has one."""
    if hole.ThreadType != "None" or units not in HOLE_START:
        return False
    hole.ThreadType, hole.ThreadSize = HOLE_START[units]
    return True
