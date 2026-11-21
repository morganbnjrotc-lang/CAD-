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
from StudioTests.test_keymap import (  # noqa: F401
    Conflicts,
    Defaults,
    Matching,
    Normalize,
    UserBindings,
)
from StudioTests.test_keymap import ShippedCatalog as KeymapShippedCatalog  # noqa: F401
from StudioTests.test_context_toolbar import Buttons, Kinds, Names, Ways  # noqa: F401
from StudioTests.test_home import Cards, ListSize, RecentFilesStore, Thumbnails  # noqa: F401
from StudioTests.test_icons import Drawings  # noqa: F401
from StudioTests.test_icons import Names as IconNames  # noqa: F401
from StudioTests.test_theme import Colors, FreeCADColorSettings, Mode, Palettes, QtStyle  # noqa: F401
from StudioTests.test_palette import Items, Ranking, Recent  # noqa: F401
from StudioTests.test_units import Choice, FreeCADUnitSettings, Schemas  # noqa: F401
from StudioTests.test_tasks_panel import FreeCADPanelSettings, Size  # noqa: F401
from StudioTests.test_auto_constrain import Keeping, Limits, Report, Shapes  # noqa: F401
from StudioTests.test_extrude_direction import Switching, WhenToSwitch  # noqa: F401
from StudioTests.test_field_defaults import Defaults as FieldDefaultsTest  # noqa: F401
from StudioTests.test_palette import ShippedCatalog as PaletteShippedCatalog  # noqa: F401
from StudioTests.test_warmup import WarmUpPlan  # noqa: F401
from StudioTests.test_settings import (  # noqa: F401
    Choices,
    DefaultsAndOverrides,
    Keys,
    Listing,
    Types,
)
