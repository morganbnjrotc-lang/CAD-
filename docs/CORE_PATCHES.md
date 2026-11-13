# Core patches

Every change we make to files that come from upstream FreeCAD is listed here, so upstream merges stay
predictable. New behavior should live in `src/Mod/Studio`; an entry here means no extension
point was available.

| Date | File(s) | Change | Why | Merge notes |
|---|---|---|---|---|
| 2026-11-11 | `README.md` → `README.FreeCAD.md` | Renamed; new project README added | Our README describes the fork | Upstream edits to `README.md` should follow the rename; check after each merge |
| 2026-11-11 | `AGENTS.md` → `AGENTS.FreeCAD.md` | Renamed; new fork-specific `AGENTS.md` + `CLAUDE.md` added | Upstream's agent policy targets FreeCAD contributions, not this fork | Same as above |
| 2026-11-11 | `cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake` | Added `BUILD_STUDIO` option (ON) | Lets the Studio module be switched on/off like other modules | One added line next to `BUILD_SURFACE`; trivial to re-apply |
| 2026-11-11 | `src/Mod/CMakeLists.txt` | `add_subdirectory(Studio)` under `BUILD_STUDIO` | Registers our module with the build | One small block after `BUILD_TEST`; trivial to re-apply |
| 2026-11-12 | `.github/workflows/*.yml` (all 26 upstream workflows), `.github/dependabot.yml` | Deleted; our own `.github/workflows/studio-ci.yml` added ([ADR 0005](adr/0005-own-ci-workflow.md)) | Upstream's CI tested FreeCAD, not our code, on every push; Dependabot opened daily PRs about FreeCAD's dependencies | Modify/delete conflicts on these files: resolve with `git rm`. A *new* upstream workflow makes `tools/repo_tests` fail: delete it on the merge branch |
| 2026-11-11 | `src/Mod/Start/StartMigrator.py` | First-run migration writes `ConfigGet("StartWorkbench")` instead of hardcoded `"PartDesignWorkbench"` | Bug: on every brand-new profile the 2024 migration overrode the branded start workbench. Upstream behavior unchanged (their configured default is PartDesign). Covered by `StudioTests.test_branding` + `tools/test/startup_smoke.py` | **Good candidate to send upstream.** If upstream removes the 2024 migrator, drop this patch |
