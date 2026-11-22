# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI Studio test suite. Run: FreeCAD -t TestStudioGui"""

from StudioTests.gui.test_appearance import AppearanceTest, FreeCADPanels, SessionAppearance, StudioWidgets  # noqa: F401
from StudioTests.gui.test_construction import Construction  # noqa: F401
from StudioTests.gui.test_icons import FreeCADPlaces, Toolbar  # noqa: F401
from StudioTests.gui.test_command_backend import (  # noqa: F401
    CommandServiceInTheAppTest,
    DeclaredShortcutTest,
    WorkbenchLoadingTest,
)
from StudioTests.gui.test_home_page import HomeHidesTheEmptyPanel, HomePageTest, SessionHome  # noqa: F401
from StudioTests.gui.test_main_window import Chrome, FollowsSelection, OneEnvironment  # noqa: F401
from StudioTests.gui.test_palette_window import Icons, PaletteWindowTest, Wiring  # noqa: F401
from StudioTests.gui.test_patterns import SketchPatterns  # noqa: F401
from StudioTests.gui.test_shortcuts import (  # noqa: F401
    Chords,
    EditContexts,
    Handler,
    SessionShortcuts,
)
from StudioTests.gui.test_sketch_constraints import FullyConstrainTool, WhileDrawing  # noqa: F401
from StudioTests.gui.test_sketch_sizes import TypedSizes  # noqa: F401
from StudioTests.gui.test_section import Section  # noqa: F401
from StudioTests.gui.test_display import DisplayMenu, Looks  # noqa: F401
from StudioTests.gui.test_snaps import Snaps  # noqa: F401
from StudioTests.gui.test_sketch_ways import DrawingWays  # noqa: F401
from StudioTests.gui.test_units import SavedInMillimeters, SessionUnits  # noqa: F401
from StudioTests.gui.test_warmup_runner import WarmUpRunnerTest  # noqa: F401
from StudioTests.gui.test_workbench import StudioWorkbenchTest  # noqa: F401
