# SPDX-License-Identifier: LGPL-2.1-or-later
"""Studio's GUI tests that load Part Design (PLAN 3.5 on): run in a FreeCAD session of their own.

TestStudioGui checks that workbenches' commands load without switching to them, which needs those
workbenches not loaded yet; these tests extrude with Part Design, which loads it. Run with
`pixi run python tools/test/run_gui_suites.py TestStudioModelingGui` (CI runs both suites).
"""

from StudioTests.gui.test_extrude import TypedLength  # noqa: F401
