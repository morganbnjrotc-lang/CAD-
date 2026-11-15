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
        # Layout A (docs/adr/0009): Studio's own top bar and toolbar replace FreeCAD's toolbars,
        # and one ☰ menu shows FreeCAD's File, Edit, View and Help menus.
        for name in self.listToolbars():
            self.removeToolbar(name)
        for name in self.listMenus():
            if name not in ("&File", "&Edit", "&View", "&Help"):
                self.removeMenu(name)

    def Activated(self):
        from studio.shell import environment, home, shortcuts, warmup, window

        # One environment (docs/adr/0009): editing a sketch no longer switches workbench.
        environment.install_once()
        # Keyboard shortcuts by context (docs/adr/0008); the keymap is read on the first key press.
        shortcuts.install_once()
        # Top bar, toolbar that follows the selection, status-bar hint (docs/adr/0009).
        window.install_once()
        # The Home page replaces FreeCAD's Start page while no document is open (PLAN 2.8).
        home.install_once()
        # Load the cheap workbenches in the background once startup is done (docs/adr/0007).
        warmup.start_once()

    def Deactivated(self):
        from studio.shell import environment, window

        if window.current() is not None:
            window.current().hide()
        # Something switched to another workbench (a macro, FreeCAD's Start page): come back.
        environment.schedule_return()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class _CommandPalette:
    """Search every tool by name and run it (PLAN 2.5). Bound to S and Ctrl+K (docs/adr/0008).

    FreeCAD runs InitGui.py with separate globals and locals, so methods here can't see this file's
    other top-level names (StudioWorkbench, os, FreeCAD): they import what they need.
    """

    def GetResources(self):
        import os

        import FreeCAD

        return {
            "MenuText": "Command Palette",
            "ToolTip": "Search every tool by name and run it",
            "Pixmap": os.path.join(FreeCAD.getHomePath(), "Mod", "Studio", "Resources", "icons", "Studio.svg"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from studio.shell import palette

        palette.open_palette()


FreeCADGui.addCommand("Studio_CommandPalette", _CommandPalette())
FreeCADGui.addWorkbench(StudioWorkbench())

FreeCAD.__unit_test__ += ["TestStudioGui"]
