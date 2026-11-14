# 0006 — Slim build: modules the product doesn't ship are switched off

- **Status:** accepted
- **Date:** 2026-11-13

## Context

FreeCAD builds about 30 modules. Several serve workflows outside this product's roadmap
([README](../../README.md)): FEM (structural/thermal simulation), BIM (architecture), Robot
(robot-cell simulation), Points / ReverseEngineering / Inspection (point clouds and 3D-scan
workflows), OpenSCAD (needs the external OpenSCAD program), Web (an embedded browser) and JtReader
(already off upstream). The Addon Manager downloads and runs third-party code over the network,
which conflicts with principle 3, "Fully local".

Each module costs build time, disk, CI time and tests, and adds workbenches and commands that a
clean single-environment UI would have to hide.

## Decision

- A hidden CMake preset `studio-slim` turns off `BUILD_FEM`, `BUILD_BIM`, `BUILD_ROBOT`,
  `BUILD_OPENSCAD`, `BUILD_POINTS`, `BUILD_REVERSEENGINEERING`, `BUILD_INSPECTION`, `BUILD_WEB`,
  `BUILD_JTREADER` and `BUILD_ADDONMGR`. Windows presets inherit it:
  `studio-slim-windows-rel-with-deb-info` → `build/slim` and `studio-slim-windows-release` →
  `build/slim-release`. Pixi tasks: `configure-slim`, `build-slim`, `freecad-slim` (+ `-release`).
- The slim build runs from the build tree; it isn't installed into the pixi environment, where it
  would mix with a full install's modules.
- The full build stays available unchanged (`pixi run configure` / `build`); upstream's default
  tasks aren't edited. For day-to-day work use `configure-slim`.
- CI builds `studio-slim-windows-release` (`build/slim-release`), so it tests what we ship.

### Dependency check (one module at a time)

- **CMake rules** (`CheckInterModuleDependencies.cmake`): no kept module requires a removed one.
  CAM's old dependency on Robot is commented out upstream. Points was needed only by Inspection and
  ReverseEngineering. `tools/repo_tests/test_slim_build.py` re-checks this on every CI run, along with
  the option names (an upstream rename would silently bring a module back).
- **Code references** from kept modules, searched per removed module:
  - FEM, Robot, ReverseEngineering, Inspection, JtReader: none.
  - Points: only `TemplatePyMod` (not built).
  - Web: only `StartMigrator.py` cleaning up old preferences.
  - Addon Manager: every caller checks that `Std_AddonMgr` exists first. CAM's machine editor
    falls back to opening the machines-addon web page, only when the user clicks it.
  - OpenSCAD: Mesh boolean commands try OpenSCAD only as a fallback after OpenCASCADE fails; without
    it they report the failure.
  - BIM: Draft imports Arch lazily, in `try/except` or only for BIM objects. DXF import uses
    `ArchCommands` only for the legacy "download the DXF importer from the internet" option, which
    should stay off anyway. Draft's SVG test checks `have_arch`.

## Results (2026-11-13, reference laptop, RelWithDebInfo)

| | Full | Slim |
|---|---|---|
| Modules built | 31 | 22 |
| `bin` + `Mod` on disk | 5.3 GB | 4.2 GB |
| C++ test programs | 26 pass | 25 pass (Points' removed) |
| Headless Python suites (except CAM) | 1,642 pass, 25 skipped | 1,232 pass, 25 skipped; 0 tests worse; the 410 missing are all `bimtests` (315) and `femtest` (95) |
| CAM in batches | 2,066 pass, 11 skipped | 2,066 pass, 11 skipped |
| GUI suite, startup smoke | pass | pass |
| Median startup (runs 2–6) | 3.03 s | 3.00 s |
| Working set / private bytes at ready | 597 / 559 MB | 584 / 542 MB |

Test comparison: `tools/test/compare_test_logs.py full.log slim.log --allow-missing bimtests. femtest.`

## Consequences

- **Startup is not faster.** FreeCAD only runs each module's small `Init.py`/`InitGui.py` at
  startup; the expensive loading happens when a workbench is first activated, which removed modules
  never were. Memory at startup drops 2–3%. The startup budget has to be met in the core (lazy
  loading, Phase 2), not by removing modules.
- Real gains: a smaller install, fewer tests and compiles for CI, no network-capable Addon Manager
  in the product, and fewer workbenches and commands to hide in the unified UI.
- Start page "new architectural project" no longer switches to BIM (it stays in the current
  workbench). The Start page is replaced in Phase 2 anyway.
- Users who need FEM, BIM etc. use FreeCAD itself; files containing those objects open with
  missing-type warnings.
- A fresh build folder exposed an upstream bug: C++ tests on Windows couldn't find module DLLs until
  CMake was re-run after the first build. Fixed in `tests/CMakeLists.txt` (see `docs/CORE_PATCHES.md`).
- ccache keys on the build folder when debug info is on, so `build/slim` didn't reuse the full
  build's cache: its first build took 103 min, longer than the full build's 79.
