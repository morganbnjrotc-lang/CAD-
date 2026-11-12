# 0004 — Product configuration through branding.xml

- **Status:** accepted
- **Date:** 2026-11-11

## Context

The app must start in our Studio workbench (and later carry our name, icon, splash screen and
navigation style). The obvious way is to edit `src/Main/MainGui.cpp`, which hardcodes
`StartWorkbench = PartDesignWorkbench`, but every core edit makes upstream merges harder ([0002](0002-layered-architecture.md)).

FreeCAD already supports overriding these values: at startup it reads
`<AppHomePath>/bin/branding.xml` (`src/App/Application.cpp`) and applies a whitelisted set of
keys (`src/App/Branding.cpp`): `StartWorkbench`, `ExeName`, `WindowTitle`, `WindowIcon`,
`SplashScreen`, `NavigationStyle`, `StyleSheet`, `UserParameterTemplate` and others.

## Decision

Product configuration lives in `src/Mod/Studio/branding/branding.xml`. The Studio CMake copies it
into the build's `bin/` and installs it next to the executable. We don't edit `MainGui.cpp`.

## Consequences

- No core patch for product identity; rebranding later (name, icon, splash, default navigation
  style, stylesheet) is an XML change.
- First-run code that hardcodes a workbench can still override the brand. We found and fixed one case
  (`StartMigrator.py`, see `docs/CORE_PATCHES.md`). `tools/test/startup_smoke.py` launches the real app on
  a brand-new profile and checks it lands in Studio, so a regression like that gets caught.
- Lesson recorded: FreeCAD silently ignores `FREECAD_USER_HOME/DATA/TEMP` unless the folders already
  exist. Our test and benchmark tools create them, and fail if the profile is not actually isolated.
