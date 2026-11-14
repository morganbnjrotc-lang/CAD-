# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which workbenches to load in the background after startup (ADR 0007, decision 3).

Loading a workbench registers its commands; done in idle moments after startup, a user's first
click on one of its tools doesn't wait. The shell runs the plan one workbench at a time.
"""

from studio.services.commands import CommandService
from studio.services.settings import Setting, Settings

WARM_UP = Setting("Commands/WarmUp", True)

# One blocking import takes ~0.6 s for CAM on the slim Release build (ADR 0007 measurements):
# too long to hide in an idle moment. It loads on the first CAM action instead (Phase 8 may
# make it faster).
TOO_SLOW_TO_WARM = frozenset({"CAMWorkbench"})


def warmup_plan(service: CommandService, settings: Settings) -> list:
    """Workbenches to load, in catalog order: all not yet loaded, except the slow ones; none if
    the user turned warm-up off."""
    if not settings.get(WARM_UP):
        return []
    return [
        name
        for name in service.catalog.workbenches()
        if name not in TOO_SLOW_TO_WARM and not service.is_loaded(name)
    ]
