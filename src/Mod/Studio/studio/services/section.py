# SPDX-License-Identifier: LGPL-2.1-or-later
"""One-click section view (PLAN 3.7): where the section plane starts and how its arrow moves it.

A plane is (point, normal); the view keeps the side the normal points to (Coin's clip planes do). On a
flat face picked first, the plane lies on the face and keeps the part behind it: dragging the arrow,
which points out of what is kept, then moves it into the part, as Fusion's section does. With nothing
picked it goes through the middle of the model on the front, side or top plane nearest the view, keeping
the half away from the viewer.
"""

import FreeCAD


def on_face(face):
    """(point, normal) on a flat face, keeping the part behind it; None for a curved face."""
    if face.Surface.TypeId != "Part::GeomPlane":
        return None
    u0, u1, v0, v1 = face.ParameterRange
    outward = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)  # follows the face's orientation
    return FreeCAD.Vector(face.CenterOfMass), -outward


def through_middle(bound_box, view_direction):
    """(point, normal) through the middle of `bound_box`, keeping what lies away from the viewer.

    The plane is the front, side or top one nearest the view (ties: front, then side, then top): exactly
    along the view, the arrow would point at the viewer, a dot that can't be dragged."""
    looking = FreeCAD.Vector(view_direction).normalize()
    axes = [(1, FreeCAD.Vector(0, 1, 0)), (0, FreeCAD.Vector(1, 0, 0)), (2, FreeCAD.Vector(0, 0, 1))]
    # a tie within 0.001: FreeCAD's own isometric view differs in the 7th decimal
    _, axis = max(axes, key=lambda a: (round(abs(looking[a[0]]), 3), -axes.index(a)))
    normal = axis if looking.dot(axis) >= 0 else -axis
    return FreeCAD.Vector(bound_box.Center), normal


def arrow(normal):
    """The way the section's arrow points: out of what is kept."""
    return -FreeCAD.Vector(normal)


def moved(point, normal, distance):
    """The plane after dragging the arrow `distance` along itself (negative: into what is kept)."""
    return FreeCAD.Vector(point) + arrow(normal) * distance, FreeCAD.Vector(normal)
