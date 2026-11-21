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
        from studio.shell import (appearance, environment, extrude_direction, feature_panels, field_defaults, home,
                                  shortcuts, sketching, tasks_panel, units, warmup, window)

        # One environment (docs/adr/0009): editing a sketch no longer switches workbench.
        environment.install_once()
        # Keyboard shortcuts by context (docs/adr/0008); the keymap is read on the first key press.
        shortcuts.install_once()
        # Top bar, toolbar that follows the selection, status-bar hint (docs/adr/0009).
        window.install_once()
        # Studio's look: Fusion, its light or dark palette, 3D colors; follows Windows (docs/adr/0010).
        appearance.install_once()
        # Inches or millimeters, everywhere; follows Windows' region unless the user picks (PLAN 3.1).
        units.install_once()
        # Sketching like Fusion: typing into a size box replaces it, unit included (PLAN 3.2).
        sketching.install_once()
        # Fillet and Chamfer open ready to pick more edges (PLAN 3.11).
        feature_panels.install_once()
        # Extrude dragged into the part cuts; a cut dragged out of it extrudes (PLAN 3.5).
        extrude_direction.install_once()
        # Right-click a tool's size box → Make Default (PLAN 3.6).
        field_defaults.install_once()
        # The Tasks panel medium-sized at the right of the 3D view, following the window (PLAN 3.10).
        tasks_panel.install_once()
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


class _FullyConstrain:
    """Adds what the sketch being edited is missing so it is fully defined, without moving anything
    (PLAN 3.4, like Fusion's AutoConstrain). One undo step."""

    def GetResources(self):
        import os

        import FreeCAD

        return {
            "MenuText": "Fully Constrain",
            "ToolTip": "Adds the dimensions and constraints the sketch is missing, without moving anything",
            "Pixmap": os.path.join(FreeCAD.getHomePath(), "Mod", "Studio", "Resources", "icons", "line",
                                   "fully-constrain.svg"),
        }

    def IsActive(self):
        from studio.shell import sketching

        return sketching.sketch_in_edit() is not None

    def Activated(self):
        from studio.shell import sketching

        sketching.fully_constrain()


FreeCADGui.addCommand("Studio_FullyConstrain", _FullyConstrain())


class _PanelButton:
    """The open task panel's OK or Cancel, on Studio's toolbar while the panel is open (PLAN 3.5).
    Presses the panel's own button, so the panel does what it does when the user clicks it."""

    def __init__(self, accept):
        self.accept = accept

    def GetResources(self):
        import os

        import FreeCAD

        name, icon, tip = (("Finish", "finish", "Closes the panel and keeps the changes") if self.accept
                           else ("Cancel", "cancel", "Closes the panel and takes the changes back"))
        return {"MenuText": name, "ToolTip": tip,
                "Pixmap": os.path.join(FreeCAD.getHomePath(), "Mod", "Studio", "Resources", "icons", "line",
                                       f"{icon}.svg")}

    def IsActive(self):
        import FreeCADGui

        return bool(FreeCADGui.Control.activeDialog())

    def Activated(self):
        import FreeCADGui

        dialog = FreeCADGui.Control.activeTaskDialog()
        if dialog is not None:
            dialog.accept() if self.accept else dialog.reject()


FreeCADGui.addCommand("Studio_Finish", _PanelButton(accept=True))
FreeCADGui.addCommand("Studio_Cancel", _PanelButton(accept=False))

# Studio's C++ commands: Construction (PLAN 3.13) hears from FreeCAD when construction goes on or off,
# which Python can't.
try:
    import StudioGui as _studio_gui

    _studio_gui.add_commands()
except Exception as exc:
    FreeCAD.Console.PrintWarning(f"Studio: could not add its C++ commands: {exc}\n")

# Studio's line icons under FreeCAD's icon names (docs/adr/0010), before FreeCAD builds its menus and
# model tree with them.
try:
    from studio.shell import icons as _studio_icons

    _studio_icons.register_once()
except Exception as exc:  # never stop FreeCAD from starting over the look
    FreeCAD.Console.PrintWarning(f"Studio: could not add its icons: {exc}\n")
FreeCADGui.addWorkbench(StudioWorkbench())

FreeCAD.__unit_test__ += ["TestStudioGui", "TestStudioModelingGui"]
