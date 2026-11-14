# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI Studio test suite. Run: FreeCAD -t TestStudioGui"""

from StudioTests.gui.test_command_backend import (  # noqa: F401
    CommandServiceInTheAppTest,
    DeclaredShortcutTest,
    WorkbenchLoadingTest,
)
from StudioTests.gui.test_main_window import Chrome, FollowsSelection, OneEnvironment  # noqa: F401
from StudioTests.gui.test_palette_window import Icons, PaletteWindowTest, Wiring  # noqa: F401
from StudioTests.gui.test_shortcuts import (  # noqa: F401
    Chords,
    EditContexts,
    Handler,
    SessionShortcuts,
)
from StudioTests.gui.test_warmup_runner import WarmUpRunnerTest  # noqa: F401
from StudioTests.gui.test_workbench import StudioWorkbenchTest  # noqa: F401
