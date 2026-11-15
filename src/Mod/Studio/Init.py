# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio module, application (headless) initialization."""

import FreeCAD

FreeCAD.__unit_test__ += ["TestStudioApp"]

# Studio's look (docs/adr/0010): Qt's Fusion style, picked before the GUI starts so FreeCAD builds its
# window in it. A style or FreeCAD stylesheet the user picked stays.
try:
    from studio.services import theme

    theme.default_to_fusion()
except Exception as exc:  # never stop FreeCAD from starting over the look
    FreeCAD.Console.PrintWarning(f"Studio: could not set the Qt style: {exc}\n")
