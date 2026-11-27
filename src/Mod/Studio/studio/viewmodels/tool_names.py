# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tool names as people read them (docs/adr/0009).

FreeCAD's menu texts carry accelerator marks ("&Undo") and trailing dots, and a few tools use
FreeCAD's own vocabulary where most CAD apps say something else; those get plain names here. The
palette and the toolbar show `display_title`; FreeCAD's name stays searchable and in tooltips.
"""

import re

PLAIN_NAMES = {
    "PartDesign_Pad": "Extrude",
    "PartDesign_Pocket": "Cut",
    "PartDesign_Thickness": "Shell",
    "PartDesign_Groove": "Revolve Cut",
    "PartDesign_AdditivePipe": "Sweep",
    "PartDesign_SubtractivePipe": "Sweep Cut",
    "PartDesign_AdditiveLoft": "Loft",
    "PartDesign_SubtractiveLoft": "Loft Cut",
    "Sketcher_CreateText": "Text Along a Line",  # Studio's Text is the text box (PLAN 4.1)
}


def clean_title(menu_text: str) -> str:
    """A menu text as people read it: "Save &As..." -> "Save As", "&&" -> "&"."""
    text = re.sub(r"&(&?)", lambda m: "&" if m.group(1) else "", menu_text)
    return re.sub(r"(\.\.\.|…)\s*$", "", text).strip()


def display_title(info) -> str:
    """The name to show for a catalog command."""
    return PLAIN_NAMES.get(info.name) or clean_title(info.menu_text)
