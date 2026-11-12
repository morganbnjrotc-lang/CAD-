# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio module, GUI initialization."""

import os

import FreeCAD
import FreeCADGui


class StudioWorkbench(FreeCADGui.Workbench):
    """The single environment the app runs in. Starts empty; Phase 2 fills in the shell."""

    MenuText = "Studio"
    ToolTip = "Unified modeling environment"
    Icon = os.path.join(
        FreeCAD.getHomePath(), "Mod", "Studio", "Resources", "icons", "Studio.svg"
    )

    def Initialize(self):
        pass

    def Activated(self):
        pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(StudioWorkbench())

FreeCAD.__unit_test__ += ["TestStudioGui"]
