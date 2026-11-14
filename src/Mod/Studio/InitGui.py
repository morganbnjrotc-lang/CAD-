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
        # Keyboard shortcuts by context (docs/adr/0008); the keymap is read on the first key press.
        from studio.shell import shortcuts, warmup

        shortcuts.install_once()
        # Load the cheap workbenches in the background once startup is done (docs/adr/0007).
        warmup.start_once()

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(StudioWorkbench())

FreeCAD.__unit_test__ += ["TestStudioGui"]
