# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude or cut by direction, like Fusion (PLAN 3.5, the user's pick 2026-11-20).

Dragging Extrude's arrow into the part makes it a cut; dragging a cut's arrow back out of the part makes
it an extrude again. FreeCAD has a feature for each, Part Design's Pad and Pocket, and a Pad dragged into
the part only pads backwards into material that is already there: nothing shows.

`becomes(feature)` tells when a Pad or Pocket should be the other one:
- an extrude (Pad) turned into the part, by a negative length or turned around, whose tool reaches into
  the solid before it, becomes a cut;
- a cut (Pocket) turned out of the part whose tool reaches no material becomes an extrude. A cut from a
  sketch inside the part cuts material either way, so it stays.
Only the body's last feature switches (a later feature could refer to its faces), with a plain length on
one side, no taper, no direction of its own and starting at its sketch: what dragging the arrow changes.

`switch(feature)` puts the other one in its place, with the same tool: the same sketch, length and refine
setting, pointing the same way. Inside the caller's transaction, so one undo step takes back both.
"""

PAD, POCKET = "PartDesign::Pad", "PartDesign::Pocket"
OTHER = {PAD: POCKET, POCKET: PAD}


def _body(feature):
    parent = feature.getParentGeoFeatureGroup()
    return parent if parent is not None and parent.TypeId == "PartDesign::Body" else None


def _along_its_sketch(feature) -> bool:
    """No direction of its own: none given (scripts), or its sketch's normal, as Part Design's commands
    set it."""
    axis = feature.ReferenceAxis
    return axis is None or (axis[0] == feature.Profile[0] and list(axis[1]) == ["N_Axis"])


def _plain(feature) -> bool:
    """One side, a plain length, no taper, its own sketch's direction, starting at the sketch."""
    return (feature.SideType == "One side" and feature.Type == "Length" and not feature.UseCustomVector
            and _along_its_sketch(feature) and abs(feature.TaperAngle.Value) < 1e-9
            and feature.StartType == "Profile plane")


def _turned(feature) -> bool:
    """Pointing against its usual way: a Pad into its sketch's back, a Pocket out of it."""
    return (feature.Length.Value < 0) != bool(feature.Reversed)


def _reaches_material(feature) -> bool:
    """Whether the feature's tool (the prism it adds or cuts) overlaps the solid before it."""
    base = feature.BaseFeature
    if base is None or base.Shape.isNull() or feature.AddSubShape.isNull():
        return False
    tool = feature.AddSubShape
    overlap = tool.common(base.Shape).Volume
    return overlap > 1e-6 * max(tool.Volume, 1.0)


def becomes(feature):
    """The feature type a Pad or Pocket should be for the way it points, or None if it is right."""
    kind = getattr(feature, "TypeId", "")
    if kind not in OTHER:
        return None
    body = _body(feature)
    if body is None or body.Tip != feature or not _plain(feature) or not _turned(feature):
        return None
    reaches = _reaches_material(feature)
    if kind == PAD and reaches:
        return POCKET
    if kind == POCKET and not reaches:
        return PAD
    return None


def switch(feature):
    """Replaces a Pad by a Pocket or the other way round, with the same tool; returns the new feature.
    Its sketch stays hidden as the feature's was; the caller recomputes."""
    kind = OTHER[feature.TypeId]
    body, doc = _body(feature), feature.Document
    profile, refine, axis = feature.Profile, feature.Refine, feature.ReferenceAxis
    length = abs(feature.Length.Value)
    body.removeObject(feature)  # the body's last feature is the one before it again
    doc.removeObject(feature.Name)
    new = body.newObject(kind, kind.split("::")[1])
    new.Profile = profile
    new.ReferenceAxis = axis
    new.Length = length
    # A turned Pad pointed into its sketch's back, where a Pocket points; a turned Pocket the other way,
    # where a Pad points. So the new one points its usual way.
    new.Reversed = False
    new.Refine = refine
    return new

