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
from StudioTests.test_commands import (  # noqa: F401
    Catalog,
    Service,
    ShippedCatalog,
)
from StudioTests.test_warmup import WarmUpPlan  # noqa: F401
from StudioTests.test_settings import (  # noqa: F401
    Choices,
    DefaultsAndOverrides,
    Keys,
    Types,
)
