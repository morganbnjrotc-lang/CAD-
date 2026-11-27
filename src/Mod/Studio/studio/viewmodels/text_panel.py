# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Text panel's model (PLAN 4.1, docs/adr/0015). No Qt here.

What the panel shows and changes: a text box (studio.services.sketch_text.TextBox) and the font it is drawn
in, among the installed fonts (studio.services.fonts).

- A **new text** starts as "Text" in the family, style and height used last (the first time: Arial, or the
  first family, in its regular style, a quarter inch or 5 mm), its box fitted to it.
- An **edited text** starts as it is. When its font isn't on this computer the panel says so (`missing`),
  and the text can't be redrawn until another font is picked (fonts kept in the file: PLAN 4.2).
- Picking another **family** keeps the style when the family has it, else takes the nearest by weight and
  slant.
- Sizes are millimeters; a height, spacing or box size must be more than nothing (a refused one is ignored
  and the call answers False).
"""

import dataclasses

from studio.services import fonts as font_service
from studio.services.settings import Setting, Settings
from studio.services.sketch_text import ALIGN, VALIGN, TextBox

FAMILY = Setting("Text/Family", "Arial")
STYLE = Setting("Text/Style", "Regular")
HEIGHT = Setting("Text/Height", 0.0)  # mm; 0: the units' first height
FIRST_HEIGHT = {"inches": 0.25 * 25.4, "millimeters": 5.0}
REGULAR = (400, False)


def _nearest(styles, weight, italic):
    return min(styles, key=lambda f: (abs(f.weight - weight), f.italic != italic))


class TextPanel:
    def __init__(self, found, units, settings=None, box=None):
        """`found`: the installed fonts; `units`: "inches" or "millimeters"; `box`: the text edited, or None."""
        self.settings = settings or Settings()
        self._families = font_service.families(found)
        self.editing = box is not None
        if box is None:
            box = self._new(units)
        self.box = box

    def _new(self, units):
        family = self.settings.get(FAMILY)
        if family not in self._families:
            family = FAMILY.default if FAMILY.default in self._families else next(iter(self._families), "")
        styles = self._families.get(family, [])
        names = [f.style for f in styles]
        if self.settings.get(STYLE) in names:
            style = self.settings.get(STYLE)
        else:
            style = _nearest(styles, *REGULAR).style if styles else ""
        height = self.settings.get(HEIGHT) or FIRST_HEIGHT[units]
        return TextBox("Text", family, style, height, height, height, "left", "top", 1.0, True)

    # what the panel lists

    @property
    def families(self):
        return list(self._families)

    @property
    def styles(self):
        return [f.style for f in self._families.get(self.box.family, [])]

    @property
    def font(self):
        """The font the text is drawn in, or None when it isn't installed."""
        return next((f for f in self._families.get(self.box.family, []) if f.style == self.box.style), None)

    @property
    def missing(self):
        """What to tell the user when the text's font isn't installed, else ""."""
        if self.font is not None:
            return ""
        return f"{self.box.family} {self.box.style} isn't on this computer: pick another font to change the text"

    @property
    def note(self):
        """What to tell the user when the font can't be kept in the file (PLAN 4.2), else ""."""
        font = self.font
        if font is None or font.embeddable:
            return ""
        return (f"{font.name}'s license doesn't let it be kept in the file: on a computer without it, the text "
                "shows but can't be changed")

    # changes

    def _set(self, **changes):
        self.box = dataclasses.replace(self.box, **changes)
        return True

    def set_text(self, text):
        return self._set(text=text)

    def set_family(self, family):
        styles = self._families.get(family)
        if not styles:
            return False
        same = [f for f in styles if f.style == self.box.style]
        if same:
            return self._set(family=family)
        now = self.font
        weight, italic = (now.weight, now.italic) if now else _style_guess(self.box.style)
        return self._set(family=family, style=_nearest(styles, weight, italic).style)

    def set_style(self, style):
        if style not in self.styles:
            return False
        return self._set(style=style)

    def set_height(self, mm):
        return mm > 0 and self._set(height=float(mm))

    def set_align(self, align):
        return align in ALIGN and self._set(align=align)

    def set_valign(self, valign):
        return valign in VALIGN and self._set(valign=valign)

    def set_spacing(self, times):
        return times > 0 and self._set(spacing=float(times))

    def set_fit(self, on, width=None, depth=None):
        """Fits the box to the text, or gives it its own size, starting at `width` by `depth` (mm: the size it
        has, the text's while it fitted)."""
        changes = {"fit": bool(on)}
        if not on and width and depth:
            changes.update(width=float(width), depth=float(depth))
        return self._set(**changes)

    def set_width(self, mm):
        return mm > 0 and self._set(width=float(mm))

    def set_depth(self, mm):
        return mm > 0 and self._set(depth=float(mm))

    def remember(self):
        """Keeps the family, style and height for the next new text."""
        self.settings.set(FAMILY, self.box.family)
        self.settings.set(STYLE, self.box.style)
        self.settings.set(HEIGHT, self.box.height)


def _style_guess(style):
    """Weight and slant from a style's name, for a font that isn't installed."""
    name = style.lower()
    weight = 700 if "bold" in name else 900 if "black" in name else 300 if "light" in name else 400
    return weight, "italic" in name or "oblique" in name


def with_kept(installed, kept):
    """The installed fonts and those kept in a sketch (PLAN 4.2) that aren't installed: the installed copy
    first, a kept one where there is none."""
    have = {(f.family, f.style) for f in installed}
    return list(installed) + [f for f in kept if (f.family, f.style) not in have]
