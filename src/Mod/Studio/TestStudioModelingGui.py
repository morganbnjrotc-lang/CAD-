# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's GUI tests that load Part Design (PLAN 3.5 on): run in a FreeCAD session of their own.

TestStudioGui checks that workbenches' commands load without switching to them, which needs those
workbenches not loaded yet; these tests extrude with Part Design, which loads it. Run with
`pixi run python tools/test/run_gui_suites.py TestStudioModelingGui` (CI runs both suites).
"""

from StudioTests.gui.test_context_menu import RightClick  # noqa: F401
from StudioTests.gui.test_extrude import FinishOrCancel, StaysInStudio, TypedLength  # noqa: F401
from StudioTests.gui.test_extrude_direction import LettingGo, Typing  # noqa: F401
from StudioTests.gui.test_field_defaults import MakeDefault  # noqa: F401
from StudioTests.gui.test_feature_panels import PicksEdges  # noqa: F401
from StudioTests.gui.test_model_patterns import ModelPatterns  # noqa: F401
from StudioTests.gui.test_tasks_panel import MediumSize  # noqa: F401
