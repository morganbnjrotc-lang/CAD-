# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD's GUI behind studio.services.commands.CommandBackend (docs/adr/0007)."""

import FreeCADGui

from studio.services.commands import CommandBackend


class FreeCADCommandBackend(CommandBackend):
    def load_workbench(self, name: str) -> None:
        # Studio's C++ helper does FreeCAD's first-activation work without switching workbench;
        # it does nothing for a workbench that is already loaded.
        import StudioGui

        StudioGui.initialize_workbench(name)

    def run(self, command: str, index: int = 0) -> None:
        FreeCADGui.runCommand(command, index)
