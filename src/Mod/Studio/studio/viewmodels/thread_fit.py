# SPDX-License-Identifier: LGPL-2.1-or-later
"""The toolbar's Fit box (PLAN 3.9, the allowance scrubber). No Qt here.

A threaded hole picked shows Fit on the toolbar: how much bigger (+) or smaller (-) the hole is made than
standard, for 3D-printed parts (studio.services.threads.fit, stored in mm). The box shows it in the
user's units and scrolling steps it by an amount a printer can tell apart: 0.05 mm, or 0.002 in, up to
a limit either way. A typed fit is read in the box's units, or in the unit typed after it.
"""

import re

MM_PER_INCH = 25.4
_TYPED = re.compile(r'^\s*([+-]?(?:\d+\.?\d*|\.\d+))\s*(mm|in|inch|inches|")?\s*$', re.IGNORECASE)
_MM_PER = {"mm": 1.0, "in": MM_PER_INCH, "inch": MM_PER_INCH, "inches": MM_PER_INCH, '"': MM_PER_INCH}

# units -> (suffix, decimals, step, limit), in the units shown
_RULES = {
    "millimeters": (" mm", 2, 0.05, 2.0),
    "inches": (" in", 3, 0.002, 0.08),
}


class FitBox:
    label = "Fit"
    tooltip = ("How much bigger (+) or smaller (-) the threaded hole is made than standard, for 3D-printed "
               "parts. Scroll over it to loosen or tighten; exported threads get it too")

    def __init__(self, units: str):
        """`units`: "inches" or "millimeters", what the box shows."""
        self.suffix, self.decimals, self.step, self.limit = _RULES[units]
        self._per_mm = 1 / MM_PER_INCH if units == "inches" else 1.0

    def shown(self, mm: float) -> float:
        """A fit in mm, in the units shown."""
        return mm * self._per_mm

    def mm(self, shown: float) -> float:
        """A fit in the units shown, in mm."""
        return shown / self._per_mm

    def _limited(self, shown: float) -> float:
        return max(-self.limit, min(self.limit, shown))

    def text(self, mm: float) -> str:
        """What the box shows for a fit in mm: "+0.10 mm", "0.00 mm", "-0.002 in"."""
        shown = round(self.shown(mm), self.decimals)
        if abs(shown) < 0.5 * 10 ** -self.decimals:
            return f"{0:.{self.decimals}f}{self.suffix}"
        return f"{shown:+.{self.decimals}f}{self.suffix}"

    def stepped(self, mm: float, notches: int) -> float:
        """The fit `notches` steps (scroll notches) from `mm`, on the units' grid of steps, within the limit."""
        on_grid = round(self.shown(mm) / self.step)
        return self.mm(self._limited((on_grid + notches) * self.step))

    def read(self, text: str):
        """The fit in mm a typed text means, within the limit; None if it isn't a fit."""
        typed = _TYPED.match(text)
        if typed is None:
            return None
        number, unit = float(typed.group(1)), typed.group(2)
        shown = self.shown(number * _MM_PER[unit.lower()]) if unit else number
        return self.mm(self._limited(shown))
