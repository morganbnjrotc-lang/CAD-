# SPDX-License-Identifier: LGPL-2.1-or-later
"""Headless Studio test suite. Run: FreeCADCmd -t TestStudioApp"""

from StudioTests.test_architecture import (  # noqa: F401
    ImportCheckerTest,
    LayerDependencyTest,
)
from StudioTests.test_local_only import (  # noqa: F401
    NoNetworkGuardTest,
    StudioIsLocalOnlyTest,
)
from StudioTests.test_branding import BrandingTest  # noqa: F401
